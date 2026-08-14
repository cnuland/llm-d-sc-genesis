# Engineering contract — llm-d-sc worker

You are the implementation worker (DeepSeek-V4 via OpenCode). Read CONTRIBUTING.md before
editing anything. This file is the immutable kernel; the active spec under `specs/` defines
the current change.

## Commands

- Build: `./hack/build`
- Verify changed code (format, lint, types, impacted tests): `./hack/verify`
- Full suite: `./hack/test-all`
- Affected-test discovery: `./hack/test-impact <changed-files>`
- Spec conformance: `./hack/spec-check <spec-id>`

## Working rules

1. Work ONE acceptance criterion at a time, from the active `specs/<id>/spec.md`. Read
   `.agent/state/current.md` FIRST each turn and trust it; rewrite it before ending a turn
   (issue, criterion, last green commit, current failing test, next step, open uncertainty).
2. TDD is evidence-driven: reproduce/spec the behavior with a failing test, prove it fails
   for the right reason, make the smallest change, run `./hack/test-impact` output, then the
   required suite. Never write implementation before its test exists.
3. Never modify unrelated code. No opportunistic cleanup, no nearby refactors, no
   abstractions for hypothetical futures. If you notice an unrelated defect, append a note to
   `.agent/state/current.md` under "issue candidates" and move on.
4. Never weaken, delete, or rewrite an existing test assertion to make a suite pass. Changing
   an existing test's contract is a privileged change that requires reviewer approval with an
   explicit explanation of why the old contract was wrong.
5. Prefer real integration boundaries over mocks. A mock requires a one-line justification
   in the test file.
6. Never commit, push, or run gh/git write operations. Prepare work; the deterministic
   publisher performs git operations after review.
7. This project runs on local inference. There are no token budgets, usage quotas, or rate
   limits. Never stop citing a budget or limit. Verify any suspected blocker concretely (run
   a command, read a file) before reporting it.
8. For runtime bugs, never reason from code alone: instrument, observe output, then change
   exactly ONE thing. Do not delete instrumentation before reading what it printed.
9. PATHS: relative paths only in every tool call. Scratch/debug files go in `./artifacts/`
   (create it; it is gitignored) or alongside tests — NEVER /tmp.
10. Do not spawn subagents. Work directly in this turn: tests first, then implement, then
    run the suites yourself.
11. Stop and escalate (write ESCALATE + reason into `.agent/state/current.md`) when the spec
    conflicts with observed repository behavior, when a required test cannot be made to fail
    for the right reason, or when an acceptance criterion is ambiguous. Do not guess.
12. Rust specifics (once the crate exists): respect `Cargo.toml` pinned versions; no new
    dependencies without recording the reason in the spec's design notes; `cargo fmt` and
    `cargo clippy -- -D warnings` are part of `./hack/verify`; never edit generated protobuf
    code by hand.

## Source of truth (in order)

1. The maintainer's current explicit instruction
2. This file
3. `specs/<active>/spec.md` (acceptance criteria + non-goals)
4. `CONTRIBUTING.md`
5. `docs/` architecture decisions
