"""llm-d-sc gRPC adapter — the RUNTIME plane, and the canonical qualification path.

This is what users deploy. The service owns tokenization, the forward pass,
batching and backpressure, and none of that is visible when a checkpoint is
scored directly. The gap is not theoretical: the deployment this adapter was
first pointed at had a ~96% model-plane score and had answered zero requests for
32 hours, because its init container could not survive a restart.

The wire contract makes three things possible that a local adapter cannot do:

  PROVENANCE FROM THE SERVICE. ClassifyResponse carries model_revision,
  tokenizer_revision and taxonomy_revision. The qualification report therefore
  records what the RUNTIME says it is running, rather than what the caller
  believes it deployed. Those disagreeing is a finding, not a nuisance.

  ABSTENTION AS A FIRST-CLASS STATUS. ABSTAIN is distinct from a low-confidence
  OK and from UNAVAILABLE. Collapsing them would hide exactly the behaviour an
  abstention policy is meant to govern.

  COVERAGE. UNAVAILABLE and transport errors are counted rather than dropped, so
  `classification_coverage` measures what fraction of requests actually received
  a classification. A classifier that is not answering is not fast.
"""
from __future__ import annotations
import time
import numpy as np
from .base import ClassifierAdapter


class LlmDScAdapter(ClassifierAdapter):
    plane = "runtime"

    def __init__(self, target: str, task, timeout_s: float = 5.0,
                 signal: str | None = None, channel=None):
        import grpc
        from ._generated import classify_pb2 as pb, classify_pb2_grpc as pbg
        self.pb, self.task, self.timeout_s = pb, task, timeout_s
        self.signal = signal or task.signal.split("/")[0]
        self.target = target
        self._ch = channel or grpc.insecure_channel(target)
        self._stub = pbg.ClassifyStub(self._ch)
        self.revision = "unknown"
        self.runtime_revision = f"llm-d-sc@{target}"
        self.taxonomy_revision_reported: str | None = None
        self.abstained = 0
        self.unavailable = 0
        self._missing_labels = None   # labels the service never scores
        self._probe()

    def _probe(self):
        """Read the service's self-reported provenance from a single call."""
        try:
            r = self._stub.Classify(
                self.pb.ClassifyRequest(request_id="clfeval-probe", session_id="probe",
                                        context="probe", signals=[self.signal]),
                timeout=self.timeout_s)
            if r.model_revision:
                self.revision = f"model:{r.model_revision}"
            self.runtime_revision = (
                f"llm-d-sc@{self.target}"
                f" model={r.model_revision or '?'}"
                f" tokenizer={r.tokenizer_revision or '?'}"
                f" classifier_id={r.classifier_id or '?'}")
            self.taxonomy_revision_reported = r.taxonomy_revision or None
        except Exception as e:
            self.runtime_revision = f"llm-d-sc@{self.target} (probe failed: {type(e).__name__})"

    def _one(self, text: str, i: int) -> np.ndarray | None:
        r = self._stub.Classify(
            self.pb.ClassifyRequest(request_id=f"clfeval-{i}", session_id="clfeval",
                                    context=text, signals=[self.signal]),
            timeout=self.timeout_s)
        if r.status == self.pb.ABSTAIN:
            self.abstained += 1
            return None
        if r.status == self.pb.UNAVAILABLE:
            self.unavailable += 1
            raise RuntimeError("UNAVAILABLE")
        scores = {s.label: float(s.score) for s in r.ranked}
        missing = [l for l in self.task.labels if l not in scores]
        v = np.array([scores.get(l, -np.inf) for l in self.task.labels], dtype=float)
        if np.isneginf(v).all():
            raise RuntimeError("service returned no scores for any task label")
        # llm-d-sc returns COSINE SIMILARITIES, which are negative-capable: a real
        # response looks like SIMPLE 3.395 / MEDIUM -0.251 / COMPLEX -0.773. Sum
        # normalisation is invalid on that range -- it yields values above 1 and,
        # when the scores sum to <= 0, silently collapses the row to uniform.
        #
        # It fails SILENTLY in the worst way: argmax survives any monotone
        # transform, so accuracy looks correct while calibration, risk-coverage and
        # every abstention threshold are computed on nonsense. Softmax is the
        # correct map from similarities to a distribution and is monotone, so it
        # changes no argmax while making the confidence surface meaningful.
        v = v - np.max(v[np.isfinite(v)])
        e = np.where(np.isfinite(v), np.exp(v), 0.0)
        if self._missing_labels is None and missing:
            self._missing_labels = missing
        return e / e.sum()

    @property
    def taxonomy_mismatch(self) -> list[str] | None:
        """Labels in the task spec that the service never returns.

        A silent taxonomy drift between the spec being qualified and the taxonomy
        the runtime actually serves. Surfaced rather than absorbed.
        """
        return self._missing_labels

    def predict_proba(self, texts: list[str]) -> np.ndarray:
        out = []
        for i, t in enumerate(texts):
            v = self._one(t, i)
            out.append(v if v is not None
                       else np.full(len(self.task.labels), 1.0 / len(self.task.labels)))
        return np.stack(out)

    def predict_with_telemetry(self, texts):
        """Per-request latency and true coverage through the serving path."""
        lat, rows, ok, err = [], [], 0, 0
        self.abstained = self.unavailable = 0
        for i, t in enumerate(texts):
            t0 = time.perf_counter()
            try:
                v = self._one(t, i)
                lat.append((time.perf_counter() - t0) * 1000)
                if v is None: rows.append(None)          # ABSTAIN: no prediction
                else: rows.append(v); ok += 1
            except Exception as e:
                err += 1; rows.append(None)
                if "RESOURCE_EXHAUSTED" in str(e).upper(): self.unavailable += 1
        from ..metrics.runtime import summarise
        keep = [i for i, r in enumerate(rows) if r is not None]
        P = np.stack([rows[i] for i in keep]) if keep else np.zeros((0, len(self.task.labels)))
        tel = summarise(lat, len(texts), ok, self.unavailable, err)
        tel["abstain_rate"] = self.abstained / max(1, len(texts))
        tel["_kept_indices"] = keep
        return P, tel
