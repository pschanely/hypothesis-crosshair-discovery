"""Mutations for building an environment."""

from mutation.runner import Mutation, Suite

SUITE = Suite(
    label="provision",
    module="discovery/provision.py",
    tests=["tests/test_provision.py"],
    mutations=[
        Mutation(
            "collection is allowed to use the network",
            '        [python, "-m", "pytest", "--collect-only", "-q"] + list(pytest_args),\n        cwd=project_dir,\n        env=env,\n        network=False,',
            '        [python, "-m", "pytest", "--collect-only", "-q"] + list(pytest_args),\n        cwd=project_dir,\n        env=env,\n        network=True,',
        ),
        Mutation(
            "installing is denied the network",
            "        cwd=cwd,\n        env=env,\n        network=True,",
            "        cwd=cwd,\n        env=env,\n        network=False,",
        ),
        Mutation(
            "the plugin is never installed",
            "    everything = [*toolchain_requirements(plugin), *extra_packages]",
            "    everything = [*BASE_PACKAGES, *extra_packages]",
        ),
        Mutation(
            "extra packages are dropped",
            "    everything = [*toolchain_requirements(plugin), *extra_packages]",
            "    everything = [*toolchain_requirements(plugin)]",
        ),
        Mutation(
            "a failed environment goes on to install",
            '    if made.returncode != 0:\n        result.error = f"could not create a virtual environment: {made.stderr[-300:]}"\n        return result',
            "    if False:\n        pass",
        ),
        Mutation(
            "a failed install goes on to collect",
            '            result.error = f"install failed: {detail.strip()[-300:]}"\n            return result',
            "            pass",
        ),
        Mutation(
            "a project that cannot collect counts as provisioned",
            "        if ok:\n            result.collected = count\n            return result",
            "        result.collected = count\n        return result",
        ),
        Mutation(
            "an unfamiliar failure is repaired anyway",
            "        if repair is None:",
            "        if False:",
        ),
        Mutation(
            "a repair's arguments are not carried into the retry",
            "        result.pytest_args.extend(repair.pytest_args)",
            "        pass",
        ),
        Mutation(
            "a repair's packages are never installed",
            "        if repair.packages:",
            "        if False:",
        ),
        Mutation(
            "a failed repair install is ignored",
            '                result.error = (\n                    f"repair {repair.name} could not install "\n                    f"{\' \'.join(repair.packages)}: {detail.strip()[-200:]}"\n                )\n                return result',
            "                pass",
        ),
        Mutation(
            "repairs are never recorded, so they repeat forever",
            "        result.repairs.append(repair.name)",
            "        pass",
        ),
        Mutation(
            "an empty collection counts as a broken harness",
            "_CLEAN_COLLECT_CODES = (0, 5)",
            "_CLEAN_COLLECT_CODES = (0,)",
        ),
        Mutation(
            "the collected count is never read",
            '_COLLECTED_RE = re.compile(r"(?P<count>\\d+)\\s+tests? collected")',
            '_COLLECTED_RE = re.compile(r"(?P<count>\\d+)\\s+NOPE collected")',
        ),
        Mutation(
            "a failed build is a failed provisioning",
            "        without_project, retry_detail = install(\n            sandbox, result.python, everything, project_dir, {}\n        )\n        if not without_project:",
            "        if True:",
        ),
        Mutation(
            "the retry installs the project again",
            "        without_project, retry_detail = install(\n            sandbox, result.python, everything, project_dir, {}\n        )",
            '        without_project, retry_detail = install(\n            sandbox, result.python, ["-e", project_dir, *everything], project_dir, {}\n        )',
        ),
        Mutation(
            "running from the checkout is not recorded",
            "        result.repairs.append(RUN_FROM_CHECKOUT)",
            "        pass",
        ),
    ],
)
