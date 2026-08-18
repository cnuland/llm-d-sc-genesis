# Working memory (rewrite aggressively; this is not history)

## STATUS: AC-008 (ADR-0002) IMPLEMENTED — bounded queue IN the request path, verify GREEN

## What was done this turn
Implemented AC-008 per ADR-0002 / the adjudicated escalation: the bounded queue is
now wired INTO the request path so the model forward does NOT run on a Tokio
network worker.

1. **RED (I-035)**: `specs/0.1-mvp/evidence/AC-008/RED-I035.md` records the prior
   RED proof — the proving test could not compile (`with_executor` not found)
   because no bounded handoff existed.
2. **Bounded handoff**: `src/handoff.rs` `InferenceExecutor<R>` — a bounded
   `mpsc` channel + owned semaphore (`bound` permits) between the gRPC handler and
   a DEDICATED executor thread that performs the forward and returns via oneshot.
3. **Wiring**: `src/grpc/classify.rs` gained `with_executor`/`new`,
   `queue_bound()`, `max_admitted()`; the handler calls `executor.try_enqueue` and
   maps `QueueFull` to tonic `resource_exhausted`; queue wait recorded through the
   existing `Metrics` Queue stage (`record_stage(LatencyStage::Queue, ...)`).
4. **GREEN (I-035)**: `tests/queue.rs` saturation test passes — explicit
   resource-exhausted under load, `max_admitted <= bound`, Queue metrics > 0,
   recovery after load stops. Recorded in GREEN-I035.md.
5. **LOCAL-GREEN.md updated** with a SUPERSEDED FACTS section (facts changed: I-035
   is no longer deferred; handoff is part of AC-008).

## Bug fixed during verification
`./hack/verify` caught a REAL bug in `src/handoff.rs`: the admitted-count
increment (`fetch_add(1) + 1`) ran AFTER `try_send`, so the executor thread could
`blocking_recv` the job and `fetch_sub(1)` before the increment landed — wrapping
`current` to `usize::MAX` and panicking "attempt to add with overflow" on a
tokio worker (which also cancelled in-flight requests, failing the benchmark
hit-mode methodology self-check). Fixed by incrementing BEFORE `try_send` and
decrementing on `try_send` rejection. `tests/bench_rtt.rs` (13 tests) now passes.

## Evidence
- `specs/0.1-mvp/evidence/AC-008/GREEN-I035.md` (new)
- `specs/0.1-mvp/evidence/AC-008/RED-I035.md` (prior RED proof, kept)
- `specs/0.1-mvp/evidence/AC-008/LOCAL-GREEN.md` (updated + SUPERSEDED FACTS)

## Gates (all GREEN)
- `./hack/spec-check 0.1-mvp` -> OK; AC-008 LOCAL-GREEN (3/6) — U-030/U-031/I-035
  green; pending P-020/P-021 (perf, cluster-tier) and P-023 (0.21) by design.
- `./hack/test-impact src/handoff.rs src/grpc/classify.rs src/queue.rs tests/queue.rs`
  -> FULL SUITE (unknown surface; verify runs the whole suite).
- `./hack/verify` -> exit 0, no failures.
- `./hack/test-report` -> 41 IDs executed, 41 green, 0 red.

## Files changed this turn
- src/handoff.rs (new: InferenceExecutor; increment-ordering bug fix)
- src/grpc/classify.rs (with_executor wiring)
- src/lib.rs (register `pub mod handoff;`)
- tests/queue.rs (I-035 proving test)
- specs/0.1-mvp/evidence/AC-008/GREEN-I035.md (new)
- specs/0.1-mvp/evidence/AC-008/LOCAL-GREEN.md (updated, SUPERSEDED FACTS)
- .agent/state/current.md (this file)

## Uncommitted pre-existing work NOT part of this slice
The AC-002/AC-003 realserve files (src/bin/server.rs, src/classify.rs,
src/runtime.rs, tests/realserve.rs), proto/classify.proto, and Convergence
Slice 1 files remain uncommitted from earlier turns; disposition still to be
decided by the maintainer. This slice's changes are layered on top.

## Next step
STOP per instruction. No further criterion started this turn. (P-020/P-021/P-023
remain PENDING by design — perf/cluster tier and 0.21.)

## Uncertainty
None blocking. The handoff's dedicated executor thread performs the forward off
Tokio network workers, satisfying AC-008/ADR-0002; 0.20 concerns (deadlines,
cancellation, load shedding, graceful drain, worker-failure isolation) are
deliberately NOT implemented. specs/0.20-runtime-hardening untouched (parked
unreviewed draft).
