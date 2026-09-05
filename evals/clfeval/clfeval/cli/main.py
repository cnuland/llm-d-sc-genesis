from __future__ import annotations
import argparse, json, pathlib, sys
import numpy as np


def _adapter(uri: str, task):
    """Resolve --classifier into an adapter. Scheme selects the PLANE."""
    from ..adapters import HuggingFaceAdapter, LlmDScAdapter
    if uri.startswith("grpc://"):
        return LlmDScAdapter(uri[len("grpc://"):], task)
    if uri.startswith(("hf://", "file://")):
        uri = uri.split("://", 1)[1]
    return HuggingFaceAdapter(uri, task)


def cmd_run(a) -> int:
    from ..specs import EvalSuite
    from ..runner import qualify, load_rows
    from ..sinks import MlflowLedger
    root = pathlib.Path(a.root)
    suite = EvalSuite.load(a.suite)
    rows = load_rows(suite.task, suite.datasets, root)
    if not rows:
        print(f"no rows loaded — check dataset paths relative to --root {root}", file=sys.stderr)
        return 2
    adapter = _adapter(a.classifier, suite.task)
    sep = next((d.separability_from_production for d in suite.datasets
                if d.role == "qualification"), None)
    report = qualify(adapter=adapter, task=suite.task, datasets=suite.datasets,
                     rows=rows, root=root, suite=suite.name,
                     seed_scores=[float(x) for x in a.seed_score] or None,
                     noise_floor=a.noise_floor, floor_measured_on=a.floor_from,
                     traffic={"separability": sep}, slo=suite.runtime_slo,
                     measure_runtime=a.runtime, controls=suite.active_controls(),
                     expected_identity=suite.expected_identity,
                     required_planes=suite.required_planes)

    missing = suite.check_metric_contract(report.metrics)
    if missing:
        print(f"SUITE CONTRACT VIOLATED — required metric(s) not produced: {missing}",
              file=sys.stderr)

    print(report.render())
    decision = suite.promotion.decide(report)
    print(f"\nPROMOTION: {decision['decision']}")
    for r in decision["reasons"]: print(f"  {r}")

    if a.mlflow:
        rid = MlflowLedger(f"clfeval/{suite.task.signal}",
                           tracking_uri=a.mlflow).log_qualification(
            report, run_name=a.run_name or pathlib.Path(a.classifier).name,
            extra_params={"suite_digest": suite.digest})
        print(f"\nMLflow run: {rid}")
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(report.to_dict(), indent=1, default=str))
        print(f"report written: {a.out}")
    # exit code is the CI contract
    return 0 if decision["decision"].startswith("PROMOTE") else 1


def cmd_taxonomy(a) -> int:
    """Enumerate contiguous folds and rank them, BEFORE any model is built.

    On this project four gates were built by hand before this was run, and it then
    found a fold 3.32 points better than the hand-picked one. It costs seconds.
    """
    from ..specs import ClassifierTaskSpec
    import itertools, collections
    task = (ClassifierTaskSpec.builtin(a.task) if not pathlib.Path(a.task).exists()
            else ClassifierTaskSpec.load(a.task))
    rows = [json.loads(l) for f in a.votes for l in open(f)]
    rows = [r for r in rows if isinstance(r.get(task.votes_field), list) and r[task.votes_field]]
    if not rows:
        print("no rows with vote data — fold ranking needs multi-juror labels", file=sys.stderr)
        return 2
    n = len(task.labels)
    print(f"{task.signal}: {len(rows)} rows with votes, {n} labels "
          f"({'ordered' if task.ordered else 'unordered'})\n")
    print(f"  {'fold':<44}{'groups':>7}{'agreement':>11}{'minority':>10}  verdict")
    out = []
    for k in range(1, n):
        for cuts in itertools.combinations(range(1, n), k):
            b = [0] + list(cuts) + [n]
            gid = {t: g for g, (i, j) in enumerate(zip(b, b[1:])) for t in task.labels[i:j]}
            agr = np.mean([len({gid[v] for v in r[task.votes_field] if v in gid}) == 1
                           for r in rows])
            c = collections.Counter(gid[r[task.label_field]] for r in rows
                                    if r.get(task.label_field) in gid)
            minor = min(c.values())/sum(c.values()) if c else 0
            name = " | ".join("+".join(x[:4] for x in task.labels[i:j])
                              for i, j in zip(b, b[1:]))
            out.append((agr, minor, len(b)-1, name))
    for agr, minor, g, name in sorted(out, reverse=True)[:a.top]:
        # agreement generates the candidate; BALANCE decides whether it counts.
        # A fold scoring higher on agreement while carrying far less information
        # is the specific trap this ordering exists to avoid.
        v = "DEGENERATE — accuracy would be mostly free" if minor < 0.06 else "ok"
        print(f"  {name:<44}{g:7d}{agr:10.1%}{minor:9.1%}  {v}")
    print("\n  ranked by jury agreement; agreement is a RANKING HEURISTIC, not an "
          "estimator,\n  and it is blind to failure mode — a fold whose errors are "
          "cheaper may rank lower.")
    return 0


def cmd_compare(a) -> int:
    from ..specs import EvalSuite
    from ..reports import compare, QualificationReport
    suite = EvalSuite.load(a.suite)
    def _load(p):
        d = json.loads(pathlib.Path(p).read_text())
        d.pop("report_digest", None); d.pop("unpinned_inputs", None)
        return QualificationReport(**d)
    rep = compare(suite, _load(a.champion), _load(a.candidate))
    print(rep.render())
    return 0 if rep.decision["decision"].startswith("PROMOTE") else 1


def cmd_suite(a) -> int:
    from ..specs import EvalSuite
    s = EvalSuite.load(a.suite)
    print(f"# digest {s.digest}\n# task digest {s.task.digest}")
    print(s.to_yaml())
    s.active_controls()
    print(f"# {len(s.controls)} controls resolve; "
          f"{len(s.required_metrics)} required metrics")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser("clfeval", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="qualify a classifier against a suite")
    r.add_argument("--suite", required=True)
    r.add_argument("--classifier", required=True,
                   help="path, hf://path, or grpc://host:port (runtime plane)")
    r.add_argument("--root", default=".")
    r.add_argument("--mlflow", default=None, help="tracking URI")
    r.add_argument("--run-name", default=None)
    r.add_argument("--seed-score", action="append", default=[],
                   help="repeat once per seed; enables seed_stability")
    r.add_argument("--noise-floor", type=float, default=None)
    r.add_argument("--floor-from", default=None,
                   help="config the floor was measured on — a floor is a property "
                        "of a configuration, not a signal")
    r.add_argument("--runtime", action="store_true",
                   help="measure per-request latency and coverage")
    r.add_argument("--out", default=None)
    r.set_defaults(fn=cmd_run)

    t = sub.add_parser("taxonomy", help="enumerate and rank folds before building")
    t.add_argument("--task", required=True)
    t.add_argument("--votes", nargs="+", required=True)
    t.add_argument("--top", type=int, default=8)
    t.set_defaults(fn=cmd_taxonomy)

    c = sub.add_parser("compare", help="champion vs candidate (CI regression)")
    c.add_argument("--suite", required=True)
    c.add_argument("--champion", required=True)
    c.add_argument("--candidate", required=True)
    c.set_defaults(fn=cmd_compare)

    s = sub.add_parser("suite", help="validate and print a suite document")
    s.add_argument("--suite", required=True)
    s.set_defaults(fn=cmd_suite)

    a = p.parse_args(argv)
    return a.fn(a)
