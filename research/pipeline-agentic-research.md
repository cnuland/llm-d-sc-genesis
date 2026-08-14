# Slow and Steady: A Production-Grade Agentic ASDLC for Upstream Software Engineering

## Executive conclusion

**As of Friday, August 14, 2026, the architecture I would recommend is deliberately much simpler than most “multi-agent software factories.”** Your guiding principle should be exactly the one you gave me:

> **Slow and Steady Wins the Race.**

The strongest pattern emerging from current agent-engineering guidance is not “more agents, more prompts, more MCP servers, more memory, more orchestration.” It is **small numbers of well-separated roles, explicit artifacts, deterministic gates, narrow permissions, incremental work, and independent evaluation**. Anthropic's long-standing guidance is to begin with simple, composable workflows and add autonomy only where it produces measurable value; OpenAI's current harness work similarly emphasizes controlling context bloat, repeated work, and verification rather than surrounding a capable model with enormous scaffolding. citeturn17search1turn16search0

For your environment, I recommend **three model roles plus a deterministic control plane**:

| Responsibility | Recommended component | Authority |
|---|---|---|
| Research, ambiguity reduction, specification, architecture | **GPT-5.6 Sol** | Read/research/specify; no implementation push authority |
| Day-to-day implementation | **local DeepSeek-V4**, preferably Flash first | Edit worktree, run tests, prepare commits |
| Independent review/gatekeeping | **Claude Fable 5** | PASS / CHANGES / ESCALATE; no merge authority |
| State transitions, Git operations, CI orchestration | **deterministic scripts + GitHub Actions** | Mechanical only |
| Evals and historical evidence | **Agent Eval Harness + EvalHub + MLflow** | Measurement, not source-code authority |
| Final upstream judgment | **you, the maintainer** | Only party allowed to approve final merge |

This is an **evaluator–optimizer architecture**, but importantly, the optimizer and evaluator are not allowed to become an endlessly debating “society of agents.” Anthropic explicitly describes the evaluator-optimizer pattern as one model producing work while another independently evaluates it; that fits software engineering particularly well because code can also be compiled, tested, inspected, and compared before release. citeturn17search1turn17search8

The high-level lifecycle should therefore be:

```text
IDEA
  ↓
RESEARCHED
  ↓
SPECIFIED
  ↓
TEST-DESIGNED
  ↓
IMPLEMENTING
  ↓
LOCAL-GREEN
  ↓
FABLE-REVIEWED
  ↓
PUSHED
  ↓
GITHUB-CI-GREEN
  ↓
PROD-LIKE-VALIDATED
  ↓
MAINTAINER-APPROVED
  ↓
MERGED
  ↓
OBSERVED / LEARNED
```

**The state machine should be code, not an LLM.** Models operate *inside* states; they do not invent new lifecycle states or silently waive gates.

I am interpreting your “TTD” as **TDD, test-driven development**. There is an important 2026 research wrinkle here: emerging work on agentic development suggests merely telling a coding agent “use TDD” is not enough. Supplying the agent with the *right affected tests and dependency context* can matter considerably more; one recent test-driven agent development study reported substantially fewer regressions when relevant code/test graph context was supplied. citeturn12view8

The most important recommendation in this entire report is therefore:

> **Do not automate autonomy. Automate evidence.**

An agent should gain the right to take the next small step because the repository now contains evidence that the previous one succeeded—not because another agent said it “felt confident.”

That means, in order of authority:

**compiler/type system → deterministic tests → security/invariants → behavioral evals → Fable review → maintainer judgment.**

Fable is the gatekeeper, but **Fable is not allowed to overrule a failing deterministic test**. MLflow is the record, but MLflow is not the gatekeeper. EvalHub orchestrates evals, but does not determine upstream taste. And the worker model never gets to merge its own work.

That is the foundation of an ASDLC that can produce upstream-quality code rather than AI slop.

## Architecture: agents, boundaries, and model routing

### Use an asymmetric pipeline, not a swarm

Your instinct to use a stronger frontier model to resolve ambiguity and a local model to perform the bulk of implementation is good. OpenAI itself now describes a similar “high-capability advisor/planner plus cheaper executor” division in its current model/harness work, while Anthropic documents an advisor pattern for long-horizon agentic work in which a higher-tier model handles the consequential planning while an executor handles mechanical turns. citeturn16search0turn17search19

I would implement the division like this.

**Research/specification agent — GPT-5.6 Sol**

This agent receives your idea, upstream issue/history, relevant repository sections, upstream contribution requirements, and a research harness. Its job is **uncertainty destruction**:

```text
idea
  → prior art
  → upstream constraints
  → requirements
  → non-requirements
  → risks
  → acceptance criteria
  → validation strategy
  → implementation-shaped specification
```

It should be allowed to browse documentation, papers, standards, issue trackers, and source code, but by default should not edit implementation files. GPT-5.6 Sol is OpenAI's current flagship model for high-end reasoning/coding work, and OpenAI's current engineering material specifically emphasizes managing context/tool use and verification in long-running agentic work. citeturn16search0

**Worker — DeepSeek-V4**

Use OpenCode as the worker's interactive harness and local DeepSeek-V4 as its principal executor.

The interesting development as of August 2026 is that there are now two particularly relevant official local DeepSeek choices. `DeepSeek-V4-Pro-0813` is the higher-end model; DeepSeek's model card describes stronger agentic performance and documents local/OpenAI-compatible serving through vLLM and SGLang. citeturn19view3 `DeepSeek-V4-Flash-0731` is substantially smaller and still specifically optimized for agentic work; DeepSeek's own evaluations show Flash considerably exceeding its older preview models on coding-agent benchmarks. It can likewise be served using vLLM or SGLang through OpenAI-compatible endpoints. citeturn19view4

For a home lab, **I would begin with V4 Flash, establish your own repository-specific eval baseline, and only promote tasks to V4 Pro when your measured results justify the additional hardware/runtime cost**. The official preview architecture figures put V4 Flash at 284B total/13B active parameters versus 1.6T/49B active for V4 Pro, making “just use Pro everywhere” a poor default for most local installations. citeturn16search8turn19view3

This is also timely enough that I would treat V4-Pro-0813 as a **canary model initially rather than immediately changing your entire development process around it**. Your own acceptance suites matter more than vendor benchmarks.

**Reviewer — Claude Fable 5**

Fable should have a different provider, training lineage, context construction, and prompt than the implementation worker. Anthropic currently positions Claude Fable 5 for its most demanding long-horizon agentic workloads, and its current prompt guidance recommends `high` effort as the default for most demanding work while reserving `xhigh` for the most capability-sensitive cases. citeturn17search15turn17search7

That model diversity is useful here. You do not want:

```text
DeepSeek writes code
DeepSeek reviews DeepSeek
DeepSeek explains why DeepSeek is right
```

That produces correlated mistakes.

Instead:

```text
GPT-5.6 defines intent
        ↓
DeepSeek implements
        ↓
deterministic tests
        ↓
Fable independently challenges the result
        ↓
you decide whether the work belongs upstream
```

Fable should receive the **specification, diff, relevant source context, test/eval evidence, and upstream rules**. It should ordinarily *not* receive the worker's full internal conversation or self-justification. That is a deliberate inference from good evaluation practice: evaluate the observable artifact and outcome independently instead of allowing the candidate's narrative to anchor the grader. Anthropic's evaluation guidance explicitly distinguishes agent traces from outcomes and emphasizes constructing evals around what constitutes success. citeturn17search10

### Do not make the LLM itself the orchestrator

This is where I would depart from many agent frameworks.

You do **not** need an “orchestrator agent” deciding dynamically whether to summon Architect Agent, Test Agent, Security Agent, Documentation Agent, Git Agent, Release Agent, Memory Agent, and so forth.

Use a small deterministic state machine:

```text
state = IMPLEMENTING

when worker_exit:
    run_local_gate()

if gate == GREEN:
    run_fable_review()

if review == PASS:
    publisher.commit_and_push()

if review == CHANGES:
    state = IMPLEMENTING

if review == ESCALATE:
    state = HUMAN_REQUIRED
```

That makes the workflow auditable. More importantly, a model cannot silently decide that because “tests are probably enough,” the security gate can be skipped.

Anthropic's long-running-agent work specifically emphasizes making incremental progress across context windows rather than asking an autonomous model to finish an enormous project in a single session; OpenAI's current harness engineering likewise emphasizes verification and avoiding repeated/context-heavy work. citeturn17search2turn16search0

### The publisher should not be an agent

This is a particularly important design choice.

You said you want agents pushing to GitHub in small intervals. I agree with the behavior, but I would **not give DeepSeek or Fable a general-purpose GitHub credential**.

Instead:

```text
worker
   ↓
staged diff
   ↓
local tests
   ↓
Fable PASS
   ↓
deterministic publisher
   ↓
git commit + git push
```

The worker can prepare commit message material. Fable can authorize publication. But an ordinary script performs the actual Git operation.

This gives you the desired semantics—**the agentic development loop regularly publishes small validated slices**—without giving an LLM an unrestricted `git push` capability.

OpenCode's permission model supports precisely this sort of separation: actions can be allowed, denied, or require approval on an agent-by-agent basis. citeturn19view5

For the worker, my permission policy would be approximately:

```text
read repo             allow
search repo           allow
edit worktree         allow
run known test cmds   allow
run build cmds        allow

git diff/status/log    allow
git add               allow or ask

git commit            deny
git push              deny
gh pr merge           deny

arbitrary network     deny by default
GitHub write APIs     deny
production creds      nonexistent
```

The publisher is therefore not “smart.” That is a feature.

### Small intervals should mean logical slices, not clock intervals

Do not instruct the model:

> push every 15 minutes

or:

> commit every 100 lines.

Instead, define a small change as:

**one coherent claim about the software that can be independently tested and reviewed.**

Examples:

```text
Commit: reproduce parser bug with failing test
Commit: correct parser state transition
Commit: add backwards-compatibility case
Commit: update user-visible documentation
```

Each commit should be understandable without reading five later commits to learn what it was supposed to accomplish.

This much more closely resembles skilled human upstream development.

## Specification, TDD, OpenCode, and keeping the harness light

### Make the specification the first implementation artifact

For spec-driven development, GitHub's Spec Kit is one useful contemporary reference architecture: it separates project principles/constitution, specification, clarification, implementation planning, task breakdown, analysis, and implementation rather than treating a natural-language prompt as the whole requirement. citeturn2search2turn2search26

I would adapt that idea to upstream engineering rather than blindly adopting every Spec Kit command.

Each substantial change should begin with something like:

```text
specs/issue-1234/
    research.md
    spec.md
    test-plan.md
    design.md       # only when architectural choice warrants it
```

Your `spec.md` should force the research agent to answer:

| Field | Purpose |
|---|---|
| Problem | What observable problem are we solving? |
| Upstream context | Why does this belong in this project? |
| Existing behavior | What happens today? |
| Desired behavior | What exact behavior changes? |
| Non-goals | What must *not* get pulled into scope? |
| Compatibility | APIs, upgrade behavior, older configurations |
| Security impact | New trust boundary, parser/input/network implications |
| Acceptance criteria | Machine-verifiable where practical |
| Negative cases | What must continue to fail or remain unchanged? |
| Test strategy | Unit, integration, end-to-end, regression |
| Documentation impact | Only necessary user/developer documentation |
| Rollback | How does a maintainer revert/disable the change? |
| Open questions | Anything not yet proved |

That **non-goals** field is one of your strongest anti-slop mechanisms.

Anthropic's current Fable prompting guidance explicitly advises against adding extra features, refactoring unrelated code, or introducing abstractions beyond what the requested task requires. citeturn12view1

Put the same rule in your project's engineering constitution:

> **No opportunistic cleanup. No nearby refactor unless required for correctness. No abstraction for hypothetical future needs.**

### TDD should be evidence-driven, not ceremonial

For a bug:

```text
reproduce bug
   ↓
write failing regression test
   ↓
prove it fails for the expected reason
   ↓
make smallest implementation change
   ↓
regression test passes
   ↓
run impact-selected surrounding tests
   ↓
full required suite
```

For a feature:

```text
acceptance example
   ↓
executable acceptance/integration test
   ↓
small implementation
   ↓
focused unit tests where useful
   ↓
broader compatibility suite
```

Do not simply prompt:

> “Always use TDD.”

Recent agentic TDD research is particularly relevant to your plan: work on test-driven agent development found that adding structural code-to-test impact information reduced regression failures substantially, while naïve procedural TDD prompting alone could still lead to regressions. citeturn12view8

So create one deterministic helper such as:

```text
./hack/test-impact <changed-files>
```

Its output might be:

```text
Required:
  tests/unit/parser/*
  tests/integration/import/*
  tests/regression/issue-1234

Recommended:
  tests/integration/config/*
```

The worker should consume that, rather than hallucinating which tests “look relevant.”

Also make **test weakening a privileged change**. An implementation agent should not be able to turn red tests green by casually rewriting the assertions it is meant to satisfy.

A sensible rule is:

```text
New test: normal review
Existing test assertion changed/deleted:
    Fable must explicitly explain why the old contract was wrong
```

Be particularly suspicious of excessive mocks. A 2026 empirical study found coding-agent contributions were more prone to adding mocked tests than conventional contributions, reinforcing the value of real integration boundaries where practical. citeturn6academia38

### OpenCode is a good worker shell if you resist configuring everything

OpenCode already gives you the pieces you need: specialized agents, a plan mode, permissions, `AGENTS.md`, on-demand skills, built-in repository tools, and optional MCP integration. citeturn15search5turn19view5

The critical word is **optional**.

OpenCode recommends committing a concise `AGENTS.md`; its `/init` process focuses that file on build/lint/test commands, architecture, conventions, setup quirks, and operational gotchas. citeturn19view7

That is exactly where the majority of your “harness” should live.

I would make `AGENTS.md` something like:

```markdown
# Engineering contract

Read CONTRIBUTING.md before editing.

## Build
./hack/build

## Verify changed code
./hack/verify

## Full test
./hack/test-all

## Working rules
- One issue/acceptance criterion at a time.
- Never modify unrelated code.
- Reproduce bugs with a regression test first.
- Never weaken a failing test solely to make CI pass.
- Follow existing architecture before introducing abstractions.
- Never commit or push directly.
- Stop and escalate when the spec conflicts with repository behavior.

## Source of truth
- CONTRIBUTING.md: upstream process
- specs/<current>/spec.md: change requirements
- docs/architecture/: architectural decisions
```

Notice what is **not** in there: pages of motivational instructions, giant coding-style essays already enforced by formatters, repeated language documentation, detailed GitHub API syntax, every possible edge case, and a dozen persona descriptions.

OpenCode also lets `opencode.json` reference existing development and testing guidance instead of duplicating it, and its documentation explicitly recommends need-to-know loading rather than preemptively reading everything. citeturn19view7

### Start with no more than three custom skills

OpenCode skills are `SKILL.md`-based reusable instructions discovered and loaded **on demand**, which is preferable to permanently filling the model context. citeturn15search2

My starting set would be only:

| Skill | What it does | Why it deserves to exist |
|---|---|---|
| `test-impact` | Finds affected tests and required verification | Repository-specific, reusable reasoning |
| `spec-check` | Maps proposed diff to acceptance criteria/non-goals | Prevents scope drift |
| `review-prep` | Produces machine-readable diff/test/eval evidence | Gives Fable consistent review input |

Everything deterministic should instead be a **normal script**:

```text
format
lint
typecheck
unit tests
integration tests
SBOM
static analysis
dependency checks
container build
```

A skill should exist only when an agent needs procedural knowledge about **when and why to use something**, not because “agents use skills.”

OpenAI's current guidance on evaluating agent skills recommends explicitly defining what success looks like and testing skill triggering/behavior with small targeted evaluation sets, including cases in which the skill should *not* trigger. citeturn16search9

I would therefore give every proposed skill a deletion test:

> **If the base model can pass the skill's eval suite reliably without this skill, remove it.**

This is especially important as models improve; Anthropic has warned that harnesses encode assumptions about model limitations and those assumptions become stale as capabilities change. citeturn17search13

### Avoid the “MCP Christmas tree”

For this workflow I would begin with **zero MCP servers enabled globally**.

OpenCode itself warns that each MCP server adds context and specifically notes that tool-heavy servers such as GitHub MCP can consume large amounts of context. citeturn19view6

You already have:

```text
local filesystem
git
shell
test scripts
HTTP research tools for the research role
GitHub Actions
```

That is enough.

Add a MCP server only when you can write down a concrete repeated problem it solves. Enable it only for the role that needs it.

The worker probably does **not** need GitHub MCP. Put issue/PR context into a checked-out task artifact or fetch it deterministically.

The reviewer probably does **not** need arbitrary shell/network access.

The research agent may warrant richer retrieval tools because research is the one stage where parallel exploration genuinely produces value; Anthropic's research-agent architecture is one example where parallel search agents are useful because information discovery is naturally decomposable. citeturn17search18

That is very different from spawning six coding agents to edit the same repository.

## Memory and “dreaming” without creating a hallucination database

Your “dreaming” idea is promising, but this is an area where restraint matters enormously.

Research such as Reflexion has shown that agents can improve future attempts by storing textual reflections from previous trials, and newer 2026 research is exploring “sleep” or consolidation phases in which models recursively compress and reorganize memories. Those are useful conceptual directions, but autonomous memory rewriting is not mature enough to make an agent-generated memory database the project's source of truth. citeturn7search3turn7search5

The safest architecture is **three-tier memory plus one evidence store**.

### Working memory

Ephemeral, task-specific:

```text
.agent/state/current.md
```

Example:

```markdown
Issue: #1234

Current acceptance criterion:
Parser accepts X while preserving Y.

Last green commit:
abc123

Current failing test:
tests/regression/test_1234.py::test_x

Next intended step:
Correct state transition in parser/foo.c.

Open uncertainty:
Whether legacy config path reaches same state machine.
```

This file gets aggressively rewritten. It is not history.

Its purpose is to let a new context window resume quickly. Anthropic recommends designing long-running state artifacts specifically so a new session can recover quickly, and recommends combining context compaction with explicit memory for information that must survive summarization. citeturn17search17turn17search26

### Episodic lessons

Durable but narrow:

```text
.agent/memory/lessons/
    parser-state-machine.md
    integration-test-fixtures.md
    cross-compile-gotcha.md
```

A lesson should contain:

```markdown
# Cross-compile test discovery

Observation:
Changing foo/bar causes integration tests under baz/ even though
the source tree does not make the dependency obvious.

Evidence:
PR #488, commit ..., CI run ...

Correct approach:
Run ./hack/test-impact foo/bar before targeted testing.

Do not:
Assume unit/foo is sufficient.

Last verified:
2026-08-14
```

Anthropic's recent memory guidance similarly recommends saving corrections and confirmed approaches with their reasons, avoiding material already captured elsewhere, updating instead of duplicating, and deleting incorrect memories. citeturn12view2

### Semantic/project memory

These are **not agent memory files at all**.

Stable truths belong in normal upstream artifacts:

```text
AGENTS.md
CONTRIBUTING.md
docs/
ADRs
API documentation
test infrastructure
code comments where necessary
```

When something becomes an architectural truth, promote it from “agent memory” into the project's real documentation.

That prevents the catastrophic situation where:

```text
repository says A
agent memory says B
old chat says C
vector database returns D
```

### MLflow is the historical evidence store

Do not stuff every historic trace into the worker's prompt.

Keep the full evidence in MLflow:

```text
model
prompt/harness version
tool calls
duration
tests executed
eval scores
review decision
human feedback
git SHA
final merge/revert status
```

MLflow's current GenAI stack supports evaluation datasets, trace-oriented evaluation, LLM judges, and structured human feedback; its review queues can also attach human review directly to traces, although the review-queue feature is currently marked experimental. citeturn18search0turn18search9

The model's memory should contain distilled knowledge. MLflow contains the forensic record.

### “Dreaming” should create a pull request, not change memory

This is where I would make your idea concrete.

Run a consolidation job **after merges**, or on a nightly/weekly cadence if enough changes have accumulated:

```text
merged PRs
failed agent attempts
Fable review comments
CI failures
EvalHub regressions
maintainer corrections
        ↓
Dream/consolidation model
        ↓
candidate lessons
        ↓
deduplicate / contradiction check
        ↓
memory-update PR
        ↓
human review
```

The dreaming job is allowed to propose:

```text
ADD lesson
UPDATE lesson
DELETE obsolete lesson
PROMOTE lesson → AGENTS.md / docs / test rule
```

It may not silently change persistent memory.

I would require every proposed memory to cite evidence—a PR, commit, failing test, EvalHub run, or maintainer review.

A useful promotion rule is:

```text
Observed once:
    retain in MLflow

Observed repeatedly:
    candidate episodic lesson

Stable repository rule:
    promote to docs / AGENTS.md / deterministic lint/test

No longer true:
    delete it
```

That final **delete it** matters. Good agent memory needs forgetting.

Do not start with a vector database unless ordinary files stop working. Searchable Markdown under Git gives you:

```text
review
history
diffs
blame
reverts
community visibility
```

A sophisticated memory service does not automatically give you better engineering.

## Evaluation and reviewer gating with Fable, MLflow, and Red Hat EvalHub

This is where your proposed stack fits together particularly well.

Red Hat's EvalHub is an evaluation-orchestration service for LLM evaluations in OpenShift AI and integrates evaluation results with MLflow. citeturn18search1 Even more useful for your case, the Open Data Hub **Agent Eval Harness** now provides a declarative `eval.yaml` that can run the same evaluation design locally, in containers, and through EvalHub, while supporting code and LLM judges, thresholds, pairwise evaluations, reports, and MLflow traces. citeturn19view1

That means **do not build another proprietary eval framework**.

Use this stack:

```text
               ┌──────────────┐
               │   eval.yaml  │
               └──────┬───────┘
                      │
          ┌───────────┴───────────┐
          │ Agent Eval Harness    │
          └───────────┬───────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
 deterministic      Fable       other judges
   scorers          review
        │             │
        └──────┬──────┘
               │
            EvalHub
               │
             MLflow
               │
     trace + scores + history
```

The Agent Eval Harness already describes exactly the desirable portability here: one configuration can drive laptop evaluations, containerized execution, and EvalHub, with MLflow-native traces. citeturn19view1

### Use a layered quality gate

I recommend four automated evaluation layers followed by you.

| Gate | Typical checks | Can fail build? |
|---|---|---|
| Deterministic correctness | compiler, formatter, lint, types, unit/integration tests | **Always** |
| Agent behavioral eval | spec cases, regressions, task-specific cases | **Yes** |
| Fable reviewer | correctness, scope, maintainability, test quality, upstream fit | **Yes** |
| Prod-like EvalHub suite | broader regression/e2e/performance/agent evaluation | **Yes** |
| Maintainer | community judgment, architecture, final merge | **Final authority** |

MLflow supports combining evaluation datasets with built-in or custom scorers and LLM judges, which makes it appropriate to use deterministic and model-based grading together rather than reducing everything to a single “LLM confidence score.” citeturn18search0turn18search6

### Give Fable a strict reviewer contract

Fable's job is not to rewrite the patch.

Its output schema should be boring:

```json
{
  "decision": "PASS | CHANGES | ESCALATE",
  "blocking_findings": [],
  "nonblocking_findings": [],
  "acceptance_criteria": [],
  "test_assessment": {},
  "scope_assessment": {},
  "security_assessment": {},
  "upstream_fit": {},
  "confidence": "high | medium | low"
}
```

Every blocking finding should identify:

```text
file
line/range
violated requirement
observed evidence
requested correction
```

The reviewer rubric should prioritize, in this order:

**correctness → specification compliance → regressions → security → compatibility → tests → architecture → maintainability → unnecessary complexity → documentation/style.**

Do not let style nitpicks block a correct minimal patch unless they violate actual upstream conventions.

And explicitly prompt Fable:

> Do not propose unrelated refactors. Do not expand the feature. Prefer deletion/simplification over additional abstraction. A passing review means the smallest maintainable change satisfying the written contract.

That aligns particularly well with Anthropic's current Fable guidance against needless features/refactors/abstractions. citeturn12view1turn19view2

### Use two Fable review depths, not two reviewer agents

To preserve your frequent-small-push workflow without spending frontier-model effort on every trivial line:

**Pre-push Fable gate**

Use normal/high-enough effort on each *logical commit*. It checks only:

```text
obvious correctness blocker?
scope violation?
test weakness?
security red flag?
spec mismatch?
```

**Promotion Fable gate**

When the PR becomes validation-ready, use `high`, and reserve `xhigh` for particularly difficult or high-risk changes. Anthropic currently recommends high as Fable's standard effort setting and xhigh only for capability-sensitive cases. citeturn17search7

This gives you one reviewer persona with two review budgets instead of proliferating reviewers.

### Fable + EvalHub should be an adapter, not an assumed native feature

I would implement Fable as a **judge adapter/provider inside your evaluation stack**. Red Hat's EvalHub supports bringing custom evaluator providers, while the ODH Agent Eval Harness supports LLM and code judges. So wrapping the Anthropic API as one of those judges is a straightforward architectural fit—but it should be understood as **your integration**, not as a claim that Red Hat ships a built-in “Fable 5 reviewer” button. citeturn19view1

For every evaluation run, record at least:

```text
git_sha
base_sha
spec_id
worker_model
worker_checkpoint/digest
reviewer_model
reviewer_effort
GPT research model
OpenCode version
AGENTS.md hash
skill hashes
eval.yaml hash
evaluation dataset version
container digest
test-selection manifest
hardware profile
```

This turns:

> “the agent seemed better this week”

into:

> “checkpoint X with harness Y reduced regression rate from A to B on dataset Z.”

That is ASDLC.

### Build your golden evaluation set from your own project's history

Public coding benchmarks tell you whether a model is generally capable. They do not tell you whether it understands *your upstream project's failure modes*.

Build an internal evaluation corpus from:

```text
past bugs
past regressions
tricky review comments
reverted PRs
compatibility failures
security fixes
tests agents previously weakened
architectural conventions agents repeatedly violated
```

Then every model/harness upgrade runs against the same dataset.

MLflow's Evaluation Datasets are specifically intended as reusable repositories for test cases, expectations, and evaluation data rather than ad-hoc one-time tests. citeturn18search0

Your eventual model promotion rule should be:

```text
new model/version
    ↓
offline project eval
    ↓
historical regression corpus
    ↓
small live canary tasks
    ↓
compare cost / quality / churn / regressions
    ↓
promote OR reject
```

Never upgrade your worker simply because a leaderboard moved.

## Home lab to GitHub Actions to prod-like validation

Your home lab and GitHub should have **different trust roles**.

The home lab is your high-trust development environment.

GitHub is your clean-room reproducibility environment.

That distinction is critical.

### Recommended branch topology

I would avoid one permanent shared `staging` branch because unrelated agent changes can contaminate each other's validation.

Instead:

```text
main
│
├── agent/1234-parser-fix
│
├── agent/1288-controller-timeout
│
└── ...
```

When `agent/1234-parser-fix` becomes review-ready, generate a **per-change validation branch**:

```text
validation/pr-1234-<sha>
```

Conceptually:

```text
latest main
    +
exact reviewed feature SHA
    ↓
synthetic integration commit
    ↓
validation/pr-1234-abc123
```

Run full prod-like validation there.

That branch answers the meaningful question:

> **Does the exact reviewed change still work when integrated with the current target branch?**

If `main` changes materially afterward, the validation is stale and reruns.

### The complete pipeline

I would build the flow this way:

```text
HOME LAB
──────────────────────────────────────────────

idea
 ↓
GPT-5.6 research/spec
 ↓
spec approved enough to implement
 ↓
OpenCode + local DeepSeek-V4
 ↓
failing test
 ↓
minimal implementation
 ↓
focused local verification
 ↓
Fable pre-push review
 ↓ PASS
deterministic publisher commits
 ↓
push agent/<issue>-<slug>


GITHUB
──────────────────────────────────────────────

push
 ↓
FAST CI
 ├── format/lint
 ├── type/build
 ├── unit
 ├── affected integration tests
 ├── dependency/security checks
 └── spec/check metadata
 ↓
Fable exact-SHA review
 ↓ PASS
create/update per-PR validation ref
 ↓
FULL PROD-LIKE VALIDATION
 ├── clean rebuild
 ├── complete test matrix
 ├── integration/e2e
 ├── package/container
 ├── compatibility
 ├── security
 ├── EvalHub full evaluation
 ├── MLflow evidence
 └── provenance/artifact
 ↓
required check: prod-like/validated
 ↓
YOU REVIEW
 ↓
merge queue / merge
 ↓
main
 ↓
post-merge smoke + observation
 ↓
memory consolidation candidate
```

### Fast CI should run on every small push

That workflow should be cheap and ruthless.

Something structurally like:

```yaml
name: fast-ci

on:
  push:
    branches:
      - "agent/**"
  pull_request:
    branches:
      - main

permissions:
  contents: read

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - checkout-exact-sha
      - restore-dependencies
      - run: ./hack/format-check
      - run: ./hack/lint
      - run: ./hack/typecheck
      - run: ./hack/build
      - run: ./hack/test-impact --run
      - run: ./hack/spec-check
```

The important properties are more consequential than the precise YAML:

**read-only token by default, exact SHA, deterministic environment, no model secrets in jobs executing untrusted code.**

GitHub allows workflow-level restriction of `GITHUB_TOKEN` permissions and recommends minimizing credentials exposed to workflows. citeturn15search9turn15search0

Third-party Actions should be pinned to full-length commit SHAs rather than mutable tags where possible; GitHub provides organization/repository policy specifically for enforcing full-SHA pinning. citeturn15search3turn15search12

### Full validation should happen only after reviewer promotion

Do not run an expensive full matrix, EvalHub collection, Fable xhigh review, container deployment, and compatibility matrix on every five-line work-in-progress push.

That would violate your own principle.

Use:

```text
every push:
    focused deterministic CI

every coherent reviewed commit:
    Fable gate

PR promotion:
    full Fable review
    full EvalHub
    prod-like environment
```

“Slow and steady” does not mean “perform every possible check constantly.” It means **never advance farther than the evidence justifies**.

### Do not attach a public upstream PR directly to your home lab

This is one of the highest-priority security recommendations in the report.

GitHub explicitly warns against using self-hosted runners with public repositories because a malicious fork can submit workflow code that runs on the self-hosted machine. GitHub also notes that compromise of a self-hosted runner can expose local secrets and reachable services. citeturn15search15turn15search0

Therefore:

```text
Home lab:
    trusted development
    your own agent branches
    local model inference
    optional trusted CI

Public/fork PR:
    GitHub-hosted clean runner
    NO home-lab network access
    NO local model host credentials
```

If you genuinely need GPUs or specialized infrastructure during GitHub validation, use an **isolated runner pool** that is treated as disposable infrastructure, not a runner on the same trusted LAN as your home storage and credentials. GitHub identifies Actions Runner Controller as its reference Kubernetes solution for autoscaling self-hosted runners. citeturn15search24

For a public upstream project I would still make GitHub-hosted execution the default for untrusted contributions.

### Separate secret-bearing review from untrusted execution

A reviewer job calling Fable has an API secret.

An external PR contains untrusted text/code.

Do not casually combine those things.

The secure pattern is:

```text
untrusted CI job:
    executes source
    has no valuable secrets

review job:
    receives sanitized diff/spec/test output
    read-only repository access
    has reviewer API credential
    does NOT execute contributor-controlled scripts
```

This also reduces prompt-injection risk. Untrusted issue text, source comments, documentation, tests, and PR descriptions are **data**, not authoritative instructions to your Fable/GPT agents.

### Validation branches should be pointers to evidence, not a second development universe

The agent should **never fix code directly on the validation branch**.

If validation fails:

```text
validation branch fails
        ↓
record failure
        ↓
return to agent/<issue> branch
        ↓
new implementation commit
        ↓
review again
        ↓
new validation SHA
```

Otherwise your audited path becomes:

```text
reviewed code A
validation branch secretly changed to B
human merges C
```

which defeats the entire system.

### Main should be hard-protected from every agent identity

A good main-branch ruleset would require:

```text
pull request
required status checks
Fable reviewer check
prod-like validation check
human approval
CODEOWNERS where appropriate
conversation resolution
no force push
no deletion
agents cannot bypass
```

GitHub rulesets/branch protection can require reviews and status checks before merge. citeturn15search19

For a busy upstream project, add GitHub's **merge queue**. It reruns required checks against queued merge-group state so a PR that was green against yesterday's `main` is not assumed to remain green after other queued changes land. Actions must listen for the `merge_group` event when their checks are required in the queue. citeturn15search1turn15search7

That still preserves your authority:

```text
AI prepares
AI reviews
CI validates

YOU decide:
    "Merge when ready."
```

The merge queue then guarantees the final integrated state satisfies the policy.

## Upstream quality charter and concrete implementation blueprint

The final issue is cultural, and it is arguably more important than model selection.

The best signal for “not AI slop” is **not whether someone can detect AI wording**.

It is whether the contribution behaves like responsible upstream engineering:

```text
understands the existing project
solves a real issue
contains a minimal coherent change
has evidence
does not manufacture abstractions
fits project architecture
is explainable by its submitter
survives independent review
respects contribution/legal policy
leaves maintainable tests
```

Current upstream projects are already articulating this. The Linux kernel's AI-assistance guidance keeps responsibility with the human contributor: normal review and licensing obligations still apply, and the AI itself must not supply the contributor's Signed-off-by/DCO attestation. citeturn12view10 The Git project's contribution guidance has likewise pushed back against AI-looking, verbose, low-understanding patches and emphasizes that contributors need to understand and own what they submit. citeturn12view11

Those are project-specific policies, not universal law, but they are excellent models for your philosophy.

### Your upstream contribution contract

I would encode this into the repository:

> **Agent-generated work receives no lower standard and no special shortcut. The maintainer submitting the change owns its correctness, licensing, security implications, tests, design, and upstream suitability.**

Then enforce these operating rules.

**One issue, one branch, one coherent PR.**

Do not allow the model to bundle:

```text
feature
+ refactor
+ dependency refresh
+ naming cleanup
+ docs rewrite
```

unless those are genuinely inseparable.

**No unexplained code.**

At promotion time, the worker should produce a concise engineering explanation:

```text
What changed?
Why was this implementation chosen?
What alternatives were rejected?
Which acceptance tests prove it?
What could regress?
How would we roll it back?
```

Fable checks the explanation against the actual diff rather than trusting it.

**No decorative tests.**

A test must fail against the broken behavior and pass against the corrected behavior. For critical regressions, test this property automatically where practical.

**No “helpful” adjacent cleanup.**

If the agent spots something unrelated, it creates a note/issue candidate. It does not repair it opportunistically.

**No AI DCO/legal signoff.**

You perform any human certification required by the upstream project's DCO/CLA/contribution rules. The Linux kernel guidance is particularly explicit on retaining that human responsibility. citeturn12view10

### Suggested repository structure

You do not need much:

```text
.
├── AGENTS.md
├── CONTRIBUTING.md
├── opencode.json
│
├── specs/
│   └── issue-1234/
│       ├── research.md
│       ├── spec.md
│       └── test-plan.md
│
├── .agent/
│   ├── state/
│   │   └── current.md
│   └── memory/
│       └── lessons/
│
├── .opencode/
│   └── skills/
│       ├── test-impact/
│       │   └── SKILL.md
│       ├── spec-check/
│       │   └── SKILL.md
│       └── review-prep/
│           └── SKILL.md
│
├── evals/
│   ├── eval.yaml
│   ├── datasets/
│   └── rubrics/
│       └── upstream-review.md
│
├── hack/
│   ├── verify
│   ├── test-impact
│   ├── spec-check
│   └── publish-reviewed
│
└── .github/
    └── workflows/
        ├── fast-ci.yml
        ├── reviewer.yml
        ├── validation.yml
        ├── merge-group.yml
        └── post-merge.yml
```

OpenCode officially supports project `AGENTS.md` instructions and on-demand `SKILL.md` skills, making this a native rather than improvised arrangement. citeturn19view7turn15search2 The ODH Agent Eval Harness's declarative `eval.yaml` then gives you a natural bridge from local evaluation to EvalHub/MLflow without building another evaluation DSL. citeturn19view1

### The minimum viable ASDLC

I would resist deploying the entire architecture on day one. Roll it out in this order:

| Maturity | Add | Do not add yet |
|---|---|---|
| Foundation | spec, TDD, OpenCode worker, deterministic verification | memory DB, subagent swarm |
| Review | Fable structured reviewer, pre-push publisher gate | multiple reviewer personas |
| CI | GitHub Actions, protected main, small frequent pushes | complex deployment automation |
| Validation | per-PR prod-like branch, EvalHub, MLflow | autonomous release |
| Learning | reviewed episodic memory + dreaming PR | autonomous memory mutation |
| Optimization | model routing based on measured evals | routing based on vibes |

This sequencing follows the general agent-engineering principle of starting with the simplest reliable system and adding complexity only after evaluation demonstrates a need. citeturn17search1turn17search13

### What I would explicitly ban

To keep this project from slowly turning into an agent-framework project instead of the upstream software project, put these in the operating charter:

```text
No agent may merge main.
No implementation model may waive a failing test.
No reviewer may alter the patch it is reviewing.
No model gets unrestricted GitHub credentials.
No skill exists without an eval proving its value.
No MCP server is globally enabled merely because it is available.
No memory is treated as truth without repository evidence.
No validation failure is repaired directly on the validation branch.
No hidden “agent confidence” score substitutes for test evidence.
No unrelated refactoring is bundled into a functional patch.
No AI-generated signoff represents a human legal certification.
```

### The quality metrics that actually matter

In MLflow, track **outcomes**, not token theatrics.

For each worker/reviewer/harness version, I would monitor:

| Metric | What it tells you |
|---|---|
| Acceptance-test pass rate | Did it solve the stated problem? |
| Regression rate | Did it break existing behavior? |
| First-review PASS rate | Is the worker producing reviewable increments? |
| Reviewer false-pass rate | Does Fable miss problems humans later find? |
| Reviewer false-block rate | Is Fable generating needless churn? |
| Human revisions after AI PASS | How much quality work remains? |
| Revert/fix-forward rate | Are merged contributions durable? |
| Test weakening frequency | Is the agent gaming the gate? |
| Scope-drift findings | Is the worker touching too much? |
| Post-merge defect rate | The real downstream quality signal |
| Diff churn before merge | Is the process converging or thrashing? |
| Skill-specific uplift | Does each skill actually improve outcomes? |
| Model cost/latency per accepted change | Efficiency per useful result |

MLflow's evaluation datasets, judges, traces, and human-feedback facilities are well suited to preserving those comparisons across model and harness versions. citeturn18search0turn18search6

Do **not** optimize first for:

```text
lines generated per hour
commits per day
agent tokens per minute
number of autonomous hours
number of agents running concurrently
```

Those measure activity.

You want **accepted, maintainable upstream changes**.

### The final architecture

Put everything together and your system should feel less like an AI software factory and more like a disciplined contributor with an unusually thorough pair programmer:

```text
                         YOU
                          │
                     idea / intent
                          │
                          ▼
                ┌───────────────────┐
                │ GPT-5.6 Sol       │
                │ research + spec   │
                └────────┬──────────┘
                         │
                  written contract
                         │
                         ▼
                ┌───────────────────┐
                │ OpenCode          │
                │ DeepSeek-V4       │
                │ local workhorse   │
                └────────┬──────────┘
                         │
                  test-first slice
                         │
                         ▼
             deterministic local checks
                         │
                         ▼
                ┌───────────────────┐
                │ Claude Fable 5    │
                │ independent gate  │
                └────────┬──────────┘
                         │ PASS
                         ▼
               deterministic publisher
                         │
                         ▼
                  small GitHub push
                         │
                         ▼
                  GitHub Actions
                         │
           ┌─────────────┴─────────────┐
           │                           │
        fast CI                  review/evals
           │                           │
           └─────────────┬─────────────┘
                         ▼
               validation/<PR>-<SHA>
                         │
           ┌─────────────┼──────────────┐
           │             │              │
       full CI        EvalHub       prod-like
                         │
                       MLflow
                         │
                    green evidence
                         │
                         ▼
                    YOU REVIEW
                         │
                merge when satisfied
                         │
                         ▼
                        main
                         │
                         ▼
                post-merge evidence
                         │
                         ▼
                 dreaming/consolidation
                         │
                   memory-update PR
                         │
                         ▼
                       YOU
```

The crucial property is that **authority narrows as the change moves toward production**.

Early in the process, GPT-5.6 can explore broadly.

During implementation, DeepSeek can edit freely inside an isolated worktree.

At review, Fable can criticize but not change.

At CI, machines decide objective facts.

At production-like validation, the exact integration SHA is tested.

At `main`, only you decide.

That is much closer to a healthy upstream human workflow than trying to simulate an engineering organization with fifteen LLM personas.

And it gives you a powerful rule for every future decision about agents, tools, memory, skills, and orchestration:

> **When adding another piece of harness, ask what measurable failure it prevents. If you cannot name the failure, its eval, and its removal criterion, do not add it.**

That is how I would build an agentic ASDLC intended to produce **boring, reviewable, defensible, upstream-quality software rather than AI slop**.

**Slow and Steady Wins the Race.**