"""Diagnosing a suite that will not run, and the repairs allowed for it.

A repair may change the environment a suite runs in. It may never change the
suite. Installing a plugin the project's own configuration demands is a
repair; editing a test, relaxing an assertion, deleting a failing case or
rewriting a strategy is not, and a run whose harness was "repaired" that way
would manufacture findings rather than discover them.

``Repair`` can express packages to install, environment variables, and
arguments to pytest. It cannot express a change to a file, so the forbidden
repair has no representation here rather than only a rule against it.

Every diagnosis below comes from a failure observed while provisioning the
corpus. An unrecognized failure yields no repair and is escalated by the
caller, which is the behaviour to keep: guessing at an unseen failure is how
a harness ends up quietly running something other than the suite.
"""

import dataclasses
import glob
import os
import re
import shlex
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set

from .pypi import requirement_name

#: Repairs attempted for one project before it is escalated instead.
#:
#: A guess, bounded by what has been observed: pydantic needs four -- its
#: configured plugins, a marker plugin, and two rounds of missing imports,
#: because an import error hides every later import in the same module.
MAX_REPAIRS = 6

#: Command-line flags a project's own pytest configuration may carry, mapped
#: to the distribution that supplies them. A suite whose ``addopts`` names a
#: plugin flag will not start until that plugin is installed. No prefix here
#: may extend another, so a flag matches at most one distribution.
PLUGIN_FLAGS = {
    "--benchmark-": "pytest-benchmark",
    "--cov": "pytest-cov",
    "-n": "pytest-xdist",
    "--numprocesses": "pytest-xdist",
    "--dist": "pytest-xdist",
    "--asyncio-mode": "pytest-asyncio",
    "--timeout": "pytest-timeout",
    "--randomly-": "pytest-randomly",
    "--snapshot-update": "syrupy",
    "--mypy": "pytest-mypy-plugins",
    "--hypothesis-": "hypothesis",
}

#: Plugins that must be installed for a suite to start, then kept from acting.
#: xdist moves tests into subprocesses the injected plugin does not reach, so
#: a suite configured for it is run single-process regardless.
NEUTRALIZED_PLUGINS = {"pytest-xdist": ["-n0"]}

_UNRECOGNIZED_RE = re.compile(r"unrecognized arguments:\s*(?P<flags>.+)")
_MISSING_MODULE_RE = re.compile(
    r"(?:ModuleNotFoundError|ImportError): No module named '(?P<module>[\w.]+)'"
)

#: Markers a project's strict configuration may require, mapped to the plugin
#: that registers them. pytest aborts collection when one is missing.
MARKER_DISTRIBUTIONS = {
    "thread_unsafe": "pytest-run-parallel",
}

_MISSING_MARKER_RE = re.compile(
    r"'(?P<marker>[\w-]+)' not found in `markers` configuration"
)

_DESELECTED_RE = re.compile(r"(?P<count>\d+) deselected")
_SELECTED_RE = re.compile(r"\d+ (?:passed|failed|error|skipped|xfailed|xpassed)")

_COLLECT_ERROR_RE = re.compile(r"^ERROR (?P<path>\S+\.py)", re.MULTILINE)

#: Importable names whose distribution is spelled differently, or whose
#: distribution name is the module's with underscores replaced. Guessing a
#: distribution from a module name installs whatever happens to hold that
#: name on PyPI, so this stays an explicit list.
MODULE_DISTRIBUTIONS = {
    "dirty_equals": "dirty-equals",
    "pytz": "pytz",
    "time_machine": "time-machine",
    "pytest_examples": "pytest-examples",
    "pytest_benchmark": "pytest-benchmark",
    "pytest_asyncio": "pytest-asyncio",
    "pytest_mock": "pytest-mock",
    "pytest_xdist": "pytest-xdist",
    "pytest_timeout": "pytest-timeout",
    "hypothesis": "hypothesis",
    "attr": "attrs",
    "yaml": "PyYAML",
}


#: Files a project names its dependencies in. Read as text, never executed,
#: and never for what to install -- only to confirm a name the suite already
#: asked for by importing it.
REQUIREMENT_FILES = (
    "pyproject.toml",
    "setup.cfg",
    "setup.py",
    "tox.ini",
    "requirements*.txt",
    os.path.join("requirements", "*.txt"),
)

#: Bytes read from any one of them. A generated lockfile can be enormous and
#: adds nothing a project's own declaration does not.
MAX_REQUIREMENT_BYTES = 500_000

#: Directory names that hold another project's dependencies, not this one's.
SKIPPED_DIRECTORIES = frozenset(
    {"node_modules", "site-packages", "venv", "env", "build", "dist"}
)

#: Entries of the checkout root considered before looking for configuration.
MAX_SUBDIRECTORIES = 200

_DISTRIBUTION_NAME_RE = re.compile(r"[a-z][a-z0-9._-]{1,60}")


@dataclass
class Repair:
    """A change to the environment a suite runs in, and nothing more."""

    name: str
    rationale: str
    packages: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    pytest_args: List[str] = field(default_factory=list)

    def describe(self) -> str:
        parts = []
        if self.packages:
            parts.append(f"install {' '.join(self.packages)}")
        if self.env:
            parts.append(" ".join(f"{k}={v}" for k, v in sorted(self.env.items())))
        if self.pytest_args:
            parts.append(f"pytest {' '.join(self.pytest_args)}")
        return f"{self.name}: {'; '.join(parts)}"


def _distribution_for_flag(flag: str) -> Optional[str]:
    bare = flag.split("=", 1)[0]
    for prefix, dist in PLUGIN_FLAGS.items():
        if bare.startswith(prefix):
            return dist
    return None


def _missing_modules(text: str) -> List[str]:
    """Every module an import failed on, in the order the failures appear."""
    found: List[str] = []
    for match in _MISSING_MODULE_RE.finditer(text):
        head = match.group("module").split(".")[0]
        if head not in found:
            found.append(head)
    return found


def declared_names(text: str) -> Set[str]:
    """Distribution names a configuration file mentions.

    A broad read of one file's tokens, not a parse of its dependency tables:
    it answers "does this project name this distribution at all", which is
    all that is asked of it.
    """
    found = set()
    for raw in re.split(r"[\"'\n,=\[\]]", text):
        token = raw.strip()
        if not token:
            continue
        name = requirement_name(token)
        if name and _DISTRIBUTION_NAME_RE.fullmatch(name):
            found.add(name)
    return found


def _declaring_directories(project_dir: str) -> List[str]:
    """The checkout root and its immediate subdirectories.

    A vendored subproject declares its own test dependencies, and its tests
    are collected along with everything else, so one level down is part of
    the project. Deeper is a different project's business.
    """
    found = [project_dir]
    try:
        entries = sorted(os.listdir(project_dir))
    except OSError:
        return found
    for name in entries[:MAX_SUBDIRECTORIES]:
        if name.startswith(".") or name in SKIPPED_DIRECTORIES:
            continue
        path = os.path.join(project_dir, name)
        if os.path.isdir(path):
            found.append(path)
    return found


def declared_requirements(project_dir: str) -> Set[str]:
    """Distribution names the checkout's own configuration mentions."""
    found: Set[str] = set()
    for directory in _declaring_directories(project_dir):
        for pattern in REQUIREMENT_FILES:
            for path in sorted(glob.glob(os.path.join(directory, pattern))):
                try:
                    with open(path, errors="replace") as handle:
                        found |= declared_names(handle.read(MAX_REQUIREMENT_BYTES))
                except OSError:
                    continue
    return found


def _distribution_for_module(module: str, declared: Iterable[str]) -> Optional[str]:
    """The distribution supplying a module, if that is known rather than guessed.

    A module name is not a distribution name, and resolving one to the other
    by spelling installs whatever happens to hold that name on PyPI. Either
    the mapping is recorded here, or the project itself names the
    distribution, or the failure escalates.
    """
    known = MODULE_DISTRIBUTIONS.get(module)
    if known:
        return known
    spelled = module.replace("_", "-").lower()
    return spelled if spelled in set(declared) else None


def _unrecognized_flags(text: str) -> List[str]:
    found: List[str] = []
    for match in _UNRECOGNIZED_RE.finditer(text):
        for flag in shlex.split(match.group("flags")):
            if flag.startswith("-") and flag not in found:
                found.append(flag)
    return found


def diagnose(text: str, declared: Iterable[str] = ()) -> Optional[Repair]:
    """Name a repair for a failure, or nothing if the failure is unfamiliar.

    ``declared`` holds distribution names the project's own configuration
    mentions, which turns a missing import into a confirmation rather than a
    guess at which project on PyPI supplies that module.
    """
    flags = _unrecognized_flags(text)
    distributions: List[str] = []
    for flag in flags:
        dist = _distribution_for_flag(flag)
        if dist and dist not in distributions:
            distributions.append(dist)
    if distributions:
        neutralize = [
            arg for dist in distributions for arg in NEUTRALIZED_PLUGINS.get(dist, [])
        ]
        return Repair(
            name="install-configured-plugins",
            rationale=(
                "the project's pytest configuration passes "
                f"{', '.join(flags)}, which needs "
                f"{', '.join(distributions)}"
            ),
            packages=distributions,
            pytest_args=neutralize,
        )

    modules = _missing_modules(text)
    supplying: List[str] = []
    for module in modules:
        dist = _distribution_for_module(module, declared)
        if dist and dist not in supplying:
            supplying.append(dist)
    if supplying:
        return Repair(
            name="install-missing-imports",
            rationale=(
                f"test modules import {', '.join(modules)}, supplied by "
                f"{', '.join(supplying)}"
            ),
            packages=supplying,
        )

    marker = _MISSING_MARKER_RE.search(text)
    if marker and marker.group("marker") in MARKER_DISTRIBUTIONS:
        name = marker.group("marker")
        dist = MARKER_DISTRIBUTIONS[name]
        return Repair(
            name="install-marker-plugin",
            rationale=f"the suite marks tests {name!r}, registered by {dist}",
            packages=[dist],
        )

    deselected = _DESELECTED_RE.search(text)
    if deselected and not _SELECTED_RE.search(text):
        return Repair(
            name="override-marker-filter",
            rationale=(
                f"the project's own configuration deselected all "
                f"{deselected.group('count')} of these tests"
            ),
            pytest_args=["-m", ""],
        )

    errors = _COLLECT_ERROR_RE.findall(text)
    if errors and not _mentions_crosshair(text):
        return Repair(
            name="skip-unimportable-modules",
            rationale=(
                "these test modules could not be imported, so none of their "
                f"tests can run: {', '.join(errors)}"
            ),
            pytest_args=[f"--ignore={path}" for path in errors],
        )
    return None


def _mentions_crosshair(text: str) -> bool:
    """Whether a failure implicates the solver rather than the project.

    Ignoring a module that CrossHair itself broke would hide the defect the
    pipeline exists to find, so such a failure is escalated instead.
    """
    lowered = text.lower()
    return "crosshair" in lowered or "hypothesis_crosshair" in lowered


def plan(
    text: str,
    applied: Sequence[str] = (),
    declared: Iterable[str] = (),
    installed: Iterable[str] = (),
) -> Optional[Repair]:
    """The next repair to try, given what has already been tried here.

    A repair is offered again only when it would install something not
    installed yet, which a suite needs: an import error hides every later
    import in the same module, so the modules missing from a collection are
    discovered in waves. Anything else already attempted escalates instead
    of looping, and the budget bounds the rounds either way.
    """
    if len(applied) >= MAX_REPAIRS:
        return None
    found = diagnose(text, declared)
    if found is None:
        return None
    if not found.packages:
        return None if found.name in applied else found
    fresh = [name for name in found.packages if name not in set(installed)]
    if not fresh:
        return None
    return dataclasses.replace(found, packages=fresh)
