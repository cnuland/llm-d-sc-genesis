"""Promotion policy — the difference between a verdict and a decision.

A qualification report says whether the EVIDENCE supports promotion. A promotion
policy says whether THIS deployment accepts it. They are separate because the
same evidence justifies different decisions in different places: a dev loop
tolerates a WARN that a production gate must not.

The regression guard exists because comparing a candidate to a champion on
accuracy alone was, on this project, wrong seven times out of eight. Promotion
compares on the primary metric declared by the suite -- `lift_over_chance` by
default, never raw accuracy.
"""
from __future__ import annotations
import dataclasses


@dataclasses.dataclass
class PromotionPolicy:
    primary_metric: str = "lift_over_chance"
    minimum_lift_over_baseline: float | None = None
    max_regression_vs_champion: float | None = 0.005
    allow_warnings: bool = True
    require_planes: list[str] = dataclasses.field(default_factory=list)
    require_reproducible: bool = True

    def decide(self, report, champion_metrics: dict | None = None) -> dict:
        reasons, decision = [], "PROMOTE"

        if report.verdict == "REJECTED":
            decision = "REJECT"
            reasons.append(f"qualification rejected: "
                           f"{', '.join(report.controls['blocking_failures']) or 'a plane failed'}")
        elif report.verdict == "INCOMPLETE":
            # Distinct from REJECT on purpose: the evidence does not exist yet, so
            # the honest decision is to withhold rather than to refuse.
            decision = "INCOMPLETE"
            reasons.append("a required evaluation plane was not exercised — "
                           "this is unfinished, not failed")
        elif report.verdict == "QUALIFIED_WITH_WARNINGS" and not self.allow_warnings:
            decision = "REJECT"
            reasons.append(f"warnings not permitted by policy: "
                           f"{', '.join(report.controls['warnings'])}")

        unevaluated = [p["plane"] for p in (report.planes or [])
                       if p.get("status") == "NOT_EVALUATED"]
        missing = [p for p in self.require_planes if p in unevaluated]
        if missing:
            decision = "INCOMPLETE" if decision == "PROMOTE" else decision
            reasons.append(f"required evaluation plane(s) not evaluated: {missing}")

        if self.require_reproducible and report.unpinned:
            decision = "REJECT"
            reasons.append(f"inputs not pinned: {', '.join(report.unpinned)}")

        lift = report.metrics.get("lift_over_chance")
        if self.minimum_lift_over_baseline is not None and lift is not None:
            if lift < self.minimum_lift_over_baseline:
                decision = "REJECT"
                reasons.append(f"lift {lift:+.4f} below minimum "
                               f"{self.minimum_lift_over_baseline:+.4f}")

        if champion_metrics and self.max_regression_vs_champion is not None:
            cand = report.metrics.get(self.primary_metric)
            champ = champion_metrics.get(self.primary_metric)
            if cand is not None and champ is not None:
                delta = cand - champ
                if delta < -self.max_regression_vs_champion:
                    decision = "REJECT"
                    reasons.append(
                        f"{self.primary_metric} regressed {delta:+.4f} vs champion "
                        f"(limit {-self.max_regression_vs_champion:+.4f})")
                else:
                    reasons.append(f"{self.primary_metric} {delta:+.4f} vs champion")

        return {"decision": decision, "policy_primary_metric": self.primary_metric,
                "reasons": reasons or ["all policy conditions met"]}
