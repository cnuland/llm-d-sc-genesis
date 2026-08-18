# Working memory (rewrite aggressively; this is not history)

## STATUS: CONVERGENCE SLICE 4 COMPLETE — benchmark methodology bug fixed, verify GREEN

## What was done this turn (Convergence Slice 4 of 4)
Fixed the AC-011 benchmark methodology bug found by external review: warmup sent
keys 0..n and measure sent the SAME 0..n, so in CacheMode::Miss every measured
request was actually a cache HIT.

1. **Key-space separation**: measured keys live in a per-run namespace
   `measure-{run_id}-{i}` (`run_id` unique per `BenchmarkRun`); miss-mode warmup
   uses the disjoint `warm-{i}` namespace so measured miss keys are never
   pre-warmed; hit-mode warmup deliberately pre-warms exactly the measured keys.
2. **Harness proves its own methodology**: `BenchmarkRun::with_metrics` shares
   the server's `Metrics`; `measure`/`measure_concurrent` snapshot
   cache_hits/cache_misses deltas around the measured window and assert
   miss-mode `delta_misses == measured` (+ hits==0) and hit-mode
   `delta_hits == measured` (+ misses==0). Violations return
   `BenchError::Methodology`.
3. **Concurrency**: `measure_concurrent(n, concurrency)` uses per-worker
   `DummyPraxis` clients over the persistent channel (P-020 concurrency 1 /
   P-021 concurrency 4), recording the same distributions + self-check.
4. **Tests**: 6 unit tests in src/bench.rs (keyspace separation, methodology
   rejection, monotone percentiles) + 13 integration tests in tests/bench_rtt.rs
   (serial hit/miss sidecar/clusterip, direct counter invariants, concurrency
   1 & 4, wired-in self-check). Plain tests, no cluster.
5. **End-to-end proof** the old bug is caught: artifacts/old_bug_proof.rs
   (gitignored) reuses measured keys across windows in miss mode; the harness's
   own self-check REJECTS it.

## Evidence
- `specs/0.1-mvp/evidence/AC-011/BENCH-methodology-fix.md` (new)

## Gates (all GREEN)
- `./hack/spec-check 0.1-mvp` -> OK (AC-011 pending only P-030..P-033,S-001/S-002,
  which are cluster-tier and remain PENDING)
- `./hack/test-impact src/bench.rs src/grpc/classify.rs tests/bench_rtt.rs` ->
  FULL SUITE (src/* unknown surface; verify runs the whole suite)
- `./hack/verify` -> exit 0, no failures

## Files changed this turn
- src/bench.rs (methodology fix, key namespaces, concurrency)
- src/grpc/classify.rs (added ClassifyServer::bind_with_metrics)
- tests/bench_rtt.rs (updated + new methodology/concurrency tests)
- specs/0.1-mvp/evidence/AC-011/BENCH-methodology-fix.md (new)
- .agent/state/current.md (this file)

## Uncommitted pre-existing work NOT part of this slice
The AC-002/AC-003 realserve files (src/bin/server.rs, src/classify.rs,
src/runtime.rs, tests/realserve.rs), proto/classify.proto, and Convergence
Slice 1 files remain uncommitted in the worktree from earlier turns; disposition
still to be decided by the maintainer. This slice's changes to
src/grpc/classify.rs and tests/bench_rtt.rs are layered on top of that
uncommitted work.

## Next step
STOP per instruction. No further criterion started this turn. (Cluster
measurement P-030..P-033/S-001/S-002 remains PENDING by design — this slice
only fixed the benchmark methodology so those measurements would be valid.)

## Uncertainty
None blocking. The harness's methodology self-check requires a shared
`Metrics` handle (server bound via `bind_with_metrics`); on the cluster the
harness must obtain the service's counters the same way (metrics surface) for
the self-check to run. This is a documented consideration for the cluster
deployment phase.
