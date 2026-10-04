"""What it took to build an environment, written down so it can be rebuilt.

Provisioning costs minutes per project and reaches the network to do it. A
container that is reclaimed takes every environment with it, so what
provisioning learned is recorded here instead: the commit it was built
against, the repairs it needed, and the resolved versions it ended up with.

A manifest holds the project side still and lets the toolchain move. The
pins come from the environment that was observed to collect, minus
everything CrossHair, Hypothesis, pytest and the plugin brought with them --
because those are what a run is measuring. Pinning them would make the next
upgrade uninstallable, and pinning what they depend on would do the same one
step removed.

The toolchain closure follows installed metadata rather than resolving, and
skips requirements guarded by an extra: a package named only under
``extra == "dev"`` is not something the toolchain installs, and treating it
as the toolchain's would silently refuse to pin a project's own dependency
on numpy or pandas. Conditional requirements that are not extras are kept,
which over-approximates in the safe direction -- letting one extra package
float costs a little reproducibility, while pinning one the toolchain needs
costs the upgrade entirely.
"""

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Sequence

from .provision import (
    DEFAULT_PLUGIN,
    INSTALL_LIMITS,
    RUN_FROM_CHECKOUT,
    TOOLCHAIN,
    Provisioned,
    collect,
    install,
    toolchain_requirements,
    venv_python,
)
from .pypi import requirement_name
from .sandbox import Limits, Sandbox

#: Bumped when a stored manifest can no longer be read as written. An older
#: one is rebuilt from scratch rather than guessed at.
MANIFEST_VERSION = 1

DEFAULT_PYTHON = "3.12"

FREEZE_ARGV = ("uv", "pip", "freeze", "--python")

PROBE_LIMITS = Limits(wall_seconds=120)

#: Reports every distribution the named roots pull in, following metadata
#: rather than resolving, so it answers from the environment as installed.
_CLOSURE_PROBE = """
import json, sys
from importlib.metadata import distribution, PackageNotFoundError


def normalize(name):
    return name.strip().lower().replace("_", "-").replace(".", "-")


found = set()
queue = [normalize(name) for name in json.loads(sys.argv[1])]
while queue:
    name = queue.pop()
    if name in found:
        continue
    found.add(name)
    try:
        dist = distribution(name)
    except (PackageNotFoundError, ValueError):
        continue
    for raw in dist.requires or []:
        head, _, marker = raw.partition(";")
        if "extra" in marker:
            continue
        dep = head.split("[")[0]
        for stop in ("==", ">=", "<=", "~=", "!=", ">", "<", " ", "(", ","):
            dep = dep.split(stop)[0]
        dep = normalize(dep)
        if dep and dep not in found:
            queue.append(dep)
print(json.dumps(sorted(found)))
"""


@dataclass
class Manifest:
    """One project's environment, as a later container can rebuild it."""

    project: str
    repo_url: str = ""
    commit: str = ""
    source: str = ""
    python_version: str = DEFAULT_PYTHON
    #: The requirement provisioning was asked to install the plugin from.
    plugin: str = DEFAULT_PLUGIN
    pytest_args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    repairs: List[str] = field(default_factory=list)
    #: Exact requirements for everything the toolchain did not bring.
    pins: List[str] = field(default_factory=list)
    #: Resolved versions of the packages under test, as installed.
    toolchain: Dict[str, str] = field(default_factory=dict)
    #: Tests the environment was observed to collect, the rebuild's target.
    collected: int = 0
    created_at: float = 0.0
    version: int = MANIFEST_VERSION

    @property
    def installs_project(self) -> bool:
        """Whether the project's own build worked when it was provisioned."""
        return RUN_FROM_CHECKOUT not in self.repairs

    def as_dict(self) -> dict:
        return asdict(self)

    def as_json(self) -> str:
        return json.dumps(self.as_dict(), indent=1, sort_keys=True)

    def describe(self) -> str:
        pins = f"{len(self.pins)} pin(s)"
        tools = ", ".join(f"{k} {v}" for k, v in sorted(self.toolchain.items()))
        return (
            f"{self.project} @ {self.commit[:12] or 'unpinned'}: "
            f"{self.collected} tests, {pins}" + (f" [{tools}]" if tools else "")
        )


def from_dict(raw: dict) -> Optional[Manifest]:
    """Read a stored manifest, or ``None`` if it was not written by this code."""
    if not isinstance(raw, dict) or raw.get("version") != MANIFEST_VERSION:
        return None
    fields = {f for f in Manifest.__dataclass_fields__}
    known = {key: value for key, value in raw.items() if key in fields}
    if "project" not in known:
        return None
    return Manifest(**known)


def frozen_requirements(sandbox: Sandbox, python: str, cwd: str) -> List[str]:
    """Exact requirements for the environment, excluding editable installs."""
    done = sandbox.run(
        list(FREEZE_ARGV) + [python],
        cwd=cwd,
        network=False,
        limits=PROBE_LIMITS,
    )
    if done.returncode != 0:
        return []
    lines = []
    for line in done.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "-e", "-")) or "==" not in line:
            continue
        lines.append(line)
    return lines


def toolchain_closure(sandbox: Sandbox, python: str, cwd: str) -> List[str]:
    """Normalized names of the toolchain and everything it requires."""
    done = sandbox.run(
        [python, "-c", _CLOSURE_PROBE, json.dumps(sorted(TOOLCHAIN))],
        cwd=cwd,
        network=False,
        limits=PROBE_LIMITS,
    )
    if done.returncode != 0:
        return sorted(TOOLCHAIN)
    try:
        found = json.loads(done.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return sorted(TOOLCHAIN)
    return [str(name) for name in found]


def pins_for(requirements: Sequence[str], closure: Sequence[str]) -> List[str]:
    """Requirements worth pinning: everything the toolchain did not bring."""
    excluded = {requirement_name(name) for name in closure}
    return [line for line in requirements if requirement_name(line) not in excluded]


def record(
    sandbox: Sandbox,
    built: Provisioned,
    *,
    project: str,
    repo_url: str = "",
    commit: str = "",
    source: str = "",
    python_version: str = DEFAULT_PYTHON,
    plugin: str = DEFAULT_PLUGIN,
    toolchain: Optional[Dict[str, str]] = None,
) -> Manifest:
    """Describe a provisioned environment by reading what it resolved to."""
    requirements = frozen_requirements(sandbox, built.python, built.project)
    closure = toolchain_closure(sandbox, built.python, built.project)
    versions = dict(toolchain or {})
    if not versions:
        by_name = {requirement_name(line): line for line in requirements}
        for name in sorted(TOOLCHAIN):
            line = by_name.get(name)
            if line:
                versions[name] = line.split("==", 1)[1]
    return Manifest(
        project=project,
        repo_url=repo_url,
        commit=commit,
        source=source,
        python_version=python_version,
        plugin=plugin,
        pytest_args=list(built.pytest_args),
        env=dict(built.env),
        repairs=list(built.repairs),
        pins=pins_for(requirements, closure),
        toolchain=versions,
        collected=built.collected,
        created_at=time.time(),
    )


@dataclass
class Rebuilt:
    """An environment built from a manifest, and how far it agreed with it."""

    manifest: Manifest
    python: str = ""
    collected: int = 0
    error: str = ""
    #: Set when the pins could not be installed and the project side was
    #: resolved afresh. The environment is usable; the manifest is stale.
    resolved_afresh: bool = False

    @property
    def ready(self) -> bool:
        return not self.error

    @property
    def drifted(self) -> bool:
        """Whether the rebuilt environment collects a different suite."""
        return self.ready and self.collected != self.manifest.collected

    def describe(self) -> str:
        if not self.ready:
            return f"{self.manifest.project}: not rebuilt -- {self.error}"
        notes = []
        if self.resolved_afresh:
            notes.append("pins refused, resolved afresh")
        if self.drifted:
            notes.append(
                f"collected {self.collected}, manifest says {self.manifest.collected}"
            )
        suffix = f" ({'; '.join(notes)})" if notes else ""
        return f"{self.manifest.project}: {self.collected} tests collected{suffix}"


def rebuild(
    sandbox: Sandbox,
    stored: Manifest,
    project_dir: str,
    venv_dir: str,
    plugin: str = "",
) -> Rebuilt:
    """Build an environment from a manifest and check it against it.

    The pins install in one pass with a freshly resolved toolchain. Pins the
    new toolchain refuses are dropped rather than fought with, because a
    rebuild that stops is worse than one that reports what it had to give up.
    """
    result = Rebuilt(manifest=stored, python=venv_python(venv_dir))
    made = sandbox.run(
        ["uv", "venv", "--quiet", venv_dir, "--python", stored.python_version],
        cwd=project_dir,
        network=True,
        limits=INSTALL_LIMITS,
    )
    if made.returncode != 0:
        result.error = f"could not create a virtual environment: {made.stderr[-300:]}"
        return result

    tools = toolchain_requirements(plugin or stored.plugin)
    project = ["-e", project_dir] if stored.installs_project else []
    installed, detail = install(
        sandbox, result.python, [*project, *tools, *stored.pins], project_dir, {}
    )
    if not installed:
        result.resolved_afresh = True
        installed, detail = install(
            sandbox, result.python, [*project, *tools], project_dir, {}
        )
        if not installed:
            result.error = f"install failed: {detail.strip()[-300:]}"
            return result

    ok, text, count = collect(
        sandbox, result.python, project_dir, stored.pytest_args, stored.env
    )
    if not ok:
        result.error = f"collection failed: {text.strip()[-300:]}"
        return result
    result.collected = count
    return result
