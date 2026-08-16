# Working memory (rewrite aggressively; this is not history)

Spec: 0.1-mvp
Current acceptance criterion: AC-004 pinned sensitivity model matches trusted
  reference embedding/ranking fixtures.
Slice completed this turn: U-063 (embedding normalization matches classifier
  definition).

## U-063 — GREEN (this turn)

### modules.json finding
`artifacts/models/sensitivity` had NO `modules.json`. Fetched it from the pinned
repo `cnuland/semantic-routing-sensitivity` @ rev
`43f21d21ac48134464f8510a9ac9c95bdac7ba86` via hf_hub_download — present (not
404). It declares module idx 2 `2_Normalize` of type
`sentence_transformers.models.Normalize`. `2_Normalize/config.json` is 404
(stateless Normalize, no config). So the documented normalization contract is
NORMALIZED (L2) embeddings — the task's fallback branch (no Normalize ->
unnormalized) did NOT apply.

### Change
- Added `#[ignore]` test
  `u063_embedding_normalization_matches_classifier_definition` in
  `src/embedding.rs`: asserts `embed()` L2 norm ~1.0 within 1e-3.
- RED: got norm 5.758741, want ~1.0 (embed() returned raw mean-pooled vector).
- Smallest fix in `Embedder::embed`: L2-normalize after masked mean pooling
  (`Tensor::norm` + `broadcast_div`; candle 0.11 has `norm`, not `norm_l2`).
- GREEN: `cargo test --locked -- --ignored u063` -> 1 passed.

### Evidence
- specs/0.1-mvp/evidence/AC-004/RED-U063.md   (records modules.json finding + RED)
- specs/0.1-mvp/evidence/AC-004/GREEN-U063.md
- SHA 75fa0a4; changed: src/embedding.rs only. No commits/pushes.

### Suites
- ./hack/test-impact: Required (none); Recommended `cargo test --locked` — green.
- ./hack/spec-check 0.1-mvp: OK.
- ./hack/verify: GREEN (fmt, clippy, build, test) — 10 passed, 3 ignored.

## Open items / flags for reviewer
- U-061 parity remains RED/ESCALATED (prior state): resident Candle forward does
  not match the trusted reference first16/l2_norm. OUT OF SCOPE this turn. Note:
  U-063's normalization fix changes `embed()` output (now norm ~1.0), which makes
  U-061's l2_norm assertion (want 5.7587, unnormalized golden) diverge further.
  The golden-embedding.json reference was generated WITHOUT the Normalize stage
  (transformers AutoModel + masked mean pooling, artifacts/u061_tight.sh), while
  the classifier definition (modules.json) declares Normalize. The U-061 reference
  provenance vs the Normalize module needs reconciliation by a human before U-061
  can be closed.
- Next step for a human: reconcile U-061 reference provenance (normalized vs
  unnormalized) and resolve the U-061 escalation.
