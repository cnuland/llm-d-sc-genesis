"""The five evaluation planes, each producing an explicit result.

A qualification report must not require a reader to interpret thirty metrics. Each
plane resolves to one of four states, and a plane that was not exercised says so
rather than being omitted -- omission is how model-plane evidence gets read as
whole-system evidence.

  PASS         the plane's required evidence is present and its controls passed
  WARN         evidence present, a named risk travels with it
  FAIL         evidence present and it does not support promotion
  NOT_EVALUATED the plane was not exercised in this run
"""
from __future__ import annotations
import dataclasses
from ..controls.base import Status

PLANES = ["classifier_quality", "decision_quality", "runtime_quality",
          "traffic_validity", "outcome_value"]

# Which controls speak for which plane. A plane with no evaluated control and no
# required metric present is NOT_EVALUATED, never PASS.
PLANE_CONTROLS = {
    "classifier_quality": ["baseline_lift", "seed_stability", "calibration"],
    "decision_quality":   ["matched_operating_point", "holdout_integrity"],
    "runtime_quality":    ["runtime_slo", "artifact_identity"],
    "traffic_validity":   ["traffic_alignment"],
    "outcome_value":      [],
}
PLANE_EVIDENCE = {
    "classifier_quality": ["accuracy", "lift_over_chance", "macro_f1"],
    "decision_quality":   ["selective/accuracy@0.90"],
    "runtime_quality":    ["runtime/classification_coverage"],
    "traffic_validity":   [],
    "outcome_value":      ["outcome/objective_delta"],
}


@dataclasses.dataclass
class PlaneResult:
    plane: str
    status: str
    detail: str
    controls: list[str] = dataclasses.field(default_factory=list)

    def to_dict(self): return dataclasses.asdict(self)


def resolve(metrics: dict, control_results, traffic: dict | None,
            outcome: dict | None) -> list[PlaneResult]:
    by = {c.control: c for c in control_results}
    out = []
    for p in PLANES:
        names = [n for n in PLANE_CONTROLS[p] if n in by]
        rel = [by[n] for n in names]
        applicable = [c for c in rel if c.status is not Status.NOT_APPLICABLE]
        have_evidence = any(k in metrics for k in PLANE_EVIDENCE[p])

        if p == "traffic_validity" and not (traffic or {}).get("separability"):
            out.append(PlaneResult(p, "NOT_EVALUATED",
                "no separability measured against production traffic — run shadow "
                "mode before promoting", names)); continue
        if p == "outcome_value" and not outcome:
            out.append(PlaneResult(p, "NOT_EVALUATED",
                "no outcome evidence supplied; classifier quality does not "
                "establish that the routing decision is worth making", [])); continue
        if not applicable and not have_evidence:
            out.append(PlaneResult(p, "NOT_EVALUATED",
                "plane not exercised in this run", names)); continue

        if any(c.status is Status.FAIL for c in applicable):
            fails = [c.control for c in applicable if c.status is Status.FAIL]
            out.append(PlaneResult(p, "FAIL", f"failing control(s): {', '.join(fails)}", names))
        elif any(c.status is Status.WARN for c in applicable):
            warns = [c.control for c in applicable if c.status is Status.WARN]
            out.append(PlaneResult(p, "WARN", f"warning(s): {', '.join(warns)}", names))
        else:
            out.append(PlaneResult(p, "PASS",
                f"{len(applicable)} control(s) passed" if applicable
                else "evidence present, no controls configured", names))
    return out


def verdict(planes: list[PlaneResult], control_results,
            required_planes: list[str] | None = None) -> str:
    """Four terminal states.

    INCOMPLETE is distinct from REJECTED on purpose: a run missing a required
    plane has not FAILED, it has not been finished. Collapsing the two either
    blocks work that was never evaluated or, worse, lets an unevaluated plane
    read as an acceptable one.
    """
    required = required_planes or []
    by = {p.plane: p for p in planes}
    missing = [p for p in required if by.get(p, PlaneResult(p, "NOT_EVALUATED", "")).status
               == "NOT_EVALUATED"]
    blocking = [c.control for c in control_results if c.blocks_promotion]
    if blocking:
        return "REJECTED"
    if missing:
        return "INCOMPLETE"
    if any(p.status == "FAIL" for p in planes):
        return "REJECTED"
    if any(p.status == "WARN" for p in planes) or \
       any(c.status is Status.WARN for c in control_results):
        return "QUALIFIED_WITH_WARNINGS"
    return "QUALIFIED"
