# Working memory (rewrite aggressively; this is not history)

Spec: 0.1-mvp
Current acceptance criterion: AC-002 not-ready before model load/warmup — GREEN proven this turn
  (U-020 + U-022). All three review blocking findings resolved.
Last green state: HEAD `da15ab9b68af324e63ea58be404625f83265adca` (unchanged; all changes uncommitted).
Working tree: `src/lib.rs` registers `pub mod runtime;`; `src/runtime.rs` adds minimal
  `Runtime`/`Readiness` abstraction, `warmup` that validates the model path (exists + readable)
  returning Err and leaving NotReady on failure, U-020 + U-022 tests; AC-002 RED/GREEN + RED-U022
  evidence recorded; artifacts/review/explanation.md updated.
Current failing test: none. `cargo test --locked u020` and `u022` GREEN; full unit suite 7 passed;
  `cargo build --locked` clean; `hack/test-impact` FULL SUITE green; `hack/spec-check 0.1-mvp` OK;
  `hack/verify` GREEN (exit 0).
Next step: STOP per AGENTS.md — do not start next criterion. When resumed: later AC-002 tests
  (I-010/I-011, S-006) in subsequent phases.
Open uncertainty: `hack/test-impact` maps any `src/*` change to "UNKNOWN SURFACE" -> FULL SUITE;
  map may need updating as surfaces (src/grpc, src/cache, src/infer) land later.

## Evidence
- specs/0.1-mvp/evidence/AC-001/RED.md   (cargo build exit 101, no crate)
- specs/0.1-mvp/evidence/AC-001/GREEN.md (cargo test --locked config:: 5 passed; cargo build --locked clean)
- specs/0.1-mvp/evidence/AC-002/RED.md   (U-020: cargo test --locked u020 exit 101, unresolved import Runtime)
- specs/0.1-mvp/evidence/AC-002/RED-U022.md (U-022: cargo test --locked u022 panic, warmup ignored path)
- specs/0.1-mvp/evidence/AC-002/GREEN.md (U-020 + U-022; full suite 7 passed; build clean; verify exit 0)

## Issue candidates (unrelated defects noticed in passing)
(none)
