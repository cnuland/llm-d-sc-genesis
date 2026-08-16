# llm-d-sc Engineering Contract

Read the active specification and test plan before editing implementation code.

## Authority

- Specification: intended behavior.
- Existing code/tests: current behavior.
- Deterministic tests outrank model confidence.
- Maintainer is final authority.
- Worker cannot commit, push, merge, waive gates, or alter validation evidence.

## Per-acceptance-criterion workflow

1. Read one acceptance criterion and only its relevant source/test context.
2. Select or write the proving test (IDs from `tests/TEST_MATRIX.md` via the spec's test-plan).
3. Run it and prove RED for the expected reason.
4. Record RED evidence in `specs/<id>/evidence/<AC>/RED.md` (test ID, command, SHA/worktree
   state, failure excerpt, why this is the expected failure).
5. Implement the smallest change.
6. Run focused test to GREEN; record GREEN evidence in `specs/<id>/evidence/<AC>/GREEN.md`.
7. Run deterministic test-impact selection (`./hack/test-impact`).
8. Run spec-check (`./hack/spec-check`).
9. Run required local suite (`./hack/verify`).
10. Stop. Do not opportunistically start the next criterion.

## Hard rules

- Never weaken/delete an assertion merely to make CI pass.
- No unrelated refactors or hypothetical abstractions.
- No unrestricted model forward from Tokio request workers.
- No unbounded inference queues.
- No routing policy, stickiness, or endpoint selection in llm-d-sc.
- No raw prompts in default logs/metric labels.
- No performance claim without comparable before/after p50/p95/p99 evidence.
- No average-only latency claims.
- No benchmark methodology change hidden inside an optimization patch.
- No golden-output update without explaining why the old contract was wrong.

## Operational rules (conducted worker turns)

- Read `.agent/state/current.md` FIRST each turn; rewrite it before ending the turn
  (spec, active criterion, last green state, current failing test, next step, uncertainty).
- Do not spawn subagents. Work directly: test, then implement, then run suites yourself.
- Relative paths only. Scratch/debug files in `./artifacts/` (gitignored) — never /tmp.
- Local inference: there are no token budgets, quotas, or rate limits. Never stop citing
  one. Verify any suspected blocker concretely before reporting it.
- For runtime bugs: instrument, observe output, change exactly ONE thing. Never delete
  instrumentation before reading what it printed.
- Spec drift or ambiguity: STOP, write ESCALATE + the contradiction into
  `.agent/state/current.md`, and end the turn. Do not silently reinterpret intent.
- Rust: respect pinned versions; no new dependencies without a design note; never edit
  generated protobuf code by hand.
- NEVER reimplement a mature dependency the architecture/research has already selected
  (e.g. the HF `tokenizers` crate, moka, tonic). If a task appears to require doing so,
  STOP and escalate before writing it. Parity with a fixture does not justify a clone.
- Crate research: use Bash (grep/sed) on ~/.cargo/registry sources — the Read tool is
  blocked outside the project and will kill your turn.

## Source of truth (in order)

1. The maintainer's current explicit instruction
2. This file
3. `specs/<active>/spec.md` + `test-plan.md`
4. `CONTRIBUTING.md` and `docs/SDD.md` / `docs/TDD.md`
5. `docs/` architecture decisions
