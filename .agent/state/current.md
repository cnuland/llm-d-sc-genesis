# Working memory (rewrite aggressively; this is not history)

## STATUS: AC-011 (0.1) BENCHMARK RUNNER IMPLEMENTED — measurement infrastructure, verify GREEN

## What was done this turn
Implemented AC-011's benchmark MEASUREMENT INFRASTRUCTURE: a
`src/bin/bench-runner.rs` binary the maintainer executes (also unchanged on
OpenShift) that runs the HOMELAB.md 0.1 protocol against the REAL classifier and
emits machine-readable results.

1. **Runner** (`src/bin/bench-runner.rs`, new): builds a REAL `CandleClassifier`
   from `LLM_D_SC_MODEL_DIR` (default `artifacts/models/sensitivity`) via
   `load_and_warm_modelcar`, serves it with
   `ClassifyServer::bind_with_classifier` on an ephemeral loopback port, and
   FAILS LOUDLY (exit 1) if the model dir is absent — never falls back to the
   synthetic pipeline. Runs the 0.1 matrix (Hit/Miss x 32/64/128/256 x
   conc 1/4, P-020/P-021) via `BenchmarkRun::with_metrics` + `with_seed`, with
   warmup/measure from `BENCH_WARMUP` (default 200) / `BENCH_MEASURE` (default
   1000). Records p50/p90/p95/p99/max, throughput req/s, errors, and the
   queue/tokenize/forward/total stage decomposition per scenario. Asserts the
   harness's own methodology (miss -> measured misses, hit -> measured hits) and
   aborts on any violation. Emits JSON to `artifacts/bench/<timestamp>.json`
   (`BENCH_OUT`) plus a human-readable stdout table carrying the HOMELAB.md
   manifest fields (git sha, model dir + revision, tokenizer revision,
   backend=candle, topology=loopback, cpu model, concurrency, cache mode,
   sequence length, warmup/measure).
2. **Supporting real-forward changes**: `src/classify.rs` `CandleClassifier`
   now has a real cache + metrics handle, `real_forward` measuring tokenize and
   forward stages independently, and `classify` measures total + queue stages and
   records hit/miss counters; `src/embedding.rs` split `embed` into `tokenize`
   + `embed_ids`; `src/grpc/classify.rs` shares the classifier's metrics handle
   and exposes `metrics()`; `src/bench.rs` gained `with_seed`/`run_id`/seeded
   namespaces (new unit test `seed_aware_namespaces_preserve_methodology`).
3. **Smoke test** (`tests/bench_runner.rs`, `#[ignore]`, runs under
   `./hack/test-parity`): launches the compiled binary with a tiny matrix,
   asserts exit 0 + table + valid JSON with the HOMELAB.md manifest fields.
4. **RED**: `specs/0.1-mvp/evidence/AC-011/RED-bench-runner.md` (bin target
   absent -> `CARGO_BIN_EXE_bench-runner` undefined, test could not compile).
5. **GREEN**: `BENCH-RUNNER.md` + `GREEN-bench-runner.md` — the smoke test passed
   against the REAL pinned sensitivity model (present locally): exit 0, all 16
   scenarios, real forward numbers, 0 errors.

## Fixed during verification
- Clippy `too_many_arguments` on `build_report`: grouped the manifest inputs
  into a `ManifestInput` struct.
- `cargo fmt --check` failed on PRE-EXISTING committed `tests/floor*.rs`
  (rustfmt 1.9.0 drift, unrelated to this slice). Normalized with `cargo fmt`
  (mechanical only; no semantic change) so the required gate is green.

## Evidence
- `specs/0.1-mvp/evidence/AC-011/BENCH-RUNNER.md` (new, deliverable)
- `specs/0.1-mvp/evidence/AC-011/GREEN-bench-runner.md` (new)
- `specs/0.1-mvp/evidence/AC-011/RED-bench-runner.md` (prior RED, kept)

## Gates (all GREEN)
- `./hack/verify` -> exit 0, GREEN **without weights** (smoke test is `#[ignore]`;
  runs under `./hack/test-parity`). Includes fmt + clippy + build + full test suite.
- `./hack/spec-check 0.1-mvp` -> OK; AC-011 harness + runner green;
  P-030..P-033 / S-001/S-002 pending cluster measurement by design.
- `./hack/test-impact <slice files>` -> FULL SUITE (unknown surface; verify runs
  the whole suite).
- Smoke test GREEN against the real model: `cargo test --locked --test bench_runner
  -- --ignored` -> 1 passed, exit 0.

## Files changed this turn
- src/bin/bench-runner.rs (new)
- tests/bench_runner.rs (new)
- src/bench.rs (with_seed/run_id/seeded namespaces + unit test)
- src/classify.rs (real cache+metrics, real_forward stage measurement)
- src/embedding.rs (tokenize/embed_ids split)
- src/grpc/classify.rs (shared metrics handle, metrics())
- tests/floor.rs, tests/floor_cache.rs, tests/floor_conc.rs (rustfmt
  normalization only — pre-existing drift)
- specs/0.1-mvp/evidence/AC-011/BENCH-RUNNER.md (new)
- specs/0.1-mvp/evidence/AC-011/GREEN-bench-runner.md (new)
- .agent/state/current.md (this file)

## Uncommitted pre-existing work NOT part of this slice
The AC-002/AC-003 realserve files (src/bin/server.rs, src/classify.rs,
src/runtime.rs, tests/realserve.rs), proto/classify.proto, and Convergence
Slice 1 files remain uncommitted from earlier turns; disposition still to be
decided by the maintainer. This slice's changes are layered on top.

## Next step
STOP per instruction. No further criterion started this turn. (P-030..P-033 /
S-001/S-002 remain PENDING cluster measurement by design; P-023 is 0.21.)

## Uncertainty
None blocking. The runner's `actual_token_count` is computed from the seed +
the harness's per-run measured suffix at index 0 (representative of the sent
contexts); each measured request's exact count varies by index digits. The
recorded value is the actual token count of the sent text and is documented as
an approximation in the evidence.
