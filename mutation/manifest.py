"""Mutations for recording and rebuilding an environment."""

from mutation.runner import Mutation, Suite

SUITE = Suite(
    label="manifest",
    module="discovery/manifest.py",
    tests=["tests/test_manifest.py"],
    mutations=[
        Mutation(
            "the toolchain is pinned along with everything else",
            "    excluded = {requirement_name(name) for name in closure}",
            "    excluded = set()",
        ),
        Mutation(
            "only the toolchain's own names are kept free, not what it brought",
            "    excluded = {requirement_name(name) for name in closure}",
            "    excluded = TOOLCHAIN",
        ),
        Mutation(
            "pins are compared by spelling rather than by distribution",
            "    return [line for line in requirements if requirement_name(line) not in excluded]",
            "    return [line for line in requirements if line not in excluded]",
        ),
        Mutation(
            "an unreadable closure pins the toolchain too",
            "    if done.returncode != 0:\n        return sorted(TOOLCHAIN)\n    try:",
            "    if done.returncode != 0:\n        return []\n    try:",
        ),
        Mutation(
            "an unparsable closure pins the toolchain too",
            "    except (ValueError, IndexError):\n        return sorted(TOOLCHAIN)",
            "    except (ValueError, IndexError):\n        return []",
        ),
        Mutation(
            "editable installs are pinned, so a rebuild wants a path that is gone",
            '        if not line or line.startswith(("#", "-e", "-")) or "==" not in line:',
            "        if not line:",
        ),
        Mutation(
            "freezing is allowed the network",
            "        list(FREEZE_ARGV) + [python],\n        cwd=cwd,\n        network=False,",
            "        list(FREEZE_ARGV) + [python],\n        cwd=cwd,\n        network=True,",
        ),
        Mutation(
            "the closure probe is allowed the network",
            '        [python, "-c", _CLOSURE_PROBE, json.dumps(sorted(TOOLCHAIN))],\n        cwd=cwd,\n        network=False,',
            '        [python, "-c", _CLOSURE_PROBE, json.dumps(sorted(TOOLCHAIN))],\n        cwd=cwd,\n        network=True,',
        ),
        Mutation(
            "a requirement named only under an extra counts as the toolchain's",
            '        head, _, marker = raw.partition(";")\n        if "extra" in marker:\n            continue\n        dep = head.split("[")[0]',
            '        head, _, marker = raw.partition(";")\n        dep = head.split("[")[0]',
        ),
        Mutation(
            "a conditional requirement that is not an extra is dropped",
            '        head, _, marker = raw.partition(";")\n        if "extra" in marker:\n            continue',
            '        head, _, marker = raw.partition(";")\n        if marker:\n            continue',
        ),
        Mutation(
            "the resolved toolchain versions are never recorded",
            '                versions[name] = line.split("==", 1)[1]',
            "                pass",
        ),
        Mutation(
            "the collected count is not carried, so nothing can detect drift",
            "        collected=built.collected,",
            "        collected=0,",
        ),
        Mutation(
            "the repairs are not carried into the manifest",
            "        repairs=list(built.repairs),",
            "        repairs=[],",
        ),
        Mutation(
            "a manifest written by other code is read anyway",
            '    if not isinstance(raw, dict) or raw.get("version") != MANIFEST_VERSION:',
            "    if not isinstance(raw, dict):",
        ),
        Mutation(
            "the rebuild pins nothing",
            "        sandbox, result.python, [*project, *tools, *stored.pins], project_dir, {}",
            "        sandbox, result.python, [*project, *tools], project_dir, {}",
        ),
        Mutation(
            "the rebuild pins the toolchain it is meant to be measuring",
            "    tools = toolchain_requirements(plugin or stored.plugin)",
            "    tools = []",
        ),
        Mutation(
            "a project that never built is installed anyway",
            '    project = ["-e", project_dir] if stored.installs_project else []',
            '    project = ["-e", project_dir]',
        ),
        Mutation(
            "a project that built is left uninstalled",
            '    project = ["-e", project_dir] if stored.installs_project else []',
            "    project = []",
        ),
        Mutation(
            "refused pins end the rebuild",
            "    if not installed:\n        result.resolved_afresh = True",
            "    if False:\n        result.resolved_afresh = True",
        ),
        Mutation(
            "a rebuild that had to re-resolve does not say so",
            "        result.resolved_afresh = True",
            "        pass",
        ),
        Mutation(
            "a rebuild that cannot install at all reports success",
            '        if not installed:\n            result.error = f"install failed: {detail.strip()[-300:]}"\n            return result',
            "        if False:\n            pass",
        ),
        Mutation(
            "the manifest's pytest arguments are dropped on rebuild",
            "        sandbox, result.python, project_dir, stored.pytest_args, stored.env",
            "        sandbox, result.python, project_dir, [], stored.env",
        ),
        Mutation(
            "the manifest's environment is dropped on rebuild",
            "        sandbox, result.python, project_dir, stored.pytest_args, stored.env",
            "        sandbox, result.python, project_dir, stored.pytest_args, {}",
        ),
        Mutation(
            "a rebuild that cannot collect counts as ready",
            '    if not ok:\n        result.error = f"collection failed: {text.strip()[-300:]}"\n        return result',
            "    if False:\n        pass",
        ),
        Mutation(
            "a changed suite is not reported as drift",
            "        return self.ready and self.collected != self.manifest.collected",
            "        return False",
        ),
        Mutation(
            "a failed rebuild reports drift it never measured",
            "        return self.ready and self.collected != self.manifest.collected",
            "        return self.collected != self.manifest.collected",
        ),
        Mutation(
            "a rebuilt environment is allowed the network while collecting",
            "    ok, text, count = collect(",
            "    sandbox.run([result.python, '-c', ''], cwd=project_dir, network=True)\n    ok, text, count = collect(",
        ),
    ],
)
