"""Controls are executable policy, not commentary.

Four states, because PASS/FAIL alone forces two different mistakes: it makes
"unmeasured" look like "failed", and it makes a soft concern look like a blocker.

  PASS            evidence supports promotion on this axis
  WARN            promotion is defensible, but a named risk travels with it
  FAIL            promotion is not supported by the evidence
  NOT_APPLICABLE  the axis does not exist for this task (e.g. gates on an
                  unordered taxonomy) — distinct from passing it

Every control here corresponds to a specific occasion where a naive evaluation
produced a number that looked publishable and was wrong.
"""
from __future__ import annotations
import dataclasses, enum
from typing import Any


class Status(str, enum.Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclasses.dataclass
class ControlResult:
    control: str
    status: Status
    detail: str
    evidence: dict[str, Any] = dataclasses.field(default_factory=dict)
    blocking: bool = True

    @property
    def blocks_promotion(self) -> bool:
        return self.blocking and self.status is Status.FAIL

    def to_dict(self) -> dict:
        return {"control": self.control, "status": self.status.value,
                "detail": self.detail, "evidence": self.evidence,
                "blocking": self.blocking}


class Control:
    """Base class. Subclasses implement `run` and return a ControlResult."""
    name: str = "control"
    blocking: bool = True

    def run(self, ctx: dict) -> ControlResult:      # pragma: no cover
        raise NotImplementedError

    def _r(self, status: Status, detail: str, **ev) -> ControlResult:
        return ControlResult(self.name, status, detail, ev, self.blocking)


def summarise(results: list[ControlResult]) -> dict:
    """Roll controls up into a qualification verdict.

    QUALIFIED                    no FAIL, no WARN
    QUALIFIED_WITH_WARNING       no blocking FAIL, at least one WARN
    NOT_QUALIFIED                at least one blocking FAIL
    """
    blocking_fails = [r.control for r in results if r.blocks_promotion]
    warns = [r.control for r in results if r.status is Status.WARN]
    nonblocking_fails = [r.control for r in results
                         if r.status is Status.FAIL and not r.blocking]
    if blocking_fails:
        verdict = "NOT_QUALIFIED"
    elif warns or nonblocking_fails:
        verdict = "QUALIFIED_WITH_WARNING"
    else:
        verdict = "QUALIFIED"
    return {"verdict": verdict, "blocking_failures": blocking_fails,
            "warnings": warns + nonblocking_fails,
            "controls": [r.to_dict() for r in results]}
