# A classifier eval tool for semantic routing — MLflow object model, EvalHub packaging

Derived from 123 measured findings on the llm-d-sc classifiers. The design goal is
not "compute accuracy for a classifier". Accuracy is four lines of code. The goal
is to make the **six specific ways this project nearly shipped a wrong conclusion**
impossible to repeat, by making the controls that caught them mandatory rather
than optional.

## 0. What went wrong, and what the tool must therefore enforce

Every requirement below is traceable to a finding where the naive evaluation gave
the wrong answer.

| near-miss | what happened | enforced by |
|---|---|---|
| accuracy without a baseline | a gate scored 99.65% on an eval with 2 positive rows; another scored 93.78% against a 93.45% baseline | §R1 baseline is a required metric |
| argmax comparison on a gated taxonomy | **7 of 8 interventions** looked like wins and lost at matched containment | §R2 operating-curve comparison |
| operating point fitted to the test set | threshold tuning read 98.14%, held out 97.89%; over-block read 8.87%, held out **17.13%** | §R3 held-out selection |
| single seed | a "+0.42 gain" vanished on the second seed; a published cost figure needed correcting from best-of-seeds | §R4 seed policy |
| taxonomy chosen by intuition | enumerating folds found one **+3.32** better than the hand-picked split | §R5 fold search |
| LLM-judge quality comparison | the judge scored length 70% of the time; a headline finding was **retracted** | §R6 judge controls |

## 1. MLflow object model

```
Experiment          one SIGNAL + TAXONOMY   e.g. "sensitivity/5-tier", "complexity/cx2"
  └─ Run            one trained variant
       params       encoder, corpus manifest (file:sha256[]), recipe, seed,
                    fold_definition (explicit label map), maxlen, class_weighting
       metrics      the contract in §2 — ALL of it, not a subset
       tags         prediction_registered, controls_passed, supersedes, deploy_profile
       artifacts    confusion.json, risk_coverage.csv, matched_containment.csv,
                    per_class.json, model_card.md, eval_manifest.json
  └─ Nested run     one CONTROL (see §3), so a control failure is visible in the UI
                    as a child run rather than buried in a log
```

Two deliberate choices:

**The fold definition is a parameter, not a name.** `route` and `cx2` in this
project were the same fold under two label vocabularies; their error overlap was
Jaccard 1.000 and it took an ensemble diagnostic to notice. Storing the explicit
`{tier -> group}` map makes duplicates detectable by hashing.

**The corpus is a manifest of file hashes.** A relabelling run overwrote 59,582
labels in place and the previous version was unrecoverable. Content-addressed
corpora make that impossible and make "which rows changed" answerable.

## 2. The metric contract — every run emits all of it

A run that emits only accuracy is rejected. This is the core of the tool.

```yaml
required:
  # scale — §R1. Accuracy alone reordered wrongly three times.
  accuracy
  majority_baseline
  lift_over_chance          # accuracy - majority_baseline
  minority_share            # a fold under ~10% is flagged degenerate
  per_class: {recall, precision, support}
  macro_f1
  wilson95                  # n=376 and n=707 evals need intervals, not points

  # labels — is the ceiling the model or the data?
  jury_agreement            # inter-annotator unanimity on this taxonomy
  accuracy_unanimous        # the §55 split that gave OPPOSITE answers on two signals
  accuracy_contested
  label_ceiling             # (correct_unanimous + n_contested) / n

  # operating behaviour — §R2/§R3, all HELD OUT
  risk_coverage: [(coverage, accuracy_heldout)]        # abstention curve
  threshold_cv: {argmax_acc, cv_tuned_acc, chosen_thresholds_histogram}
  confidence_vs_disagreement                           # contested-enrichment ratio

  # deployment
  cpu_p50_ms, cpu_p99_ms    # measured interleaved with comparators, ±15% honest

required_if_ordered_taxonomy_with_gate:
  containment_over_block: [(gate, target, over_block_heldout)]
  released_rate             # fraction of top-tier content emitted to the ALLOW branch
```

`released_rate` exists because of §119: a three-way gate scored **0.99 points
lower** than the binary one and released **0.00% of secrets against 14.88%**. No
accuracy-shaped metric can express that, and it is the number that decided the
recommendation.

## 3. Controls as run-blocking gates

Each is a nested run that must pass, or the parent run is tagged
`controls_failed` and cannot be promoted in the registry.

| control | fails when | evidence |
|---|---|---|
| `baseline_lift` | lift < 2 pts, or minority_share < 6% | §117: a fold scored higher and carried 26.7 pts less information |
| `matched_operating_point` | a claimed win does not hold at matched containment | §113: 7 of 8 rejected |
| `holdout_selection` | any threshold was chosen on scored rows | §107: 8.87% vs 17.13% |
| `seed_stability` | fewer than 2 seeds, or spread > signal noise floor | §66's monotone sweep vs §110's single-seed mirage |
| `corpus_distribution` | training/eval separability > 95%, or prior mismatch > 1.5x unreported | §112: prior matching pays only above 1.5x; §108: off-distribution rows still help |
| `judge_integrity` (LLM-judged evals only) | judge is a contestant, position not randomised, length-win rate > 60%, or a second judge disagrees in sign | §123: retraction |

The seed policy is a rule, not a suggestion: **publish the first seed run, report
all seeds in the card.** Every model in this project shipped that way after a cost
figure had to be corrected from best-of-seeds.

## 4. Taxonomy design, before any training

The highest-leverage tool in the whole project runs in seconds on vote data and
was written after four gates had been built.

```
evalhub taxonomy search --signal complexity --votes gold.jsonl --ordered
```

Enumerates every contiguous fold, reporting jury agreement, minority share, and
predicted accuracy from the fitted agreement relationship. Ranks by agreement,
**rejects** any candidate failing the balance gate.

Two documented limits ship with it, or it will mislead:
- agreement is a **ranking heuristic, not an estimator** (r=0.760, n=7, and it
  under-predicted the winning fold by half)
- it is **blind to failure mode** — it ranked the binary egress gate first, and
  the three-way gate that releases nothing was third

## 5. EvalHub packaging

An eval suite is a declarative artifact anyone can run against their own model:

```yaml
suite: llm-d-sc/sensitivity
taxonomy:
  labels: [PUBLIC, INTERNAL, CONFIDENTIAL, REGULATED, NEVER_EGRESS]
  ordered: true
  gates: [CONFIDENTIAL, REGULATED, NEVER_EGRESS]
datasets:
  - id: entsec-gold
    rows: 707
    provenance: synthetic-enterprise
    separability_from_real_traffic: 0.958      # PUBLISHED, not hidden
    jury: {models: 3, agreement: 0.745}
controls: [baseline_lift, matched_operating_point, holdout_selection, seed_stability]
report:
  sort_by: lift_over_chance                    # NOT accuracy
```

`separability_from_real_traffic: 0.958` is the field I would most want other teams
to copy. The single largest unresolved risk in this project is that sensitivity is
validated entirely on synthetic data 95.8% distinguishable from real traffic — and
nothing in a conventional eval report would surface that. Making it a required
dataset field turns a footnote into a gate.

## 6. What already exists here

| requirement | implementation |
|---|---|
| matched operating point | `harness/roc_match.py`, `egress_compare.py` |
| held-out thresholds | `harness/threshold_cv.py`, `containment_cv.py` |
| risk-coverage | `harness/selective.py` |
| confidence vs disagreement | `harness/abstain_contested.py` |
| label vs model ceiling | `harness/headroom.py` |
| fold search | `harness/fold_search.py` |
| corpus separability | `harness/frozen5.py`, the §64/§77 probes |
| interleaved latency | `harness/latency_bench.py` |
| judge controls | `harness/quality_delta.py` + the §123 control set |

These are roughly 500 lines total. **They caught more errors than every modelling
idea in this project combined** — 7 rejected interventions, 3 reordered result
tables, 1 retracted finding. Productising them is mostly packaging, not research.

## 6b. Terminal states, planes, and artifact identity

**Four verdicts, not three.** `INCOMPLETE` is deliberately distinct from
`REJECTED`: a run missing a required plane has not failed, it has not been
finished. Collapsing them either blocks work that was never evaluated or -- worse
-- lets an unevaluated plane read as an acceptable one. It is `NOT_APPLICABLE`
lifted from the control level to the verdict.

```
QUALIFIED  |  QUALIFIED_WITH_WARNINGS  |  REJECTED  |  INCOMPLETE
```

**Each of the five planes resolves to its own state**, so a reader does not
interpret thirty metrics:

```
EVALUATION PLANES
  PASS  classifier_quality   1 control(s) passed
  PASS  decision_quality     evidence present, no controls configured
  FAIL  runtime_quality      failing control(s): runtime_slo
   --   traffic_validity     no separability measured against production traffic
   --   outcome_value        no outcome evidence supplied
```

A plane with no applicable control AND no required evidence is NOT_EVALUATED,
never PASS.

**Artifact identity is mandatory for runtime qualification.** The finding that
motivated it: a runtime scored 63.67% while the project's own checkpoint scored
81.82% on identical rows, and the first question that raises is not "why is it
worse" but *which model is that*. `ArtifactIdentityControl` reads
`model_revision`, `tokenizer_revision` and `taxonomy_revision` from the service's
own `ClassifyResponse` and compares them to the suite's `expectedIdentity`. It
fails on mismatch, on taxonomy drift, and on **unknown** -- an unidentifiable
artifact cannot be qualified, because the qualification would attribute to
nothing.

**Coverage is the production invariant**, checked before latency:

> A classifier is not qualified at a given traffic level unless the required
> share of requests actually receives a classification.

```yaml
runtime:
  min_classification_coverage: 0.999
```

An unmeasured coverage FAILS. A gateway returning 200s while llm-d-sc is bypassed
is not a successful semantic-routing deployment, and latency percentiles computed
over the requests that survived will look excellent throughout.

## 7. The one thing the tool cannot do

It cannot tell you whether the routing decision is worth making. §122/§123 tried
and the instrument failed: LLM-judge quality comparison is contaminated by length
at 70%, and the model you route *away from* writes 20–35% less, so every naive
pairwise comparison favours the expensive model.

A tool that reports classifier quality while the end-to-end value is unmeasured is
answering the easy question well. That should be stated in the report header, not
discovered later.
