"""Mutations for the baseline gate and the differential."""

from mutation.runner import Mutation, Suite

SUITE = Suite(
    label="classify",
    module="discovery/classify.py",
    tests=["tests/test_classify.py"],
    mutations=[
        Mutation(
            "non-decisive outcomes count as disagreement",
            "        decisive = [o for o in outcomes if o in (Outcome.PASSED, Outcome.FAILED)]",
            "        decisive = list(outcomes)",
        ),
        Mutation(
            "an all-error baseline is judged stable",
            "        if not decisive:\n            stability = Stability.NO_RESULT",
            "        if False:\n            stability = Stability.NO_RESULT",
        ),
        Mutation(
            "real disagreement is swallowed",
            "        else:\n            stability = Stability.UNSTABLE",
            "        else:\n            stability = Stability.STABLE_PASS",
        ),
        Mutation(
            "the no-result rationale hides what happened",
            '        result.rationale = (\n            "the baseline arm produced no pass or fail for this test: "\n            + ", ".join(o.value for o in baseline.outcomes)\n        )',
            '        result.rationale = "no result"',
        ),
    ],
)
