"""Controls on the CLASSIFIER QUALITY and DECISION QUALITY planes."""
from __future__ import annotations
import numpy as np
from .base import Control, Status


class BaselineControl(Control):
    """A number without a baseline is not a result.

    Caught: a gate scoring 99.65% on an eval holding 2 positive rows, and a
    candidate taxonomy scoring 93.78% against a 93.45% majority baseline.
    """
    name = "baseline_lift"
    def __init__(self, min_lift=0.02, min_minority=0.06):
        self.min_lift, self.min_minority = min_lift, min_minority
    def run(self, ctx):
        m = ctx["metrics"]
        lift, minor = m.get("lift_over_chance", 0.0), m.get("minority_share", 0.0)
        if minor < self.min_minority:
            return self._r(Status.FAIL,
                f"minority class is {minor:.1%} of the eval (<{self.min_minority:.0%}): "
                f"most of this accuracy is free and the split is degenerate",
                lift=lift, minority_share=minor)
        if lift < self.min_lift:
            return self._r(Status.FAIL,
                f"lift over chance {lift:+.2%} (<{self.min_lift:.0%}): barely beating "
                f"'always answer the majority class'", lift=lift)
        if lift < 2 * self.min_lift:
            return self._r(Status.WARN, f"lift over chance is only {lift:+.2%}", lift=lift)
        return self._r(Status.PASS, f"lift {lift:+.2%}, minority {minor:.1%}",
                       lift=lift, minority_share=minor)


class SeedStabilityControl(Control):
    """One seed is not a measurement.

    Caught: a '+0.42 gain' that vanished on the second seed; a published figure
    corrected from best-of-seeds to median; and an audit showing that the
    "noise floor" quoted across a whole signal was the MINIMUM spread ever
    observed, inflating every "Nx the floor" claim by about 4x.

    That last one is why `floor_measured_on` exists. A noise floor is a property
    of a CONFIGURATION -- encoder, corpus, loss -- not of a signal. Inheriting one
    measured on a different configuration is allowed, because measuring it fresh
    costs seeds, but it can never pass silently.
    """
    name = "seed_stability"
    def run(self, ctx):
        scores = ctx.get("seed_scores") or []
        floor = ctx.get("noise_floor") or ctx["task"].noise_floor
        floor_src = ctx.get("floor_measured_on")
        inherited = floor is not None and floor_src not in (None, ctx.get("config_id"))
        if len(scores) < 2:
            return self._r(Status.FAIL,
                f"{len(scores)} seed(s): a difference cannot be separated from "
                f"initialisation noise", n_seeds=len(scores))
        spread = max(scores) - min(scores)
        med = sorted(scores)[len(scores)//2]
        # spread is a weak estimator of sigma at small n (E[spread] ~ 1.13*sigma
        # for n=2), so report it rather than asserting stability from it
        sigma = spread / {2: 1.128, 3: 1.693, 4: 2.059}.get(len(scores), 2.3)
        ev = dict(spread=spread, median=med, sigma_estimate=sigma,
                  n_seeds=len(scores), noise_floor=floor,
                  floor_inherited=inherited, floor_measured_on=floor_src)
        note = (f" — NOTE floor was measured on '{floor_src}', not this "
                f"configuration; a floor is a property of a config, not a signal"
                if inherited else "")
        if floor is None:
            return self._r(Status.WARN,
                f"{len(scores)} seeds, spread {spread:.4f} (sigma~{sigma:.4f}); "
                f"no noise floor declared, so effect sizes cannot be judged", **ev)
        if spread > 3 * floor:
            return self._r(Status.FAIL,
                f"seed spread {spread:.4f} is >3x the declared floor ({floor:.4f}): "
                f"either this configuration is unstable or the floor does not apply "
                f"to it{note}", **ev)
        if spread > floor:
            return self._r(Status.WARN,
                f"seed spread {spread:.4f} exceeds the floor ({floor:.4f}); report "
                f"effect sizes against the spread, not the floor{note}", **ev)
        return self._r(Status.PASS,
            f"{len(scores)} seeds, spread {spread:.4f}, median {med:.4f}"
            f"{note}", **ev)


class HoldoutControl(Control):
    """Any operating point chosen on the rows it is scored on is fitted.

    Caught: 98.14% fitted vs 97.89% held out on accuracy, and 8.87% vs 17.13% on
    over-block at high containment -- roughly 2x optimistic where it matters most.
    """
    name = "holdout_integrity"
    def run(self, ctx):
        m = ctx["metrics"]
        f, h = m.get("threshold/fitted_accuracy"), m.get("threshold/heldout_accuracy")
        if f is None or h is None:
            return self._r(Status.NOT_APPLICABLE,
                           "no operating point was selected for this run")
        gap = f - h
        if gap > 0.01:
            return self._r(Status.FAIL,
                f"fitted {f:.2%} vs held out {h:.2%}: {gap:+.2%} of the reported "
                f"figure is selection bias", optimism=gap)
        if gap > 0.005:
            return self._r(Status.WARN, f"selection optimism {gap:+.2%}; report the "
                           f"held-out figure", optimism=gap)
        return self._r(Status.PASS, f"held out {h:.2%}, optimism {gap:+.2%}", optimism=gap)


class MatchedOperatingPointControl(Control):
    """Compare candidates at MATCHED containment, never at argmax.

    Seven of eight interventions on this project looked like wins at argmax and
    lost here: an argmax comparison on a gated ordered taxonomy compares two
    arbitrary operating points, not two models.
    """
    name = "matched_operating_point"
    def run(self, ctx):
        task = ctx["task"]
        if not task.gates:
            return self._r(Status.NOT_APPLICABLE, "task has no gates")
        cmp = ctx.get("champion_comparison")
        if not cmp:
            return self._r(Status.NOT_APPLICABLE, "no champion supplied to compare against")
        won, total = cmp["cells_won"], cmp["cells"]
        if won > total / 2:
            return self._r(Status.PASS, f"wins {won}/{total} matched-containment cells", **cmp)
        return self._r(Status.FAIL,
            f"wins only {won}/{total} matched-containment cells: the argmax "
            f"advantage is an operating point, not a better model", **cmp)


class CalibrationControl(Control):
    """Are confidence scores usable for abstention and thresholds?

    Also checks whether abstention drops the rows the JURY disagreed on.
    Enrichment near 1.0 means confidence is BLIND to disagreement -- the model is
    confidently wrong on hard rows rather than uncertain, so no threshold policy
    can rescue it. That distinction explained why one published gate had the worst
    abstention curve in its family despite the second-highest accuracy.
    """
    name = "calibration"
    blocking = False
    def run(self, ctx):
        m = ctx["metrics"]
        ece = m.get("calibration/ece")
        enrich = m.get("selective/contested_enrichment")
        bits = []
        status = Status.PASS
        if ece is None and enrich is None:
            return self._r(Status.NOT_APPLICABLE, "no confidence scores available")
        if ece is not None:
            bits.append(f"ECE {ece:.3f}")
            if ece > 0.10: status = Status.WARN
        if enrich is not None:
            bits.append(f"abstention enriches contested rows {enrich:.2f}x")
            if enrich < 1.2:
                status = Status.WARN
                bits.append("confidence is near-blind to jury disagreement — "
                            "abstention will not mitigate hard rows")
        return self._r(status, "; ".join(bits), ece=ece, contested_enrichment=enrich)
