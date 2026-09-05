"""ClassifierTaskSpec — the one contract the whole framework revolves around.

Not "DomainSpec". A domain classifier is one KIND of classifier task, alongside
intent, safety, tool selection, model affinity and any customer taxonomy. The
evaluator must not know what "complexity" means; it knows only:

    input -> prediction distribution -> taxonomy -> decision policy -> outcome

Everything that differs between tasks is data. That is what makes the
qualification machinery reusable across signals, teams and customers.
"""
from __future__ import annotations
import dataclasses, hashlib, json, pathlib
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None


@dataclasses.dataclass(frozen=True)
class Gate:
    """A deployment threshold on an ordered taxonomy: act at this tier or above."""
    at: str
    action: str = "escalate"          # escalate | block | review
    target_containment: float | None = None


@dataclasses.dataclass(frozen=True)
class AbstentionPolicy:
    """What the system does when the classifier is unsure.

    A first-class field because a classifier with nowhere to send uncertain rows
    converts every near-miss into a wrong decision. On this project a three-way
    gate with a REVIEW tier scored 0.99 points LOWER than its binary counterpart
    and released 0.00% of secrets against 14.88% -- the fallback was worth more
    than the accuracy.
    """
    enabled: bool = False
    fallback_class: str | None = None       # where unsure rows go
    max_abstain_rate: float | None = None


@dataclasses.dataclass
class ClassifierTaskSpec:
    signal: str
    labels: list[str]
    taxonomy_version: str = "v1"
    ordered: bool = False
    gates: list[Gate] = dataclasses.field(default_factory=list)
    class_relationships: dict[str, list[str]] = dataclasses.field(default_factory=dict)
    abstention: AbstentionPolicy = dataclasses.field(default_factory=AbstentionPolicy)
    folds: dict[str, dict[str, str]] = dataclasses.field(default_factory=dict)
    noise_floor: float | None = None
    text_field: str = "text"
    label_field: str = "tier"
    votes_field: str = "votes"
    description: str = ""

    def __post_init__(self):
        if isinstance(self.abstention, dict):
            self.abstention = AbstentionPolicy(**self.abstention)
        self.gates = [Gate(**g) if isinstance(g, dict) else g for g in self.gates]
        bad = [g.at for g in self.gates if g.at not in self.labels]
        if bad:
            raise ValueError(f"{self.signal}: gate tier(s) {bad} not in labels")
        if self.gates and not self.ordered:
            raise ValueError(
                f"{self.signal}: gates require ordered=true — 'at or above tier X' "
                f"has no meaning without an order")
        if self.abstention.fallback_class and self.abstention.fallback_class not in self.labels:
            raise ValueError(f"{self.signal}: abstention fallback not in labels")
        for name, table in self.folds.items():
            missing = set(self.labels) - set(table)
            if missing:
                raise ValueError(f"{self.signal}: fold '{name}' does not map {sorted(missing)}")

    @property
    def rank(self) -> dict[str, int]:
        return {l: i for i, l in enumerate(self.labels)}

    @property
    def digest(self) -> str:
        """Taxonomy digest. Goes into every qualification report.

        Two taxonomies with the same labels in a different order are different
        tasks; two with different names and identical structure are the same one.
        """
        payload = json.dumps({
            "signal": self.signal, "labels": self.labels, "ordered": self.ordered,
            "gates": [dataclasses.asdict(g) for g in self.gates],
            "abstention": dataclasses.asdict(self.abstention),
        }, sort_keys=True)
        return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()[:16]

    def fold_digest(self, name: str) -> str:
        t = self.folds[name]
        return "sha256:" + hashlib.sha256(
            json.dumps([[k, t[k]] for k in self.labels]).encode()).hexdigest()[:16]

    def folded(self, name: str) -> "ClassifierTaskSpec":
        """Derive the task spec for a collapsed taxonomy."""
        t = self.folds[name]
        out = sorted(set(t.values()))
        return ClassifierTaskSpec(
            signal=f"{self.signal}/{name}", labels=out, ordered=self.ordered,
            taxonomy_version=self.taxonomy_version, noise_floor=self.noise_floor,
            text_field=self.text_field, label_field=self.label_field,
            votes_field=self.votes_field,
            description=f"fold '{name}' of {self.signal}: {t}")

    @classmethod
    def load(cls, path) -> "ClassifierTaskSpec":
        p = pathlib.Path(path); raw = p.read_text()
        d = yaml.safe_load(raw) if p.suffix in (".yaml", ".yml") and yaml else json.loads(raw)
        return cls(**d)

    @classmethod
    def builtin(cls, name: str) -> "ClassifierTaskSpec":
        here = pathlib.Path(__file__).parent.parent / "tasks"
        for ext in (".yaml", ".json"):
            p = here / f"{name}{ext}"
            if p.exists(): return cls.load(p)
        avail = sorted(x.stem for x in here.glob("*.*") if not x.stem.startswith("_"))
        raise FileNotFoundError(f"no builtin task '{name}'; available: {avail}")
