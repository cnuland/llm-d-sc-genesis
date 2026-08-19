# llm-d-sc-genesis

**The agentic software development lifecycle (ASDLC) scaffolding for building llm-d-sc** — the
low-latency Rust semantic-classifier runtime that will eventually merge into a future upstream.

This repository contains **both the process and the emerging product**. The 0.1 MVP is at
14/14 LOCAL-GREEN (unit + local-integration evidence, each independently reviewed) and
**0/14 PROMOTION-GREEN** — integration/system/performance evidence does not exist yet, and
`hack/spec-check --promotion` refuses to call 0.1 complete until it does. Run
`./hack/spec-check 0.1-mvp` for the live ledger, including every pending test ID.

Classification is REAL as of the taxonomy slice: three classifier definitions
(`complexity`, `cost`, `sensitivity`) are compiled into the binary, ranked against
labelled anchors embedded by the resident model, and a custom definition can be
supplied by path without a rebuild. Try it:

```
./hack/fetch-model --classifier complexity
./target/release/llm-d-sc-classify "Prove that the square root of two is irrational."
```

Previously-tracked integration gaps, all now closed with executed-test evidence:
1. CLOSED - the model forward runs on a dedicated executor thread pool off the
   Tokio network workers (`I-090`/`I-091` prove real parallelism, not just admission).
2. CLOSED - the production Candle path runs through the shared `ServiceCore`, so
   the result cache and metrics are on the real path.
3. CLOSED - `CandleClassifier` ranks against a real taxonomy and reports that
   taxonomy's revisions (`I-072`/`I-073`/`I-074`); synthetic prototypes are now
   confined to weight-free tests.

Open work is tracked in `upstream-staging/docs/known-gaps.md`.

> **Slow and Steady Wins the Race.**
> Do not automate autonomy. Automate evidence.

## Model roles (adversarial by design)

| Responsibility | Component | Authority |
|---|---|---|
| Specification & research | Maintainer + research model | Writes `specs/<id>/`; no implementation authority |
| Implementation & integration tests | **DeepSeek-V4 (local, via OpenCode)** | Edits worktree, runs tests, prepares commits — never pushes |
| Independent review / eval gate | **Claude Fable 5** | PASS / CHANGES / ESCALATE — may not edit the patch |
| State transitions, git, CI | **Deterministic scripts** (`pipeline/`, `hack/`) | Mechanical only |
| Final merge | **The maintainer (human)** | Only party who merges `main` |

The worker and the reviewer are deliberately different models from different vendors.
DeepSeek never reviews DeepSeek. Fable never edits the code it reviews. No model holds a
GitHub credential — a deterministic publisher performs every git operation after review PASS.

## Lifecycle state machine (code, not an LLM)

```
IDEA → RESEARCHED → SPECIFIED → TEST-DESIGNED → IMPLEMENTING → LOCAL-GREEN
     → FABLE-REVIEWED → PUSHED → GITHUB-CI-GREEN → PROD-LIKE-VALIDATED
     → MAINTAINER-APPROVED → MERGED → OBSERVED/LEARNED
```

Models operate *inside* states. They do not invent states or waive gates. Order of
authority: **compiler/types → deterministic tests → security/invariants → behavioral
evals → Fable review → maintainer judgment.** Fable cannot overrule a failing test.

## Repository map

```
AGENTS.md                    worker engineering contract (OpenCode reads this)
CONTRIBUTING.md              upstream charter + hard bans
specs/                       one directory per change/version (research/spec/design/
                             test-plan/acceptance + evidence/); 0.1-mvp is the active spec,
                             0.20-0.30 are phase stubs (see docs/VERSIONS.md)
  TEMPLATE/                  copy to start a new spec
.agent/state/current.md      working memory (aggressively rewritten, not history)
.agent/memory/lessons/       durable episodic lessons (evidence-cited, PR-reviewed)
.opencode/skills/            exactly three skills: test-impact, spec-check, review-prep
hack/                        deterministic scripts: build, verify, test-all, test-impact,
                             spec-check, publish-reviewed
pipeline/                    the conductor: state machine + watchdog + gates + review bundle
evals/                       eval.yaml, datasets, and the Fable reviewer rubric
.github/workflows/           fast-ci (every push), reviewer + validation (promotion)
docs/                        SDD.md, TDD.md, VERSIONS.md (0.x roadmap), PROCESS_REVIEW.md,
                             architecture notes
tests/                       TEST_MATRIX.md (evidence-anchored test IDs), HOMELAB.md,
                             GITHUB_ACTIONS.md, DUMMY_GATEWAY.md, fixtures/modelcar/
```

## The conducted loop (home lab)

```
spec approved                                   (maintainer)
  → pipeline/conduct.sh <spec-id>               (deterministic driver)
      → DSV4 turn: failing test                 (OpenCode, watchdogged)
      → DSV4 turn: minimal implementation
      → hack/verify                             (local gate — must be GREEN)
      → pipeline/review-bundle.sh               (evidence for Fable)
      → Fable review                            (PASS / CHANGES / ESCALATE)
      → hack/publish-reviewed                   (deterministic commit + push)
  → GitHub fast-ci on agent/<id> branch
  → promotion: full validation + maintainer merge
```

Small pushes are **logical slices** — one coherent, independently testable claim about the
software — never clock intervals or line counts.

## What is banned (see CONTRIBUTING.md for the full charter)

No agent merges main. No worker waives a failing test. No reviewer edits the patch.
No model holds git credentials. No skill without an eval justifying it. No memory treated
as truth without repository evidence. No unrelated refactoring bundled into a patch.

## Target system context (for orientation only — NOT built here yet)

llm-d-sc is the semantic-classification component of a three-part system:
**the AI Gateway** (intelligent routing — github.com/gateway-proxy/gateway) consumes ranked
domain/complexity/sensitivity signals from **llm-d-sc** (this project: classify, never
route), improved offline by a **classifier optimization loop** (SDG Hub / Training Hub).
The service will be Rust: tokio + tonic/axum, Candle + ModernBERT, moka cache, bounded
inference workers, sub-20ms uncached budget. See `docs/` and the research corpus for detail.
