# Working memory (rewrite aggressively; this is not history)

Spec: 0.1-mvp
Current acceptance criterion: AC-004 pinned sensitivity model matches trusted
  reference embedding/ranking fixtures. In-progress: U-062 real Candle forward
  GREEN this turn. AC-004 is NOT complete until U-061..U-067 and I-020..I-025 all
  pass. STOP per AGENTS.md step 10; do not start AC-005 or the next AC-004 test.
Last green state: HEAD `b08e335221fa5c69b089a1ef187003863923f250` (committed
  baseline; all changes this turn are uncommitted).

Working tree (uncommitted):
- `src/embedding.rs` (rewritten this turn): real Candle forward. `Embedder::load`
  serde-parses `config.json` into `bert::Config`, `unsafe
  VarBuilder::from_mmaped_safetensors(&[model.safetensors], F32, Cpu)`,
  `BertModel::load`; `embed(text)` tokenizes with resident `Tokenizer` ->
  `input_ids`/zero `token_type_ids`/ones `attention_mask` -> `BertModel::forward`
  -> masked mean-pool seq dim -> `Vec<f32>`. Validates pooling
  `word_embedding_dimension` == bert `hidden_size`.
- `Cargo.toml`/`Cargo.lock`: add `candle-transformers@0.11`.
- `specs/0.1-mvp/evidence/AC-004/RED-U062.md` (E0433 unresolved `Embedder`) and
  `GREEN-U062.md` (real forward, `cargo test --locked -- --ignored u062` ok).
- U-062 test is now `#[ignore]` (needs gitignored weights; run after
  `./hack/fetch-model`).

Current failing test: none. `./hack/verify` exit 0; `./hack/test-impact` ->
  FULL SUITE (UNKNOWN SURFACE); `./hack/spec-check 0.1-mvp` OK; ignored suite
  (fetch-model + `cargo test --locked -- --ignored`) 1 passed.

Next step: STOP (GREEN-only turn per AGENTS.md step 10). Later AC-004 tests:
  U-061..U-067 (U-067 next), I-020..I-025.

Open uncertainty / flags for reviewer:
- U-062 now proves a REAL Candle forward emits a 384-dim embedding matching the
  pooling config's `word_embedding_dimension`. The forward is deterministic
  (eval mode: candle `Dropout` is disabled when train=false, which is how
  `BertModel::forward` runs). This replaces the earlier contract-only check.
- Weights/configs live under `artifacts/models/sensitivity/` (gitignored via
  `artifacts/`); the U-062 test is `#[ignore]` and requires `./hack/fetch-model`
  to have run.
- `hack/test-impact` maps any `src/*` change to "UNKNOWN SURFACE" -> FULL SUITE;
  map may need updating as surfaces (src/grpc, src/cache, src/infer,
  src/embedding) land later.

## Evidence
- specs/0.1-mvp/evidence/AC-001/RED.md   (cargo build exit 101, no crate)
- specs/0.1-mvp/evidence/AC-001/GREEN.md
- specs/0.1-mvp/evidence/AC-002/RED.md   (U-020: unresolved import Runtime)
- specs/0.1-mvp/evidence/AC-002/RED-U022.md (U-022: warmup ignored path)
- specs/0.1-mvp/evidence/AC-002/GREEN.md
- specs/0.1-mvp/evidence/AC-003/RED.md   (I-064: warmup Ok(()) for incomplete ModelCar)
- specs/0.1-mvp/evidence/AC-003/GREEN.md
- specs/0.1-mvp/evidence/AC-004/RED.md   (U-060: unresolved import Tokenizer)
- specs/0.1-mvp/evidence/AC-004/GREEN-U060.md
- specs/0.1-mvp/evidence/AC-004/RED-U066.md
- specs/0.1-mvp/evidence/AC-004/GREEN-U066.md
- specs/0.1-mvp/evidence/AC-004/RED-U062.md   (E0433 unresolved type Embedder)
- specs/0.1-mvp/evidence/AC-004/GREEN-U062.md (real Candle forward, 384-dim ok; verify exit 0)

## Issue candidates (unrelated defects noticed in passing)
(none)
