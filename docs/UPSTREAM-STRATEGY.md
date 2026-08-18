# Upstream split strategy: genesis (lab) -> llm-d-sc (community)

Two repositories with distinct charters. Nothing is deleted; the experimental
record stays where it belongs and the upstream repo carries only what a
community contributor needs.

## 1. Charters

| | `llm-d-sc-genesis` (this repo) | `llm-d-sc` (new upstream) |
|---|---|---|
| Purpose | ASDLC laboratory: agentic process, evidence harness, experiments | The semantic classifier runtime as a community project |
| Audience | maintainer + agents | contributors, adopters, llm-d SIGs |
| Keeps | pipeline/, .opencode/, .agent/, evals/, artifacts/, watchdog, full research corpus, conducted-turn AGENTS.md, ADRs about process | src/, proto/, tests/, specs/ (record), docs/ (condensed), deploy/, hack/ (product subset), benchmarks |
| Tone | notebook, honest failure log | professional, front-facing |
| History | untouched, full 39-commit narrative | same narrative, filtered + scrubbed (see §4) |

Genesis remains the answer to "how was this built"; upstream answers "what is
this and how do I use it".

## 2. Upstream layout (familiar to llm-d / kgateway / vLLM readers)

Rust idiom mapped onto llm-d's Go-shaped conventions:

```
llm-d-sc/
  README.md              badges, what it is, quickstart, architecture, community
  CONTRIBUTING.md        DCO, dev loop, review expectations
  CODE_OF_CONDUCT.md     CNCF CoC by reference
  SECURITY.md            reporting, supported versions
  MAINTAINERS.md         + CODEOWNERS
  ADOPTERS.md            empty-but-present, invites adopters
  LICENSE                Apache-2.0
  AGENTS.md              SLIM: build/test/convention pointers only
                         (kgateway ships one; the conducting rules stay in genesis)
  src/                   library crate (config, runtime, cache, handoff, grpc, classify)
  src/bin/               binaries (server, bench-runner)   <- Rust analogue of cmd/
  proto/                 the wire contract
  tests/                 integration + parity suites
  benches/               criterion microbenchmarks (later)
  deploy/                Kubernetes/OpenShift manifests, ModelCar build
  examples/              dummy AI-Gateway client, config samples
  hack/                  build/verify/test-impact/test-parity/fetch-model
  docs/
    architecture.md      the hot path, boundaries, state ownership
    performance.md       measured numbers + methodology (from docs/benchmarks/)
    research/            CONDENSED research (see §3)
    decisions/           ADRs that are product decisions (0001, 0002)
  specs/                 the SDD record: 0.1-mvp + phase stubs, evidence trail
  .github/workflows/     product CI only (fast-ci, validation)
```

Deliberately NOT upstream: `pipeline/`, `.opencode/`, `.agent/`, `evals/`
(reviewer rubric), `artifacts/` (178MB of run detritus + model weights),
`docs/SDD.md`/`TDD.md`/`PROCESS_REVIEW.md` in full, and the raw research corpus.

## 3. Research condensation

The two research documents (3,400 lines) become upstream design rationale, not
lab notes:

- `docs/research/runtime-performance.md` — the Rust latency guide distilled to
  the decisions actually implemented (tokio for I/O only, bounded inference,
  Candle backend, cache identity, benchmark methodology) with measured results
  substituted for predictions.
- `docs/research/asdlc-notes.md` — one page: this project was built with an
  evidence-gated agentic process; pointer to the genesis repo for the full
  method. Upstream readers should not need to care.

Full originals stay in genesis `research/`.

## 4. History transfer (the hard requirement)

The 39-commit narrative transfers with authorship, dates, and messages intact.
Mechanism: `git filter-repo` on a fresh clone, never on the working repo.

```
git clone --no-local llm-d-sc-genesis llm-d-sc-export && cd llm-d-sc-export
git filter-repo \
  --path src --path proto --path tests --path specs --path docs \
  --path hack --path Containerfile --path Cargo.toml --path Cargo.lock \
  --path .github --path .gitignore \
  --path-rename docs/benchmarks:docs/performance \
  --replace-text ../praxis-scrub.txt \
  --message-callback '<scrub + append Signed-off-by>'
```

Four things this must do:

1. **Path filter** — drop the lab-only trees listed in §2 from every commit, so
   the upstream history contains no `pipeline/` or `artifacts/` blobs (this also
   removes the 178MB of weights/logs from history, which matters for clone time).
2. **Praxis scrub across all history** — 38 files currently reference it, plus 3
   commit messages. `--replace-text` handles blob content; a message callback
   handles subjects/bodies. Renames: `dummy_praxis.rs -> dummy_gateway.rs`,
   `DummyPraxis -> DummyGateway`, `tests/DUMMY_PRAXIS.md -> DUMMY_GATEWAY.md`,
   prose "Praxis" -> "the AI Gateway".
3. **DCO signoff — currently ABSENT on all 39 commits.** CNCF/llm-d gate merges
   on DCO; a history without `Signed-off-by` will be rejected. The message
   callback must append `Signed-off-by: C.J. Nuland <cjnuland@gmail.com>` to
   every commit. This is the single most likely thing to block the first push,
   and it is only fixable during the rewrite.
4. **Author normalisation** — commits are split between `cnuland
   <cnuland@users.noreply.github.com>` (35) and `C.J. Nuland
   <cjnuland@gmail.com>` (2); unify via `--mailmap` so the log reads cleanly.

Then, on top of the filtered history, ONE restructuring commit adds the
community files (README, CONTRIBUTING, CoC, SECURITY, MAINTAINERS, ADOPTERS,
CODEOWNERS) and performs the layout moves. Result: a repo whose `git log` shows
the real engineering story, ending in a deliberate "prepare for upstream" commit.

Note: filter-repo rewrites SHAs. Genesis keeps the originals; a mapping file
(`.git/filter-repo/commit-map`) is retained in genesis for traceability.

## 5. README shape (following llm-d + kgateway conventions)

1. Title + one-line value proposition + badge row (CI, license, CNCF/llm-d,
   OpenSSF best practices, Slack)
2. **What is llm-d-sc** — semantic classification for inference routing; the
   "classify, never route" boundary stated immediately
3. **Why** — the problem an AI Gateway has without it (bullets, no marketing)
4. **Quick start** — run the service against a ModelCar, one classify call
5. **Architecture** — the hot-path diagram (gateway -> cache -> bounded queue ->
   resident runtime -> ranked signals) and what the service does NOT own
6. **Performance** — the measured table with methodology link and honest scope
7. **Project status** — pre-1.0, phase roadmap from VERSIONS.md, what is proven
   vs pending (this is a strength with maintainers, not a weakness)
8. **Community** — llm-d SIG, meetings, Slack channel, good-first-issues
9. **Contributing** — DCO, dev loop, spec-driven expectations
10. **License** — Apache-2.0

Explicitly avoided: benchmark claims without methodology, "production ready"
language pre-1.0, and any implication that the sensitivity taxonomy is verified.

## 6. Sequenced plan

| Step | Owner | Gate |
|---|---|---|
| 1. Finish P0s + local sweep in genesis | agents | spec-check ledger |
| 2. Praxis -> AI Gateway rename IN GENESIS first (code + specs) | worker slice | verify green |
| 3. Condense research into docs/research/ | reviewer | maintainer read |
| 4. Author upstream README + governance set | reviewer | maintainer approval |
| 5. Dry-run filter-repo into a scratch dir; inspect log, tree, sizes | reviewer | no praxis, DCO present, weights absent |
| 6. Push to the new upstream `main` | maintainer | maintainer only |
| 7. Genesis adds a pointer README section: "upstream lives at ..." | reviewer | — |

Doing step 2 in genesis first means the rename is reviewed under the existing
evidence gates rather than performed blind during a history rewrite.


## Issue backlog additions (signal types and custom domains)

From the maintainer, 2026-08-18: release 0.1 is a GENERIC domain classifier.
Everything below is future work and must exist as tracked issues rather than
README caveats, so each incomplete capability maps to an issue:

| Issue | Capability | Notes |
|---|---|---|
| complexity signal | estimate prompt complexity/depth to drive model tiering | needs a classifier or heuristic + calibration |
| sensitivity signal | data sensitivity / risk level | the early fixture model becomes an opt-in backend here; taxonomy still needs verifying |
| cost signal | cost/budget-aware routing evidence | likely derived rather than a model |
| custom domain classifiers | route by business function: sales, shipping, finance, support | the key adopter-facing capability; needs a documented path to bring your own labels |
| multi-signal response | several signal types in ONE response with independent status | phase 0.23; partial failure semantics matter |
| per-classifier lanes | separate queues/concurrency per classifier | prevents one signal starving another |

The generic classifier stays the default in every case; custom and additional
classifiers are opt-in by configuration (ADR-0005).
