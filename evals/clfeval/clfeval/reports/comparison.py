"""Champion-vs-candidate comparison — what CI regression actually needs.

Deliberately does NOT lead with accuracy. Seven of eight interventions on this
project looked like improvements on accuracy and lost at matched containment, and
one recommendation reversed entirely once failure mode was considered: a gate
scoring 0.99 points LOWER released 0.00% of secrets against 14.88%.

So the comparison reports the suite's primary metric first, then per-gate
behaviour, then accuracy — and flags any place where accuracy and the deployed
metric disagree, because that disagreement is the finding.
"""
from __future__ import annotations
import dataclasses


@dataclasses.dataclass
class ComparisonReport:
    suite: str
    champion: str
    candidate: str
    primary_metric: str
    deltas: dict[str, float]
    decision: dict
    disagreements: list[str]

    def render(self) -> str:
        L = [f"CHAMPION vs CANDIDATE  ({self.suite})",
             f"  champion   {self.champion}",
             f"  candidate  {self.candidate}",
             f"  primary    {self.primary_metric}", ""]
        for k in sorted(self.deltas, key=lambda x: (x != self.primary_metric, x)):
            v = self.deltas[k]
            mark = "  <- primary" if k == self.primary_metric else ""
            L.append(f"  {k:<40}{v:+.4f}{mark}")
        if self.disagreements:
            L += ["", "METRIC DISAGREEMENT — read before promoting:"]
            L += [f"  {d}" for d in self.disagreements]
        L += ["", f"DECISION: {self.decision['decision']}"]
        L += [f"  {r}" for r in self.decision["reasons"]]
        return "\n".join(L)


def compare(suite, champion_report, candidate_report) -> ComparisonReport:
    pm = suite.promotion.primary_metric
    cm, dm = champion_report.metrics, candidate_report.metrics
    keys = [k for k in dm
            if isinstance(dm.get(k), (int, float)) and isinstance(cm.get(k), (int, float))
            and (k == pm or k.startswith("gate/") or k in
                 ("accuracy", "macro_f1", "calibration/ece", "minority_share"))]
    deltas = {k: dm[k] - cm[k] for k in keys}

    # The check that matters: does raw accuracy point the other way from the
    # metric the deployment actually runs on?
    dis = []
    acc = deltas.get("accuracy")
    prim = deltas.get(pm)
    if acc is not None and prim is not None and acc * prim < 0:
        dis.append(f"accuracy {acc:+.4f} but {pm} {prim:+.4f} — they disagree in "
                   f"sign; the accuracy ranking is not the deployment ranking")
    for k, v in deltas.items():
        if k.endswith("/containment") and v < -0.005 and (acc or 0) > 0:
            dis.append(f"accuracy improved but {k} fell {v:+.4f}: the candidate is "
                       f"letting more at-or-above content through")
        if k.endswith("/released_to_lowest") and v > 0.001:
            dis.append(f"{k} rose {v:+.4f}: the candidate RELEASES more of the "
                       f"top tier to the lowest branch — usually disqualifying "
                       f"regardless of accuracy")
    decision = suite.promotion.decide(candidate_report, champion_metrics=cm)
    if dis and decision["decision"] == "PROMOTE":
        decision = {**decision, "decision": "PROMOTE_WITH_REVIEW",
                    "reasons": decision["reasons"] + ["metric disagreement detected"]}
    return ComparisonReport(suite.name, champion_report.classifier_revision,
                            candidate_report.classifier_revision, pm, deltas,
                            decision, dis)
