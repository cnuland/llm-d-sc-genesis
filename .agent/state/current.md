# Working memory (rewrite aggressively; this is not history)

Spec: 0.1-mvp
Current acceptance criterion: AC-001 clean Rust build/server lifecycle — LOCAL GREEN achieved this turn.
Last green state: HEAD `6286ff70abecc707a9bdce23b8debe79c1afb20a`; working tree has uncommitted first crate
  (Cargo.toml, Cargo.lock, src/lib.rs, src/config.rs) + AC-001 evidence. `./hack/verify` exit 0.
Current failing test: none — U-001..U-005 all pass (5/5), full suite green.
Next step: STOP per instruction after AC-001. When resumed, begin AC-002 (not-ready before model load/warmup)
  with its own RED evidence first.
Open uncertainty: none for AC-001. Note: `hack/test-impact` maps any `src/*` change to "UNKNOWN SURFACE" ->
  FULL SUITE; map may need updating as surfaces (grpc/http/cache/infer/model) land later.

## Evidence
- specs/0.1-mvp/evidence/AC-001/RED.md   (cargo build exit 101, no crate)
- specs/0.1-mvp/evidence/AC-001/GREEN.md (cargo test --locked config:: 5 passed; cargo build --locked clean)

## Issue candidates (unrelated defects noticed in passing)
(none)
