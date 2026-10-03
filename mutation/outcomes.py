"""Mutations for routing a triaged cluster."""

from mutation.runner import Mutation, Suite

SUITE = Suite(
    label="outcomes",
    module="discovery/outcomes.py",
    tests=["tests/test_outcomes.py"],
    mutations=[
        Mutation(
            "an unconfirmed project bug is promoted anyway",
            "            if _is_trophy_eligible(group, by_nodeid):",
            "            if True:",
        ),
        Mutation(
            "pending_validation counts as a confirmation",
            "TROPHY_ELIGIBLE = frozenset({Verdict.TROPHY_CANDIDATE})",
            "TROPHY_ELIGIBLE = frozenset(\n    {Verdict.TROPHY_CANDIDATE, Verdict.PENDING_VALIDATION}\n)",
        ),
        Mutation(
            "a crosshair artifact still drafts a trophy",
            "        if verdict.category is TriageCategory.CROSSHAIR_ARTIFACT:",
            "        if False:",
        ),
        Mutation(
            "an overstrong property is treated as a bug",
            "        elif verdict.category is TriageCategory.OVERSTRONG_PROPERTY:",
            "        elif False:",
        ),
        Mutation(
            "unclear is silently dropped",
            "        else:\n            routing.needs_human.append(",
            "        elif False:\n            routing.needs_human.append(",
        ),
        Mutation(
            "an untriaged cluster is routed anyway",
            "        if verdict is None:\n            continue",
            "        if verdict is None:\n            verdict = TriageVerdict(\n                TriageCategory.PROJECT_BUG, 0.5, 'assumed'\n            )",
        ),
        Mutation(
            "the baseline effort is not counted",
            '            f"the baseline found nothing in {self.baseline_examples} examples "\n            f"across {self.baseline_seeds} seeds ({total} draws)"',
            '            "random search would not find it"',
        ),
        Mutation(
            "the classifier verdicts are not recorded",
            "        classifier_verdicts=sorted({c.verdict.value for c in seen}),",
            "        classifier_verdicts=[],",
        ),
        Mutation(
            "the falsifying example is dropped",
            '        falsifying_example=group.examples[0] if group.examples else "",',
            '        falsifying_example="",',
        ),
    ],
)
