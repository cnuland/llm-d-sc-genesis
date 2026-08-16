# Working memory (rewrite aggressively; this is not history)

Spec: 0.1-mvp
Current acceptance criterion: AC-006 cache hit bypasses tokenizer/model forward.
Slice completed this turn: resolved the reviewer's blocking CHANGES verdict on
AC-006 — `CacheKey` is now a versioned fingerprint (design.md); U-042/U-043/U-044
RED-first and GREEN; U-040 stays green; AC-006 GREEN.md updated to cover all four.
STOP after this criterion.

## AC-006 — GREEN (this turn, reviewer CHANGES resolved)

### What landed
- `src/cache.rs`: `CacheKey(String)` (raw prompt as entire key — the reviewer's
  blocking finding, a design.md violation) replaced by a versioned fingerprint
  struct `{ classifier_id, model_revision, tokenizer_revision,
  taxonomy_revision, normalized_text_hash }`, built via
  `CacheKey::new(classifier_id, model_revision, tokenizer_revision,
  taxonomy_revision, normalized_text)`. `normalized_text` hashed via
  `std DefaultHasher`; raw prompt never retained as key identity (also removes
  the privacy smell). Hand-implemented `PartialEq`/`Eq`/`Hash` fold EVERY
  revision + the normalized-text hash into key identity, so identical text under
  a different revision -> different key -> miss (never stale cached result).
- `ExactCache::classify` bypass logic (U-040) unchanged and still green.
- New tests U-042/U-043/U-044 (key changes with model/classifier, tokenizer,
  taxonomy/prototype revision respectively), RED-first then GREEN.
- Recorded `specs/0.1-mvp/evidence/AC-006/RED-U-042.md` / `-U-043.md` /
  `-U-044.md` (RED) and `GREEN-U-042.md` / `-U-043.md` / `-U-044.md` (GREEN);
  updated criterion `GREEN.md` to cover all four.
- Updated `artifacts/review/explanation.md` (What changed / Why / Alternatives /
  Tests / Regressions / Rollback).

### RED proof (U-042/U-043/U-044)
RED state: struct carried all five fields but `PartialEq`/`Hash` considered ONLY
the normalized-text hash (the design violation). Each test asserted a revision
change must produce a different key -> `assert_ne!` FAILED (keys equal, same text
hash). Each failure excerpt recorded. U-040 stayed green at RED state.

### GREEN proof
```
cargo test --locked u040 -> 1 passed
cargo test --locked u042 -> 1 passed
cargo test --locked u043 -> 1 passed
cargo test --locked u044 -> 1 passed
```
U-040: forward runs exactly ONCE (miss only; hit bypasses), hit_count==1, exact
cached result returned. U-042/U-043/U-044: revision change -> different key ->
second classify is a MISS (forward_count reaches 2), never a stale cached result.

## Suites / worktree
- `./hack/test-impact src/cache.rs` -> `src/*` unknown surface -> FULL SUITE
  required.
- `./hack/spec-check 0.1-mvp` -> OK.
- `./hack/verify` -> GREEN: fmt, clippy `-D warnings`, build, full test
  (17 passed, 4 ignored — ignored require fetch-model runtime, unrelated).
- Worktree: SHA `df21d9a` (uncommitted). git status:
  `M src/lib.rs`, `?? src/cache.rs`, `?? specs/0.1-mvp/evidence/AC-006/`.
  No commits/pushes.

## Evidence
- `specs/0.1-mvp/evidence/AC-006/RED.md` (U-040 RED, prior turn).
- `specs/0.1-mvp/evidence/AC-006/RED-U-042.md` / `-U-043.md` / `-U-044.md` (this turn).
- `specs/0.1-mvp/evidence/AC-006/GREEN-U-040.md` (prior turn, still valid).
- `specs/0.1-mvp/evidence/AC-006/GREEN-U-042.md` / `-U-043.md` / `-U-044.md` (this turn).
- `specs/0.1-mvp/evidence/AC-006/GREEN.md` (updated this turn to cover all four).
- `artifacts/review/explanation.md` (updated this turn).

## Open items / flags for reviewer
- AC-006's other tests I-030 (warmed result cache hit invokes zero model
  forwards) and P-001/P-002 (perf cache hit) are integration/perf-environment
  tests and remain open for those environments.
- Per instruction: STOP after this criterion.
