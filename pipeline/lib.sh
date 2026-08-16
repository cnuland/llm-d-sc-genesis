#!/usr/bin/env bash
# Shared conductor machinery: watchdogged worker turns + gates.
# Battle-tested pattern from the momentum-rush build (watchdog kills client hangs;
# server-idle detection distinguishes 'quietly working' from 'dead').
WORKER_MODEL="${WORKER_MODEL:-ds4/ds4-flash-0731}"
SLOTS_URL="${SLOTS_URL:-https://llama-server-ds4-homelab-maas.apps.ironman.cjlabs.dev/slots}"
API_KEY_FILE="${API_KEY_FILE:-$HOME/.ds4_api_key}"   # durable path — never /tmp
IDLE_LIMIT="${IDLE_LIMIT:-8}"                        # x90s ≈ 12 min server-idle → kill
STANDING_RULES="IMPORTANT: do NOT spawn subagents - work DIRECTLY. Scratch files in ./artifacts/ only, never /tmp. RELATIVE paths only. Never commit or push."

log() { echo "[conduct $(date +%H:%M:%S)] $*"; }

METRICS_URL="${METRICS_URL:-https://llama-server-ds4-homelab-maas.apps.ironman.cjlabs.dev/metrics}"

# Real liveness: tokens actually produced since the last poll. A wedged
# generation leaves is_processing=true forever (observed 2026-08-16: slot
# held 34k tokens of zombie context while producing nothing), so claimed
# state is NOT a liveness signal — token progress is.
tokens_predicted() {
  curl -sk -m 15 -H "Authorization: Bearer $(cat "$API_KEY_FILE")" "$METRICS_URL" 2>/dev/null \
    | grep '^llamacpp:tokens_predicted_total' | awk '{print int($2)}'
}

# State lives in a file: server_busy is called via $(...) which runs in a
# SUBSHELL, so a shell variable would never persist between polls.
TOKEN_STATE="${TOKEN_STATE:-artifacts/.watchdog-tokens}"

server_busy() {
  local now prev
  now=$(tokens_predicted)
  prev=$(cat "$TOKEN_STATE" 2>/dev/null || echo 0)
  if [ -z "$now" ]; then echo True; return; fi   # metrics unreachable: do not kill on a probe failure
  echo "$now" > "$TOKEN_STATE"
  [ "$now" -gt "$prev" ] && echo True || echo False
}

worker_turn() {  # <spec-id> <prompt>  — returns 1 on watchdog kill
  local id="$1" prompt="$2"
  opencode run --agent build -m "$WORKER_MODEL" "$prompt" >> "artifacts/conduct-$id.log" 2>&1 &
  local pid=$! idle=0
  while kill -0 "$pid" 2>/dev/null; do
    sleep 90
    if [ "$(server_busy)" = "True" ]; then idle=0; else idle=$((idle+1)); fi
    if [ "$idle" -ge "$IDLE_LIMIT" ]; then
      log "[watchdog] killing hung turn ($pid)"; kill "$pid" 2>/dev/null; return 1
    fi
  done
  wait "$pid" 2>/dev/null; return 0
}

retry_write_now() {  # <spec-id> <what>  — recovery for read-only/empty turns
  local id="$1" what="$2"
  log "retrying $what turn with write-now nudge"
  worker_turn "$id" "Your previous turn ended without writing anything. WRITE NOW: continue the $what work for the active criterion in specs/$id/ per .agent/state/current.md. Start with the file you must create or edit. $STANDING_RULES"
}

next_criterion() {  # <spec-dir> — first AC-NNN in spec.md without GREEN evidence
  local dir="$1"
  grep -oE 'AC-[0-9]+' "$dir/spec.md" | sort -u | while read -r ac; do
    [ -f "$dir/evidence/$ac/LOCAL-GREEN.md" ] || { echo "$ac"; return; }
  done | head -1
}

criterion_text() {  # <spec-dir> <AC-ID> — the criterion's full line
  grep -m1 "$2" "$1/spec.md" | sed 's/^- *//'
}
