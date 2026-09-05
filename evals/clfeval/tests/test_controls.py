"""Tests for the controls, written as REGRESSIONS against real mistakes.

Each test names the incident it prevents. A control that silently stops firing is
worse than no control, and these are the specific failures that produced numbers
which looked publishable.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import numpy as np
from clfeval.controls import (BaselineControl, SeedStabilityControl, HoldoutControl,
                              TrafficAlignmentControl, RuntimeSLOControl,
                              CorpusImmutabilityControl, JudgeIntegrityControl, Status)
from clfeval.specs import ClassifierTaskSpec

TASK = ClassifierTaskSpec(signal="t", labels=["A", "B"], noise_floor=0.002)


def _ctx(**kw):
    base = {"metrics": {}, "task": TASK, "seed_scores": [0.9, 0.9],
            "dataset_manifest": [{"id": "d", "digest": "sha256:abc"}]}
    return {**base, **kw}


def test_degenerate_split_fails():
    """A gate scored 99.65% on an eval holding 2 positive rows."""
    r = BaselineControl().run(_ctx(metrics={"lift_over_chance": 0.003,
                                            "minority_share": 0.004}))
    assert r.status is Status.FAIL and "degenerate" in r.detail


def test_lift_below_baseline_fails():
    """A candidate scored 93.78% against a 93.45% majority baseline."""
    r = BaselineControl().run(_ctx(metrics={"lift_over_chance": 0.003,
                                            "minority_share": 0.3}))
    assert r.status is Status.FAIL


def test_single_seed_fails():
    """A '+0.42 gain' vanished on the second seed."""
    assert SeedStabilityControl().run(_ctx(seed_scores=[0.9])).status is Status.FAIL


def test_inherited_floor_is_flagged():
    """The floor was measured once on one config and carried across all others,
    inflating every 'Nx the noise floor' claim by about 4x."""
    r = SeedStabilityControl().run(_ctx(seed_scores=[0.90, 0.9025],
                                        noise_floor=0.002,
                                        floor_measured_on="other-config",
                                        config_id="this-config"))
    assert "property of a config" in r.detail


def test_no_floor_warns_not_passes():
    """Omitting the floor must not be the easy way to pass stability."""
    t = ClassifierTaskSpec(signal="t", labels=["A", "B"])
    r = SeedStabilityControl().run({**_ctx(), "task": t, "seed_scores": [0.9, 0.91]})
    assert r.status is Status.WARN


def test_fitted_operating_point_fails():
    """Threshold tuning read 98.14% fitted and 97.89% held out; over-block read
    8.87% fitted and 17.13% held out."""
    r = HoldoutControl().run(_ctx(metrics={"threshold/fitted_accuracy": 0.9814,
                                           "threshold/heldout_accuracy": 0.9689}))
    assert r.status is Status.FAIL


def test_offdistribution_corpus_fails():
    """A signal was qualified entirely against data 95.8% distinguishable from
    the traffic it would serve."""
    r = TrafficAlignmentControl().run(_ctx(traffic={"separability": 0.958}))
    assert r.status is Status.FAIL and r.evidence["transfer_confidence"] == "LOW"


def test_unmeasured_alignment_warns_not_passes():
    r = TrafficAlignmentControl().run(_ctx(traffic={}))
    assert r.status is Status.WARN


def test_coverage_gates_before_latency():
    """A classifier scoring ~96% offline sat in CrashLoopBackOff for 32 hours.
    Latency percentiles over an empty sample look excellent."""
    r = RuntimeSLOControl().run(_ctx(runtime={"classification_coverage": 0.0,
                                              "p95_ms": 1.0, "p99_ms": 1.0},
                                     slo={"max_p95_ms": 20}))
    assert r.status is Status.FAIL and "coverage" in r.detail


def test_unpinned_corpus_fails():
    """A relabel overwrote 59,582 labels in place, unrecoverably."""
    r = CorpusImmutabilityControl().run(
        _ctx(dataset_manifest=[{"id": "d", "digest": "sha256:MISSING"}]))
    assert r.status is Status.FAIL


def test_length_biased_judge_fails():
    """A headline finding was retracted: the judge picked the longer answer in
    70.2% of decided pairs."""
    r = JudgeIntegrityControl().run(_ctx(judge={
        "judge_is_contestant": False, "position_randomised": True,
        "longer_answer_win_rate": 0.702}))
    assert r.status is Status.FAIL and "scoring length" in r.detail


def test_not_applicable_is_not_pass():
    """'Unmeasured' must never render as 'passed'."""
    r = JudgeIntegrityControl().run(_ctx())
    assert r.status is Status.NOT_APPLICABLE and not r.blocks_promotion
