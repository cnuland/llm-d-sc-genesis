# Working memory (rewrite aggressively; this is not history)

## Active work (AC-009 — dummy Praxis semantics — GREEN this turn)

Spec: 0.1-mvp
Active criterion: AC-009 "dummy Praxis consumes response over persistent gRPC."
Slice this turn: I-005/I-006 (dummy-Praxis semantics), steps 5-9 of AGENTS.md.
Implemented, GREEN, LOCAL-GREEN written. STOPPING after this criterion.

### Prior AC-009 slices (committed)
- I-001 `i001_real_tonic_round_trip` + I-002 `i002_persistent_http2_channel_reused`
  (gRPC layer: `src/grpc/classify.rs`, tonic blocking client/server). I-002 asserts
  I-008 (multi-turn requests do not reconnect per call) via
  `channel_reconnect_count()==0`.

### This slice (GREEN)
- Added `src/dummy_praxis.rs` (smallest change):
  - `DummyRequest { request_id, session_id, context, signals, deadline }`.
  - `DummyPraxis::connect` reuses the persistent `ClassifyClient`.
  - `DummyPraxis::classify_and_route` propagates session metadata verbatim,
    consumes the top ranked signal, applies fixed test-only mapping
    (`NEVER_EGRESS_SIGNAL "proto-a" -> "local-model"`, otherwise ->
    `"general-model"`), records route + classifier RTT in `DummyOutcome`.
  - Routing authority stays outside llm-d-sc (AC-010).
- Wired `pub mod dummy_praxis;` in `src/lib.rs`.

### GREEN evidence (recorded)
- Command: `cargo test --locked --test grpc i005`, `... i006` -> both PASS.
- Full `cargo test --locked --test grpc`: 4 passed; 0 failed (I-001/I-002/I-005/I-006).
- `./hack/test-all`: 22 passed; 0 failed; 5 ignored (Candle, run with `--ignored`
  after fetch-model); grpc 4/4.
- `./hack/test-impact` on changed files: reports UNKNOWN SURFACE -> FULL SUITE;
  full suite run GREEN.
- `./hack/spec-check 0.1-mvp`: OK; AC-009 now LOCAL-GREEN.
- `./hack/verify`: GREEN (fmt, clippy -D warnings, build, workspace tests).
- Evidence file: `specs/0.1-mvp/evidence/AC-009/GREEN-I005-I006.md`;
  whole-criterion `LOCAL-GREEN.md` written (S-001/S-002 OpenShift system tier
  deferred; PROMOTION-GREEN is never worker-written).
- HEAD SHA `83063564edd0eddade63d7de7b399c7015fe8ee8`, working tree uncommitted.

### Next step
STOP after this criterion per instructions. Later AC-009 phases: S-001/S-002
(OpenShift system tier) — not run by the worker; required for PROMOTION-GREEN only.

## Not done this turn
- No commits/pushes (per contract).
- No subagents spawned (worked directly).
- S-001/S-002 (OpenShift system) remain for later AC-009 phases.

## Worktree
- HEAD SHA `83063564edd0eddade63d7de7b399c7015fe8ee8`.
- Changed this turn: `src/dummy_praxis.rs` (new), `src/lib.rs`,
  `tests/grpc.rs` (fmt), `specs/.../AC-009/GREEN-I005-I006.md` (new),
  `specs/.../AC-009/LOCAL-GREEN.md` (new), `specs/.../AC-009/RED.md`,
  `artifacts/review/explanation.md` (new), `.agent/state/current.md`.
- No commits/pushes.
