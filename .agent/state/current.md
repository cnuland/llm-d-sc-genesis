# Working memory (rewrite aggressively; this is not history)

Spec: 0.1-mvp
Current acceptance criterion: AC-004 pinned sensitivity model matches trusted
  reference embedding/ranking fixtures. In-progress: U-060 and U-066 GREEN this
  turn; AC-004 is NOT complete until U-061..U-067 and I-020..I-025 all pass.
  STOP per AGENTS.md step 10; do not start AC-005 or the next AC-004 test.
Last green state: HEAD `ce7768670e066930ee08fec335e682bbe8cc68d5` (committed
  baseline; all changes this turn are uncommitted).
Review disposition: verdict.json CHANGES with one blocking finding — AC-004
  GREEN.md claimed the whole criterion after only U-060. Fixed by (1) renaming
  GREEN.md -> GREEN-U060.md (header clarifies AC-004 stays open) and
  (2) implementing U-066 "max-length truncation deterministic" test-first.

Working tree (uncommitted):
- `src/tokenizer.rs` (new): resident BERT wordpiece `Tokenizer` replicating the
  pinned `tokenizers` library pipeline (BertNormalizer + BertPreTokenizer +
  WordPiece + TemplateProcessing) from a committed `tokenizer.json`; U-060 and
  U-066 proving tests. U-066 adds `max_length: Option<usize>` from
  `truncation.max_length` and right-truncates content to `max_length - 2` before
  wrapping with `[CLS]`/`[SEP]`.
- `Cargo.toml`/`Cargo.lock`: added `serde_json`, `unicode-normalization`,
  `unicode_categories`.
- `tests/fixtures/modelcar/tokenizer.json` (new, ~711 KB real ModelCar artifact,
  truncation.max_length=256) and `tests/fixtures/modelcar/golden-token-ids.json`
  (new, golden token IDs `[101, 2023, 2003, 1037, 3585, 14639, 7953, 102]`
  generated with pinned Python reference).
- `src/lib.rs` registers `tokenizer` module (already staged pre-turn).
- Evidence: specs/0.1-mvp/evidence/AC-004/{RED.md, GREEN-U060.md, RED-U066.md,
  GREEN-U066.md}; explanation updated at artifacts/review/explanation.md.

Current failing test: none — U-066 passes; full suite 10 passed; build clean;
  `hack/spec-check 0.1-mvp` OK; `hack/verify` exit 0. U-066 verified against the
  pinned reference: Rust IDs exactly equal tokenizers 0.22.1 output for an
  over-length input (throwaway check, deleted after passing).
Next step: STOP (GREEN-only turn per AGENTS.md step 10). Later AC-004 tests to
  exercise in later phases: U-061..U-067 (U-067 next), I-020..I-025.

Open uncertainty / flags for reviewer:
- U-060 load path deviates from the RED-recorded `/models/tokenizer.json` to the
  committed fixture path for hermetic CI (assertion unchanged). Documented in
  GREEN-U060.md and explanation.md.
- U-066 content budget is hardcoded as `max_length - 2` (the two special tokens
  `[CLS]`/`[SEP]` the single-sequence TemplateProcessing adds). Empirically
  matches the pinned reference (256 total, 254 content). Re-check if a pair
  (two-sequence) template is ever added to the resident tokenizer.
- `hack/test-impact` maps any `src/*` change to "UNKNOWN SURFACE" -> FULL SUITE;
  map may need updating as surfaces (src/grpc, src/cache, src/infer,
  src/tokenizer) land later.
- Committing a ~711 KB tokenizer.json fixture: confirm acceptable.
- Unicode-category/accent-strip parity relies on `unicode_categories` +
  `unicode-normalization`; U-014 (Unicode) is the real stressor later.

## Evidence
- specs/0.1-mvp/evidence/AC-001/RED.md   (cargo build exit 101, no crate)
- specs/0.1-mvp/evidence/AC-001/GREEN.md (cargo test --locked config:: 5 passed; cargo build --locked clean)
- specs/0.1-mvp/evidence/AC-002/RED.md   (U-020: cargo test --locked u020 exit 101, unresolved import Runtime)
- specs/0.1-mvp/evidence/AC-002/RED-U022.md (U-022: cargo test --locked u022 panic, warmup ignored path)
- specs/0.1-mvp/evidence/AC-002/GREEN.md (U-020 + U-022; full suite 7 passed; build clean; verify exit 0)
- specs/0.1-mvp/evidence/AC-003/RED.md   (I-064: cargo test --locked i064, warmup Ok(()) for incomplete ModelCar, readiness flipped)
- specs/0.1-mvp/evidence/AC-003/GREEN.md (I-064: cargo test --locked i064 ok; full suite 8 passed; build clean; verify exit 0)
- specs/0.1-mvp/evidence/AC-004/RED.md   (U-060: cargo test --locked u060 exit 101, E0432 unresolved import Tokenizer)
- specs/0.1-mvp/evidence/AC-004/GREEN-U060.md (U-060: cargo test --locked u060 ok; full suite 9 passed; build clean; verify exit 0; AC-004 NOT complete)
- specs/0.1-mvp/evidence/AC-004/RED-U066.md   (U-066: cargo test --locked u066, 405 IDs vs fixture cap 256, truncation absent)
- specs/0.1-mvp/evidence/AC-004/GREEN-U066.md (U-066: cargo test --locked u066 ok; full suite 10 passed; build clean; verify exit 0)

## Issue candidates (unrelated defects noticed in passing)
(none)
