"""Checks one run's shape: phases, the deadline, and what a failure stops.

The deadline is the point of the driver. A machine that will be reclaimed
makes "which projects fit" the question, and a project not reached has to
read as not reached rather than as having found nothing.
"""

import json
import os
import sys
import time
from typing import Dict, List, Optional, Sequence

import pytest

from discovery import driver
from discovery.driver import (
    BUILD,
    CLEAN_ROOM_BUILD,
    MIN_PROJECT_SECONDS,
    RESTORE,
    TEST,
    Attempt,
    PipelineResult,
    RunReport,
    drive,
    pipeline_argv,
    project_run_id,
    run_pipeline,
    verdicts_recorded,
    write_report,
)
from discovery.manifest import Manifest, Rebuilt
from discovery.model import Classification, Outcome, Verdict
from discovery.sandbox import ExecResult, Limits, Sandbox
from discovery.store import Store
from discovery.workspace import Workspace


class FakeSandbox(Sandbox):
    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: str,
        env: Optional[Dict[str, str]] = None,
        network: bool = False,
        limits: Optional[Limits] = None,
    ) -> ExecResult:
        raise AssertionError(f"the driver should not run commands itself: {argv}")


class Clock:
    """A clock the test moves, so a deadline is reached without waiting."""

    def __init__(self, start: float = 1000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def space(tmp_path):
    return Workspace(str(tmp_path)).prepare()


def checkout(space, name, commit="a" * 40):
    """A project that is already in the workspace, with a manifest."""
    path = space.checkout_dir(name)
    os.makedirs(os.path.join(path, ".git"), exist_ok=True)
    space.write_manifest(Manifest(project=name, commit=commit, collected=10))
    return path


def built(space, name, **kw):
    fields = dict(
        manifest=space.read_manifest(name) or Manifest(project=name),
        python="/work/.venv-ch/bin/python",
        collected=10,
    )
    fields.update(kw)
    return Rebuilt(**fields)


@pytest.fixture
def quiet_build(monkeypatch, space):
    """Builds succeed without a sandbox, so the tests are about the driver."""

    def fake(space_, sandbox, name, project_dir, plugin, python_version):
        return built(space_, name)

    monkeypatch.setattr(driver, "_build", fake)
    return fake


def ran(verdicts=None, collected=10, error=""):
    def fake(argv, budget):
        fake.calls.append({"argv": list(argv), "budget": budget})
        return PipelineResult(
            verdicts=dict(verdicts or {}), collected=collected, error=error
        )

    fake.calls = []
    return fake


def test_a_project_runs_through_every_phase(space, quiet_build):
    checkout(space, "alpha")
    run = ran({"trophy_candidate": 1})
    report = drive(
        space,
        FakeSandbox(),
        ["alpha"],
        deadline=9e9,
        image="img",
        run=run,
    )
    assert [a.phase for a in report.attempts] == [TEST]
    assert report.attempts[0].ok
    assert report.verdicts == {"trophy_candidate": 1}


def test_projects_past_the_deadline_are_unreached_not_failed(space, quiet_build):
    for name in ("alpha", "beta", "gamma"):
        checkout(space, name)
    clock = Clock()

    def slow(argv, budget):
        clock.advance(MIN_PROJECT_SECONDS)
        return PipelineResult(verdicts={"no_signal": 1})

    report = drive(
        space,
        FakeSandbox(),
        ["alpha", "beta", "gamma"],
        deadline=clock.now + MIN_PROJECT_SECONDS * 2.5,
        image="img",
        run=slow,
        now=clock,
    )
    assert [a.project for a in report.attempts] == ["alpha", "beta"]
    assert report.unreached == ["gamma"]
    assert all(a.ok for a in report.attempts)


def test_a_project_is_not_started_without_time_to_finish(space, quiet_build):
    checkout(space, "alpha")
    clock = Clock()
    report = drive(
        space,
        FakeSandbox(),
        ["alpha"],
        deadline=clock.now + MIN_PROJECT_SECONDS - 1,
        image="img",
        run=ran(),
        now=clock,
    )
    assert report.attempts == [] and report.unreached == ["alpha"]


def test_a_failed_project_does_not_stop_the_next_one(space, monkeypatch):
    checkout(space, "alpha")
    checkout(space, "beta")

    def fake(space_, sandbox, name, project_dir, plugin, python_version):
        if name == "alpha":
            return Rebuilt(manifest=Manifest(project=name), error="no environment")
        return built(space_, name)

    monkeypatch.setattr(driver, "_build", fake)
    report = drive(
        space, FakeSandbox(), ["alpha", "beta"], deadline=9e9, image="img", run=ran()
    )
    assert not report.attempts[0].ok and report.attempts[0].phase == BUILD
    assert report.attempts[1].ok


def test_a_project_with_no_checkout_stops_at_restore(space, quiet_build):
    space.write_manifest(Manifest(project="absent"))
    report = drive(
        space, FakeSandbox(), ["absent"], deadline=9e9, image="img", run=ran()
    )
    assert report.attempts[0].phase == RESTORE and not report.attempts[0].ok


def test_a_run_reports_what_the_build_had_to_give_up(space, monkeypatch):
    checkout(space, "alpha")
    monkeypatch.setattr(
        driver,
        "_build",
        lambda s, sb, n, d, p, v: built(s, n, collected=3, resolved_afresh=True),
    )
    report = drive(
        space, FakeSandbox(), ["alpha"], deadline=9e9, image="img", run=ran()
    )
    assert report.attempts[0].drifted and report.attempts[0].resolved_afresh


def test_a_clean_room_is_built_and_handed_to_the_pipeline(
    space, quiet_build, monkeypatch
):
    checkout(space, "alpha")
    asked = {}

    def fake_rebuild(sandbox, stored, project_dir, venv_dir, plugin=None):
        asked["plugin"] = plugin
        asked["venv"] = venv_dir
        return Rebuilt(manifest=stored, python="/work/.venv-clean/bin/python")

    monkeypatch.setattr(driver, "rebuild", fake_rebuild)
    run = ran()
    drive(
        space,
        FakeSandbox(),
        ["alpha"],
        deadline=9e9,
        image="img",
        clean_room=True,
        run=run,
    )
    assert asked["plugin"] == "", "a clean room installs no plugin"
    assert asked["venv"].endswith(".venv-clean")
    argv = run.calls[0]["argv"]
    assert "--validation-python" in argv
    assert argv[argv.index("--validation-python") + 1].endswith(
        ".venv-clean/bin/python"
    )


def test_no_clean_room_means_no_validation_interpreter(space, quiet_build):
    checkout(space, "alpha")
    run = ran()
    drive(space, FakeSandbox(), ["alpha"], deadline=9e9, image="img", run=run)
    assert "--validation-python" not in run.calls[0]["argv"]


def test_a_clean_room_that_cannot_be_built_stops_the_project(
    space, quiet_build, monkeypatch
):
    checkout(space, "alpha")
    monkeypatch.setattr(
        driver,
        "rebuild",
        lambda *a, **k: Rebuilt(manifest=Manifest(project="alpha"), error="nope"),
    )
    report = drive(
        space,
        FakeSandbox(),
        ["alpha"],
        deadline=9e9,
        image="img",
        clean_room=True,
        run=ran(),
    )
    assert report.attempts[0].phase == CLEAN_ROOM_BUILD and not report.attempts[0].ok


def test_the_pipeline_is_given_the_remaining_time_as_its_budget(space, quiet_build):
    checkout(space, "alpha")
    clock = Clock()
    run = ran()
    drive(
        space,
        FakeSandbox(),
        ["alpha"],
        deadline=clock.now + 4000,
        image="img",
        run=run,
        now=clock,
    )
    assert run.calls[0]["budget"] == pytest.approx(4000)


def test_the_pipeline_runs_sandboxed_against_the_built_interpreter():
    argv = pipeline_argv("/w/proj", "/work/.venv-ch/bin/python", "/w/store.db", "img")
    assert argv[argv.index("--sandbox") + 1] == "docker"
    assert argv[argv.index("--image") + 1] == "img"
    assert argv[argv.index("--crosshair-python") + 1] == "/work/.venv-ch/bin/python"
    assert argv[argv.index("--store") + 1] == "/w/store.db"
    assert "--per-test" in argv and "--json" in argv


def test_verdicts_are_counted_from_what_the_pipeline_reported(tmp_path):
    payload = {
        "collected": 3,
        "classifications": [
            {"verdict": "trophy_candidate"},
            {"verdict": "no_signal"},
            {"verdict": "no_signal"},
        ],
    }
    script = tmp_path / "fake.py"
    script.write_text(f"print({json.dumps(json.dumps(payload))})")
    tested = run_pipeline(["python", str(script)], 60)
    assert tested.verdicts == {"trophy_candidate": 1, "no_signal": 2}
    assert tested.collected == 3


def test_a_pipeline_that_says_nothing_readable_is_an_error(tmp_path):
    script = tmp_path / "fake.py"
    script.write_text("print('not json at all')")
    assert run_pipeline(["python", str(script)], 60).error


def test_a_pipeline_that_outruns_the_budget_is_cut_off(tmp_path):
    script = tmp_path / "fake.py"
    script.write_text("import time; time.sleep(30)")
    tested = run_pipeline(["python", str(script)], 0.5)
    assert "deadline" in tested.error


def test_a_pipeline_that_cannot_start_is_an_error():
    assert run_pipeline(["/definitely/not/here"], 10).error


def test_a_report_is_written_where_a_later_run_can_read_it(space):
    report = RunReport(run_id="abc123", started_at=1.0)
    report.attempts.append(Attempt(project="alpha", verdicts={"no_signal": 2}))
    where = write_report(space, report)
    with open(where) as handle:
        again = json.load(handle)
    assert again["run_id"] == "abc123"
    assert again["verdicts"] == {"no_signal": 2}


def test_verdicts_are_totalled_across_projects():
    report = RunReport(run_id="r", started_at=0.0)
    report.attempts.append(Attempt(project="a", verdicts={"no_signal": 2}))
    report.attempts.append(
        Attempt(project="b", verdicts={"no_signal": 1, "trophy_candidate": 1})
    )
    assert report.verdicts == {"no_signal": 3, "trophy_candidate": 1}


def test_a_project_keeps_its_run_id_across_windows():
    """Two windows over the same commit continue one run, not two."""
    assert project_run_id("alpha", "a" * 40) == project_run_id("alpha", "a" * 40)
    assert project_run_id("alpha", "a" * 40) != project_run_id("alpha", "b" * 40)


def test_the_pipeline_is_told_to_continue_that_run():
    argv = pipeline_argv("/w/p", "/py", "/w/s.db", "img", run_id="alpha-aaaa")
    assert argv[argv.index("--resume") + 1] == "alpha-aaaa"


def test_a_project_cut_off_still_reports_what_it_recorded(space, quiet_build):
    """The deadline stops a run; it does not throw away its verdicts."""
    checkout(space, "alpha")
    # The id follows the commit on disk, which is what actually gets tested.
    run_id = project_run_id("alpha", space.existing_checkout("alpha").commit)
    with Store(space.store_path) as store:
        store.record_verdict(
            run_id,
            Classification(
                nodeid="t::one",
                verdict=Verdict.NO_SIGNAL,
                baseline=Outcome.PASSED,
                crosshair=Outcome.PASSED,
            ),
        )
        # Another project's run shares the store and must not be counted here.
        store.record_verdict(
            "somewhere-else",
            Classification(
                nodeid="t::two",
                verdict=Verdict.TROPHY_CANDIDATE,
                baseline=Outcome.PASSED,
                crosshair=Outcome.FAILED,
            ),
        )
    report = drive(
        space,
        FakeSandbox(),
        ["alpha"],
        deadline=9e9,
        image="img",
        run=ran(error="the deadline arrived while this project was running"),
    )
    assert report.attempts[0].verdicts == {"no_signal": 1}
    assert not report.attempts[0].ok


def test_a_store_that_does_not_exist_yet_has_recorded_nothing(tmp_path):
    assert verdicts_recorded(str(tmp_path / "absent.db"), "whatever") == {}


def test_a_window_bounds_what_one_test_may_spend(space, quiet_build):
    checkout(space, "alpha")
    run = ran()
    drive(
        space,
        FakeSandbox(),
        ["alpha"],
        deadline=9e9,
        image="img",
        pipeline_args=["--crosshair-timeout", "60"],
        run=run,
    )
    argv = run.calls[0]["argv"]
    assert argv[argv.index("--crosshair-timeout") + 1] == "60"


def test_a_cut_off_pipeline_does_not_wait_for_what_it_started(tmp_path):
    """A killed pipeline leaves grandchildren holding its pipes.

    Reading its output would then block until they finished, which is what
    the deadline arrived to prevent, so the whole group goes at once.
    """
    script = tmp_path / "fake.py"
    script.write_text(
        "import subprocess, sys\n"
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
        "import time; time.sleep(120)\n"
    )
    started = time.monotonic()
    tested = run_pipeline([sys.executable, str(script)], 1.0)
    assert "deadline" in tested.error
    assert time.monotonic() - started < 20, "it waited for the grandchild"


def test_a_cut_off_run_takes_its_containers_with_it(space, quiet_build, monkeypatch):
    checkout(space, "alpha")
    reaped = []
    monkeypatch.setattr(driver, "reap_containers", lambda label: reaped.append(label))
    drive(
        space,
        FakeSandbox(),
        ["alpha"],
        deadline=9e9,
        image="img",
        run=ran(error="the deadline arrived while this project was running"),
    )
    assert reaped == [project_run_id("alpha", space.existing_checkout("alpha").commit)]


def test_a_run_that_finished_leaves_nothing_to_reap(space, quiet_build, monkeypatch):
    checkout(space, "alpha")
    monkeypatch.setattr(
        driver,
        "reap_containers",
        lambda label: pytest.fail("a finished run removed its own containers"),
    )
    drive(space, FakeSandbox(), ["alpha"], deadline=9e9, image="img", run=ran())


def test_the_tests_a_pipeline_reports_are_named_not_counted(tmp_path):
    """The pipeline reports node ids under `collected`, not a number."""
    payload = {"collected": ["t::one", "t::two"], "classifications": []}
    script = tmp_path / "fake.py"
    script.write_text(f"print({json.dumps(json.dumps(payload))})")
    assert run_pipeline([sys.executable, str(script)], 60).collected == 2


def test_a_report_this_cannot_read_does_not_fail_the_run(tmp_path):
    payload = {"collected": "all of them", "classifications": []}
    script = tmp_path / "fake.py"
    script.write_text(f"print({json.dumps(json.dumps(payload))})")
    tested = run_pipeline([sys.executable, str(script)], 60)
    assert tested.collected == 0 and not tested.error
