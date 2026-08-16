# Working memory (rewrite aggressively; this is not history)

## Active work (AC-010 — response contains signals, not final route — GREEN)

Spec: 0.1-mvp
Active criterion: AC-010 "response contains signals, not final route."
Tests mapped: `specs/0.1-mvp/test-plan.md` -> U-010, I-007.
Status: LOCAL-GREEN complete this turn (TDD RED->GREEN executed directly).

## Escalation resolved
The AC-010 contradiction (field kept-but-never-set vs removed) was adjudicated in
my favor by the reviewer via `docs/decisions/0001-no-route-field-in-response.md`:
interpretation (B) is authoritative — the route field is REMOVED from the schema
entirely; U-010 is a SCHEMA invariant. The reviewer also recorded a review miss
(AC-009 passed with the field present).

## This turn (TDD order, worked directly, no subagents)
1. RED: wrote `tests/schema.rs` U-010 (deterministic plain `#[test]`, reads
   `proto/classify.proto`, parses `ClassifyResponse` field declarations, asserts
   no final_route/route/endpoint/target field). Ran `cargo test --test schema
   --locked` -> RED for the right reason (field exists). Recorded
   `specs/0.1-mvp/evidence/AC-010/RED-U010.md`.
2. Removed `optional string final_route = 3;` from `ClassifyResponse` in
   `proto/classify.proto`.
3. Privileged existing-test change (authorized by ADR-0001): replaced
   `response.final_route.is_none()` in `tests/grpc.rs` i001 with the U-010 schema
   invariant (no field to reference).
4. Added `tests/grpc.rs` I-007 `i007_response_cannot_dictate_endpoint`: dummy
   Praxis receives a response; the ONLY route in the system is the one it
   computes itself; asserts the response type offers no route to consume.
5. GREEN: `cargo test --test schema --locked` 2/2; `cargo test --test grpc
   --locked` 5/5. Recorded GREEN-U010.md, GREEN-I007.md, LOCAL-GREEN.md.

## Required suites (all green)
- `./hack/test-impact`: Required tests/grpc; Recommended cargo test (unit) — both pass.
- `./hack/spec-check 0.1-mvp`: OK (AC-010 LOCAL-GREEN).
- `./hack/verify`: PASSED (22 unit + 5 grpc + 2 schema + 0 doc, 5 ignored Candle).
- `cargo test --test grpc --locked`: 5/5 green.

## Files changed this turn (uncommitted, no commit/push)
- `proto/classify.proto` (removed final_route field)
- `src/grpc/classify.rs` (removed final_route: None in response build)
- `tests/grpc.rs` (i001 assertion replaced by schema invariant; added i007)
- `tests/schema.rs` (new U-010 + generated-type surface tests)
- `specs/0.1-mvp/evidence/AC-010/{RED-U010,GREEN-U010,GREEN-I007,LOCAL-GREEN}.md`
- `.agent/state/current.md`

## Worktree
- HEAD SHA `e6361b73c4865d14fee6147a218463d9ec30099f`, working tree has the above
  changes plus pre-existing untracked ADR (`docs/decisions/`) and `tests/TEST_MATRIX.md`.
- No commits/pushes (worker never commits).

## Next step
Stop per AGENTS.md step 10. AC-010 is locally green and ready for review
(review-prep skill is available for the evidence bundle if requested).
