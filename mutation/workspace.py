"""Mutations for the directory that carries state between containers."""

from mutation.runner import Mutation, Suite

SUITE = Suite(
    label="workspace",
    module="discovery/workspace.py",
    tests=["tests/test_workspace.py"],
    mutations=[
        Mutation(
            "any name is trusted",
            '    if (\n        not project\n        or project != project.strip()\n        or project in (os.curdir, os.pardir)\n        or os.sep in project\n    ):\n        raise ValueError(f"unusable project name: {project!r}")',
            "    if False:\n        pass",
        ),
        Mutation(
            "only an empty name is refused",
            "        or project != project.strip()\n        or project in (os.curdir, os.pardir)\n        or os.sep in project",
            "",
        ),
        Mutation(
            "a name made only of separators is accepted",
            "        or project in (os.curdir, os.pardir)\n",
            "",
        ),
        Mutation(
            "a name holding a separator is accepted",
            "        or os.sep in project\n",
            "",
        ),
        Mutation(
            "a checkout with no manifest is not a project",
            "        found = {stored.project for stored in self.manifests()}",
            "        return sorted({stored.project for stored in self.manifests()})",
        ),
        Mutation(
            "a manifest whose checkout is gone is not a project",
            "        found = {stored.project for stored in self.manifests()}",
            "        found = set()",
        ),
        Mutation(
            "any directory counts as a checkout",
            '            if os.path.isdir(os.path.join(self.path(CHECKOUTS), name, ".git")):',
            "            if True:",
        ),
        Mutation(
            "a manifest with no repository clones from nowhere",
            "        if not stored.repo_url or stored.repo_url == UNKNOWN:",
            "        if False:",
        ),
        Mutation(
            "a repository that could not be read is cloned anyway",
            "        if not stored.repo_url or stored.repo_url == UNKNOWN:",
            "        if not stored.repo_url:",
        ),
        Mutation(
            "a restored checkout ignores the commit the manifest pins",
            "        return self.ensure_checkout(stored.project, stored.repo_url, stored.commit)",
            "        return self.ensure_checkout(stored.project, stored.repo_url)",
        ),
        Mutation(
            "a checkout path is joined without checking the name",
            "        return self.path(CHECKOUTS, safe_name(project))",
            "        return self.path(CHECKOUTS, project)",
        ),
        Mutation(
            "a manifest path is joined without checking the name",
            '        return self.path(MANIFESTS, safe_name(project) + ".json")',
            '        return self.path(MANIFESTS, project + ".json")',
        ),
        Mutation(
            "a dataset path is joined without checking the name",
            "        found = self.path(DATASETS, safe_name(name))",
            "        found = self.path(DATASETS, name)",
        ),
        Mutation(
            "a dataset that was never mounted reads as present",
            "        return found if os.path.isfile(found) else None",
            "        return found",
        ),
        Mutation(
            "an unreadable manifest raises instead of reading as absent",
            "        except (OSError, ValueError):\n            return None",
            "        except OSError:\n            return None",
        ),
        Mutation(
            "a manifest this code cannot read is returned raw",
            "        return from_dict(raw)",
            "        return raw",
        ),
        Mutation(
            "listing includes what could not be read",
            "            if stored is not None:\n                found.append(stored)",
            "            found.append(stored)",
        ),
        Mutation(
            "preparing makes nothing",
            "        for name in (CHECKOUTS, MANIFESTS, DATASETS, REPORTS):\n            os.makedirs(self.path(name), exist_ok=True)",
            "        pass",
        ),
        Mutation(
            "an existing checkout is cloned over",
            '        state = Checkout(project=project, path=dest)\n        if not os.path.isdir(os.path.join(dest, ".git")):',
            "        state = Checkout(project=project, path=dest)\n        if True:",
        ),
        Mutation(
            "a clone is never attempted",
            '        state = Checkout(project=project, path=dest)\n        if not os.path.isdir(os.path.join(dest, ".git")):',
            "        state = Checkout(project=project, path=dest)\n        if False:",
        ),
        Mutation(
            "a failed clone reads as a checkout",
            "                state.error = str(exc) or type(exc).__name__\n                return state",
            "                pass",
        ),
        Mutation(
            "the recorded commit is never checked out",
            "        if commit and commit != UNKNOWN and project_commit(dest) != commit:\n            state.drifted = not _fetch_commit(dest, commit)",
            "        pass",
        ),
        Mutation(
            "a commit that could not be reached is not reported as drift",
            "            state.drifted = not _fetch_commit(dest, commit)",
            "            _fetch_commit(dest, commit)",
        ),
        Mutation(
            "the checkout reports the commit asked for rather than the one on disk",
            "        state.commit = project_commit(dest)",
            "        state.commit = commit",
        ),
        Mutation(
            "a failed fetch still checks out",
            "        if done.returncode != 0:\n            return False\n    return True",
            "    return True",
        ),
        Mutation(
            "the environment is read even when a workspace was named",
            '        chosen = root or os.environ.get(WORKSPACE_ENV, "")',
            '        chosen = os.environ.get(WORKSPACE_ENV, "") or root',
        ),
        Mutation(
            "a workspace exists even when none was configured",
            "        return cls(os.path.abspath(chosen)) if chosen else None",
            "        return cls(os.path.abspath(chosen))",
        ),
    ],
)
