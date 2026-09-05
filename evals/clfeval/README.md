# clfeval — classifier qualification framework

Not an accuracy harness. A **qualification system**: it answers whether a
classifier revision is trustworthy enough for this taxonomy, this workload, this
traffic, this runtime and this environment — and produces the evidence.

It evaluates **both** the classifier artifact and the classifier that llm-d-sc is
actually serving, which are not the same thing. On first use against a live
deployment it found a **32-hour outage** behind a healthy-looking model, and a
deployed classifier with **+4.50 lift over chance** where the corresponding
checkpoint scores **+25.42** on identical rows.

## Quick start

```bash
pip install -e evals/clfeval                     # + [hf] [mlflow] [grpc] extras

# qualify a checkpoint (model plane)
clfeval run --suite evals/clfeval/clfeval/suites/complexity-dev-v1.yaml \
            --classifier /path/to/model --root .

# qualify what is ACTUALLY DEPLOYED (runtime plane)
clfeval run --suite evals/clfeval/clfeval/suites/complexity-runtime-v1.yaml \
            --classifier grpc://llm-d-sc.llm-d-sc.svc:50051 \
            --runtime --mlflow $MLFLOW_TRACKING_URI

# choose a taxonomy BEFORE building a classifier for it
clfeval taxonomy --task complexity --votes gold.jsonl contested.jsonl
```

Exit code is the CI contract: non-zero when the promotion policy rejects.

## Five evaluation planes

| plane | question |
|---|---|
| classifier quality | does it classify correctly? |
| decision quality | does the taxonomy/gate/threshold give the right ACTION? |
| runtime quality | can the serving path deliver it within SLO? |
| traffic validity | does the corpus resemble the traffic it will serve? |
| outcome value | does using it improve the declared objective? |

Each resolves to PASS / WARN / FAIL / NOT_EVALUATED. A plane that was not
exercised says so — it never reads as a pass.

```
EVALUATION PLANES
  PASS  classifier_quality   1 control(s) passed
  PASS  decision_quality     evidence present, no controls configured
  FAIL  runtime_quality      failing control(s): runtime_slo
   --   traffic_validity     no separability measured against production traffic
   --   outcome_value        no outcome evidence supplied
```

Terminal states: `QUALIFIED` / `QUALIFIED_WITH_WARNINGS` / `REJECTED` /
`INCOMPLETE`. INCOMPLETE is distinct on purpose — a run missing a required plane
is unfinished, not failed.

## Ten controls, each a regression against a real incident

| control | incident it prevents |
|---|---|
| `baseline_lift` | a gate scored 99.65% on an eval holding 2 positive rows |
| `matched_operating_point` | 7 of 8 interventions won at argmax and lost at matched containment |
| `holdout_integrity` | over-block read 8.87% fitted, 17.13% held out |
| `seed_stability` | a "+0.42 gain" vanished on the second seed |
| `traffic_alignment` | a signal qualified on data 95.8% distinguishable from its traffic |
| `runtime_slo` | a 96%-accurate classifier answered zero requests for 32 hours |
| `artifact_identity` | "which model is actually deployed?" had no answer in the evidence |
| `corpus_immutability` | a relabel overwrote 59,582 labels in place, unrecoverably |
| `judge_integrity` | a finding retracted; the judge picked the longer answer 70.2% of the time |
| `calibration` | a gate was confidently WRONG on contested rows, so no threshold helped |

**The production invariant**, checked before latency:

> A classifier is not qualified at a given traffic level unless the required share
> of requests actually receives a classification.

A gateway returning 200s while llm-d-sc is bypassed is not a successful
semantic-routing deployment, and latency percentiles over the surviving requests
look excellent throughout.

## Adding your own classifier task

`complexity`, `cost` and `sensitivity` ship in `clfeval/tasks/`. Nothing in the
evaluator knows what a "tier" means — intent, safety, tool-selection, model
affinity or a customer taxonomy is a YAML/JSON document:

```yaml
signal: my_signal
labels: [LOW, MEDIUM, HIGH]
ordered: true
gates: [{at: HIGH, action: block}]
noise_floor: 0.01
folds:
  escalate: {LOW: NO, MEDIUM: NO, HIGH: YES}
```

## Layout

```
clfeval/
  specs/      ClassifierTaskSpec, DatasetSpec, EvalSuite, PromotionPolicy
  adapters/   HuggingFace (model plane), llm-d-sc gRPC (runtime plane), callable/rules
  metrics/    classification, calibration, gates, selective, runtime
  controls/   ten controls, four states, promotion-blocking
  traffic/    shadow mode for POC traffic
  sinks/      MLflow ledger (degrades to JSONL), controls as nested runs
  reports/    QualificationReport (immutable digest), champion-vs-candidate
  cli/        run | compare | taxonomy | suite
  suites/     EvalHub-shaped declarative suites
  tasks/      built-in taxonomies
```

`DESIGN.md` records the reasoning. The research it was derived from — 126 numbered
findings, including the two thirds that did not work — is at
https://github.com/cnuland/llm-d-sc-v02-classifier-optimizations

## Status

| surface | state |
|---|---|
| CLI (`run`, `compare`, `taxonomy`, `suite`) | validated |
| Python API | validated |
| MLflow ledger | validated against a live tracking server |
| Model plane / decision plane | validated |
| Runtime plane (llm-d-sc gRPC) | validated against a live service |
| Traffic validity | measurable, NOT_EVALUATED on every run so far |
| Outcome value | not measurable offline; reports as NOT_EVALUATED |
| Shadow-mode collector / `clfeval observe` | **not built** |

21 tests: `pytest evals/clfeval/tests`
