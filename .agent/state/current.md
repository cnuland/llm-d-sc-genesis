# Working memory (rewrite aggressively; this is not history)

## Active work (CORRECTIVE SLICE 3 — tokenizer crate swap — COMPLETE this turn)

Spec: 0.1-mvp
Slice: replace hand-rolled tokenizer with official HF `tokenizers` crate.

### Done
1. `tokenizers = "0.23.1"` confirmed present in Cargo.toml/Cargo.lock; compiles standalone.
2. `src/tokenizer.rs` rewritten to a thin resident wrapper `struct Tokenizer { inner:
   tokenizers::Tokenizer }`: `load` -> `Tokenizer::from_file`, `tokenize` ->
   `encode(text, true).get_ids()`. Truncation via the crate (fixture JSON carries
   truncation.max_length=256; from_file applies it). Production body ~45 lines (was ~324);
   ALL hand-rolled components deleted (BertNormalizer/BertPreTokenizer/WordPiece/
   TemplateProcessing/unicode tables/accent strip/CJK spacing).
3. Public signatures preserved: `Tokenizer::load`, `tokenize`, `TokenizerError` (Display+Error)
   so embedding.rs/runtime.rs compile unchanged.
4. Evidence: `specs/0.1-mvp/evidence/AC-004/SWAP-tokenizers-crate.md`.

### Gates (all GREEN)
- `cargo test -- u060 u066` -> GREEN (2 passed; token-ID + truncation parity).
- `./hack/test-parity` -> GREEN (5 passed: u060/u061/u062/u063/u066/u067 etc.).
- `./hack/test-impact src/tokenizer.rs --run` -> GREEN (22 unit + 2 grpc, 5 ignored).
- `./hack/spec-check 0.1-mvp` -> OK (14 ACs mapped; 48 test IDs).
- `./hack/verify` -> GREEN exit 0 (fmt, clippy -D warnings, build, full test).

### Gates (all GREEN)
- `./hack/verify` -> GREEN (fmt, clippy -D warnings, build, full test: 22 unit + 2 grpc,
  5 ignored).
- `./hack/test-impact <changed files> --run` -> GREEN (full suite).
- `./hack/spec-check 0.1-mvp` -> OK (14 ACs mapped; 48 test IDs).
- `./hack/test-parity` -> GREEN (model present; 5 ignored model-dependent tests incl.
  `u072_candle_classifier_implements_classifier_runtime`).

### Spec-check (skill) answers
- Primary AC satisfied: AC-004 (tokenizer parity), now via the official crate.
- Out-of-surface files: src/tokenizer.rs + evidence file only (this corrective slice).
- Non-goals: none (no routing/stickiness/unbounded queues; no new dependencies added —
  tokenizers was already pinned).

## Not done this turn
- No commits/pushes (per contract).
- STOPPED after the required gates per instruction.

## Worktree
- HEAD SHA `99e529f5261a94d845246f16edee808c5c07af35` (uncommitted).
- This turn modified: `src/tokenizer.rs` (rewritten to crate wrapper),
  `specs/.../AC-004/SWAP-tokenizers-crate.md` (new), `.agent/state/current.md`.
- Prior turn's changes still uncommitted: `M Cargo.lock Cargo.toml src/cache.rs src/lib.rs`;
  `?? build.rs proto/ src/classify.rs src/grpc/ tests/grpc.rs specs/.../AC-006/HARDENING-blake3.md
  specs/.../AC-009/`. No commits/pushes.
