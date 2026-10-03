"""Mutations for telemetry clues, which must never decide a verdict."""

from mutation.runner import Mutation, Suite

SUITE = Suite(
    label="clues",
    module="discovery/telemetry.py",
    tests=["tests/test_classify.py", "tests/test_telemetry.py"],
    mutations=[
        Mutation(
            "telemetry decides a verdict again",
            '    result.rationale = "neither arm found a failure"',
            '    if stats is not None and stats.crosshair_cases:\n        result.verdict = Verdict.QUARANTINED_NONDETERMINISTIC\n    result.rationale = "neither arm found a failure"',
            path="discovery/classify.py",
        ),
        Mutation(
            "exhaustion decides a verdict again",
            '            result.verdict = Verdict.CROSSHAIR_FALSE_NEGATIVE\n            result.rationale = "baseline fails but CrossHair does not"',
            '            result.verdict = (\n                Verdict.SOUNDNESS_SUSPECT\n                if stats is not None and stats.counts\n                else Verdict.CROSSHAIR_FALSE_NEGATIVE\n            )\n            result.rationale = "baseline fails but CrossHair does not"',
            path="discovery/classify.py",
        ),
        Mutation(
            "a clue carries no follow-up",
            '                    "re-run with a larger budget before treating "\n                    f"\'{verdicts[nodeid]}\' as evidence the solver explored this",',
            '                    "",',
        ),
        Mutation(
            "degraded search clues on every verdict",
            '        if search_is_degraded(entry) and verdicts.get(nodeid) in (\n            "crosshair_false_negative",\n            "no_signal",\n        ):',
            "        if search_is_degraded(entry):",
        ),
        Mutation(
            "the observer_effect entry masks the verdict",
            "        if item.verdict is not Verdict.OBSERVER_EFFECT or item.nodeid not in verdicts:\n            verdicts[item.nodeid] = item.verdict.value",
            "        verdicts[item.nodeid] = item.verdict.value",
            path="discovery/cli.py",
        ),
        Mutation(
            "healthy runs produce clues",
            "        if not entry.crosshair_cases:\n            continue",
            "        if False:\n            continue",
        ),
    ],
)
