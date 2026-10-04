"""The directory that outlives the container.

A run happens in a container that will be reclaimed, so everything worth
keeping between runs is written here: the operator's inputs, the checkouts,
the manifests describing how each checkout's environment was built, and the
store holding verdicts. Mount one directory and a later container resumes;
mount nothing and every run starts from the beginning.

Inputs live alongside the outputs rather than being baked into this package.
A recorded index is a snapshot that goes stale, and a 3 MB file in version
control cannot be refreshed without a release, so the workspace is where it
belongs and the index path is resolved from there.

A project name becomes a path here, so it is checked rather than trusted: a
name arriving from PyPI metadata or a recorded index may contain anything.
"""

import json
import os
import subprocess
from dataclasses import dataclass
from typing import List, Optional

from .manifest import Manifest, from_dict
from .probe import CLONE_TIMEOUT, clone
from .provenance import UNKNOWN, project_commit

CHECKOUTS = "checkouts"
MANIFESTS = "manifests"
DATASETS = "datasets"
REPORTS = "reports"

STORE_NAME = "store.db"

#: Known CrossHair and plugin defects. Kept beside the store rather than in
#: it because a person writes in it: what a defect was filed as, and why.
DEFECTS_NAME = "crosshair-defects.json"

#: The recorded index, looked for under ``datasets`` when none is named.
DATASET_NAME = "hypothesis_nodes.json"

#: Environment variable naming the workspace, so a container is configured
#: by its mount rather than by every command line repeating the path.
WORKSPACE_ENV = "DISCOVERY_WORKSPACE"


def safe_name(project: str) -> str:
    """The project's name, rejected if it could name somewhere else."""
    if (
        not project
        or project != project.strip()
        or project in (os.curdir, os.pardir)
        or os.sep in project
    ):
        raise ValueError(f"unusable project name: {project!r}")
    return project


@dataclass
class Checkout:
    """A project's source on disk, and whether it is at the wanted commit."""

    project: str
    path: str
    commit: str = ""
    cloned: bool = False
    error: str = ""
    #: Set when a specific commit was asked for and could not be reached.
    drifted: bool = False

    @property
    def ready(self) -> bool:
        return not self.error

    def describe(self) -> str:
        if not self.ready:
            return f"{self.project}: no checkout -- {self.error}"
        how = "cloned" if self.cloned else "reused"
        note = " (wanted commit unavailable)" if self.drifted else ""
        return f"{self.project}: {how} at {self.commit[:12]}{note}"


def _fetch_commit(path: str, commit: str, timeout: float = CLONE_TIMEOUT) -> bool:
    """Fetch one commit into a shallow clone and check it out."""
    for argv in (
        ["git", "-C", path, "fetch", "--depth", "1", "--quiet", "origin", commit],
        ["git", "-C", path, "checkout", "--quiet", commit],
    ):
        try:
            done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.SubprocessError):
            return False
        if done.returncode != 0:
            return False
    return True


@dataclass
class Workspace:
    """A persistent directory, and the places inside it things belong."""

    root: str

    @classmethod
    def from_environment(cls, root: str = "") -> Optional["Workspace"]:
        """The workspace named by an argument or the environment, if any."""
        chosen = root or os.environ.get(WORKSPACE_ENV, "")
        return cls(os.path.abspath(chosen)) if chosen else None

    def path(self, *parts: str) -> str:
        return os.path.join(self.root, *parts)

    def prepare(self) -> "Workspace":
        for name in (CHECKOUTS, MANIFESTS, DATASETS, REPORTS):
            os.makedirs(self.path(name), exist_ok=True)
        return self

    @property
    def store_path(self) -> str:
        return self.path(STORE_NAME)

    @property
    def defects_path(self) -> str:
        """The registry of known CrossHair defects, which a person edits."""
        return self.path(DEFECTS_NAME)

    def dataset(self, name: str = DATASET_NAME) -> Optional[str]:
        """An operator-supplied input file, if it was mounted."""
        found = self.path(DATASETS, safe_name(name))
        return found if os.path.isfile(found) else None

    def checkout_dir(self, project: str) -> str:
        return self.path(CHECKOUTS, safe_name(project))

    def manifest_path(self, project: str) -> str:
        return self.path(MANIFESTS, safe_name(project) + ".json")

    def write_manifest(self, stored: Manifest) -> str:
        where = self.manifest_path(stored.project)
        os.makedirs(os.path.dirname(where), exist_ok=True)
        with open(where, "w") as handle:
            handle.write(stored.as_json())
        return where

    def read_manifest(self, project: str) -> Optional[Manifest]:
        """The stored manifest, or ``None`` if there is none this code can read."""
        where = self.manifest_path(project)
        try:
            with open(where) as handle:
                raw = json.load(handle)
        except (OSError, ValueError):
            return None
        return from_dict(raw)

    def manifests(self) -> List[Manifest]:
        """Every readable manifest, by project name."""
        found = []
        for name in sorted(os.listdir(self.path(MANIFESTS))):
            if not name.endswith(".json"):
                continue
            stored = self.read_manifest(name[: -len(".json")])
            if stored is not None:
                found.append(stored)
        return found

    def restore(self, stored: Manifest) -> Checkout:
        """Put a manifest's checkout back, at the commit it was built against."""
        if not stored.repo_url or stored.repo_url == UNKNOWN:
            return Checkout(
                project=stored.project,
                path=self.checkout_dir(stored.project),
                error="the manifest records no repository to clone",
            )
        return self.ensure_checkout(stored.project, stored.repo_url, stored.commit)

    def existing_checkout(self, project: str) -> Checkout:
        """A checkout already in the workspace, without fetching anything."""
        dest = self.checkout_dir(project)
        if not os.path.isdir(os.path.join(dest, ".git")):
            return Checkout(
                project=project,
                path=dest,
                error="no checkout here, and no manifest to restore one from",
            )
        return Checkout(project=project, path=dest, commit=project_commit(dest))

    def projects(self) -> List[str]:
        """Every project the workspace holds, by name.

        A checkout counts even with no manifest: the first run of a project
        is the one that writes its manifest, so requiring one would mean a
        fresh workspace had nothing to do.
        """
        found = {stored.project for stored in self.manifests()}
        for name in sorted(os.listdir(self.path(CHECKOUTS))):
            if os.path.isdir(os.path.join(self.path(CHECKOUTS), name, ".git")):
                found.add(name)
        return sorted(found)

    def ensure_checkout(
        self, project: str, repo_url: str, commit: str = ""
    ) -> Checkout:
        """Put the project's source in place, at the recorded commit if given."""
        dest = self.checkout_dir(project)
        state = Checkout(project=project, path=dest)
        if not os.path.isdir(os.path.join(dest, ".git")):
            os.makedirs(self.path(CHECKOUTS), exist_ok=True)
            try:
                clone(repo_url, dest)
            except (RuntimeError, subprocess.SubprocessError, OSError) as exc:
                state.error = str(exc) or type(exc).__name__
                return state
            state.cloned = True
        if commit and commit != UNKNOWN and project_commit(dest) != commit:
            state.drifted = not _fetch_commit(dest, commit)
        state.commit = project_commit(dest)
        return state
