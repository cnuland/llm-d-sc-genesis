"""MLflow as the EVALUATION LEDGER, not a metrics sink.

The distinction is provenance. A sink stores numbers; a ledger stores a claim and
everything needed to reproduce or refute it. Every run carries the digests of the
classifier, taxonomy, datasets, runtime and eval code, so a figure six months old
can be re-derived or shown to be unreproducible.

Controls are NESTED RUNS rather than tags. A failed control has to be as visible
as a metric, because every failure this framework catches produced a number that
looked publishable.
"""
from __future__ import annotations
import json, os, pathlib, subprocess, time

REQUIRED = {"accuracy", "majority_baseline", "lift_over_chance", "minority_share", "n"}

# MLflow permits only [alnum _ - . space /] in metric names. Sanitising happens
# HERE, at the boundary, rather than by renaming the metrics: `selective/
# accuracy@0.95` reads correctly in a report and in code, and a storage backend's
# character set should not dictate the vocabulary of the framework.
_SAFE = str.maketrans({"@": "_at_", "(": "", ")": "", ",": "_", "%": "pct",
                       "[": "", "]": "", ":": "_"})


def _safe_name(k: str) -> str:
    return k.translate(_SAFE)


def eval_code_revision() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5,
                             cwd=pathlib.Path(__file__).resolve().parents[2])
        if out.returncode == 0:
            return "git:" + out.stdout.strip()
    except Exception:
        pass
    return "unversioned"


class MlflowLedger:
    def __init__(self, experiment: str, tracking_uri: str | None = None,
                 fallback_dir: str = "clfeval-runs"):
        self.experiment = experiment
        self.fallback = pathlib.Path(fallback_dir)
        self._mf = None
        uri = tracking_uri or os.environ.get("MLFLOW_TRACKING_URI")
        try:
            import mlflow
            if uri: mlflow.set_tracking_uri(uri)
            mlflow.set_experiment(experiment)
            self._mf = mlflow
            self.uri = mlflow.get_tracking_uri()
        except Exception as e:
            self.fallback.mkdir(parents=True, exist_ok=True)
            self.uri = f"jsonl://{self.fallback}"
            print(f"[clfeval] MLflow unavailable ({type(e).__name__}); "
                  f"ledger falling back to {self.fallback}/")

    def log_qualification(self, report, *, run_name: str, extra_params=None):
        m = {k: v for k, v in report.metrics.items() if isinstance(v, (int, float))}
        missing = REQUIRED - set(m)
        if missing:
            raise ValueError(
                f"metric contract violated: {sorted(missing)} missing. Accuracy "
                f"without a baseline is not a result.")
        params = {
            "classifier_revision": report.classifier_revision,
            "taxonomy_digest": report.taxonomy_digest,
            "runtime_revision": report.runtime_revision or "not-evaluated",
            "eval_code_revision": report.eval_code_revision or eval_code_revision(),
            "suite": report.suite, "signal": report.signal,
            "dataset_manifest": json.dumps(report.dataset_manifest)[:480],
            # per-plane status as params, so a run can be filtered in the UI by
            # "which planes actually passed" rather than by a single verdict
            **{f"plane.{p['plane']}": p["status"] for p in (report.planes or [])},
            **(extra_params or {}),
        }
        planes = {p["plane"]: p["status"] for p in (report.planes or [])}
        tags = {"verdict": report.verdict, "report_digest": report.digest,
                "planes_not_evaluated": ",".join(
                    k for k, v in planes.items() if v == "NOT_EVALUATED") or "none",
                "primary_metric": "lift_over_chance",
                "reproducible": str(not report.unpinned),
                "unpinned_inputs": ",".join(report.unpinned) or "none"}
        if not self._mf:
            rec = {"ts": time.time(), "experiment": self.experiment, "run": run_name,
                   "params": params, "metrics": m, "tags": tags,
                   "report": report.to_dict()}
            with open(self.fallback / f"{self.experiment.replace('/','_')}.jsonl", "a") as f:
                f.write(json.dumps(rec, default=str) + "\n")
            return None
        mf = self._mf
        with mf.start_run(run_name=run_name) as run:
            mf.set_tags(tags)
            mf.log_params({k: str(v)[:500] for k, v in params.items()})
            mf.log_metrics({_safe_name(k): float(v) for k, v in m.items() if v == v})
            for c in report.controls.get("controls", []):
                with mf.start_run(run_name=f"control:{c['control']}", nested=True):
                    mf.set_tags({"status": c["status"], "detail": c["detail"][:480],
                                 "blocking": str(c["blocking"])})
                    mf.log_metric("passed", 1.0 if c["status"] == "PASS" else 0.0)
            p = pathlib.Path(f"/tmp/qualification-{report.digest[7:19]}.json")
            p.write_text(json.dumps(report.to_dict(), indent=1, default=str))
            mf.log_artifact(str(p))
            txt = pathlib.Path(f"/tmp/qualification-{report.digest[7:19]}.txt")
            txt.write_text(report.render()); mf.log_artifact(str(txt))
            return run.info.run_id

    def log_shadow(self, *, run_name, params, metrics, traffic_report, tags=None):
        """Phase-1 POC telemetry. Exempt from the metric contract by design:
        shadow mode answers 'do the offline figures transfer here?' with no labels."""
        t = {**(tags or {}), "mode": "shadow",
             "transfer_confidence": str(traffic_report.get("transfer_confidence", "UNKNOWN"))}
        m = {**metrics, **{k: v for k, v in traffic_report.items()
                           if isinstance(v, (int, float))}}
        if not self._mf:
            with open(self.fallback / f"{self.experiment.replace('/','_')}.jsonl", "a") as f:
                f.write(json.dumps({"ts": time.time(), "run": run_name, "kind": "shadow",
                                    "params": params, "metrics": m, "tags": t},
                                   default=str) + "\n")
            return None
        with self._mf.start_run(run_name=run_name) as run:
            self._mf.set_tags(t)
            self._mf.log_params({k: str(v)[:500] for k, v in params.items()})
            self._mf.log_metrics({_safe_name(k): float(v) for k, v in m.items() if v == v})
            return run.info.run_id
