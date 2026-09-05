"""EvalSuite — the declarative contract describing what must be PROVEN.

EvalHub does not ingest metrics; it declares requirements. A suite names the task,
the datasets, the metrics that must be present, the controls that must pass, the
runtime SLOs and the promotion policy. Complexity, sensitivity, cost, intent, tool
selection or a customer taxonomy are then just different suite documents.

Kubernetes-shaped on purpose: these are cluster artifacts in the deployments this
framework targets, and `apiVersion`/`kind` makes them versionable, admission-
checkable and reviewable through the same path as everything else.
"""
from __future__ import annotations
import dataclasses, hashlib, json, pathlib
from .task import ClassifierTaskSpec
from .dataset import DatasetSpec
from .promotion import PromotionPolicy

try:
    import yaml
except ImportError:
    yaml = None

API_VERSION = "eval.llm-d.ai/v1alpha1"
KIND = "ClassifierEvalSuite"


@dataclasses.dataclass
class EvalSuite:
    name: str
    task: ClassifierTaskSpec
    datasets: list[DatasetSpec]
    required_metrics: list[str] = dataclasses.field(default_factory=lambda: [
        "accuracy", "majority_baseline", "lift_over_chance", "minority_share",
        "macro_f1", "calibration/ece"])
    controls: list[str] = dataclasses.field(default_factory=lambda: [
        "baseline_lift", "seed_stability", "holdout_integrity",
        "matched_operating_point", "calibration", "traffic_alignment",
        "runtime_slo", "corpus_immutability", "judge_integrity"])
    runtime_slo: dict = dataclasses.field(default_factory=dict)
    expected_identity: dict = dataclasses.field(default_factory=dict)
    required_planes: list[str] = dataclasses.field(default_factory=list)
    promotion: PromotionPolicy = dataclasses.field(default_factory=PromotionPolicy)
    description: str = ""

    @property
    def digest(self) -> str:
        payload = json.dumps({
            "name": self.name, "task": self.task.digest,
            "datasets": sorted(d.id for d in self.datasets),
            "required_metrics": sorted(self.required_metrics),
            "controls": sorted(self.controls),
            "runtime_slo": self.runtime_slo,
            "expected_identity": self.expected_identity,
            "required_planes": self.required_planes,
            "promotion": dataclasses.asdict(self.promotion),
        }, sort_keys=True)
        return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()[:16]

    def active_controls(self):
        from ..controls import DEFAULT_CONTROLS
        by = {c.name: c for c in DEFAULT_CONTROLS}
        unknown = [c for c in self.controls if c not in by]
        if unknown:
            raise ValueError(f"suite '{self.name}' names unknown control(s): {unknown}; "
                             f"available: {sorted(by)}")
        return [by[c] for c in self.controls]

    def check_metric_contract(self, metrics: dict) -> list[str]:
        return [m for m in self.required_metrics if m not in metrics]

    @classmethod
    def load(cls, path, task_root: pathlib.Path | None = None) -> "EvalSuite":
        p = pathlib.Path(path)
        d = (yaml.safe_load(p.read_text()) if p.suffix in (".yaml", ".yml") and yaml
             else json.loads(p.read_text()))
        if d.get("apiVersion") != API_VERSION or d.get("kind") != KIND:
            raise ValueError(f"{p}: expected apiVersion={API_VERSION} kind={KIND}, "
                             f"got {d.get('apiVersion')}/{d.get('kind')}")
        spec = d["spec"]
        t = spec["task"]
        task = (ClassifierTaskSpec.builtin(t) if isinstance(t, str)
                else ClassifierTaskSpec(**t))
        ds = [DatasetSpec(**x) for x in spec.get("datasets", [])]
        pol = PromotionPolicy(**spec.get("promotion", {}))
        return cls(name=d["metadata"]["name"], task=task, datasets=ds,
                   required_metrics=spec.get("metrics", {}).get("required",
                       cls.__dataclass_fields__["required_metrics"].default_factory()),
                   controls=spec.get("controls",
                       cls.__dataclass_fields__["controls"].default_factory()),
                   runtime_slo=spec.get("runtime", {}), promotion=pol,
                   expected_identity=spec.get("expectedIdentity", {}),
                   required_planes=spec.get("requiredPlanes", []),
                   description=spec.get("description", ""))

    def to_yaml(self) -> str:
        doc = {
            "apiVersion": API_VERSION, "kind": KIND,
            "metadata": {"name": self.name},
            "spec": {
                "description": self.description,
                "task": self.task.signal,
                "datasets": [dataclasses.asdict(d) for d in self.datasets],
                "metrics": {"required": self.required_metrics},
                "controls": self.controls,
                "runtime": self.runtime_slo,
                "expectedIdentity": self.expected_identity,
                "requiredPlanes": self.required_planes,
                "promotion": dataclasses.asdict(self.promotion),
            },
        }
        for d in doc["spec"]["datasets"]: d.pop("_digest", None)
        return yaml.safe_dump(doc, sort_keys=False) if yaml else json.dumps(doc, indent=1)
