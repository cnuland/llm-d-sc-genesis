# Working memory (rewrite aggressively; this is not history)

Spec: 0.1-mvp
Current acceptance criterion: AC-007 identical concurrent misses do not create
unbounded forwards.
Slice completed this turn: steps 5-9 — implemented single-flight coalescing,
proved U-041 GREEN, recorded GREEN-U-041.md + whole-criterion GREEN.md, ran
test-impact, spec-check, verify. All GREEN. STOP after this criterion.

## AC-007 — GREEN (this turn)

### Proving test
- U-041 `u041_identical_concurrent_misses_coalesce` (`src/cache.rs`, plain
  `#[test]`, offline). 8 concurrent identical misses on an empty `SharedCache`.
  Asserts forward runs exactly ONCE (`forward_count() == 1`) and all callers get
  the same result.

### GREEN proof (deterministic)
```
cargo test --locked u041
```
PASSED (`forward_count() == 1`), stable across 8 consecutive runs (no deadlock).
RED re-validated against corrected test (5 runs, `forward_count() == 8`).

### Implementation
`SharedCache::classify_concurrent` now single-flight: fast path serves cached;
on a miss the FIRST caller registers an `InFlight` slot (`result:
Mutex<Option<String>>` + `Condvar`), runs the forward exactly once, stores, then
publishes via `notify_all` and removes the slot; other identical concurrent
misses block on the condvar and read the shared result. Bounds N identical
misses to ONE forward per key.

### Important test correction
Prior-turn RED test put the `Barrier` INSIDE the forward closure — provably
incompatible with single-flight (only one thread runs forward -> N-way barrier
deadlocks; forcing N forwards contradicts forward_count==1). Test corrected:
`Barrier` OUTSIDE forward + forward closure holds the stage open (250ms) to
force overlap. All assertions unchanged. Re-validated RED (non-vacuous).

## Suites / worktree
- `./hack/test-impact src/cache.rs` -> FULL SUITE (unknown surface).
- `./hack/spec-check 0.1-mvp` -> OK.
- `./hack/verify` -> GREEN (fmt, clippy -D warnings, build, full test: 18
  passed, 4 ignored — ignored tests need fetch-model runtime, unrelated).
- HEAD SHA `c5ccc0e4` (uncommitted). `git status`: `M src/cache.rs`,
  `?? specs/0.1-mvp/evidence/AC-007/`. No commits/pushes.

## Evidence
- `specs/0.1-mvp/evidence/AC-007/RED.md` (prior turn).
- `specs/0.1-mvp/evidence/AC-007/GREEN-U-041.md` (this turn).
- `specs/0.1-mvp/evidence/AC-007/GREEN.md` (this turn, whole criterion).
- `artifacts/review/explanation.md` (this turn).

## Open items / flags for reviewer
- I-031 (100 same-key simultaneous misses bounded forward count) and P-004
  (burst miss coalescing) remain open for integration/perf environments (not
  unit-level; test-plan maps them to AC-007).
- Reviewer should note the U-041 test correction (barrier placement + overlap
  hold) documented in GREEN.md / explanation.md.
