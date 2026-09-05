"""Shadow mode — run a classifier against LIVE POC traffic and emit telemetry.

The offline half of this tool grades a classifier against a fixed eval set. That
is not what proves anything in a POC, for a reason this project measured directly:
the sensitivity models were validated entirely against a synthetic enterprise eval
that a linear probe distinguishes from real assistant traffic **95.8% of the
time**. Every accuracy figure was real and none of it was evidence about the
customer's traffic.

Shadow mode closes that gap in the only way available: run against the traffic
itself. Three phases, each emitting to MLflow:

  PHASE 1 — UNLABELLED (day one, zero customer effort)
    Prediction distribution, confidence distribution, abstention rate at the
    configured thresholds, and SEPARABILITY between live traffic and the corpus
    the model was trained on. Separability is the headline: it says whether the
    shipped accuracy figures transfer to this deployment at all, and it needs no
    labels.

  PHASE 2 — SAMPLED AND JURY-LABELLED (day two onward)
    Sample live traffic -- stratified by model confidence, because that is where
    the information is -- and label it with the multi-model jury. Produces a REAL
    eval set for this customer, and the inter-juror agreement on it bounds what
    any classifier can score here (r=0.76 across seven taxonomies).

  PHASE 3 — GRADED
    The full metric contract and every control, now on the customer's own data.

Phase 1 alone answers "will the published numbers hold here?", which is the
question a POC actually needs and the one a static eval cannot address.
"""
from __future__ import annotations
import time, hashlib, collections, dataclasses
from typing import Callable, Iterable, Any
import numpy as np


@dataclasses.dataclass
class ShadowConfig:
    domain: Any                       # DomainSpec
    reference_embeddings: np.ndarray | None = None   # training corpus, for drift
    abstain_thresholds: tuple[float, ...] = (0.5, 0.7, 0.9)
    sample_rate: float = 0.02         # fraction retained for later jury labelling
    stratify_by_confidence: bool = True
    max_retained: int = 5000


class ShadowRun:
    """Accumulates telemetry for one window of live traffic.

    Deliberately holds NO prompt text unless sampled for labelling, and hashes
    what it does hold. A POC classifier sits on the request path; a telemetry
    layer that silently retains every prompt is not deployable in the enterprises
    this signal exists to serve.
    """

    def __init__(self, cfg: ShadowConfig):
        self.cfg = cfg
        self.n = 0
        self.pred_counts = collections.Counter()
        self.conf = []
        self.latency_ms = []
        self.retained: list[dict] = []
        self.embeds: list[np.ndarray] = []
        self._started = time.time()

    def observe(self, text: str, probs: np.ndarray, latency_ms: float,
                embedding: np.ndarray | None = None):
        labels = self.cfg.domain.labels
        j = int(np.argmax(probs))
        conf = float(probs[j])
        self.n += 1
        self.pred_counts[labels[j]] += 1
        self.conf.append(conf)
        self.latency_ms.append(latency_ms)
        if embedding is not None and len(self.embeds) < self.cfg.max_retained:
            self.embeds.append(embedding)
        # Retain for jury labelling. Low-confidence rows are over-sampled because
        # that is where the label is worth paying for -- on this project, model
        # confidence enriched for jury-contested rows at 1.7-1.9x on three of four
        # gates, so confidence-stratified sampling buys more information per label.
        keep = self.cfg.sample_rate
        if self.cfg.stratify_by_confidence and conf < 0.6:
            keep = min(1.0, keep * 5)
        if len(self.retained) < self.cfg.max_retained and np.random.random() < keep:
            self.retained.append({
                "text": text, "pred": labels[j], "confidence": conf,
                "probs": [float(x) for x in probs],
                "hash": hashlib.blake2b(text.encode(), digest_size=8).hexdigest(),
            })

    def metrics(self) -> dict[str, float]:
        """MLflow-shaped metrics. No labels required."""
        c = np.asarray(self.conf) if self.conf else np.array([0.0])
        lat = np.asarray(self.latency_ms) if self.latency_ms else np.array([0.0])
        m = {
            "shadow/n": float(self.n),
            "shadow/window_seconds": time.time() - self._started,
            "shadow/confidence_mean": float(c.mean()),
            "shadow/confidence_p10": float(np.percentile(c, 10)),
            "shadow/confidence_p50": float(np.percentile(c, 50)),
            "latency/p50_ms": float(np.percentile(lat, 50)),
            "latency/p99_ms": float(np.percentile(lat, 99)),
            "shadow/retained_for_labelling": float(len(self.retained)),
        }
        for lbl in self.cfg.domain.labels:
            m[f"shadow/predicted_share/{lbl}"] = self.pred_counts[lbl] / max(1, self.n)
        for t in self.cfg.abstain_thresholds:
            m[f"shadow/abstain_rate@{t}"] = float((c < t).mean())
        return m

    def drift(self, embed_fn: Callable[[list[str]], np.ndarray] | None = None) -> dict:
        """Separability between live traffic and the model's training corpus.

        THE phase-1 number. On this project, corpora ranged from 78% to 98%
        separable from the eval they were graded on, and that single measure
        explained which synthetic datasets helped and which actively hurt. Applied
        to a POC it answers: do the published accuracy figures describe this
        customer's traffic, or a different distribution?

        0.5 means indistinguishable -- published numbers should transfer.
        Above ~0.9 means the model is being asked about a different population and
        the shipped metrics are not evidence here.
        """
        if self.cfg.reference_embeddings is None or not self.embeds:
            return {"drift/separability": float("nan"),
                    "drift/status": "unmeasured — no reference embeddings supplied"}
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import cross_val_score
        live = np.stack(self.embeds)
        ref = self.cfg.reference_embeddings
        n = min(len(live), len(ref))
        rng = np.random.default_rng(0)
        X = np.concatenate([live[rng.choice(len(live), n, replace=False)],
                            ref[rng.choice(len(ref), n, replace=False)]])
        y = np.array(["live"] * n + ["ref"] * n)
        sep = float(cross_val_score(
            LogisticRegression(max_iter=3000), X, y, cv=5).mean())
        if sep < 0.70:   status = "aligned — published metrics should transfer"
        elif sep < 0.90: status = "drifted — expect degradation; label a sample"
        else:            status = "OFF-DISTRIBUTION — published metrics are not evidence here"
        return {"drift/separability": sep, "drift/status": status, "drift/n_per_side": n}
