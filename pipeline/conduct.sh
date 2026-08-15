#!/usr/bin/env bash
# The conductor: drives one acceptance criterion through IMPLEMENTING → LOCAL-GREEN
# → review bundle, per docs/SDD.md and docs/TDD.md.
# Usage: pipeline/conduct.sh <spec-id> [AC-ID]
set -euo pipefail
cd "$(dirname "$0")/.."
ID="${1:?usage: conduct.sh <spec-id> [AC-ID]}"
DIR="specs/$ID"
test -f "$DIR/spec.md" || { echo "[conduct] no such spec: $DIR/spec.md"; exit 1; }
source pipeline/lib.sh
mkdir -p artifacts

AC="${2:-$(next_criterion "$DIR")}"
[ -z "$AC" ] && { log "all acceptance criteria have GREEN evidence — nothing to do"; exit 0; }
CRIT="$(criterion_text "$DIR" "$AC")"
mkdir -p "$DIR/evidence/$AC"
log "state=IMPLEMENTING spec=$ID criterion=$AC"
log "text: $CRIT"

# Turn 1: proving test → RED evidence
worker_turn "$ID" "Read .agent/state/current.md FIRST, then $DIR/spec.md, $DIR/test-plan.md, and the test IDs mapped to $AC in tests/TEST_MATRIX.md. Work ONLY criterion $AC: '$CRIT'. Follow AGENTS.md steps 1-4: select/write the proving test, run it, prove RED for the expected reason, and record RED evidence in $DIR/evidence/$AC/RED.md (test ID, command, worktree state, failure excerpt, why expected). Do NOT implement yet. Update .agent/state/current.md before ending. $STANDING_RULES" \
  || retry_write_now "$ID" "proving-test ($AC)"
test -f "$DIR/evidence/$AC/RED.md" || { log "no RED evidence — HUMAN_REQUIRED"; exit 2; }

# Turn 2: minimal implementation → GREEN evidence
worker_turn "$ID" "Read .agent/state/current.md FIRST. Criterion $AC has RED evidence in $DIR/evidence/$AC/RED.md. Follow AGENTS.md steps 5-9: smallest implementation change, focused test to GREEN, record slice evidence in $DIR/evidence/$AC/GREEN-<TESTID>.md (same test ID, command, result, worktree state); write the whole-criterion GREEN.md ONLY when EVERY unit-level test mapped to this criterion in test-plan.md passes, then ./hack/test-impact on changed files, ./hack/spec-check $ID, ./hack/verify. Write your engineering explanation to artifacts/review/explanation.md (What changed / Why this implementation / Alternatives rejected / Which tests prove it / What could regress / Rollback). STOP after this criterion. $STANDING_RULES" \
  || retry_write_now "$ID" "implementation ($AC)"

# Local gate
if ./hack/verify; then
  log "state=LOCAL-GREEN ($AC)"
else
  log "verify RED — one diagnosed-fix turn"
  worker_turn "$ID" "Read .agent/state/current.md FIRST. ./hack/verify is RED after $AC. Diagnose with evidence (run it, read the failure), change exactly ONE thing, re-run to green. Never weaken an assertion. $STANDING_RULES"
  ./hack/verify || { log "still RED — HUMAN_REQUIRED"; exit 2; }
fi
test -f "$DIR/evidence/$AC/GREEN.md" || { log "verify green but GREEN evidence missing — HUMAN_REQUIRED"; exit 2; }

pipeline/review-bundle.sh "$ID"
log "state=AWAITING-INDEPENDENT-REVIEW  bundle: artifacts/review/  ($AC)"
log "next: reviewer writes artifacts/review/verdict.json, then ./hack/publish-reviewed $ID <msg-file>"
