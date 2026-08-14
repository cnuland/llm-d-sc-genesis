#!/usr/bin/env bash
# The conductor: drives DSV4 worker turns through the state machine for one spec.
# Usage: pipeline/conduct.sh <spec-id> [criterion-index]
# Requires: opencode CLI configured with the ds4 provider; jq/python3; the spec approved.
set -euo pipefail
cd "$(dirname "$0")/.."
ID="${1:?usage: conduct.sh <spec-id>}"
SPEC="specs/$ID/spec.md"
test -f "$SPEC" || { echo "[conduct] no such spec: $SPEC"; exit 1; }
source pipeline/lib.sh

log "state=IMPLEMENTING spec=$ID"
CRIT="$(next_criterion "$SPEC")"
[ -z "$CRIT" ] && { log "no unchecked acceptance criteria — nothing to do"; exit 0; }
log "criterion: $CRIT"

# Turn 1: failing test (TDD evidence)
worker_turn "$ID" "Read .agent/state/current.md FIRST, then specs/$ID/spec.md and specs/$ID/test-plan.md. Work ONLY criterion: '$CRIT'. WRITE the failing test now per the test plan (prove it fails for the right reason by running it and quoting the failure in .agent/state/current.md). Do NOT implement yet. Update .agent/state/current.md before ending. $STANDING_RULES" \
  || retry_write_now "$ID" "test"

# Turn 2: minimal implementation to green
worker_turn "$ID" "Read .agent/state/current.md FIRST. Criterion: '$CRIT'. The failing test exists. Make the SMALLEST implementation change that turns it green. Run ./hack/test-impact on your changed files and run its Required suites, then ./hack/verify. Update .agent/state/current.md. $STANDING_RULES" \
  || retry_write_now "$ID" "impl"

# Local gate
if ./hack/verify; then
  log "state=LOCAL-GREEN"
else
  log "verify RED — returning to IMPLEMENTING (one diagnosed-fix turn)"
  worker_turn "$ID" "Read .agent/state/current.md FIRST. ./hack/verify is RED. Diagnose with evidence (run it, read the failure), change exactly ONE thing, re-run until green. $STANDING_RULES"
  ./hack/verify || { log "still RED — HUMAN_REQUIRED"; exit 2; }
fi

# Evidence bundle for the reviewer (Fable). The conductor stops here;
# the maintainer runs the Fable review out-of-band and drops verdict.json in place,
# then runs: ./hack/publish-reviewed <spec-id> artifacts/review/commit-msg.txt
pipeline/review-bundle.sh "$ID"
log "state=AWAITING-FABLE-REVIEW  bundle: artifacts/review/"
