"""Mutations for the decider scorecard."""

from mutation.runner import Mutation, Suite

SUITE = Suite(
    label="evaluate",
    module="discovery/evaluate.py",
    tests=["tests/test_evaluate.py"],
    mutations=[
        Mutation(
            "nothing is dangerous",
            "            and self.case.expected is not TriageCategory.PROJECT_BUG\n        )",
            "            and False\n        )",
        ),
        Mutation(
            "a correct project bug counts as dangerous",
            "        return (\n            self.predicted is TriageCategory.PROJECT_BUG\n            and self.case.expected is not TriageCategory.PROJECT_BUG\n        )",
            "        return self.predicted is TriageCategory.PROJECT_BUG",
        ),
        Mutation(
            "no finding is ever lost",
            "        return self.case.expected is TriageCategory.PROJECT_BUG and self.predicted in (",
            "        return False and self.predicted in (",
        ),
        Mutation(
            "deferral is not counted",
            "            self.predicted is TriageCategory.UNCLEAR\n            and self.case.expected is not TriageCategory.UNCLEAR",
            "            False\n            and self.case.expected is not TriageCategory.UNCLEAR",
        ),
        Mutation(
            "stream confusion is not counted",
            "            self.predicted in pair and self.case.expected in pair and not self.correct",
            "            False",
        ),
        Mutation(
            "an unusable answer is scored as correct",
            "    @property\n    def correct(self) -> bool:\n        return self.predicted is self.case.expected",
            "    @property\n    def correct(self) -> bool:\n        return self.predicted is self.case.expected or self.predicted is None",
        ),
        Mutation(
            "a raising decider is not recorded",
            '            card.outcomes.append(\n                Outcome(case, None, error=f"{type(exc).__name__}: {exc}")\n            )\n            continue',
            "            continue",
        ),
        Mutation(
            "the confusion table drops unusable answers",
            '            name = outcome.predicted.value if outcome.predicted else "unusable"',
            "            if outcome.predicted is None:\n                continue\n            name = outcome.predicted.value",
        ),
        Mutation(
            "the summary buries the dangerous count",
            '            f"  reaching a stranger: {len(self.reaching_a_stranger)}   "\n            "(called someone else\'s correct code a bug)",\n        ]',
            '        ]\n        lines.append(f"  lost findings pre: {len(self.lost_findings)}")\n        lines.append(\n            f"  reaching a stranger: {len(self.reaching_a_stranger)}"\n        )\n        _unused = [',
        ),
    ],
)
