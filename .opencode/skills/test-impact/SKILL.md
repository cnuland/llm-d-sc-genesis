---
name: test-impact
description: Determine which tests are affected by a set of changed files and which suites are required before claiming green. Use BEFORE running tests after any edit, and when writing a test plan.
---
# test-impact

Run `./hack/test-impact <changed-files...>` and treat its output as authoritative:
- `Required:` suites MUST pass before a criterion is claimed complete.
- `Recommended:` suites should run when the change touches shared modules.
Do not guess which tests "look relevant" — consume the tool output. If the tool reports
`UNKNOWN SURFACE`, run `./hack/test-all` instead and note the gap in `.agent/state/current.md`.

Deletion test: if the worker reliably selects correct suites without this skill (eval:
`evals/datasets/test-impact/`), delete this skill.
