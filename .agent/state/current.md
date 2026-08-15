# Working memory (rewrite aggressively; this is not history)

Spec: 0.1-mvp
Current acceptance criterion: AC-003 ModelCar supplies required files with no runtime HF fetch —
  I-064 GREEN proven this turn. STOP per AGENTS.md step 10; do not start next criterion.
Last green state: HEAD `eb591f81ea04c765736b8974cb7280d383eb36b3` (committed baseline; all
  changes this turn are uncommitted).
Working tree: `src/runtime.rs` adds `Runtime::warmup_modelcar(path, required_files)` — validates
  every required ModelCar file is present before flipping READY, else stays NOT ready; existing
  AC-002 `warmup` unchanged; I-064 proving test updated to call `warmup_modelcar` with
  `MODELCAR_REQUIRED_FILES`; `#[cfg(test)]` constant to keep build clean.
Current failing test: none. `cargo test --locked i064` GREEN; full unit suite 8 passed
  (U-020/U-022/I-064/U-001..U-005); `cargo build --locked` clean; `hack/test-impact` FULL SUITE;
  `hack/spec-check 0.1-mvp` OK; `hack/verify` GREEN exit 0.
Next step: STOP. When resumed, exercise remaining AC-003 tests (I-060..I-063, S-010/S-051/S-053)
  in later phases; those may move required-file contract from a slice to parsing the manifest.
Open uncertainty: `hack/test-impact` maps any `src/*` change to "UNKNOWN SURFACE" -> FULL SUITE;
  map may need updating as surfaces (src/grpc, src/cache, src/infer) land later.

## Evidence
- specs/0.1-mvp/evidence/AC-001/RED.md   (cargo build exit 101, no crate)
- specs/0.1-mvp/evidence/AC-001/GREEN.md (cargo test --locked config:: 5 passed; cargo build --locked clean)
- specs/0.1-mvp/evidence/AC-002/RED.md   (U-020: cargo test --locked u020 exit 101, unresolved import Runtime)
- specs/0.1-mvp/evidence/AC-002/RED-U022.md (U-022: cargo test --locked u022 panic, warmup ignored path)
- specs/0.1-mvp/evidence/AC-002/GREEN.md (U-020 + U-022; full suite 7 passed; build clean; verify exit 0)
- specs/0.1-mvp/evidence/AC-003/RED.md   (I-064: cargo test --locked i064, warmup Ok(()) for incomplete ModelCar, readiness flipped)
- specs/0.1-mvp/evidence/AC-003/GREEN.md (I-064: cargo test --locked i064 ok; full suite 8 passed; build clean; verify exit 0)

## Issue candidates (unrelated defects noticed in passing)
(none)
