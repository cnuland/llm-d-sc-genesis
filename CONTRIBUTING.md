# Contributing — the upstream charter

This project is being built for eventual upstream merge. Agent-generated work receives **no
lower standard and no special shortcut**. The maintainer submitting a change owns its
correctness, licensing, security implications, tests, design, and upstream suitability.

## The operating charter (hard bans)

```
No agent may merge main.
No implementation model may waive a failing test.
No reviewer may alter the patch it is reviewing.
No model gets git or GitHub credentials — the deterministic publisher performs git ops.
No skill exists without an eval proving its value.
No MCP server is enabled merely because it is available.
No memory is treated as truth without repository evidence.
No validation failure is repaired directly on a validation branch.
No hidden "agent confidence" substitutes for test evidence.
No unrelated refactoring is bundled into a functional patch.
No AI-generated signoff represents a human legal certification (DCO/CLA is human-only).
```

## Change lifecycle

Every substantial change starts as a spec directory (copy `specs/TEMPLATE/`):

```
specs/<id>/
    research.md     # prior art, upstream constraints, uncertainty destruction
    spec.md         # the contract: problem, behavior, non-goals, acceptance criteria
    test-plan.md    # how each criterion is proven; negative cases; impact analysis
    design.md       # only when an architectural choice warrants it
```

Then: `pipeline/conduct.sh <id>` drives implementation through the state machine.
See README.md for the full lifecycle. States are code; gates are scripts; review is Fable;
merge is human.

## Branch topology

```
main                          protected; human-merge only
agent/<id>-<slug>             one issue, one branch, one coherent PR
validation/pr-<id>-<sha>      synthetic integration ref; never developed on directly
```

A commit is one coherent claim about the software that can be independently tested and
reviewed. Commit messages state the claim; the diff proves it.

## Review contract

The reviewer (Claude Fable 5) receives the spec, diff, and test/eval evidence — not the
worker's self-justification. Its output is a structured verdict (see
`evals/rubrics/upstream-review.md`). Rubric priority: correctness → spec compliance →
regressions → security → compatibility → tests → architecture → maintainability →
complexity → docs/style. Style nitpicks do not block a correct minimal patch.

Review depths: a fast pre-push gate on each logical commit; a full-effort promotion review
when a PR becomes validation-ready.

## Promotion requirements for merge to main

1. `./hack/verify` and `./hack/test-all` green at the exact SHA
2. Fable review: PASS (promotion depth)
3. fast-ci green on GitHub at the exact SHA
4. Prod-like validation green on `validation/pr-<id>-<sha>` (once validation exists)
5. Worker-produced engineering explanation (what/why/alternatives/proof/risk/rollback)
   checked by the reviewer against the actual diff
6. Maintainer approval — the only step with merge authority

## Memory discipline

- `.agent/state/current.md` is working memory: rewritten constantly, never history.
- `.agent/memory/lessons/` are durable, narrow, evidence-cited lessons. They enter through
  reviewed PRs (the "dreaming" consolidation job proposes; humans approve). Lessons that
  stop being true are deleted. Stable truths get promoted OUT of agent memory into
  `docs/`, this file, or deterministic checks.
- MLflow (when wired) is the forensic record. It is evidence, not a gatekeeper.
