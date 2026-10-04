"""One run: projects walked through their phases, bounded by a deadline.

The orchestrator stays on the host and every command it issues is a
container of its own, so nothing here needs a container that can reach a
container runtime. What this adds over running a project by hand is the
shape a scheduled run needs.

A run is bounded by a deadline rather than by its list of projects. The
machine is reclaimed on someone else's schedule, so the question is not
which projects to attempt but which ones fit, and a project not reached is
reported as not reached rather than as having found nothing.

A phase that fails stops its project and not the run. The next project is
independent: it has its own checkout, its own environment, and nothing of
the one that failed.
"""

import json
import os
import signal
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

from . import defects as defects_mod
from .manifest import CLEAN_ROOM, Manifest, Rebuilt, rebuild, record
from .provenance import project_commit, remote_url
from .provision import DEFAULT_PLUGIN, provision
from .sandbox import Sandbox, reap_containers
from .store import Store
from .workspace import Workspace

RESTORE = "restore"
BUILD = "build"
CLEAN_ROOM_BUILD = "clean-room"
TEST = "test"

#: Seconds a project needs left before starting it is worth anything. A
#: project cut off mid-run costs its whole build and reports nothing.
MIN_PROJECT_SECONDS = 300.0

#: Where a project's environments live inside its checkout.
VENV_NAME = ".venv-ch"
CLEAN_ROOM_VENV_NAME = ".venv-clean"


@dataclass
class Attempt:
    """What happened to one project, and how far it got."""

    project: str
    #: The phase it was in when it stopped, successfully or not.
    phase: str = RESTORE
    commit: str = ""
    collected: int = 0
    repairs: List[str] = field(default_factory=list)
    verdicts: Dict[str, int] = field(default_factory=dict)
    drifted: bool = False
    resolved_afresh: bool = False
    error: str = ""
    seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return not self.error

    def describe(self) -> str:
        if not self.ok:
            return f"{self.project}: {self.phase} failed -- {self.error}"
        counted = ", ".join(
            f"{count} {name}" for name, count in sorted(self.verdicts.items())
        )
        notes = []
        if self.drifted:
            notes.append("collection drifted from the manifest")
        if self.resolved_afresh:
            notes.append("pins refused")
        suffix = f" [{'; '.join(notes)}]" if notes else ""
        return (
            f"{self.project}: {self.collected} tests, "
            f"{counted or 'no verdicts'} in {self.seconds:.0f}s{suffix}"
        )


@dataclass
class RunReport:
    """Every project a run reached, and the ones it did not."""

    run_id: str
    started_at: float
    attempts: List[Attempt] = field(default_factory=list)
    #: Projects the deadline arrived before. Not failures.
    unreached: List[str] = field(default_factory=list)
    seconds: float = 0.0
    #: What this run did to the registry of known CrossHair defects.
    defects: defects_mod.Changes = field(default_factory=defects_mod.Changes)

    @property
    def verdicts(self) -> Dict[str, int]:
        total: Dict[str, int] = {}
        for attempt in self.attempts:
            for name, count in attempt.verdicts.items():
                total[name] = total.get(name, 0) + count
        return total

    def as_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "seconds": round(self.seconds, 1),
            "verdicts": self.verdicts,
            "unreached": list(self.unreached),
            "attempts": [vars(attempt) for attempt in self.attempts],
            "defects": {
                "new": [vars(d) for d in self.defects.new],
                "gone": [vars(d) for d in self.defects.gone],
                "still_present": [d.signature for d in self.defects.still_present],
                "unverified": [d.signature for d in self.defects.unverified],
            },
        }

    def describe(self) -> List[str]:
        lines = [attempt.describe() for attempt in self.attempts]
        done = [a for a in self.attempts if a.ok]
        lines.append(
            f"\n{len(done)}/{len(self.attempts)} projects ran in "
            f"{self.seconds:.0f}s"
        )
        if self.unreached:
            lines.append(
                f"{len(self.unreached)} not reached before the deadline: "
                f"{', '.join(self.unreached)}"
            )
        for name, count in sorted(self.verdicts.items()):
            lines.append(f"  {count} {name}")
        lines.extend(self.defects.describe())
        return lines


@dataclass
class PipelineResult:
    """What the pipeline reported for one project."""

    verdicts: Dict[str, int] = field(default_factory=dict)
    collected: int = 0
    error: str = ""


def project_run_id(project: str, commit: str) -> str:
    """The run id a project keeps across windows.

    A run cut off by the deadline has still recorded every verdict it
    reached, and a later window continues that same run rather than
    starting one that repeats its work.
    """
    return f"{project}-{commit[:8] or 'nocommit'}"[:64]


def pipeline_argv(
    project_dir: str,
    python: str,
    store_path: str,
    image: str,
    *,
    run_id: str = "",
    validation_python: str = "",
    nodeids: Sequence[str] = (),
    extra: Sequence[str] = (),
) -> List[str]:
    """The command that runs one project's pipeline."""
    argv = [
        sys.executable,
        "-m",
        "discovery.cli",
        "--project",
        project_dir,
        "--sandbox",
        "docker",
        "--image",
        image,
        "--crosshair-python",
        python,
        "--store",
        store_path,
        "--per-test",
        "--json",
    ]
    if run_id:
        argv += ["--resume", run_id]
    if validation_python:
        argv += ["--validation-python", validation_python]
    argv += list(extra)
    argv += list(nodeids)
    return argv


def end_process_group(proc: "subprocess.Popen") -> None:
    """Kill a pipeline and everything it started.

    A pipeline spawns a container client per command, and killing only the
    pipeline leaves those holding its pipes open, so reading its output
    would block until they finished -- which is exactly what the deadline
    arrived to prevent.
    """
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        proc.kill()


def _collected(payload: dict) -> int:
    """How many tests the pipeline reported, however it reported them.

    It names them rather than counting them, and a report this cannot read
    is not worth failing a run over.
    """
    value = payload.get("collected")
    if isinstance(value, (list, tuple, dict)):
        return len(value)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def run_pipeline(argv: Sequence[str], budget: float) -> PipelineResult:
    """Run one project's pipeline, reading the verdicts it reports.

    It runs as its own process group so that a pipeline which dies takes
    nothing else with it, and so the deadline can cut it off whole.
    """
    try:
        proc = subprocess.Popen(
            list(argv),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            start_new_session=True,
        )
    except OSError as exc:
        return PipelineResult(error=str(exc))
    try:
        stdout, stderr = proc.communicate(timeout=max(budget, 1.0))
    except subprocess.TimeoutExpired:
        end_process_group(proc)
        proc.communicate()
        return PipelineResult(
            error="the deadline arrived while this project was running"
        )
    try:
        payload = json.loads(stdout[stdout.index("{") :])
    except (ValueError, IndexError):
        detail = (stderr or stdout).strip()[-300:]
        return PipelineResult(error=f"the pipeline reported nothing readable: {detail}")
    counted: Dict[str, int] = {}
    for entry in payload.get("classifications") or []:
        name = str(entry.get("verdict"))
        counted[name] = counted.get(name, 0) + 1
    return PipelineResult(verdicts=counted, collected=_collected(payload))


def verdicts_recorded(store_path: str, run_id: str) -> Dict[str, int]:
    """What a run has recorded so far, however it ended."""
    if not os.path.exists(store_path):
        return {}
    counted: Dict[str, int] = {}
    with Store(store_path) as store:
        for payload in store.verdicts(run_id):
            name = str(payload.get("verdict"))
            counted[name] = counted.get(name, 0) + 1
    return counted


def defects_recorded(
    store_path: str, run_id: str, project: str, version: str
) -> List[defects_mod.Sighting]:
    """CrossHair's own failures in a run, on the version being measured."""
    if not os.path.exists(store_path):
        return []
    with Store(store_path) as store:
        return defects_mod.sightings_from(store.failures(run_id, version), project)


def _build(
    space: Workspace,
    sandbox: Sandbox,
    name: str,
    project_dir: str,
    plugin: str,
    python_version: str,
) -> Rebuilt:
    """Rebuild from the manifest, or provision and write one."""
    venv_dir = os.path.join(project_dir, VENV_NAME)
    stored = space.read_manifest(name)
    if stored is not None:
        return rebuild(sandbox, stored, project_dir, venv_dir, plugin=plugin)
    built = provision(
        sandbox,
        project_dir,
        plugin,
        venv_dir=venv_dir,
        python_version=python_version,
    )
    if not built.ready:
        return Rebuilt(manifest=Manifest(project=name), error=built.error)
    written = record(
        sandbox,
        built,
        project=name,
        repo_url=remote_url(project_dir),
        commit=project_commit(project_dir),
        python_version=python_version,
        plugin=plugin,
    )
    space.write_manifest(written)
    return Rebuilt(
        manifest=written,
        python=built.python,
        collected=built.collected,
        toolchain=dict(written.toolchain),
    )


def _record_defects(
    space: Workspace,
    report: RunReport,
    seen: Sequence[defects_mod.Sighting],
    version: str,
) -> defects_mod.Changes:
    """Fold this run's sightings into the registry and write it back.

    Only projects that finished count as looked at: a project the deadline
    cut off says nothing about whether a defect it used to show is gone.
    """
    covered = {a.project for a in report.attempts if a.ok and a.phase == TEST}
    registry, changes = defects_mod.update(
        defects_mod.load(space.defects_path), seen, covered=covered, version=version
    )
    if registry:
        defects_mod.save(space.defects_path, registry)
    return changes


def drive(
    space: Workspace,
    sandbox: Sandbox,
    projects: Sequence[str],
    *,
    deadline: float,
    image: str,
    plugin: str = DEFAULT_PLUGIN,
    python_version: str = "3.12",
    clean_room: bool = False,
    crosshair_version: str = "",
    pipeline_args: Sequence[str] = (),
    run: Optional[Callable[..., PipelineResult]] = None,
    now: Callable[[], float] = time.time,
) -> RunReport:
    """Take each project as far as the deadline allows, and report."""
    run = run or run_pipeline
    report = RunReport(run_id=uuid.uuid4().hex[:12], started_at=now())
    space.prepare()
    seen: List[defects_mod.Sighting] = []

    for index, name in enumerate(projects):
        if deadline - now() < MIN_PROJECT_SECONDS:
            report.unreached = list(projects[index:])
            break
        started = now()
        attempt = Attempt(project=name)
        report.attempts.append(attempt)

        stored = space.read_manifest(name)
        checkout = (
            space.restore(stored)
            if stored is not None and stored.repo_url
            else space.existing_checkout(name)
        )
        attempt.commit = checkout.commit
        if not checkout.ready:
            attempt.error = checkout.error
            attempt.seconds = now() - started
            continue

        attempt.phase = BUILD
        built = _build(space, sandbox, name, checkout.path, plugin, python_version)
        attempt.repairs = list(built.manifest.repairs)
        attempt.collected = built.collected
        attempt.drifted = built.drifted
        attempt.resolved_afresh = built.resolved_afresh
        crosshair_version = crosshair_version or built.toolchain.get(
            "crosshair-tool", ""
        )
        if not built.ready:
            attempt.error = built.error
            attempt.seconds = now() - started
            continue

        validation_python = ""
        if clean_room:
            attempt.phase = CLEAN_ROOM_BUILD
            clean = rebuild(
                sandbox,
                built.manifest,
                checkout.path,
                os.path.join(checkout.path, CLEAN_ROOM_VENV_NAME),
                plugin=CLEAN_ROOM,
            )
            if not clean.ready:
                attempt.error = f"no clean room: {clean.error}"
                attempt.seconds = now() - started
                continue
            validation_python = clean.python

        attempt.phase = TEST
        run_id = project_run_id(name, checkout.commit)
        tested = run(
            pipeline_argv(
                checkout.path,
                built.python,
                space.store_path,
                image,
                run_id=run_id,
                validation_python=validation_python,
                extra=pipeline_args,
            ),
            deadline - now(),
        )
        # A run the deadline cut off still recorded what it reached, and the
        # store is where that is, so the report counts from there either way.
        if tested.error:
            reap_containers(run_id)
        attempt.verdicts = (
            verdicts_recorded(space.store_path, run_id) or tested.verdicts
        )
        attempt.error = tested.error
        attempt.seconds = now() - started
        seen.extend(defects_recorded(space.store_path, run_id, name, crosshair_version))

    report.defects = _record_defects(space, report, seen, crosshair_version)
    report.seconds = now() - report.started_at
    return report


def write_report(space: Workspace, report: RunReport) -> str:
    """Store a run's report in the workspace, and return where it went."""
    where = space.path("reports", f"{report.run_id}.json")
    os.makedirs(os.path.dirname(where), exist_ok=True)
    with open(where, "w") as handle:
        json.dump(report.as_dict(), handle, indent=1, sort_keys=True)
    return where
