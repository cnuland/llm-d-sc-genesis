# Working memory (rewrite aggressively; this is not history)

## Active work (AC-011 — OpenShift sidecar/ClusterIP RTT distributions captured — GREEN)

Spec: 0.1-mvp
Active criterion: AC-011 "OpenShift sidecar/ClusterIP RTT distributions captured."
Tests mapped: `specs/0.1-mvp/test-plan.md` -> P-030..P-033, S-001/S-002.
Status: LOCAL-GREEN this turn (TDD RED->GREEN executed directly, no subagents).

## This turn (worked directly, no subagents)

Selected the local deterministic mechanics proving tests for AC-011: P-030
(sidecar cache-hit RTT distribution), P-031 (sidecar cache-miss), P-032
(ClusterIP cache-hit), P-033 (ClusterIP cache-miss) — all in `tests/bench_rtt.rs`.
S-001/S-002 (OpenShift cluster E2E) deferred to the deployment phase (same
pattern as AC-009).

1. RED was proven last turn: the crate had no RTT distribution capture — only a
   single scalar `DummyOutcome.rtt`; `llm_d_sc::bench` was undefined, so
   `cargo test --locked --test bench_rtt` failed E0432/E0433 at exit 101.
   Recorded in `specs/0.1-mvp/evidence/AC-011/RED.md`.
2. Implemented the smallest change: added the RTT-distribution benchmark harness.
3. GREEN: `cargo test --locked --test bench_rtt` -> all 4 pass (P-030..P-033).
   Recorded `specs/0.1-mvp/evidence/AC-011/GREEN.md`.
4. `./hack/test-impact src/bench.rs src/lib.rs tests/bench_rtt.rs` -> UNKNOWN
   SURFACE -> ran `./hack/test-all`: all suites green (23+4+5+2 passed, 5 ignored
   Candle tests requiring `./hack/fetch-model`).
5. `./hack/spec-check 0.1-mvp` -> OK; AC-011 now LOCAL-GREEN (was open).
6. `./hack/verify` -> exit 0 (all suites + fmt-check pass).

## Implementation (smallest change, no unrelated refactors)

- `src/bench.rs` (new): `BenchmarkRun` / `Topology` (Sidecar/ClusterIp) /
  `CacheMode` (Hit/Miss) / `RttDistribution` (p50/p90/p95/p99/max via
  nearest-rank percentile over sorted per-request RTT samples). Drives the dummy
  Praxis over the persistent gRPC channel (I-008), never a route (AC-010).
  `CacheMode::Hit` reuses one fixed context (exact-result cache hit);
  `CacheMode::Miss` sends a unique context per request (cache miss).
  `BenchmarkRun` methods take `&self` (praxis behind a `Mutex`) so the recorded
  immutable `let run` test signature compiles unchanged.
- `src/lib.rs`: added `pub mod bench;`.

## Why the tests are non-vacuous
Each scenario asserts a real percentile distribution (p50 <= p90 <= p95 <= p99
<= max, strictly positive p50). A mean-only harness cannot satisfy the tests
(AGENTS.md hard rule: no average-only latency claims).

## Files changed (uncommitted, no commit/push)
- `tests/bench_rtt.rs` (new, untracked): P-030..P-033 proving tests
- `src/bench.rs` (new, untracked)
- `src/lib.rs` (modified): `pub mod bench;`
- `specs/0.1-mvp/evidence/AC-011/RED.md`, `GREEN.md` (new)
- `.agent/state/current.md`

## Worktree
- HEAD SHA `d3b467cb952818c455f20ba372b2257b868bd08a`, no commits/pushes (worker
  never commits). `git status`: `M .agent/state/current.md`, `M src/lib.rs`,
  `?? specs/0.1-mvp/evidence/AC-011/`, `?? src/bench.rs`, `?? tests/bench_rtt.rs`.

## Next step
Stop per AGENTS.md step 10. AC-011 LOCAL-GREEN complete for the deterministic
slice (P-030..P-033). Remaining for AC-011: S-001/S-002 (OpenShift cluster E2E,
deployment phase). When directed, proceed to the next open criterion.

## Open question for maintainer
The `bench` harness API referenced by the proving tests (BenchmarkRun/Topology/
CacheMode/RttDistribution) is my proposed surface. If the maintainer prefers a
different harness shape for AC-011, escalate before extending it to S-001/S-002.
