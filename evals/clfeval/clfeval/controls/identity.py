"""Artifact identity — make "we benchmarked the wrong deployment" impossible.

The finding that motivated this: a runtime qualification returned 63.67% while the
project's own checkpoint scored 81.82% on identical rows. The first question that
raises is not "why is the model worse" but "WHICH MODEL IS THAT?" -- and until the
runtime is asked directly, the honest answer is that nobody knows.

llm-d-sc reports `model_revision`, `tokenizer_revision`, `taxonomy_revision` and
`classifier_id` on every ClassifyResponse. This control compares what the runtime
SAYS it is running against what the suite EXPECTED, and fails when they differ or
when the runtime declines to say.

Deliberately blocking, and deliberately failing on "unknown": an unidentifiable
artifact cannot be qualified, because the qualification would not be attributable
to anything.
"""
from __future__ import annotations
from .base import Control, Status


class ArtifactIdentityControl(Control):
    name = "artifact_identity"

    def run(self, ctx):
        ad = ctx.get("adapter")
        if ad is None or getattr(ad, "plane", "model") != "runtime":
            return self._r(Status.NOT_APPLICABLE,
                           "model-plane run — artifact identity is verified by the "
                           "checkpoint digest, not by a serving contract")
        reported = {
            "model_revision": getattr(ad, "revision", None),
            "taxonomy_revision": getattr(ad, "taxonomy_revision_reported", None),
            "runtime": getattr(ad, "runtime_revision", None),
        }
        if not reported["model_revision"] or reported["model_revision"] == "unknown":
            return self._r(Status.FAIL,
                "the runtime did not report a model revision: this qualification "
                "cannot be attributed to a specific artifact", **reported)

        expected = ctx.get("expected_identity") or {}
        mismatches = []
        for k in ("model_revision", "taxonomy_revision"):
            exp = expected.get(k)
            got = reported.get(k)
            if exp and got and exp not in str(got):
                mismatches.append(f"{k}: expected {exp}, runtime reports {got}")
        if mismatches:
            return self._r(Status.FAIL,
                "DEPLOYED ARTIFACT IS NOT THE ONE UNDER QUALIFICATION — "
                + "; ".join(mismatches), **reported)

        drift = getattr(ad, "taxonomy_mismatch", None)
        if drift:
            return self._r(Status.FAIL,
                f"taxonomy drift: the runtime never scores label(s) {drift} that "
                f"the task spec declares", **reported)

        if not expected:
            return self._r(Status.WARN,
                f"runtime identity recorded but not pinned by the suite: "
                f"{reported['model_revision']} / taxonomy "
                f"{reported['taxonomy_revision']}. Declare expected_identity to "
                f"make a wrong-deployment benchmark impossible", **reported)
        return self._r(Status.PASS,
            f"runtime artifact matches: {reported['model_revision']}, taxonomy "
            f"{reported['taxonomy_revision']}", **reported)
