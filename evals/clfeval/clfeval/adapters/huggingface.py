"""Local Hugging Face sequence-classification adapter. MODEL plane."""
from __future__ import annotations
import hashlib, pathlib
import numpy as np
from .base import ClassifierAdapter


class HuggingFaceAdapter(ClassifierAdapter):
    plane = "model"

    def __init__(self, path: str, task, maxlen: int = 256):
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        import torch
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(path)
        self.m = AutoModelForSequenceClassification.from_pretrained(path).eval()
        native = [self.m.config.id2label[i] for i in range(self.m.config.num_labels)]
        missing = set(task.labels) - set(native)
        if missing:
            raise ValueError(f"model emits {native}; task expects {task.labels} "
                             f"(missing {sorted(missing)})")
        # Column alignment is not cosmetic: two models in this project were the
        # same fold under different label vocabularies and were briefly treated
        # as separate results.
        self.idx = [native.index(l) for l in task.labels]
        self.maxlen = maxlen
        self.revision = self._digest(path)

    @staticmethod
    def _digest(path: str) -> str:
        p = pathlib.Path(path)
        h = hashlib.sha256()
        for f in sorted(p.glob("*.safetensors")) + sorted(p.glob("*.bin")):
            with open(f, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""): h.update(chunk)
        return "sha256:" + h.hexdigest()[:16] if h.hexdigest() else "sha256:MISSING"

    def predict_proba(self, texts):
        out = []
        with self.torch.no_grad():
            for i in range(0, len(texts), 64):
                e = self.tok(texts[i:i+64], truncation=True, max_length=self.maxlen,
                             padding=True, return_tensors="pt")
                out.append(self.torch.softmax(self.m(**e).logits, -1).numpy()[:, self.idx])
        return np.concatenate(out)
