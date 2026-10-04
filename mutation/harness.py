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
            "the repair budget is ignored",
            "    if len(applied) >= MAX_REPAIRS:\n        return None",
            "    if False:\n        return None",
        ),
        Mutation(
            "every missing import but the first is ignored",
            "        if head not in found:\n            found.append(head)",
            "        if head not in found and not found:\n            found.append(head)",
        ),
        Mutation(
            "a module name is turned into a distribution without confirmation",
            "    return spelled if spelled in set(declared) else None",
            "    return spelled",
        ),
        Mutation(
            "a declaration overrides the recorded mapping",
            "    known = MODULE_DISTRIBUTIONS.get(module)",
            "    known = None",
        ),
        Mutation(
            "a module name is matched to a declaration without respelling it",
            '    spelled = module.replace("_", "-").lower()',
            "    spelled = module",
        ),
        Mutation(
            "a vendored subproject's declarations are not read",
            "    for directory in _declaring_directories(project_dir):",
            "    for directory in [project_dir]:",
        ),
        Mutation(
            "every directory in the checkout is read, however deep",
            "        if os.path.isdir(path):\n            found.append(path)",
            "        if os.path.isdir(path):\n            found.extend(r for r, _, _ in os.walk(path))",
        ),
        Mutation(
            "a configuration file that cannot be read fails the scan",
            "                except OSError:\n                    continue",
            "                except KeyboardInterrupt:\n                    continue",
        ),
        Mutation(
            "a requirement keeps its version specifier",
            "        name = requirement_name(token)",
            "        name = token.lower()",
        ),
        Mutation(
            "a repeated repair reinstalls what is already there",
            "    fresh = [name for name in found.packages if name not in set(installed)]",
            "    fresh = list(found.packages)",
        ),
        Mutation(
            "a name of any length may be a distribution",
            'r"[a-z][a-z0-9._-]{1,60}"',
            'r"[a-z][a-z0-9._-]{1,600}"',
        ),
        Mutation(
            "a repair with nothing new to install is offered anyway",
            "    if not fresh:\n        return None",
            "    if False:\n        return None",
        ),
        Mutation(
            "a repair that installs nothing may repeat forever",
            "    if not found.packages:\n        return None if found.name in applied else found",
            "    if not found.packages:\n        return found",
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
            "        dist = _distribution_for_module(module, declared)",
            "        dist = None",
        ),
    ],
)
