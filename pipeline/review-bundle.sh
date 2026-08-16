#!/usr/bin/env bash
# Assemble the evidence bundle for the Fable reviewer.
# The reviewer receives artifacts + spec — never the worker's conversation.
set -euo pipefail
cd "$(dirname "$0")/.."
ID="${1:?usage: review-bundle.sh <spec-id>}"
OUT="artifacts/review"
mkdir -p "$OUT"
# include untracked files in the reviewed diff (intent-to-add, then reset)
git add -N -A ':!artifacts' 2>/dev/null || true
git diff HEAD > "$OUT/diff.patch"
git diff --name-only HEAD > "$OUT/changed-files.txt"
git reset -q 2>/dev/null || true
shasum -a 256 "$OUT/diff.patch" | awk '{print $1}' > "$OUT/diff.sha256"
./hack/test-impact $(cat "$OUT/changed-files.txt" | tr '\n' ' ') > "$OUT/test-impact.txt" 2>&1 || true
./hack/verify > "$OUT/verify-output.txt" 2>&1 && echo GREEN > "$OUT/verify-status.txt" || echo RED > "$OUT/verify-status.txt"
cp "specs/$ID/spec.md" "$OUT/spec.md"
cp .agent/state/current.md "$OUT/working-memory.md"
test -f "$OUT/explanation.md" || cat > "$OUT/explanation.md" <<'T'
(worker: fill before review)
What changed?
Why this implementation?
Alternatives rejected?
Which acceptance tests prove it?
What could regress?
Rollback?
T
echo "[bundle] ready at $OUT/ — reviewer writes verdict.json per evals/rubrics/upstream-review.md"
