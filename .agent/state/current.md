# Working memory (rewrite aggressively; this is not history)

## Active work (AC-014) — GREEN proven, gates pass, awaiting review
Spec: 0.1-mvp
Active criterion: AC-014 "default telemetry contains no raw prompt/session text."
Tests mapped: `specs/0.1-mvp/test-plan.md` -> U-085 (raw prompt absent from
default logs/metrics), I-085 (trace capture has IDs/hashes but no raw prompt).
No OpenShift system test mapped to AC-014.

## This turn (worked directly, no subagents; maintainer directed steps 5-9)
1. Read state, AC-014 RED evidence, `tests/telemetry.rs`, spec, test-plan,
   TEST_MATRIX, AC-012/AC-013 GREEN/LOCAL-GREEN precedents, src/lib.rs,
   src/metrics.rs, src/classify.rs, src/grpc/classify.rs, Cargo.toml.
2. Implemented the smallest change:
   - `src/telemetry.rs` (new): `Telemetry` (Arc<Mutex<Vec<TraceEvent>>>, Clone
     shares state), `RequestEvent`, `TraceEvent`; `record_request` hashes
     context (`ctx_`) and session (`sess_`) with blake3 (no raw text retained);
     `default_output()` emits request_id/context_hash/session_hash lines;
     `trace_capture()`.
   - `src/lib.rs`: `pub mod telemetry;`.
   - `src/grpc/classify.rs`: `ClassifyServiceImpl` holds a shared `Telemetry`;
     handler records a `RequestEvent` BEFORE moving request fields into the
     pipeline input; `ClassifyServer` holds shared `Telemetry` and exposes
     `trace_capture() -> Vec<TraceEvent>`.
   - `tests/grpc.rs`: mechanical call-site fix for the new constructor arity
     (inseparable — reverting breaks the build).
3. Ran `cargo test --locked --test telemetry` -> GREEN (2 passed, exit 0):
   U-085 + I-085.
4. Recorded GREEN evidence: `specs/0.1-mvp/evidence/AC-014/GREEN-U085.md`,
   `GREEN-I085.md`. Wrote whole-criterion `LOCAL-GREEN.md` because every test
   mapped to AC-014 (U-085, I-085) passes locally and no S-tier test exists.
   PROMOTION-GREEN.md not written (reserved for integration/system/perf tiers;
   worker never writes it).
5. Gates:
   - `./hack/test-impact src/telemetry.rs src/grpc/classify.rs src/lib.rs
     tests/telemetry.rs tests/grpc.rs` -> FULL SUITE (unknown surface
     `src/telemetry.rs`); full suite passes via verify.
   - `./hack/spec-check 0.1-mvp` -> OK; AC-014: LOCAL-GREEN.
   - `./hack/verify` -> EXIT 0 (fmt, clippy -D warnings, build, full workspace
     suite all green; 5 Candle tests ignored pending fetch-model).
6. Wrote engineering explanation to `artifacts/review/explanation.md`.
7. Spec-check skill: diff satisfies exactly AC-014; the only out-of-surface hunk
   (tests/grpc.rs call site) is inseparable (constructor arity change); no
   non-goals in the diff.

## Status
AC-014 GREEN proven for the expected reason: the telemetry surface now exists,
U-085/I-085 pass, and all gates pass. Implementation complete; criterion is
LOCAL-GREEN and ready for review.

## Files changed (uncommitted, no commit/push)
- `src/telemetry.rs` (new)
- `src/lib.rs` (added `pub mod telemetry;`)
- `src/grpc/classify.rs` (telemetry wiring + `trace_capture`)
- `tests/grpc.rs` (call-site fix)
- `tests/telemetry.rs` (new, U-085/I-085)
- `specs/0.1-mvp/evidence/AC-014/RED.md`, `GREEN-U085.md`, `GREEN-I085.md`,
  `LOCAL-GREEN.md`
- `artifacts/review/explanation.md`
- `.agent/state/current.md` (this file)

## Worktree
- HEAD SHA `259e707f8e5a2c3a030e84df9d9413295f5184e6` (unchanged; no commits).
- Working tree: `M .agent/state/current.md M src/grpc/classify.rs M src/lib.rs
  M tests/grpc.rs ?? src/telemetry.rs ?? tests/telemetry.rs ??
  specs/0.1-mvp/evidence/AC-014/`.

## Next step
STOP after this criterion. Await maintainer review. Do not start the next
criterion opportunistically.
