<!-- DRAFT of the upstream llm-d-sc README. Placeholders marked <<TODO>> need
     org-specific facts from the maintainer before the first push. -->

# llm-d-sc

**Semantic classification for inference routing.** A low-latency Rust service
that turns an incoming request into calibrated semantic signals — domain,
complexity, sensitivity — so an AI Gateway can route it well.

<!-- <<TODO badges>>: CI, Apache-2.0, llm-d incubation / CNCF tier, OpenSSF Best
     Practices, Slack -->

> **Status: pre-1.0 and under active development.** APIs and configuration may
> change between 0.x releases. See [Project status](#project-status) for what is
> proven today and what is still pending.

## What llm-d-sc is

llm-d-sc executes semantic classifiers in the inference request path and returns
ranked, versioned evidence about a request. It is a **signal producer, not a
decision maker**.

```
        request
           │
           ▼
     ┌───────────┐   classification request   ┌──────────┐
     │ AI Gateway│ ────────────────────────►  │ llm-d-sc │
     │           │ ◄──────────────────────── │          │
     └─────┬─────┘   ranked signals +         └──────────┘
           │         confidence + revisions
           │
           │ gateway applies policy, session state, health,
           │ capacity, cost, fallback …
           ▼
    selected model / endpoint
```

**llm-d-sc owns**: classifier execution, model and tokenizer lifecycle, residency
and warmup, caching, calibration, confidence, and abstention.

**llm-d-sc does not own**: routing decisions, endpoint selection, policy or
guardrail enforcement, session state, or model lifecycle across an
organisation. Those belong to the gateway and its control plane. The wire
contract enforces this: the response type has **no route or endpoint field**, by
design ([ADR-0001](docs/decisions/0001-no-route-field-in-response.md)).

## Why it exists

Routing an inference request well requires knowing something about it. Doing
that inference inside a gateway couples classifier lifecycle, model residency,
and GPU/CPU scheduling to the data plane. llm-d-sc separates them:

- **A gateway stays a gateway.** No model loading, no tokenizer versioning, no
  warmup semantics in the routing hot path.
- **Classification stays cheap.** Resident models, an exact-result cache with
  versioned identity, and bounded inference admission.
- **Signals stay honest.** Versioned revisions on every result, explicit
  abstention when context is insufficient, and no fabricated labels on failure.
- **Backends stay replaceable.** `ClassifierRuntime` is an abstraction; Candle is
  the first implementation, not the architecture.

## Quick start

Requires a Rust toolchain, `protoc`, and a classifier artifact.

```bash
# 1. Materialise a classifier artifact (ModelCar layout under /models)
./hack/fetch-model

# 2. Run the service
LLM_D_SC_MODEL_DIR=./artifacts/models/sensitivity \
LLM_D_SC_LISTEN=0.0.0.0:50051 cargo run --release --bin llm-d-sc-server
# -> READY (resident classifier loaded and warmed)

# 3. Exercise it with the bundled gateway stand-in
cargo test --release --test grpc -- --nocapture
```

The service reports **not ready** until the artifact is validated, the model and
tokenizer are loaded, and a warmup forward has succeeded — so an orchestrator
never routes to a cold instance.

Deployment manifests: [`deploy/`](deploy/). Container build:
[`Containerfile`](Containerfile) (the service image ships **no model**; the
classifier arrives as a separate OCI artifact).

## Architecture

```
 gateway ──gRPC──►  tonic handler
                        │
                        ▼
                exact-result cache          hit ──► ranked signals
                        │ miss
                        ▼
                bounded admission ──── over capacity ──► RESOURCE_EXHAUSTED
                        │
                        ▼
             dedicated inference executor        (never a network worker)
                        │
                        ▼
              resident ClassifierRuntime  ──►  Candle backend
```

Three properties are load-bearing:

1. **The network runtime is not the model scheduler.** Forwards run on dedicated
   executor threads; the handler only admits work and awaits a result.
2. **Overload is explicit.** Beyond the configured bound, requests are rejected
   rather than queued indefinitely.
3. **Cache identity is versioned.** Keys are BLAKE3 fingerprints over classifier,
   model, tokenizer and taxonomy revisions plus a hash of the normalized input —
   never the raw prompt, and never reusable across a revision change.

Details: [`docs/architecture.md`](docs/architecture.md),
[`docs/research/runtime-performance.md`](docs/research/runtime-performance.md).

## Performance

Measured on a developer host (Apple M4 Max, release build, loopback, CPU
backend) with a pinned ~22.7M-parameter BERT embedding classifier. Full
methodology, manifest and raw results: [`docs/performance.md`](docs/performance.md).

| path | p50 | p99 | throughput |
|---|---:|---:|---:|
| cache hit (gRPC, any input length) | **0.09 ms** | 0.21 ms | ~33,000 req/s @ conc 4 |
| miss, 32-token input | 11.8 ms | 14.4 ms | 83 req/s |
| miss, 64-token input | 15.1 ms | 17.8 ms | 66 req/s |
| miss, 128-token input | 22.8 ms | 27.5 ms | 43 req/s |

A hit is roughly four orders of magnitude cheaper than a miss, so hit rate
dominates mean latency (≈1.6 ms at a 90% hit rate on 64-token inputs).

These are **not** cluster numbers and **not** an SLO. Absolute latency targets
should be set per named hardware profile after cluster characterisation.

## Project status

Pre-1.0, phased. See [`docs/VERSIONS.md`](docs/VERSIONS.md).

| phase | focus | state |
|---|---|---|
| 0.1 | service shape: gRPC contract, runtime abstraction, Candle backend, artifact delivery, cache, bounded admission, gateway integration | local evidence complete; cluster evidence pending |
| 0.20 | runtime hardening: deadlines, cancellation, load shedding, graceful drain | not started |
| 0.21 | performance characterisation and named hardware profiles | not started |
| 0.22 | cache/session optimisation and abstention on context loss | not started |
| 0.23 | multi-signal runtime | not started |
| 0.30 | production-like Kubernetes/OpenShift validation | not started |

**Known gaps, stated plainly:**

- The classifier **taxonomy is unverified** for the bundled fixture. The runtime
  proves embedding and ranking mechanics; semantic label meaning awaits a
  packaged, verified classifier definition.
- Cluster validation (topology RTT, disconnected artifact start, non-root UID,
  restart behaviour) is **pending**.
- Per-stage latency is currently accumulated, not histogrammed.

Run `./hack/spec-check 0.1-mvp` for the machine-checked ledger: every acceptance
criterion, every required test ID, and its execution status. The project treats
"lots of passing unit tests" and "the system is proven" as different claims.

## Community

<!-- <<TODO>>: SIG name, meeting cadence + calendar link, Slack workspace/channel,
     mailing list, good-first-issue label link -->

- Issues and discussions: this repository
- llm-d project: https://github.com/llm-d/llm-d

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: commits require a
[DCO](https://developercertificate.org/) `Signed-off-by` line, changes need
tests with evidence, and existing test assertions are protected — weakening one
requires an explicit argument that the previous contract was wrong.

The development process is specification-first; see
[`docs/research/development-method.md`](docs/research/development-method.md) for
the artefacts you will encounter in `specs/`.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
