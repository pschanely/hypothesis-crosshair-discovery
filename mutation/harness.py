"""Mutations for harness repair."""

from mutation.runner import Mutation, Suite

SUITE = Suite(
    label="harness",
    module="discovery/harness.py",
    tests=["tests/test_harness.py"],
    mutations=[
        Mutation(
            "xdist is installed but left switched on",
            'NEUTRALIZED_PLUGINS = {"pytest-xdist": ["-n0"]}',
            "NEUTRALIZED_PLUGINS = {}",
        ),
        Mutation(
            "every plugin gets neutralized",
            "        neutralize = [\n            arg for dist in distributions for arg in NEUTRALIZED_PLUGINS.get(dist, [])\n        ]",
            '        neutralize = ["-n0"]',
        ),
        Mutation(
            "an unfamiliar failure is repaired anyway",
            "    return None\n\n\ndef _mentions_crosshair(",
            '    return Repair(name="guess", rationale="?", packages=["pytest"])\n\n\ndef _mentions_crosshair(',
        ),
        Mutation(
            "an unmapped import is guessed from its module name",
            '        dist = MODULE_DISTRIBUTIONS.get(module.split(".")[0])',
            '        dist = MODULE_DISTRIBUTIONS.get(module.split(".")[0], module)',
        ),
        Mutation(
            "only the first unrecognized flag is handled",
            "    for flag in flags:\n        dist = _distribution_for_flag(flag)",
            "    for flag in flags[:1]:\n        dist = _distribution_for_flag(flag)",
        ),
        Mutation(
            "flags are matched exactly rather than by prefix",
            "        if bare.startswith(prefix):",
            "        if bare == prefix:",
        ),
        Mutation(
            "a repair repeats forever",
            "    if found is None or found.name in applied:",
            "    if found is None:",
        ),
        Mutation(
            "the repair budget is ignored",
            "    if len(applied) >= MAX_REPAIRS:\n        return None",
            "    if False:\n        return None",
        ),
        Mutation(
            "a repair gains the power to edit a file",
            "    pytest_args: List[str] = field(default_factory=list)",
            '    pytest_args: List[str] = field(default_factory=list)\n    patch_file: str = ""',
        ),
        Mutation(
            "describe hides the packages",
            "        if self.packages:\n            parts.append(f\"install {' '.join(self.packages)}\")",
            '        if False:\n            parts.append("")',
        ),
        Mutation(
            "a repairable failure is escalated to a person",
            "        repair = harness.plan(str(exc))",
            "        repair = None",
            path="discovery/cli.py",
        ),
        Mutation(
            "non-flag words are treated as flags",
            '            if flag.startswith("-") and flag not in found:',
            "            if flag not in found:",
        ),
        Mutation(
            "a prefix may shadow another distribution",
            '    "--numprocesses": "pytest-xdist",',
            '    "--benchmark-sort": "pytest-cov",',
        ),
        Mutation(
            "a partly deselected run is overridden too",
            "    if deselected and not _SELECTED_RE.search(text):",
            "    if deselected:",
        ),
        Mutation(
            "the marker filter is not actually overridden",
            '            pytest_args=["-m", ""],',
            "            pytest_args=[],",
        ),
        Mutation(
            "an unknown marker is guessed at",
            '    if marker and marker.group("marker") in MARKER_DISTRIBUTIONS:',
            "    if marker:",
        ),
        Mutation(
            "a crosshair collection error is skipped like any other",
            "    if errors and not _mentions_crosshair(text):",
            "    if errors:",
        ),
        Mutation(
            "unimportable modules are installed rather than skipped",
            '            pytest_args=[f"--ignore={path}" for path in errors],',
            "            packages=list(errors),",
        ),
        Mutation(
            "the ignored modules are not named",
            '                "these test modules could not be imported, so none of their "\n                f"tests can run: {\', \'.join(errors)}"',
            '                "some test modules could not be imported"',
        ),
        Mutation(
            "a known test dependency is skipped instead of installed",
            '        dist = MODULE_DISTRIBUTIONS.get(module.split(".")[0])\n        if dist:',
            "        dist = None\n        if dist:",
        ),
    ],
)
