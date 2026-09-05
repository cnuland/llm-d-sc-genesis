"""Runtime metrics — the SYSTEM plane, measured through the serving path.

Coverage is listed first deliberately. On the cluster this framework was built
against, the classifier's model-plane score was ~96% while its serving pod sat in
CrashLoopBackOff for 32 hours and answered zero requests. Latency percentiles over
an empty sample look excellent, so coverage has to be the first thing reported and
the first thing gated.
"""
from __future__ import annotations
import numpy as np


def summarise(latencies_ms: list[float], attempted: int, succeeded: int,
              resource_exhausted: int = 0, errors: int = 0) -> dict:
    lat = np.asarray(latencies_ms) if latencies_ms else np.array([np.nan])
    return {
        # measured FIRST: a classifier that is not answering is not fast
        "classification_coverage": succeeded / max(1, attempted),
        "attempted": float(attempted),
        "succeeded": float(succeeded),
        "resource_exhausted_rate": resource_exhausted / max(1, attempted),
        "error_rate": errors / max(1, attempted),
        "p50_ms": float(np.nanpercentile(lat, 50)),
        "p95_ms": float(np.nanpercentile(lat, 95)),
        "p99_ms": float(np.nanpercentile(lat, 99)),
        "mean_ms": float(np.nanmean(lat)),
    }
