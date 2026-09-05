"""ClassifierQualificationReport — the artifact downstream systems consume.

The output of an evaluation is not a dashboard. It is a signed, immutable claim
about one classifier revision, on one taxonomy, against one corpus, in one
runtime, and the evidence for it. That artifact can be attached to a model
revision beside its SBOM and provenance, and a deployment controller can read it.

An evaluation whose inputs are not digested is an anecdote, so every digest that
was available is carried and every one that was NOT is named in `unpinned`.
"""
from __future__ import annotations
import dataclasses, hashlib, json, platform, time
from typing import Any


@dataclasses.dataclass
class QualificationReport:
    suite: str
    signal: str
    taxonomy_digest: str
    classifier_revision: str
    dataset_manifest: list[dict]
    metrics: dict[str, Any]
    controls: dict[str, Any]
    verdict: str
    environment: dict[str, Any] = dataclasses.field(default_factory=dict)
    runtime_revision: str | None = None
    eval_code_revision: str | None = None
    qualified_at: float = dataclasses.field(default_factory=time.time)
    planes: list[dict] = dataclasses.field(default_factory=list)

    @property
    def unpinned(self) -> list[str]:
        out = []
        if not self.classifier_revision or "MISSING" in self.classifier_revision:
            out.append("classifier_revision")
        if not self.runtime_revision: out.append("runtime_revision")
        if not self.eval_code_revision: out.append("eval_code_revision")
        out += [f"dataset:{d['id']}" for d in self.dataset_manifest
                if str(d.get("digest", "")).endswith("MISSING")]
        return out

    @property
    def digest(self) -> str:
        payload = json.dumps({
            "suite": self.suite, "taxonomy": self.taxonomy_digest,
            "classifier": self.classifier_revision,
            "datasets": self.dataset_manifest, "verdict": self.verdict,
            "metrics": {k: v for k, v in sorted(self.metrics.items())
                        if isinstance(v, (int, float))},
        }, sort_keys=True, default=str)
        return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()

    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d["report_digest"] = self.digest
        d["unpinned_inputs"] = self.unpinned
        return d

    def render(self) -> str:
        L = []
        A = L.append
        A(f"CLASSIFIER QUALIFICATION REPORT")
        A(f"  suite          {self.suite}")
        A(f"  signal         {self.signal}")
        A(f"  classifier     {self.classifier_revision}")
        A(f"  taxonomy       {self.taxonomy_digest}")
        A(f"  runtime        {self.runtime_revision or '(not evaluated — model plane only)'}")
        A(f"  environment    {self.environment.get('platform','?')}")
        A("")
        A("EVALUATION PLANES")
        for p in self.planes:
            mark = {"PASS":"PASS","WARN":"WARN","FAIL":"FAIL",
                    "NOT_EVALUATED":" -- "}[p["status"]]
            A(f"  {mark:<5} {p['plane']:<20} {p['detail'][:70]}")
        A("")
        A("EVIDENCE")
        for d in self.dataset_manifest:
            sep = d.get("separability_from_production")
            s = f"  {d['id']:<16} {d['digest'][:19]}  {d.get('provenance','?')}"
            if sep is not None: s += f"  separability={sep:.3f}"
            A(s)
        A("")
        A("HEADLINE")
        for k in ("accuracy", "lift_over_chance", "majority_baseline", "minority_share"):
            if k in self.metrics: A(f"  {k:<24} {self.metrics[k]:.4f}")
        A("")
        A("CONTROLS")
        for c in self.controls.get("controls", []):
            mark = {"PASS":"PASS","WARN":"WARN","FAIL":"FAIL","NOT_APPLICABLE":"n/a "}[c["status"]]
            A(f"  {mark}  {c['control']:<26} {c['detail'][:90]}")
        A("")
        A(f"RESULT: {self.verdict}")
        if self.verdict == "INCOMPLETE":
            A("  a required plane was not evaluated — this is not a failure, "
              "it is unfinished")
        if self.unpinned:
            A(f"  NOT REPRODUCIBLE — unpinned inputs: {', '.join(self.unpinned)}")
        A(f"  report digest {self.digest}")
        return "\n".join(L)

    @classmethod
    def build(cls, *, suite, task, classifier_revision, dataset_manifest,
              metrics, control_results, planes, verdict,
              runtime_revision=None, eval_code_revision=None):
        from ..controls.base import summarise
        c = summarise(control_results)
        return cls(suite=suite, signal=task.signal, taxonomy_digest=task.digest,
                   classifier_revision=classifier_revision,
                   dataset_manifest=dataset_manifest, metrics=metrics, controls=c,
                   verdict=verdict, runtime_revision=runtime_revision,
                   eval_code_revision=eval_code_revision,
                   planes=[p.to_dict() for p in planes],
                   environment={"platform": platform.platform(),
                                "python": platform.python_version()})
