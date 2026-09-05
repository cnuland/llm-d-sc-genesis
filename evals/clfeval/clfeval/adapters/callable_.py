"""Adapter for anything callable: a rules engine, an HTTP endpoint, a notebook.

Included so a heuristic baseline is qualified through the SAME contract as a
fine-tuned encoder. Without a cheap baseline in the same report, "96% accurate"
has nothing to be compared against -- and the majority-class baseline was the
single most reordering metric in the underlying research.
"""
from __future__ import annotations
import numpy as np
from .base import ClassifierAdapter


class CallableAdapter(ClassifierAdapter):
    plane = "model"

    def __init__(self, fn, task, revision="callable:unversioned", plane="model"):
        self.fn, self.task, self.revision, self.plane = fn, task, revision, plane

    def predict_proba(self, texts):
        out = []
        for t in texts:
            r = self.fn(t)
            if isinstance(r, str):
                v = np.zeros(len(self.task.labels)); v[self.task.labels.index(r)] = 1.0
            else:
                v = np.asarray([float(r.get(l, 0.0)) for l in self.task.labels])
                s = v.sum(); v = v/s if s > 0 else np.full(len(v), 1/len(v))
            out.append(v)
        return np.stack(out)


def majority_class_baseline(task, train_rows):
    """The baseline every report needs and few include."""
    import collections
    c = collections.Counter(r[task.label_field] for r in train_rows)
    top = c.most_common(1)[0][0]
    return CallableAdapter(lambda _t: top, task, revision=f"baseline:majority={top}")
