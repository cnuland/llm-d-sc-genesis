# Rust Low-Latency Classifier Runtime
## Performance Implementation Guide for gRPC/HTTP, Caching, and Candle/ModernBERT Inference

**Scope:** Rust implementation and performance only.  
**Target:** A latency-critical classifier service where cache hits should be effectively negligible and uncached inference should be pushed as close to — or below — a 20 ms service budget as the selected hardware, input length, and model allow.  
**Reference timeframe:** August 2026.

---

# 1. Performance Priorities

Optimize in this order:

1. **Do less work**
   - Cache completed classifications.
   - Truncate inputs to the smallest model-supported length that preserves classifier quality.
   - Avoid repeated tokenization where possible.
   - Avoid reconstructing masks, tensors, metadata, and response objects unnecessarily.

2. **Keep the hot path resident**
   - Model loaded once.
   - Tokenizer loaded once.
   - Model weights resident in RAM/VRAM.
   - CUDA context initialized before readiness.
   - Common tensor shapes warmed before serving traffic.
   - Common ModernBERT attention masks cached by sequence-length bucket.

3. **Bound concurrency**
   - Networking concurrency and inference concurrency are different problems.
   - Tokio handles networking.
   - A bounded inference scheduler controls CPU/GPU model execution.
   - Never allow request concurrency to translate directly into unlimited simultaneous model forwards.

4. **Avoid allocations and copies**
   - Reuse buffers where practical.
   - Use `bytes::Bytes` for shared immutable network buffers.
   - Use `Arc<T>` for cached values that would otherwise be expensive to clone.
   - Pre-size vectors and response buffers.
   - Keep tensors on the model device.

5. **Optimize the compiler and CPU target**
   - `--release` is only the baseline.
   - Use LTO, one codegen unit, and native/known target CPU instructions for production builds.

6. **Measure p50/p95/p99, not just average latency**
   - A classifier runtime is only fast if it stays fast under concurrency.

---

# 2. Recommended Rust Component Stack

Current practical baseline:

| Purpose | Rust component |
|---|---|
| Async runtime | `tokio` |
| gRPC | `tonic` |
| Protobuf | `prost` |
| HTTP | `axum` / `hyper` |
| Service middleware | `tower` |
| Network buffers | `bytes` |
| In-memory cache | `moka` |
| Simple concurrent map | `dashmap` |
| ML inference | `candle-core`, `candle-nn`, `candle-transformers` |
| Model weights | `safetensors` |
| Tokenization | Hugging Face `tokenizers` |
| Microbenchmarks | `criterion` |
| Application tracing | `tracing` |
| CPU parallelism when explicitly needed | `rayon` |

Relevant current versions during this review include:

- Candle `0.11.x`
- Tonic `0.14.x`
- Prost `0.14.x`
- Tokio `1.53.x`
- Tokenizers `0.23.x`
- Moka `0.12.x`
- SafeTensors `0.8.x`
- Criterion `0.8.x`

Pin exact versions in the repository and upgrade deliberately after benchmark validation.

---

# 3. Reference Hot-Path Architecture

```text
                    ┌──────────────────────────────┐
                    │       Tokio I/O Runtime      │
                    │                              │
Request ───────────▶│ tonic / axum / hyper         │
                    │ protobuf / HTTP decode       │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                         ┌─────────────────┐
                         │ Normalize Input │
                         │ + Build Key     │
                         └────────┬────────┘
                                  │
                       ┌──────────▼──────────┐
                       │ In-Process Cache    │
                       │ Moka / specialized │
                       └───────┬──────┬─────┘
                               │ HIT  │ MISS
                               │      │
                               │      ▼
                               │  ┌─────────────────┐
                               │  │ Bounded Queue   │
                               │  │ / Backpressure  │
                               │  └────────┬────────┘
                               │           │
                               │           ▼
                               │  ┌─────────────────┐
                               │  │ Tokenizer       │
                               │  │ + Tensor Build  │
                               │  └────────┬────────┘
                               │           │
                               │           ▼
                               │  ┌─────────────────┐
                               │  │ Candle Model    │
                               │  │ CPU or GPU      │
                               │  └────────┬────────┘
                               │           │
                               │           ▼
                               │  ┌─────────────────┐
                               │  │ Cache Result    │
                               │  └────────┬────────┘
                               │           │
                               └───────────┴──────────────▶ Response
```

The most important implementation rule is:

> **The async networking runtime must not become the model execution scheduler.**

Tokio should stay responsive to sockets, HTTP/2, timers, request cancellation, and response delivery. CPU-intensive tokenization/inference must be explicitly bounded.

---

# 4. Rust Build Configuration

Start with an aggressively optimized production profile.

```toml
[profile.release]
opt-level = 3
lto = "fat"
codegen-units = 1
panic = "abort"
incremental = false
debug = false
strip = "symbols"
```

Why:

- `opt-level = 3` enables aggressive optimization.
- LTO lets LLVM optimize across crate boundaries.
- `codegen-units = 1` gives LLVM a larger optimization scope.
- `panic = "abort"` removes unwinding machinery where acceptable.
- disabling incremental compilation is appropriate for production binaries.

For faster CI builds, `lto = "thin"` is a reasonable alternative, but benchmark the production binary built with `fat` LTO before choosing.

## 4.1 Compile for the actual CPU

For a controlled deployment fleet:

```bash
RUSTFLAGS="-C target-cpu=native" cargo build --release
```

This allows LLVM to use the instruction set of the build host.

**Do not use `target-cpu=native` if the binary will be moved to older or different CPUs.**

For heterogeneous fleets, compile for a known minimum CPU generation instead.

This matters for:

- SIMD
- AVX/AVX2/AVX-512 where available
- FMA
- optimized hashing
- Candle CPU kernels
- matrix operations

## 4.2 Treat allocator replacement as an experiment

Do not automatically add jemalloc or mimalloc because "Rust services use it."

The classifier hot path should be designed to allocate very little. If allocator pressure is still visible in profiles, benchmark:

- system allocator
- mimalloc
- jemalloc

Keep the allocator that improves **p99 under representative load**, not the one that wins a synthetic allocation benchmark.

---

# 5. Tokio Runtime Rules

## 5.1 Tokio is for I/O

Do not execute long model forwards directly inside ordinary async request futures if they monopolize a Tokio worker.

Bad pattern:

```rust
async fn classify(...) -> Result<Response, Error> {
    // potentially expensive CPU work directly in the Tokio task
    let output = model.forward(...)?;
    Ok(output)
}
```

For CPU inference this can starve unrelated network tasks.

## 5.2 Do not use unlimited `spawn_blocking`

Tokio's blocking pool is intentionally allowed to grow very large because it also supports blocking filesystem and DNS operations.

Therefore this is **not** sufficient concurrency control:

```rust
tokio::task::spawn_blocking(move || {
    model.forward(...)
})
```

If 1,000 requests arrive, you do not want 1,000 CPU inference jobs competing for cores.

If `spawn_blocking` is used, place a semaphore in front of it.

```rust
let permit = inference_semaphore
    .acquire()
    .await
    .map_err(|_| Error::ShuttingDown)?;

let result = tokio::task::spawn_blocking(move || run_inference(input))
    .await??;

drop(permit);
```

For a highly latency-sensitive service, a dedicated inference worker or worker pool is usually easier to reason about.

## 5.3 Preferred bounded worker pattern

```text
Tokio request task
      │
      ▼
bounded mpsc queue
      │
      ▼
dedicated inference worker(s)
      │
      ▼
oneshot response
```

Properties:

- fixed maximum queue depth
- fixed maximum model concurrency
- predictable overload behavior
- independent from Tokio's blocking pool
- easy queue-time instrumentation

A GPU deployment will often start with **one model-execution worker per GPU** and then experimentally increase in-flight work.

A CPU deployment may use one or a small number of workers depending on:

- BLAS/MKL internal thread count
- Candle/Rayon parallelism
- physical core count
- NUMA topology
- sequence length

Never multiply all forms of parallelism together accidentally.

---

# 6. Avoid CPU Oversubscription

Rust ML services can create multiple independent thread pools:

- Tokio worker threads
- Tokio blocking threads
- Rayon
- Hugging Face Tokenizers
- MKL / BLAS
- application inference workers

This can destroy tail latency even when average throughput rises.

Example of a bad configuration on a 16-core system:

```text
Tokio:             16 threads
Rayon:             16 threads
Tokenizers:        16 threads
MKL:               16 threads
Inference workers: 8
```

That configuration can create large runnable queues and constant context switching.

Instead assign an explicit concurrency budget.

Example starting point:

```text
Network runtime:      2–4 threads
Inference execution:  hardware dependent
Tokenizer Rayon:      capped
BLAS/MKL threads:     explicitly configured
```

The exact values must come from benchmark data.

For Hugging Face Tokenizers, control Rayon concurrency explicitly where appropriate:

```bash
RAYON_RS_NUM_THREADS=4
```

or disable tokenizer internal parallelism if request-level parallelism is already sufficient:

```bash
TOKENIZERS_PARALLELISM=false
```

For batch size 1 / short classifier inputs, more tokenizer threads can cost more than they save.

---

# 7. gRPC / Tonic Performance

Use Tonic over HTTP/2 with persistent client connections.

## 7.1 Keep `TCP_NODELAY`

Tonic enables `TCP_NODELAY` by default. Keep it enabled for small latency-sensitive RPCs.

```rust
tonic::transport::Server::builder()
    .tcp_nodelay(true)
```

Do not add artificial Nagle delays to classifier requests.

## 7.2 Bound request concurrency

Tonic exposes request concurrency controls.

```rust
tonic::transport::Server::builder()
    .concurrency_limit_per_connection(LIMIT)
    .load_shed(true)
```

The concurrency limit should correspond to actual service capacity rather than an arbitrary high number.

Load shedding is preferable to allowing queueing delay to grow without bound.

For this type of service:

> Reject overload quickly instead of converting overload into multi-second p99 latency.

## 7.3 Keep connections alive

Repeated TCP/TLS handshakes are incompatible with a strict low-latency target.

Clients should:

- create channels once
- reuse channels
- clone `tonic::transport::Channel` when needed
- avoid reconnecting per request

Tonic channels are designed to be cheaply cloned and multiplex requests over HTTP/2.

## 7.4 HTTP/2 flow control

Tonic exposes:

- `initial_stream_window_size`
- `initial_connection_window_size`
- `http2_adaptive_window`
- `max_concurrent_streams`
- `max_frame_size`
- HTTP/2 keepalive settings

For small classifier payloads, default HTTP/2 windows are rarely the first bottleneck.

Do **not** blindly increase windows.

Tune these only after profiling indicates HTTP/2 flow-control stalls or larger payloads are expected.

## 7.5 Compression

Avoid gRPC compression for tiny request/response objects.

Compression trades:

```text
network bytes ↓
CPU work      ↑
latency       potentially ↑
```

For short text classifier RPCs inside a cluster, compression is usually a poor latency trade unless network constraints are measurable.

## 7.6 Keep protobuf messages small

A classifier RPC should not return a giant object graph.

Prefer compact fields:

```protobuf
message Classification {
  uint32 class_id = 1;
  float confidence = 2;
  string model_revision = 3;
}
```

Do not duplicate large input strings in responses.

---

# 8. Protobuf, Bytes, and Copy Reduction

`prost::Message::encode_to_vec()` creates a new `Vec<u8>`.

For custom serialization hot paths, preallocate when the size is known:

```rust
let required = message.encoded_len();
let mut buffer = Vec::with_capacity(required);
message.encode(&mut buffer)?;
```

For networking buffers use `bytes::Bytes` where ownership sharing is useful.

`Bytes` is:

- cheaply cloneable
- sliceable
- reference-counted internally where appropriate
- suitable for zero-copy-style networking paths

Do not turn every `Bytes` into a `Vec<u8>` or `String` unless required.

---

# 9. Allocation Rules for the Hot Path

## 9.1 Avoid repeated heap construction

Bad:

```rust
let labels = vec!["a".to_string(), "b".to_string(), "c".to_string()];
```

per request.

Prefer static or startup-owned metadata:

```rust
static LABELS: &[&str] = &["a", "b", "c"];
```

or immutable shared state:

```rust
Arc<[Label]>
```

## 9.2 Pre-size collections

Use:

```rust
Vec::with_capacity(expected)
String::with_capacity(expected)
HashMap::with_capacity(expected)
```

when size is known.

## 9.3 Avoid unnecessary string ownership

Prefer:

```rust
&str
Cow<'_, str>
Arc<str>
```

where lifetime and ownership semantics allow it.

Do not clone request text repeatedly between:

```text
gRPC decode
→ normalization
→ cache key
→ tokenizer
→ logging
```

## 9.4 Be careful with `format!`

`format!` allocates.

Do not build verbose debug strings on every successful request.

## 9.5 Logging is not free

Avoid synchronous or high-cardinality logging on the hot path.

Do not log the full user prompt for every request.

Use metrics for:

- latency
- queue depth
- cache status
- sequence length
- model revision
- errors

Trace detailed request internals only when sampled or explicitly enabled.

---

# 10. Cache Design

Caching is the single largest latency optimization when requests repeat.

A cache hit should bypass:

- tokenization
- tensor creation
- device transfer
- model inference
- softmax/postprocessing when stored result is final

## 10.1 Prefer an in-process cache

For the latency-critical hot path:

```text
in-process cache
    ↓
model inference
```

Do not put Redis or another network cache in front of a model if the primary purpose is shaving microseconds/milliseconds from a same-process classifier.

A remote cache can still exist at another layer, but the first lookup should be local.

## 10.2 Moka is a strong default

Moka provides:

- concurrent access
- bounded capacity
- TinyLFU/LRU behavior
- TTL/TTI
- async and sync variants
- stampede protection/coalescing for same-key initialization

Example:

```rust
use moka::future::Cache;
use std::sync::Arc;
use std::time::Duration;

type CachedResult = Arc<ClassificationResult>;

let cache: Cache<CacheKey, CachedResult> = Cache::builder()
    .max_capacity(100_000)
    .time_to_live(Duration::from_secs(1800))
    .build();
```

Store `Arc<T>` if the cached result is not trivially cheap to clone.

## 10.3 Coalesce identical misses

Moka's `get_with` / `try_get_with` can coalesce concurrent cache misses for the same key.

That avoids:

```text
100 identical requests
→ 100 identical tokenizations
→ 100 identical model forwards
```

and instead permits:

```text
100 identical requests
→ 1 inference
→ shared cached result
```

This is especially important after:

- startup
- cache expiration
- model rollout
- popular prompt bursts

## 10.4 Cache key correctness

The cache key must include every value that can affect the classification.

Example:

```rust
#[derive(Clone, Hash, PartialEq, Eq)]
struct CacheKey {
    model_revision: Arc<str>,
    tokenizer_revision: Arc<str>,
    classifier_revision: Arc<str>,
    max_length: u16,
    normalized_input: Arc<str>,
}
```

Also include, where applicable:

- tenant-specific classifier
- adapter/revision
- preprocessing mode
- language mode
- classifier taxonomy version

A model update must not accidentally reuse results from the previous model.

## 10.5 Normalize before caching — carefully

Possible normalization:

- line ending canonicalization
- removal of semantically irrelevant surrounding whitespace
- stable Unicode normalization if the model/tokenizer semantics permit it

Do **not** lowercase, collapse whitespace, or otherwise modify text unless model behavior is intentionally defined that way.

Cache normalization must preserve classifier semantics.

## 10.6 Moka vs DashMap

Use **Moka** when you need:

- capacity bounding
- eviction
- TTL
- admission policy
- stampede protection

Use **DashMap** when:

- key cardinality is naturally bounded
- you control invalidation manually
- you want a simple concurrent map
- benchmark evidence shows policy overhead matters

Do not implement a custom sharded cache before measuring Moka.

---

# 11. Candle: Recommended Model Loading

Use SafeTensors and load the model once during startup.

Candle exposes memory-mapped SafeTensor loading:

```rust
use candle_core::{DType, Device};
use candle_nn::VarBuilder;

let device = Device::Cpu;

let vb = unsafe {
    VarBuilder::from_mmaped_safetensors(
        &[model_path],
        DType::F32,
        &device,
    )?
};
```

For GPU:

```rust
let device = Device::new_cuda(0)?;
```

Then build the model once:

```rust
use candle_transformers::models::modernbert::{
    Config,
    ModernBertForSequenceClassification,
};

let model =
    ModernBertForSequenceClassification::load(vb, &config)?;
```

Keep:

```text
Device
Model
Tokenizer
Model config
Label map
Common masks
```

alive for the life of the process.

Do not reload weights per request.

---

# 12. Candle ModernBERT: Important Current Implementation Details

Candle 0.11 includes native ModernBERT support, including:

- `ModernBert`
- `ModernBertForMaskedLM`
- `ModernBertForSequenceClassification`
- `ModernBertClassifier`
- CLS or mean classifier pooling

For a classification service use the sequence-classification model rather than the masked-LM head.

## 12.1 Current Candle ModernBERT attention path

As of Candle 0.11, the implementation performs the attention path approximately as:

```text
QKV projection
→ reshape / permute
→ RoPE
→ Q × Kᵀ
→ add attention mask
→ softmax
→ attention × V
→ output projection
```

This means the current implementation still materializes a dense attention matrix.

That matters because the upstream ModernBERT design derives much of its efficiency from local/global attention and optimized attention implementations.

**Do not assume that "ModernBERT architecture" automatically means the current Candle implementation receives every optimization from the reference PyTorch/FlashAttention path.**

## 12.2 Current Candle implementation builds a local mask during forward

The current implementation constructs the local attention mask from sequence length during `forward`.

Conceptually:

```rust
for i in 0..seq_len {
    for j in 0..seq_len {
        ...
    }
}
```

and then creates a tensor from the result.

This is unnecessary repeated work when many requests use the same sequence lengths.

### High-priority optimization

Patch or wrap the ModernBERT implementation so local masks are cached by:

```text
(device, dtype, sequence_length, local_attention_size)
```

Example conceptual cache:

```rust
DashMap<MaskKey, Tensor>
```

or a small fixed table for supported sequence buckets.

If the service uses only:

```text
32
64
128
256
512
```

token buckets, precompute all local masks at startup.

## 12.3 Precompute all-static RoPE state

Candle already creates the rotary embeddings during model loading, which is good.

Do not recreate RoPE tables per request.

## 12.4 Global attention masks

Padding masks vary by request, but optimize the common case.

If batch size is 1 and the request is padded to a known bucket:

- cache reusable all-valid masks where possible
- create the final per-request padding representation once
- keep it on the same device as the model

Avoid:

```text
CPU mask
→ derived CPU mask
→ GPU copy
```

when it can be:

```text
model-device mask
→ model-device operations
```

## 12.5 Full dense attention can dominate long sequences

For 64–256 tokens, dense attention may be acceptable.

For thousands of tokens, dense materialization becomes incompatible with the reason ModernBERT uses local/global attention in the first place.

If long input is required, profile a custom Candle ModernBERT path that implements:

- true windowed/local attention
- FlashAttention-compatible kernels where applicable
- no dense `seq × seq` mask for local layers
- fused mask/application where practical

For a strict latency classifier, the easiest optimization is often:

> **Do not send thousands of tokens to the classifier.**

Set an explicit classifier maximum input length based on accuracy testing.

---

# 13. Sequence-Length Bucketing

Variable sequence lengths create:

- variable compute
- variable tensor allocation
- variable GPU behavior
- variable mask construction
- unpredictable p99

Use a small number of buckets:

```text
32
64
128
256
512
```

or whatever matches the real traffic distribution.

Flow:

```text
tokenize
→ determine sequence length
→ round to next supported bucket
→ pad to bucket
→ use precomputed bucket assets
→ infer
```

Benefits:

- reusable attention masks
- predictable tensor shapes
- easier warmup
- simpler benchmark matrices
- easier micro-batching
- more stable latency

Do not blindly use 512 tokens for every request if most inputs are 40 tokens.

---

# 14. Tokenizer Performance

Use Hugging Face's Rust `tokenizers` crate directly.

Load once:

```rust
let tokenizer = tokenizers::Tokenizer::from_file(path)?;
```

Do not:

- parse `tokenizer.json` per request
- download from Hugging Face in the hot path
- reconstruct truncation/padding configuration per request

Configure startup state once.

## 14.1 Cap input length

Classifier latency scales strongly with token count.

Set truncation intentionally.

Example principle:

```text
Model supports 8192 tokens
≠
Classifier service should accept 8192 tokens on its low-latency path
```

If routing quality is nearly unchanged at 256 tokens, then 256 should be the service limit.

## 14.2 Tokenizer parallelism

The tokenizer can use Rayon.

For single short requests, internal parallelization may add overhead.

Benchmark:

```text
TOKENIZERS_PARALLELISM=false
```

versus controlled Rayon concurrency.

For throughput-oriented batch tokenization, parallel tokenization may win.

For latency-oriented batch=1 traffic, sequential tokenization often deserves serious consideration.

## 14.3 Optional tokenization cache

If cache semantics require outputs for different classifier heads but identical text is frequently reused, a second cache can store tokenized inputs.

Example:

```text
normalized text
→ TokenizedInput {
    ids,
    attention_mask,
    bucket
}
```

However:

- completed classification caching is more valuable
- tokenized inputs consume memory
- tokenization cache adds complexity

Implement only if profiling shows tokenizer time is material after result caching.

---

# 15. Tensor Construction

Minimize host allocations around:

```text
Vec<u32> token IDs
Vec<u32> attention mask
Tensor creation
device transfer
```

## 15.1 Construct exactly once

Bad:

```text
Encoding
→ Vec clone
→ request struct clone
→ Tensor CPU
→ Tensor clone
→ Tensor GPU
```

Aim for:

```text
Encoding
→ contiguous IDs/mask
→ Tensor on target device
```

## 15.2 Keep dtype deliberate

For token IDs use the dtype required by the model API.

For model weights/activations:

- CPU: benchmark F32 vs lower precision support on actual hardware
- NVIDIA GPU: benchmark F16/BF16 where the model weights and Candle path support them

Do not convert dtype repeatedly during every layer/request if the model can be loaded in the intended inference dtype.

## 15.3 Avoid device synchronization inside the request path

GPU APIs are asynchronous.

A forced synchronization blocks the CPU until all prior GPU work completes.

Use synchronization:

- during benchmark timing when accurate GPU elapsed time is required
- during warmup verification
- when host access to the result requires completion

Do not sprinkle `device.synchronize()` throughout inference.

---

# 16. CPU Inference

CPU can be the right answer for a small classifier, especially when:

- batch = 1
- sequence lengths are short
- the CPU is modern and high-frequency
- the GPU would otherwise be lightly utilized
- avoiding PCIe transfer and GPU queueing matters

## 16.1 Enable the optimized Candle CPU backend

On x86, benchmark Candle with MKL support.

Example dependency configuration:

```toml
candle-core = { version = "0.11", features = ["mkl"] }
candle-nn = "0.11"
candle-transformers = "0.11"
```

For supported Apple systems, benchmark Accelerate.

## 16.2 Control math-library thread counts

A small transformer forward may not benefit from using every CPU core for each matrix multiplication.

Benchmark:

```text
1
2
4
8
...
```

math threads.

The winner for throughput may not be the winner for p99 latency.

## 16.3 Avoid request-level × BLAS-level multiplication

If each inference uses 8 BLAS threads, do not run 16 inference jobs simultaneously on a 16-core CPU.

Start with:

```text
few inference workers
×
few internal math threads
≈
available physical cores
```

and benchmark.

## 16.4 Pinning and NUMA

Only pursue CPU affinity / NUMA pinning after basic profiling.

For multi-socket servers:

- keep model memory local to the execution NUMA node
- avoid inference threads bouncing between sockets
- avoid remote memory access to model weights

This can matter materially for large resident weights and p99.

---

# 17. GPU Inference

GPU inference is most useful when enough work exists to amortize:

- kernel launch
- device transfer
- synchronization
- queueing

## 17.1 Keep model weights permanently in VRAM

Load at process startup and fail readiness if the model cannot stay resident.

Never offload/reload model weights between requests.

## 17.2 Transfer only what is needed

For a text classifier:

```text
token IDs
attention mask
```

are tiny compared with model weights.

Keep preprocessing on CPU, then transfer compact model inputs.

## 17.3 Warm the GPU before readiness

Startup:

```text
load model
→ initialize CUDA
→ run representative forwards
→ synchronize
→ mark service ready
```

Warm at least the common buckets:

```text
32
64
128
256
512
```

if those are the supported shapes.

This removes first-request penalties from user traffic.

## 17.4 Concurrency is not automatically good

Launching more simultaneous model forwards may increase throughput but worsen latency.

For a classifier service:

- start with one execution lane per GPU
- measure
- test 2, 4, etc. in-flight requests
- stop increasing when p95/p99 gets worse

## 17.5 Micro-batching

Dynamic batching is a throughput optimization with a latency cost.

If the SLA is strict, use either:

- no batching, or
- a very small batching window

Example experimental range:

```text
0 µs
100 µs
250 µs
500 µs
1 ms
```

Do not use a multi-millisecond batch collection window in a service trying to stay under ~20 ms unless the throughput gain clearly compensates.

Batch only compatible sequence buckets.

---

# 18. Backpressure and Load Shedding

An inference system has a finite service rate.

Once arrival rate exceeds inference rate:

```text
queue grows
→ queue latency grows
→ p99 explodes
→ client timeouts
→ wasted work
```

The solution is bounded queues.

Example:

```rust
let (tx, rx) = tokio::sync::mpsc::channel::<InferenceJob>(QUEUE_DEPTH);
```

Use `try_send` where immediate overload rejection is desirable:

```rust
match tx.try_send(job) {
    Ok(()) => {}
    Err(tokio::sync::mpsc::error::TrySendError::Full(_)) => {
        return Err(Status::resource_exhausted("classifier saturated"));
    }
    Err(_) => {
        return Err(Status::unavailable("classifier unavailable"));
    }
}
```

Measure:

```text
queue_wait_ms
inference_ms
end_to_end_ms
```

separately.

A 10 ms model with 40 ms of queue delay is not a 10 ms service.

---

# 19. Suggested Inference Worker Skeleton

Conceptual pattern:

```rust
struct InferenceJob {
    input: Arc<str>,
    response: tokio::sync::oneshot::Sender<Result<ClassificationResult, InferenceError>>,
}

struct InferenceHandle {
    tx: tokio::sync::mpsc::Sender<InferenceJob>,
}

impl InferenceHandle {
    async fn classify(
        &self,
        input: Arc<str>,
    ) -> Result<ClassificationResult, InferenceError> {
        let (tx, rx) = tokio::sync::oneshot::channel();

        self.tx
            .try_send(InferenceJob {
                input,
                response: tx,
            })
            .map_err(|_| InferenceError::Overloaded)?;

        rx.await.map_err(|_| InferenceError::WorkerStopped)?
    }
}
```

Worker:

```rust
fn run_worker(
    mut rx: tokio::sync::mpsc::Receiver<InferenceJob>,
    engine: ModelEngine,
) {
    while let Some(job) = rx.blocking_recv() {
        let result = engine.classify(&job.input);
        let _ = job.response.send(result);
    }
}
```

This creates a clean boundary between:

```text
async I/O
and
synchronous model execution
```

For CPU, instantiate a deliberately sized worker pool.

For GPU, begin with one worker per GPU and benchmark additional concurrency.

---

# 20. Cache + Inference Composition

The cache should sit before the expensive inference queue.

Pseudo-flow:

```rust
async fn classify(&self, request: Request) -> Result<Arc<Result>, Error> {
    let normalized = normalize(&request.text);
    let key = self.cache_key(&normalized);

    self.cache
        .try_get_with(key, async {
            self.inference
                .classify(normalized)
                .await
        })
        .await
        .map_err(|e| ...)
}
```

This combines:

- fast cache hit
- same-key miss coalescing
- bounded inference execution

A popular missing entry should consume only one inference slot.

---

# 21. Latency Budget

The service must track cache-hit and cache-miss latency separately.

## 21.1 Cache-hit path

Example engineering budget:

| Stage | Goal |
|---|---:|
| RPC decode | < 0.5 ms |
| normalize/key | < 0.2 ms |
| cache lookup | < 0.1 ms |
| response encode | < 0.3 ms |
| internal service total | ~1 ms-class |

Exact network end-to-end time depends on deployment topology.

## 21.2 Cache-miss path

A 20 ms-class target might look like:

| Stage | Budget |
|---|---:|
| gRPC + decode | 0.5–1.0 ms |
| normalization/cache miss | 0.1–0.3 ms |
| queue | < 1 ms |
| tokenization | 0.5–2 ms |
| tensor/device preparation | 0.2–1.0 ms |
| model forward | 8–15 ms |
| postprocess | < 0.5 ms |
| response encode | < 0.5 ms |

This is not a guarantee.

The model-forward budget must be validated for:

- exact checkpoint
- exact dtype
- exact hardware
- exact sequence length
- batch size
- concurrency

The service cannot claim a 20 ms target from an isolated batch=1 benchmark while real traffic runs at a different concurrency.

---

# 22. Benchmark Matrix

At minimum benchmark:

## Sequence lengths

```text
32
64
128
256
512
```

## Batch sizes

```text
1
2
4
8
```

## Concurrency

```text
1
2
4
8
16
32
```

## Cache modes

```text
100% hit
0% hit
realistic mixed distribution
```

## Execution backends

```text
CPU
GPU
```

where available.

Measure:

```text
p50
p90
p95
p99
max
requests/sec
queue wait
tokenization
model forward
cache hit ratio
CPU utilization
GPU utilization
```

---

# 23. Correct GPU Benchmark Timing

GPU kernel launches can return before the GPU finishes.

Incorrect:

```rust
let start = Instant::now();
model.forward(&input)?;
println!("{:?}", start.elapsed());
```

This may measure launch time instead of completed execution.

For an isolated GPU forward benchmark:

```rust
device.synchronize()?;

let start = Instant::now();
let output = model.forward(&input)?;
device.synchronize()?;

let elapsed = start.elapsed();
```

Candle's own CUDA examples use device synchronization when timing GPU operations.

For end-to-end server benchmarks, measure from the client so the response naturally requires useful completion.

---

# 24. Criterion Microbenchmarks

Use Criterion for stable local microbenchmarks of:

- normalization
- cache key creation
- cache lookup
- tokenization
- tensor preparation
- protobuf encoding
- CPU model forward

Example structure:

```rust
fn bench_tokenization(c: &mut Criterion) {
    let tokenizer = load_tokenizer();

    c.bench_function("tokenize_128_chars", |b| {
        b.iter(|| {
            tokenizer.encode(
                black_box(TEST_INPUT),
                true,
            ).unwrap()
        })
    });
}
```

Do not use Criterion as the only end-to-end load test.

Microbenchmarks answer:

> "Did this function get faster?"

Load tests answer:

> "Does the service still meet p99 under concurrency?"

Both are required.

---

# 25. Profiling

Profile optimized binaries.

Useful tools:

```text
Linux perf
FlameGraph
cargo-flamegraph
pprof
Criterion
Tokio console during development
```

Look for:

- allocator activity
- string cloning
- tokenizer work
- mask construction
- tensor copies
- `contiguous()` copies
- softmax
- matrix multiplication
- runtime queueing
- lock contention
- cache policy overhead
- tracing/logging overhead
- CPU oversubscription

Optimization must be driven by measured samples.

---

# 26. ModernBERT-Specific Optimization Worklist

For Candle ModernBERT, prioritize these in order.

## P0 — Measure by sequence length

Establish forward-only latency for:

```text
32 / 64 / 128 / 256 / 512
```

before changing code.

## P0 — Cache local attention masks

Current Candle ModernBERT constructs the local sliding-window mask during each forward.

Move this out of the request path.

Precompute masks by sequence bucket.

## P0 — Keep mask/input tensors on model device

Avoid unnecessary `to_device` transfers.

## P0 — Cap classifier sequence length

Do not expose the full ModernBERT 8192-token capability unless classifier accuracy requires it.

## P1 — Remove unnecessary per-forward tensor construction

Profile:

- mask expansion
- dtype conversion
- reshapes
- `contiguous()`
- intermediate allocations

## P1 — Evaluate true local/Flash attention implementation

The current Candle ModernBERT source uses dense attention math.

For longer contexts or aggressive GPU latency targets, investigate a custom ModernBERT attention implementation using Candle's lower-level CUDA/custom-op capabilities or `candle-flash-attn` where semantics can be matched.

The important target is:

```text
local layer
≠
construct full seq × seq attention matrix and mask it
```

## P1 — Bucket shapes

Use pre-warmed sequence buckets.

## P2 — Fuse postprocessing

For classification, the service usually needs:

```text
argmax
confidence
```

not the full probability tensor copied back to host.

Minimize host-visible output.

## P2 — Custom kernels

Only after profiling proves framework-level operations dominate:

- fused QKV + RoPE
- fused masked attention
- fused classification postprocess

Do not begin with custom CUDA kernels before eliminating avoidable host-side work.

---

# 27. Things Not to Do

Do not:

- load the model per request
- load the tokenizer per request
- download model assets at request time
- execute unrestricted CPU inference on Tokio workers
- use unlimited `spawn_blocking` as a scheduler
- allow unbounded inference queues
- reconnect gRPC channels per request
- compress tiny gRPC messages by default
- allocate labels/config structures per request
- clone prompt strings through every layer
- use a remote cache as the only cache
- rebuild static attention masks every forward
- use 8192 tokens because ModernBERT supports 8192
- assume GPU is always faster at batch=1
- assume more threads always reduce latency
- benchmark only average latency
- benchmark GPU kernels without synchronization
- optimize debug builds
- add custom unsafe code before profiling
- change allocator/compiler/runtime simultaneously and then guess which change helped

---

# 28. Cargo Configuration Example

Use this as a starting point, not as an unreviewed lockfile.

```toml
[dependencies]
anyhow = "1"
bytes = "1"
prost = "0.14"
tonic = { version = "0.14", features = ["transport"] }
tokio = { version = "1", features = [
    "rt-multi-thread",
    "macros",
    "sync",
    "time",
    "net"
] }
tower = { version = "0.5", features = [
    "limit",
    "load-shed",
    "timeout"
] }

moka = { version = "0.12", features = ["future"] }
dashmap = "6"

candle-core = "0.11"
candle-nn = "0.11"
candle-transformers = "0.11"
safetensors = "0.8"
tokenizers = "0.23"

serde = { version = "1", features = ["derive"] }
serde_json = "1"
tracing = "0.1"

[dev-dependencies]
criterion = "0.8"

[profile.release]
opt-level = 3
lto = "fat"
codegen-units = 1
panic = "abort"
incremental = false
strip = "symbols"
```

GPU build:

```toml
candle-core = { version = "0.11", features = ["cuda", "cudnn"] }
```

CPU x86 test:

```toml
candle-core = { version = "0.11", features = ["mkl"] }
```

Do not enable backends you do not ship.

---

# 29. Suggested Repository Performance Tests

```text
benches/
├── cache.rs
├── tokenizer.rs
├── protobuf.rs
├── modernbert_forward.rs
└── preprocessing.rs

tests/perf/
├── grpc_single_request.rs
├── grpc_concurrency.rs
├── cache_hit.rs
├── cache_miss.rs
└── overload.rs
```

The CI performance job should retain a baseline for:

```text
tokenization p50
forward p50
cache lookup
single-RPC latency
p95/p99 under fixed concurrency
```

Do not make noisy cloud-hosted microbenchmarks a hard merge gate without dedicated/repeatable hardware.

---

# 30. Definition of Done for the Rust Hot Path

A performance-oriented implementation is not complete until all of the following are true:

- [ ] Release binary uses an explicitly documented optimization profile.
- [ ] Production CPU target flags are intentional.
- [ ] Model loads exactly once.
- [ ] Tokenizer loads exactly once.
- [ ] Readiness occurs only after model warmup.
- [ ] Common sequence buckets are warmed.
- [ ] ModernBERT local attention masks are cached/precomputed.
- [ ] Result cache is bounded.
- [ ] Cache key includes model/classifier revision.
- [ ] Concurrent identical misses are coalesced.
- [ ] Inference queue is bounded.
- [ ] Overload is rejected rather than queued indefinitely.
- [ ] Tokio I/O threads are isolated from heavy CPU inference.
- [ ] Tokenizer/Rayon/MKL thread counts are deliberately controlled.
- [ ] gRPC connections are reused.
- [ ] `TCP_NODELAY` remains enabled.
- [ ] Cache-hit latency is measured separately from cache-miss latency.
- [ ] Queue time is measured separately from model execution.
- [ ] Benchmarks cover realistic sequence lengths.
- [ ] Benchmarks cover realistic concurrency.
- [ ] p50/p95/p99 are reported.
- [ ] GPU timing is synchronized correctly in isolated benchmarks.
- [ ] Full end-to-end latency is measured from an external client.
- [ ] No performance claim is based solely on `cargo run`.
- [ ] No optimization is merged without a before/after benchmark.

---

# 31. Highest-Impact Optimization Order

If implementation time is limited, do this:

### 1. Build release correctly

```text
-O3
LTO
codegen-units=1
target CPU
```

### 2. Keep model + tokenizer permanently resident

No request-path loading.

### 3. Add in-process result cache

Moka, bounded, versioned keys.

### 4. Add same-key miss coalescing

Prevent duplicate inference bursts.

### 5. Enforce sequence-length limits

Do not waste transformer compute.

### 6. Separate Tokio networking from model scheduling

Bounded inference workers.

### 7. Control all thread pools

Prevent oversubscription.

### 8. Precompute ModernBERT local attention masks

This is a concrete optimization against the current Candle implementation.

### 9. Benchmark CPU vs GPU by real traffic shape

Especially batch=1.

### 10. Add shape buckets and warmup

Reduce variance.

### 11. Profile Candle attention

If attention dominates, replace dense local attention with a truly local/fused implementation.

### 12. Consider lower-level kernel work

Only after the rest of the hot path is clean.

---

# 32. Key Implementation Principle

For this service, "written in Rust" is not itself the optimization.

The performance advantage comes from using Rust to build a hot path with:

```text
persistent state
+ bounded concurrency
+ no runtime GC
+ minimal allocation
+ minimal copying
+ local caching
+ predictable scheduling
+ native model execution
+ compiler specialization
```

The desired request path is:

```text
decode
→ normalize
→ cache
→ [only on miss] tokenize
→ infer
→ cache
→ encode
```

Every additional operation should justify its latency.

---

# 33. Primary Technical References

The recommendations above were checked against current primary/documentation sources including:

- Rust Cargo Book — release profiles, LTO, codegen units
- Rust Compiler Book — `target-cpu` and code generation options
- Tokio runtime documentation — worker scheduling and blocking work
- Tonic documentation — HTTP/2 server/channel controls, load shedding, concurrency limits, TCP_NODELAY
- Prost documentation — message encoding and allocation behavior
- Bytes documentation — cheap cloning/slicing and shared network buffers
- Moka documentation — concurrent cache behavior, TinyLFU, TTL, same-key initialization coalescing
- Hugging Face Tokenizers documentation — Rust tokenizer implementation and Rayon parallelism
- SafeTensors Rust documentation — zero-copy-oriented tensor format and mmap usage
- Candle 0.11 documentation and source
- Candle `ModernBERT` implementation source
- Candle `VarBuilder::from_mmaped_safetensors`
- ModernBERT model configuration and model documentation
- Criterion documentation

Important current-source observation:

> Candle 0.11 includes first-class ModernBERT sequence classification, but its current `modernbert.rs` implementation constructs the local sliding-window mask during each forward and uses dense attention matrix operations. For a latency-critical classifier, this should be directly benchmarked and is a high-value target for optimization.
