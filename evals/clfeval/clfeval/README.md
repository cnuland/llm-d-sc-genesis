# clfeval — classifier qualification framework

Not an eval library. A **qualification system**: it answers whether a classifier
revision is trustworthy enough for THIS taxonomy, THIS workload, THIS traffic,
THIS runtime and THIS environment — and produces the evidence that proves it.

```
clfeval run --suite sensitivity-production-v1.yaml \
            --classifier grpc://llm-d-sc:50051 --runtime --mlflow $MLFLOW_URI
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

Planes are reported separately and a report NAMES the ones it did not evaluate.
`outcome_value` is usually unevaluated and says so, rather than being omitted.

## Why the controls exist

Every control is a regression against a real incident:

| control | incident |
|---|---|
| `baseline_lift` | a gate scored 99.65% on an eval holding 2 positive rows |
| `matched_operating_point` | 7 of 8 interventions won at argmax and lost at matched containment |
| `holdout_integrity` | over-block read 8.87% fitted, 17.13% held out |
| `seed_stability` | a "+0.42 gain" vanished on the second seed |
| `traffic_alignment` | a signal qualified against data 95.8% distinguishable from its traffic |
| `runtime_slo` | a 96%-accurate classifier answered zero requests for 32 hours |
| `corpus_immutability` | a relabel overwrote 59,582 labels in place, unrecoverably |
| `judge_integrity` | a headline retracted; the judge picked the longer answer 70.2% of the time |
| `calibration` | a gate was confidently WRONG on jury-contested rows, so no threshold helped |

Four states — PASS / WARN / FAIL / NOT_APPLICABLE — because "unmeasured" must
never render as "passed".

## Layout

```
specs/      ClassifierTaskSpec, DatasetSpec, EvalSuite, PromotionPolicy
adapters/   HuggingFace (model plane), llm-d-sc gRPC (runtime plane), callable/rules
metrics/    classification, calibration, gates, selective, runtime
controls/   nine controls, four states, promotion-blocking
traffic/    shadow mode for POC traffic (unlabelled -> sampled -> graded)
sinks/      MLflow ledger (degrades to JSONL), nested control runs
reports/    QualificationReport (immutable digest), champion-vs-candidate
cli/        run | compare | taxonomy | suite
```

## Built-in tasks

`complexity`, `cost`, `sensitivity`. Any other taxonomy is a YAML file —
`specs/task.py` knows nothing about what a "tier" means.

## Status

Model plane, decision plane, traffic plane and the MLflow ledger are validated
end to end. The runtime plane is validated against a live llm-d-sc service. Shadow
mode is written and has not yet run against production traffic.
