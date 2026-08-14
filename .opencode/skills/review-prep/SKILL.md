---
name: review-prep
description: Produce the machine-readable evidence bundle the reviewer requires. Use when a logical slice is locally green and ready for review.
---
# review-prep

Run `./pipeline/review-bundle.sh <spec-id>`. It assembles:
diff, changed-file list, test-impact manifest, verify/test output tails, spec + criterion
mapping, and your engineering explanation (what / why / alternatives rejected / proof /
regression risk / rollback). Write the explanation into `artifacts/review/explanation.md`
BEFORE running the bundler. The reviewer checks the explanation against the diff — write
what the diff actually does, not what you intended.

Deletion test: if bundles assembled without this skill are never rejected for missing
evidence across 20 reviews, delete it.
