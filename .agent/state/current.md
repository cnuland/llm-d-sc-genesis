# Working memory (rewrite aggressively; this is not history)

## Active work (AC-012 — queue/tokenize/forward/total latency visible — LOCAL-GREEN)

Spec: 0.1-mvp
Active criterion: AC-012 "queue/tokenize/forward/total latency visible."
Tests mapped: `specs/0.1-mvp/test-plan.md` -> U-080/U-081, I-080, S-080.
Status: LOCAL-GREEN this turn. U-080/U-081 proven locally; I-080 passes locally
(integration tier not discharged by this unit LOCAL-GREEN); S-080 deferred to
deployment phase (OpenShift cluster E2E, same pattern as AC-009/AC-011).

## This turn (worked directly, no subagents)

Continued AC-012 after the watchdog false-positive fix (watchdog commits landed:
HEAD now `e27ccd39a938670d9e9c5858151dd3e5b964b573`, on top of RED base
`06f34218`). RED evidence in `specs/0.1-mvp/evidence/AC-012/RED.md` still valid
(failure was the missing metrics module, unrelated to the watchdog).

1. Read `tests/metrics.rs` and `.agent/state/current.md` to recover prior turns.
2. Implemented the smallest change:
   - `src/metrics.rs` (new): `LatencyStage`, `Metrics`, `MetricsSnapshot`.
   - `src/classify.rs`: instrumented `ClassifyService` (Queue/Tokenize/Forward/
     Total stages + cache hit/miss counters); added `with_metrics` and
     `from_synthetic_fixtures_with_metrics`.
   - `src/grpc/classify.rs`: `ClassifyServer` holds shared `Metrics`,
     `metrics_snapshot()` surface.
   - `src/lib.rs`: `pub mod metrics;`.
   - Removed `let mut metrics` -> `let metrics` in `tests/metrics.rs` (interior
     mutability; `unused_mut` fails clippy `-D warnings`). No assertion removed.
3. Ran `cargo test --locked --test metrics` -> GREEN (3 passed: U-080/U-081/I-080).
4. Recorded `GREEN-U080.md`, `GREEN-U081.md`, `LOCAL-GREEN.md`.
5. `./hack/test-impact` -> FULL SUITE (unknown surface `src/metrics.rs`);
   full workspace suite passes.
6. `./hack/spec-check 0.1-mvp` -> OK (AC-012 now LOCAL-GREEN).
7. `./hack/verify` -> exit 0 (fmt, clippy `-D warnings`, build, full tests).

## Files changed (uncommitted, no commit/push)
- `src/metrics.rs` (new)
- `src/classify.rs`, `src/grpc/classify.rs`, `src/lib.rs` (modified)
- `tests/metrics.rs` (untracked; `mut` removed on Metrics bindings)
- `specs/0.1-mvp/evidence/AC-012/` (RED.md, GREEN-U080.md, GREEN-U081.md, LOCAL-GREEN.md)

## Worktree
- HEAD SHA `e27ccd39a938670d9e9c5858151dd3e5b964b573`, no commits/pushes.

## Next step
Stop. AC-012 local mechanics GREEN; `./hack/verify` green (the gate). I-080
(integration) and S-080 (OpenShift cluster E2E) remain for their tiers. Do NOT
start AC-013.

## Open question for maintainer
The `metrics` module API referenced by the proving tests (`LatencyStage`, `Metrics`,
`MetricsSnapshot`, `ClassifyServer::metrics_snapshot`) was implemented as
proposed. No spec drift/ambiguity encountered this turn; no escalation needed.
