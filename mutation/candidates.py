"""Mutations for the candidate survey."""

from mutation.runner import Mutation, Suite

SUITE = Suite(
    label="candidates",
    module="discovery/candidates.py",
    tests=["tests/test_candidates.py"],
    mutations=[
        Mutation(
            "a low score becomes a rejection",
            "    if not units and not found.hidden_tests:",
            "    if not units or sum(SCORE_WEIGHTS.values()) > 40:",
        ),
        Mutation(
            "an unreadable file is read as an empty one",
            "            markers = len(_MARKER_RE.findall(source))",
            "            markers = 0",
        ),
        Mutation(
            "hidden markers no longer keep a project in",
            "    if not units and not found.hidden_tests:",
            "    if not units:",
        ),
        Mutation(
            "any decorator named given counts",
            '        if _resolve(aliases, _dotted(func)) != "hypothesis.given":',
            '        if not (_dotted(func) or "").endswith("given"):',
        ),
        Mutation(
            "a dotted import binds its full path",
            '                    head = entry.name.split(".")[0]\n                    aliases[head] = head',
            '                    aliases[entry.name.split(".")[0]] = entry.name',
        ),
        Mutation(
            "positional strategies do not bind trailing parameters",
            "        if args:\n            supplied.update(params[len(params) - len(args) :])",
            "        if False:\n            supplied.update(params)",
        ),
        Mutation(
            "self counts as a fixture",
            '            if arg.arg != "self"',
            "            if True",
        ),
        Mutation(
            "skipped directories are walked",
            '    found = []\n    for root, dirs, names in os.walk(project_dir):\n        dirs[:] = [\n            d for d in sorted(dirs) if d not in SKIP_DIRS and not d.startswith(".venv")\n        ]\n        for name in sorted(names):\n            if name.endswith(".py"):',
            '    found = []\n    for root, dirs, names in os.walk(project_dir):\n        for name in sorted(names):\n            if name.endswith(".py"):',
        ),
        Mutation(
            "state machine bases are not recognized",
            '                if (_resolve(aliases, _dotted(base)) or "").endswith(\n                    "RuleBasedStateMachine"\n                ):',
            "                if False:",
        ),
        Mutation(
            "composites are counted as property tests",
            "            elif _is_composite(node, aliases):\n                module.composites.append(node.name)",
            "            elif _is_composite(node, aliases):\n                pass",
        ),
        Mutation(
            "opaque and external imports score alike",
            "    clear_opaque, opaque = _share_clear(found, OPAQUE_IMPORTS)",
            "    clear_opaque, opaque = _share_clear(found, EXTERNAL_RESOURCE_IMPORTS)",
        ),
        Mutation(
            "breadth stops distinguishing sizes",
            "    breadth = math.log10(1 + min(units, BREADTH_SATURATION)) / math.log10(\n        1 + BREADTH_SATURATION\n    )",
            "    breadth = 1.0",
        ),
        Mutation(
            "domain strategies stop counting",
            "            min(1.0, len(found.composites) / DOMAIN_SATURATION),",
            "            0.0,",
        ),
        Mutation(
            "an uncontrolled source moves the score instead of noting it",
            "        result.notes.append(\n            f\"draws from {', '.join(risky)}, which the solver does not control\"\n        )",
            "        result.signals = result.signals[:-1]",
        ),
        Mutation(
            "a blocked project does not sort last",
            "    return sorted(assessed, key=lambda a: (not a.runnable, -a.score))",
            "    return sorted(assessed, key=lambda a: -a.score)",
        ),
        Mutation(
            "describe prints signals for a blocked project",
            '        if not self.runnable:\n            return [f"{name}: not runnable -- {self.blocker}"]',
            "        if False:\n            return []",
        ),
        Mutation(
            "fixtures never lower the score",
            "            len(fixtureless) / len(tests) if tests else 1.0,",
            "            1.0,",
        ),
        Mutation(
            "a compiled extension costs nothing",
            "            0.0 if found.native_markers else 1.0,",
            "            1.0,",
        ),
        Mutation(
            "cargo is not a sign of a compiled extension",
            'NATIVE_BUILD_FILES = ("Cargo.toml", "build.rs", "meson.build", "CMakeLists.txt")',
            'NATIVE_BUILD_FILES = ("meson.build",)',
        ),
        Mutation(
            "cython sources are not noticed",
            'NATIVE_SOURCE_SUFFIXES = (".pyx", ".pxd")',
            'NATIVE_SOURCE_SUFFIXES = (".nope",)',
        ),
        Mutation(
            "any setup.py counts as building an extension",
            "            if any(marker in text for marker in _EXTENSION_MARKERS):",
            "            if True:",
        ),
        Mutation(
            "the weights no longer add up to the reported total",
            '    "breadth": 25,',
            '    "breadth": 26,',
        ),
    ],
)
