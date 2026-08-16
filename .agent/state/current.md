# Working memory (rewrite aggressively; this is not history)

Spec: 0.1-mvp
Current acceptance criterion: AC-005 model/tokenizer load once per active
  revision.
Slice completed this turn: U-021 GREEN implemented and proven. Suites run.
  Evidence recorded. STOP after this criterion.

## U-021 — GREEN (this turn)

### What landed
- `src/runtime.rs`: implemented load-once-per-active-revision caching in
  `load_tokenizer_once`. `Runtime` now holds `resident_tokenizer:
  Option<Tokenizer>` and `active_revision: Option<String>`. When the requested
  revision matches the stored active revision, the resident tokenizer is reused
  (no reload, no count increment); only when the active revision changes does it
  reload the tokenizer and increment `tokenizer_load_count` by one.
- Replaced the RED stub (which reloaded on every call).

### GREEN proof
`cargo test --locked u021` -> `u021_model_tokenizer_load_once_per_active_revision`
PASSED: `left == right` now holds; load count == 1 for ten same-revision calls.

## Suites / worktree
- `./hack/test-impact src/runtime.rs` -> `src/*` unknown surface -> FULL SUITE
  required.
- `./hack/spec-check 0.1-mvp` -> OK.
- `./hack/verify` -> GREEN (fmt, clippy `-D warnings`, build, full test: 13
  passed, 4 ignored — ignored tests need fetch-model runtime, unrelated).
- Worktree: SHA `13cac01` (uncommitted). git status: `M src/runtime.rs`,
  `?? specs/0.1-mvp/evidence/AC-005/` (RED.md, GREEN-U-021.md, GREEN.md). No
  commits/pushes.

## Evidence
- `specs/0.1-mvp/evidence/AC-005/GREEN-U-021.md` (slice evidence: test ID,
  command, result, worktree state).
- `specs/0.1-mvp/evidence/AC-005/GREEN.md` (whole-criterion — written because the
  sole unit-level test U-021 mapped to AC-005 passes).
- `artifacts/review/explanation.md` (engineering explanation).

## Open items / flags for reviewer
- AC-005's other test I-012 (repeated calls do not reload model/tokenizer in the
  integration environment) is out of scope for this local unit turn and remains
  open for the integration environment. Noted in GREEN.md.
- The resident holder currently holds the tokenizer only; AC-005 says
  "model/tokenizer". Model residency is not exercised by U-021 and remains for
  the integration environment.
- Next criterion: STOP after AC-005 per instruction; no further slices this
  turn.
