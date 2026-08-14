---
name: spec-check
description: Map the current diff to the active spec's acceptance criteria and non-goals before finishing a turn. Use before declaring any criterion complete and before requesting review.
---
# spec-check

Run `./hack/spec-check <spec-id>`. Then answer, in the turn output:
1. Which acceptance criterion does this diff satisfy? (exactly one per logical commit)
2. Does any hunk touch files outside the criterion's surface? If yes: revert those hunks
   or justify why they are inseparable.
3. Do any non-goals appear in the diff? If yes: STOP, revert, note in working memory.

Deletion test: if scope-drift findings from the reviewer drop to zero for 20 consecutive
reviews without this skill, delete it.
