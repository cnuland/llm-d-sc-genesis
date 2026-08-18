# Working memory (rewrite aggressively; this is not history)

## STATUS: SERVICE-CORE (P0) IMPLEMENTED — shared cache/metrics core for BOTH synthetic + Candle backends

## What was done this turn
Introduced a generic `ServiceCore<R>` `{ runtime, cache: SharedCache, metrics }`
that OWNS the exact-result cache, single-flight coalescing, and cache
hit/miss/total/queue metrics, and wrapped EVERY backend (synthetic
`ClassifyService` AND production `CandleClassifier`) in it. Backends are now raw
forwards (tokenize + rank) with NO cache logic of their own.

1. **`ServiceCore<R>`** (`src/classify.rs`): `with_metrics`, `metrics()`,
   `forward_count()` (delegates to `cache.forward_count()`), `ClassifierRuntime`
   impl doing cache-first `classify_concurrent` with `CacheKey::new(...)`.
   Queue/Total stages recorded via `Arc<AtomicBool>` flag (cache hit skips
   tokenize/forward stage recording).
2. **`CandleClassifier` raw** (`src/classify.rs`): removed `cache` field; added
   `tokenizer_calls`/`forward_calls` `Arc<AtomicU64>` + `tokenizer_call_counter()`
   / `forward_call_counter()`; `real_forward(&str)` uses `self.metrics`; `classify`
   is a raw forward. Constructors `new`/`with_metrics`.
3. **`ClassifyService` raw** (`src/classify.rs`): removed `cache` field;
   `deterministic_classify` uses `self.metrics`; `classify` is raw deterministic
   forward.
4. **Wiring** (`src/grpc/classify.rs`): `with_executor` wraps backend in
   `ServiceCore::with_metrics(service, metrics.clone())`; executor field type
   `Arc<InferenceExecutor<ServiceCore<R>>>`. Server bind functions already share
   ONE `Metrics` handle across backend + core + executor.
5. **Tests updated**: `u071` now routes through `ServiceCore` (proves the cache
   pipeline lives in the core); parity test
   `service_core_production_candle_cache_hit_zero_tokenizer_zero_forward`
   (GREEN) proves a Candle cache hit = ZERO tokenizer calls + ZERO forwards.

## Evidence
- `specs/0.1-mvp/evidence/AC-006/SERVICE-CORE.md` (new, deliverable)
- `specs/0.1-mvp/evidence/AC-006/GREEN-SERVICE-CORE.md` (new)
- `specs/0.1-mvp/evidence/AC-006/RED-SERVICE-CORE.md` (prior RED, kept)

## Gates (all GREEN)
- Focused parity test: `cargo test --locked --lib -- --ignored
  service_core_production_candle_cache_hit_zero_tokenizer_zero_forward` -> 1 passed.
- `cargo test --locked --lib` -> 34 passed, 0 failed (u070/u071, cache u040..u044,
  metrics u080/u081).
- `cargo test --locked --test bench_rtt --test metrics --test grpc` -> 22 passed.
- `./hack/test-impact src/classify.rs src/grpc/classify.rs` -> FULL SUITE
  (unknown surface; verify runs whole suite).
- `./hack/spec-check 0.1-mvp` -> OK; AC-006/AC-007 LOCAL-GREEN (I-030/I-031/P-001/
  P-002/P-004 pending cluster measurement by design).
- `./hack/verify` -> exit 0, GREEN **without weights** (fmt + clippy + build + full suite).
- `./hack/test-parity` -> exit 0, GREEN **with weights** (all ignored model-dependent
  tests pass incl. realserve, bench_runner, u072, parity).

## Files changed this turn
- src/classify.rs (ServiceCore, raw CandleClassifier + ClassifyService, counters, u071 + parity test)
- src/grpc/classify.rs (with_executor wraps backend in ServiceCore; executor field type)
- specs/0.1-mvp/evidence/AC-006/SERVICE-CORE.md (new)
- specs/0.1-mvp/evidence/AC-006/GREEN-SERVICE-CORE.md (new)
- specs/0.1-mvp/evidence/AC-006/RED-SERVICE-CORE.md (prior RED, kept)
- .agent/state/current.md (this file)

## Uncommitted pre-existing work NOT part of this slice
The AC-002/AC-003 realserve files (src/bin/server.rs, src/runtime.rs,
tests/realserve.rs), proto/classify.proto, and Convergence Slice 1 files remain
uncommitted from earlier turns; disposition still to be decided by the maintainer.
This slice's changes are layered on top.

## Next step
STOP per instruction. No further criterion started this turn. (SERVICE-CORE P0
complete; P-030..P-033 / S-001/S-002 remain PENDING cluster measurement by design.)

## Uncertainty
None blocking. `forward_count()` on the core delegates to the cache's
single-flight forward count (cache owns forward accounting), NOT the runtime's
forward counter — this is intentional and documented in SERVICE-CORE.md.
