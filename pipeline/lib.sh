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

server_busy() {
  curl -sk -m 15 -H "Authorization: Bearer $(cat "$API_KEY_FILE")" "$SLOTS_URL" 2>/dev/null \
    | python3 -c 'import json,sys; print(any(x.get("is_processing") for x in json.load(sys.stdin)))' 2>/dev/null
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

next_criterion() {  # <spec.md> — first unchecked acceptance criterion
  grep -m1 '\- \[ \]' "$1" | sed 's/.*\- \[ \] *//'
}
