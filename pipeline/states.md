# The state machine (code, not an LLM)

IDEA → RESEARCHED → SPECIFIED → TEST-DESIGNED → IMPLEMENTING → LOCAL-GREEN
→ FABLE-REVIEWED → PUSHED → GITHUB-CI-GREEN → PROD-LIKE-VALIDATED
→ MAINTAINER-APPROVED → MERGED → OBSERVED/LEARNED

| Transition | Gate | Owner |
|---|---|---|
| SPECIFIED → TEST-DESIGNED | test-plan.md complete, maintainer approves spec | human |
| TEST-DESIGNED → IMPLEMENTING | conduct.sh starts worker turns | script |
| IMPLEMENTING → LOCAL-GREEN | ./hack/verify exit 0 | script |
| LOCAL-GREEN → FABLE-REVIEWED | review-bundle + Fable verdict PASS | Fable |
| FABLE-REVIEWED → PUSHED | ./hack/publish-reviewed (checks verdict) | script |
| PUSHED → GITHUB-CI-GREEN | fast-ci required check | GitHub |
| → MAINTAINER-APPROVED → MERGED | human review + merge | human |

Failure edges: verify RED → back to IMPLEMENTING (same criterion). Review CHANGES → back to
IMPLEMENTING with blocking findings as the next turn's input. Review ESCALATE → HUMAN_REQUIRED
(conductor halts). Validation RED → new commit on the agent branch, never on the validation ref.

## Worker-turn discipline (from the momentum-rush / rabbit-run playbook)
- One acceptance criterion per turn; micro-scope big criteria into test-turn + impl-turn.
- Every turn prompt: "Do NOT spawn subagents", "scratch in ./artifacts/, never /tmp",
  "read .agent/state/current.md FIRST", "WRITE immediately, starting with <file>".
- Empty/read-only turn (known DSV4 mode): retry once with "you wrote nothing — WRITE NOW".
- Design-paralysis burnout (silence): shrink the design space in the spec, or use a
  thinking-off transcription call for pure-transcription writes; the worker still authors code.
- Client hang (server idle, client alive): the watchdog kills the turn after IDLE_LIMIT.
- Sessions are standalone per turn; state carries via .agent/state/current.md, never session
  history. Gates count artifacts (files, test counts via the Tests line, symbols) — never
  keyword greps alone, and never the "Test Files" line.
