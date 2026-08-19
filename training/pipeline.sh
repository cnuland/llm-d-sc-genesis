#!/usr/bin/env bash
# End-to-end classifier improvement: generate -> cross-verify -> train -> evaluate.
set -uo pipefail
cd "$(dirname "$0")"
export PATH="$HOME/.cargo/bin:$PATH"

for TAX in cost sensitivity; do
  echo "================ $TAX: GENERATE ================"
  python3 sdg_llm.py "$TAX" || { echo "$TAX generation failed"; continue; }
  echo "================ $TAX: CROSS-VERIFY ================"
  python3 verify.py "$TAX"   || { echo "$TAX verification failed"; continue; }
  echo "================ $TAX: TRAIN ================"
  python3 train.py "$TAX" 12 || { echo "$TAX training failed"; continue; }
  echo "================ $TAX: EVALUATE (held-out) ================"
  cd ..
  # Report an eval failure loudly. It previously scrolled past as a bare
  # "Abort trap: 6" while the pipeline moved on to the next taxonomy, which is
  # exactly how a broken artifact reaches a published number unnoticed.
  ./target/release/eval-classifier \
      --model "training/models/$TAX" \
      --classifier "classifiers/$TAX.json" \
      --dataset "evals/datasets/$TAX-heldout.jsonl" \
      --json "docs/benchmarks/$TAX-heldout-retrained.json" \
    || echo "!!!! $TAX EVALUATION FAILED -- the trained model did not load or score !!!!"
  ./hack/benchmark-report || true
  cd training
done
echo "================ PIPELINE COMPLETE ================"
