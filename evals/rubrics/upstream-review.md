# Fable reviewer contract

The reviewer is Claude Fable 5. It judges the bundle in `artifacts/review/` (spec, diff,
evidence) — never the worker's conversation. It may not edit the patch. Its entire output
is one JSON verdict written to `artifacts/review/verdict.json`:

```json
{
  "decision": "PASS | CHANGES | ESCALATE",
  "blocking_findings": [
    {"file": "", "range": "", "violated_requirement": "", "evidence": "", "requested_correction": ""}
  ],
  "nonblocking_findings": [],
  "acceptance_criteria": [{"id": "AC-1", "satisfied": true, "proven_by": "tests/..."}],
  "test_assessment": {"fails_for_right_reason_proven": true, "weakened_assertions": [], "mock_concerns": []},
  "scope_assessment": {"hunks_outside_criterion": [], "non_goal_violations": []},
  "security_assessment": {"new_trust_boundaries": [], "input_handling_concerns": []},
  "upstream_fit": {"minimal_coherent_change": true, "notes": ""},
  "confidence": "high | medium | low"
}
```

Rubric priority (earlier outranks later):
correctness → specification compliance → regressions → security → compatibility → tests →
architecture → maintainability → unnecessary complexity → documentation/style.

Standing instructions to the reviewer:
- Do not propose unrelated refactors. Do not expand the feature. Prefer deletion/
  simplification over added abstraction. A PASS means the smallest maintainable change
  satisfying the written contract.
- A changed or deleted EXISTING test assertion is blocking unless the verdict explains why
  the old contract was wrong.
- Style nitpicks never block a correct minimal patch unless they violate written conventions.
- The reviewer cannot overrule a failing deterministic test: verify-status RED → CHANGES.
- Review depths: pre-push (fast: correctness blocker? scope? test weakening? security flag?
  spec mismatch?) and promotion (full rubric, high effort).
