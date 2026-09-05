"""Dataset specification — immutable, content-addressed, provenance-carrying.

Two requirements come directly from things that went wrong:

  IMMUTABILITY. A relabelling run on this project overwrote 59,582 labels in place
  and the previous version was unrecoverable, so "which rows changed" became
  permanently unanswerable. A dataset is identified by the digest of its content.

  PROVENANCE AND TRAFFIC ALIGNMENT. A signal was qualified entirely against data
  95.8% distinguishable from the traffic it would serve. Every figure was correct
  and none was evidence about production. `separability_from_production` is a
  required-to-consider field, not an optional note.
"""
from __future__ import annotations
import dataclasses, hashlib, json, pathlib


@dataclasses.dataclass
class DatasetSpec:
    id: str
    path: str
    role: str = "qualification"       # qualification | contested | traffic | secondary
    provenance: str = "unspecified"   # real-traffic | synthetic | mixed | customer
    label_source: str = "unspecified" # human | llm-jury | heuristic | production-feedback
    jury_models: int | None = None
    jury_agreement: float | None = None
    separability_from_production: float | None = None
    collected_at: str | None = None
    notes: str = ""
    _digest: str | None = None

    def digest(self, root: pathlib.Path | None = None) -> str:
        if self._digest: return self._digest
        p = (pathlib.Path(root) / self.path) if root else pathlib.Path(self.path)
        if not p.exists(): return "sha256:MISSING"
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""): h.update(chunk)
        self._digest = "sha256:" + h.hexdigest()[:16]
        return self._digest

    def manifest(self, root=None) -> dict:
        return {"id": self.id, "digest": self.digest(root), "role": self.role,
                "provenance": self.provenance, "label_source": self.label_source,
                "separability_from_production": self.separability_from_production}
