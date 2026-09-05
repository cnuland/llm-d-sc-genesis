"""ClassifierAdapter — what is being qualified.

Evaluating a model artifact directly is not enough. Users deploy a RUNTIME, and
the runtime is where a classifier stops answering. On the cluster this framework
was built against, a checkpoint scoring ~96% on the model plane sat behind a pod
that had answered zero requests for 32 hours.

So adapters distinguish the two planes explicitly. `plane` says which one an
adapter exercises, and the qualification report names the plane it did NOT reach
rather than quietly omitting it.
"""
from __future__ import annotations
import abc, time
import numpy as np


class ClassifierAdapter(abc.ABC):
    plane: str = "model"          # "model" | "runtime"
    revision: str = "unknown"
    runtime_revision: str | None = None

    @abc.abstractmethod
    def predict_proba(self, texts: list[str]) -> np.ndarray:
        """Rows aligned to `texts`, columns aligned to task.labels."""

    def predict_with_telemetry(self, texts: list[str]) -> tuple[np.ndarray, dict]:
        """Predictions plus runtime telemetry. Per-request, not batched.

        Batched throughput is a different measurement from per-request latency,
        and conflating them is how a serving path looks fine until it is on the
        request path.
        """
        lat, rows, ok, exhausted, err = [], [], 0, 0, 0
        for t in texts:
            t0 = time.perf_counter()
            try:
                p = self.predict_proba([t])[0]
                rows.append(p); ok += 1
                lat.append((time.perf_counter() - t0) * 1000)
            except Exception as e:
                msg = str(e).upper()
                if "RESOURCE_EXHAUSTED" in msg: exhausted += 1
                else: err += 1
                rows.append(None)
        from ..metrics.runtime import summarise
        keep = [i for i, r in enumerate(rows) if r is not None]
        P = np.stack([rows[i] for i in keep]) if keep else np.zeros((0, 0))
        return P, {**summarise(lat, len(texts), ok, exhausted, err),
                   "_kept_indices": keep}
