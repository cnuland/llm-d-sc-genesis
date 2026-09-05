"""Controls on the TRAFFIC VALIDITY and RUNTIME QUALITY planes.

These two planes are the ones a model-only evaluation cannot see, and both have
produced live failures on this project: a signal qualified against data 95.8%
distinguishable from its traffic, and a classifier with a 96% model-plane score
whose serving pod has not answered a request in 32 hours.
"""
from __future__ import annotations
from .base import Control, Status


class TrafficAlignmentControl(Control):
    """Does the qualification corpus resemble the traffic this will serve?

    The largest unresolved risk in the underlying research: sensitivity was
    qualified entirely against synthetic data 95.8% distinguishable from real
    assistant traffic. Every figure was correct and none was evidence about
    production. Reported as a transfer-confidence verdict rather than a bare
    number, because "97.8% accurate" and "separability 0.94" mean very different
    things when shown together.
    """
    name = "traffic_alignment"
    def run(self, ctx):
        sep = ctx.get("traffic", {}).get("separability")
        if sep is None:
            return self._r(Status.WARN,
                "separability from production traffic is UNMEASURED — offline "
                "figures may not transfer; run shadow mode before promotion",
                separability=None, transfer_confidence="UNKNOWN")
        if sep > 0.90:
            return self._r(Status.FAIL,
                f"corpus is {sep:.1%} distinguishable from production traffic: "
                f"these metrics describe a different population",
                separability=sep, transfer_confidence="LOW")
        if sep > 0.70:
            return self._r(Status.WARN,
                f"corpus is {sep:.1%} distinguishable from production traffic: "
                f"expect degradation; label a traffic sample",
                separability=sep, transfer_confidence="MEDIUM")
        return self._r(Status.PASS, f"separability {sep:.1%} — offline figures "
                       f"should transfer", separability=sep, transfer_confidence="HIGH")


class RuntimeSLOControl(Control):
    """Can the serving system actually deliver classifications, within SLO?

    COVERAGE IS CHECKED FIRST AND ON ITS OWN. On the cluster this framework was
    built against, the classifier's model-plane score was ~96% while its serving
    pod sat in CrashLoopBackOff for 32 hours and answered zero requests. Latency
    percentiles over an empty sample look excellent. A classifier that is not
    answering is not fast.
    """
    name = "runtime_slo"
    def run(self, ctx):
        rt = ctx.get("runtime")
        if not rt:
            return self._r(Status.NOT_APPLICABLE,
                           "no runtime measurements — model-plane evaluation only")
        slo = ctx.get("slo", {})
        cov = rt.get("classification_coverage")
        # THE PRODUCTION INVARIANT, checked before anything else:
        #   a classifier is not qualified at a given traffic level unless the
        #   required share of requests actually receives a classification.
        # A gateway returning 200s while llm-d-sc is bypassed is not a successful
        # semantic-routing deployment, and latency percentiles computed over the
        # requests that did succeed will look excellent while it happens.
        required = slo.get("min_classification_coverage", 0.99)
        if cov is None:
            return self._r(Status.FAIL,
                "classification coverage was not measured; a runtime plane without "
                "coverage cannot distinguish a fast classifier from a bypassed one")
        if cov < required:
            return self._r(Status.FAIL,
                f"classification coverage {cov:.4%} < required {required:.2%} at "
                f"{int(rt.get('attempted', 0))} requests: the serving path is not "
                f"classifying. Latency percentiles below full coverage describe only "
                f"the requests that survived",
                coverage=cov, required_coverage=required,
                attempted=rt.get("attempted"))
        fails, warns = [], []
        for k, key in (("max_p95_ms", "p95_ms"), ("max_p99_ms", "p99_ms")):
            lim, got = slo.get(k), rt.get(key)
            if lim is None or got is None: continue
            if got > lim: fails.append(f"{key} {got:.1f}ms > SLO {lim}ms")
            elif got > 0.8 * lim: warns.append(f"{key} {got:.1f}ms is within 20% of SLO {lim}ms")
        if rt.get("resource_exhausted_rate", 0) > 0.001:
            fails.append(f"RESOURCE_EXHAUSTED on {rt['resource_exhausted_rate']:.2%} of requests")
        if fails: return self._r(Status.FAIL, "; ".join(fails), **rt)
        if warns: return self._r(Status.WARN, "; ".join(warns), **rt)
        return self._r(Status.PASS,
            f"coverage {cov:.2%}, p95 {rt.get('p95_ms', float('nan')):.1f}ms, "
            f"p99 {rt.get('p99_ms', float('nan')):.1f}ms" if cov is not None
            else "within SLO", **rt)


class CorpusImmutabilityControl(Control):
    """Is this result reproducible from immutable inputs?

    A relabelling run on this project overwrote 59,582 labels in place, making
    "which rows changed" permanently unanswerable. A qualification claim that
    cannot be reproduced from digests is an anecdote.
    """
    name = "corpus_immutability"
    def run(self, ctx):
        man = ctx.get("dataset_manifest") or []
        if not man:
            return self._r(Status.FAIL, "no dataset manifest — result is not reproducible")
        missing = [d["id"] for d in man if d.get("digest", "").endswith("MISSING")]
        if missing:
            return self._r(Status.FAIL, f"dataset(s) not resolvable: {missing}", missing=missing)
        return self._r(Status.PASS,
            f"{len(man)} dataset(s) content-addressed: "
            + ", ".join(f"{d['id']}@{d['digest'][7:19]}" for d in man))


class JudgeIntegrityControl(Control):
    """LLM-judged comparisons need controls or they measure the wrong thing.

    Caught: a headline finding retracted after the judge picked the longer answer
    in 70.2% of decided pairs and a second judge reversed the result.
    """
    name = "judge_integrity"
    def run(self, ctx):
        j = ctx.get("judge")
        if not j:
            return self._r(Status.NOT_APPLICABLE, "no LLM-judged comparison in this run")
        fails = []
        if j.get("judge_is_contestant"): fails.append("judge is also a contestant")
        if not j.get("position_randomised"): fails.append("answer position not randomised")
        lw = j.get("longer_answer_win_rate")
        if lw is not None and lw > 0.60:
            fails.append(f"longer answer wins {lw:.1%} (>60%): judge is scoring length")
        if j.get("second_judge_agrees_in_sign") is False:
            fails.append("a second judge disagrees in sign")
        return self._r(Status.FAIL if fails else Status.PASS,
                       "; ".join(fails) if fails else
                       "position randomised, judge neutral, length bias in tolerance", **j)
