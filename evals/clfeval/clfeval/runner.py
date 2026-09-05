"""Qualification runner — five planes, one contract, one report.

The planes are kept SEPARATE and each is named as evaluated or not, because
collapsing them is how a classifier gets promoted on model-plane evidence alone:

  classifier quality   does it classify correctly?
  decision quality     does the taxonomy/gate/threshold give the right ACTION?
  runtime quality      can the serving path deliver it within SLO?
  traffic validity     does the corpus resemble the traffic it will serve?
  outcome value        does using it improve the declared objective?

The last plane is almost never measurable offline and this framework says so
rather than omitting it. Attempting it on this project produced a headline that
had to be retracted when the LLM judge turned out to be scoring answer length in
70.2% of decided pairs -- so `outcome value` is reported as UNEVALUATED unless
explicit outcome evidence is supplied.
"""
from __future__ import annotations
import json, pathlib
import numpy as np
from .metrics import classification as M
from .metrics.calibration import expected_calibration_error
from .controls import DEFAULT_CONTROLS, summarise
from .reports import QualificationReport
from .reports.planes import resolve as resolve_planes, verdict as plane_verdict
from .sinks import eval_code_revision

PLANES = ["classifier_quality", "decision_quality", "runtime_quality",
          "traffic_validity", "outcome_value"]


def load_rows(task, datasets, root: pathlib.Path, roles=("qualification", "contested")):
    rows = []
    for ds in datasets:
        if ds.role not in roles: continue
        p = root / ds.path
        if not p.exists(): continue
        for line in open(p):
            r = json.loads(line)
            if r.get(task.label_field) in task.labels:
                rows.append({**r, "_dataset": ds.id})
    return rows


def qualify(*, adapter, task, datasets, rows, suite="ad-hoc", root=None,
            seed_scores=None, noise_floor=None, floor_measured_on=None, config_id=None, champion=None, traffic=None, slo=None,
            judge=None, measure_runtime=False, outcome=None, controls=None,
            expected_identity=None, required_planes=None):
    texts = [r[task.text_field] for r in rows]
    runtime = None
    if measure_runtime:
        P, runtime = adapter.predict_with_telemetry(texts)
        keep = runtime.pop("_kept_indices")
        rows = [rows[i] for i in keep]
    else:
        P = adapter.predict_proba(texts)

    y = [r[task.label_field] for r in rows]
    pred = [task.labels[i] for i in P.argmax(1)]
    correct = np.array([a == b for a, b in zip(pred, y)])

    m = {}
    m.update(M.core(y, pred, task.labels))                       # classifier quality
    m.update(M.label_ceiling(rows, pred, task))
    m.update({k: v for k, v in expected_calibration_error(P, correct).items()
              if not k.endswith("bins")})
    m.update(M.gates(y, P, task))                                # decision quality
    m.update(M.risk_coverage(y, P, task))
    m.update(M.confidence_vs_disagreement(rows, P, task))
    if runtime:
        m.update({f"runtime/{k}": v for k, v in runtime.items()})

    manifest = [d.manifest(root) for d in datasets]
    ctx = {"metrics": m, "task": task, "seed_scores": seed_scores or [m["accuracy"]],
           "noise_floor": noise_floor, "floor_measured_on": floor_measured_on,
           "config_id": config_id or getattr(adapter, "revision", "unknown"),
           "champion_comparison": champion, "traffic": traffic or {},
           "runtime": runtime, "slo": slo or {}, "judge": judge,
           "dataset_manifest": manifest, "adapter": adapter,
           "expected_identity": expected_identity, "outcome": outcome}
    results = [c.run(ctx) for c in (controls or DEFAULT_CONTROLS)]
    planes = resolve_planes(m, results, traffic, outcome)
    v = plane_verdict(planes, results, required_planes)

    return QualificationReport.build(
        suite=suite, task=task,
        classifier_revision=getattr(adapter, "revision", "unknown"),
        runtime_revision=getattr(adapter, "runtime_revision", None),
        eval_code_revision=eval_code_revision(),
        dataset_manifest=manifest, metrics=m, control_results=results,
        planes=planes, verdict=v)
