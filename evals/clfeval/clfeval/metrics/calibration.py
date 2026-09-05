"""Calibration — are the confidence scores usable as a control surface?

This matters more than it looks. Every threshold policy, abstention rule and gate
setting in the framework assumes confidence means something. On this project one
published gate turned out to be confidently WRONG on the rows a jury disagreed
about -- its abstention curve was the worst in its family despite the second-
highest accuracy -- and no threshold could rescue it.
"""
from __future__ import annotations
import numpy as np


def expected_calibration_error(probs: np.ndarray, correct: np.ndarray, bins: int = 10) -> dict:
    conf = probs.max(1)
    edges = np.linspace(0, 1, bins + 1)
    ece, mce, n = 0.0, 0.0, len(conf)
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if not m.any(): continue
        acc, avg = correct[m].mean(), conf[m].mean()
        gap = abs(acc - avg)
        ece += m.sum() / n * gap
        mce = max(mce, gap)
        rows.append({"bin": f"({lo:.1f},{hi:.1f}]", "n": int(m.sum()),
                     "confidence": float(avg), "accuracy": float(acc)})
    return {"calibration/ece": float(ece), "calibration/mce": float(mce),
            "calibration/bins": rows,
            # >0 means overconfident: the model claims more certainty than it earns
            "calibration/overconfidence": float(conf.mean() - correct.mean())}
