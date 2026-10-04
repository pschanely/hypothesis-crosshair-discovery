"""Checks that a manifest describes an environment well enough to rebuild it.

The property that matters is the split: the project side is pinned, the
packages under test are not. A manifest that pinned CrossHair would make the
next run measure the previous run's solver.
"""

from typing import Dict, List, Optional, Sequence

from discovery.manifest import (
    MANIFEST_VERSION,
    Manifest,
    from_dict,
    frozen_requirements,
    pins_for,
    rebuild,
    record,
    toolchain_closure,
)
from discovery.provision import RUN_FROM_CHECKOUT, Provisioned
from discovery.sandbox import ExecResult, Limits, Sandbox

FREEZE = """
attrs==23.2.0
crosshair-tool==0.0.78
hypothesis==6.98.0
hypothesis-crosshair==0.0.18
packaging==24.0
pytest==8.1.1
z3-solver==4.12.6.0
-e file:///proj
"""

CLOSURE = '["hypothesis", "pytest", "crosshair-tool", "hypothesis-crosshair", "z3-solver", "attrs"]'

COLLECTED = "41 tests collected in 0.4s"


class FakeSandbox(Sandbox):
    def __init__(self, answers: Sequence[ExecResult]):
        self.answers = list(answers)
        self.calls: List[dict] = []

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: str,
        env: Optional[Dict[str, str]] = None,
        network: bool = False,
        limits: Optional[Limits] = None,
    ) -> ExecResult:
        self.calls.append(
            {"argv": list(argv), "cwd": cwd, "env": dict(env or {}), "network": network}
        )
        if not self.answers:
            raise AssertionError(f"unscripted command: {list(argv)}")
        return self.answers.pop(0)


def ok(stdout: str = "") -> ExecResult:
    return ExecResult(returncode=0, stdout=stdout, stderr="", duration=0.0)


def fail(stdout: str = "", stderr: str = "") -> ExecResult:
    return ExecResult(returncode=1, stdout=stdout, stderr=stderr, duration=0.0)


def built(**kw) -> Provisioned:
    fields = dict(
        project="/proj",
        python="/proj/.venv/bin/python",
        collected=41,
    )
    fields.update(kw)
    return Provisioned(**fields)


def recorded(answers=None, **kw) -> Manifest:
    sandbox = FakeSandbox(answers or [ok(FREEZE), ok(CLOSURE)])
    return record(sandbox, built(**kw), project="proj", commit="a" * 40)


def test_the_project_side_is_pinned():
    stored = recorded()
    assert "packaging==24.0" in stored.pins


def test_the_packages_under_test_are_not_pinned():
    stored = recorded()
    assert not [line for line in stored.pins if line.startswith("crosshair-tool")]
    assert not [line for line in stored.pins if line.startswith("hypothesis")]
    assert not [line for line in stored.pins if line.startswith("pytest")]


def test_what_the_toolchain_brought_is_not_pinned():
    """z3 is CrossHair's, so pinning it would block CrossHair's next release."""
    stored = recorded()
    assert not [line for line in stored.pins if line.startswith("z3-solver")]
    assert not [line for line in stored.pins if line.startswith("attrs")]


def test_an_unreadable_closure_pins_nothing_the_toolchain_names():
    sandbox = FakeSandbox([ok(FREEZE), fail()])
    stored = record(sandbox, built(), project="proj")
    names = [line.split("==")[0] for line in stored.pins]
    assert "crosshair-tool" not in names
    assert "z3-solver" in names


def test_editable_installs_are_not_pinned():
    stored = recorded()
    assert not [line for line in stored.pins if "file://" in line]


def test_the_resolved_toolchain_is_recorded():
    stored = recorded()
    assert stored.toolchain["crosshair-tool"] == "0.0.78"
    assert stored.toolchain["hypothesis-crosshair"] == "0.0.18"


def test_the_collected_count_is_carried_as_the_rebuild_target():
    assert recorded().collected == 41


def test_freezing_does_not_use_the_network():
    sandbox = FakeSandbox([ok(FREEZE)])
    frozen_requirements(sandbox, "/py", "/proj")
    assert sandbox.calls[0]["network"] is False


def test_the_closure_probe_does_not_use_the_network():
    sandbox = FakeSandbox([ok(CLOSURE)])
    toolchain_closure(sandbox, "/py", "/proj")
    assert sandbox.calls[0]["network"] is False


def test_pins_compare_distribution_names_not_spelling():
    kept = pins_for(["Zope-Interface==6.0", "keep-me==1.0"], ["zope_interface"])
    assert kept == ["keep-me==1.0"]


def test_a_manifest_round_trips():
    stored = recorded(repairs=[RUN_FROM_CHECKOUT], pytest_args=["-p", "no:xdist"])
    again = from_dict(stored.as_dict())
    assert again == stored


def test_a_manifest_from_another_version_is_not_read():
    raw = recorded().as_dict()
    raw["version"] = MANIFEST_VERSION + 1
    assert from_dict(raw) is None


def test_rebuilding_installs_the_pins():
    stored = recorded()
    sandbox = FakeSandbox([ok(), ok(), ok(COLLECTED), ok(FREEZE)])
    done = rebuild(sandbox, stored, "/proj", "/proj/.venv")
    assert done.ready and done.collected == 41
    installed = sandbox.calls[1]["argv"]
    assert "packaging==24.0" in installed


def test_rebuilding_leaves_the_toolchain_free_to_resolve():
    stored = recorded()
    sandbox = FakeSandbox([ok(), ok(), ok(COLLECTED), ok(FREEZE)])
    rebuild(sandbox, stored, "/proj", "/proj/.venv")
    installed = sandbox.calls[1]["argv"]
    assert "hypothesis-crosshair" in installed
    assert not [arg for arg in installed if arg.startswith("crosshair-tool==")]


def test_rebuilding_carries_the_repairs_into_collection():
    stored = recorded(pytest_args=["-m", ""], env={"MPLBACKEND": "Agg"})
    sandbox = FakeSandbox([ok(), ok(), ok(COLLECTED), ok(FREEZE)])
    rebuild(sandbox, stored, "/proj", "/proj/.venv")
    collected = sandbox.calls[2]
    assert collected["argv"][-2:] == ["-m", ""]
    assert collected["env"] == {"MPLBACKEND": "Agg"}


def test_a_project_that_never_built_is_not_installed_on_rebuild():
    stored = recorded(repairs=[RUN_FROM_CHECKOUT])
    sandbox = FakeSandbox([ok(), ok(), ok(COLLECTED), ok(FREEZE)])
    rebuild(sandbox, stored, "/proj", "/proj/.venv")
    assert "-e" not in sandbox.calls[1]["argv"]


def test_a_project_that_built_is_installed_on_rebuild():
    stored = recorded()
    sandbox = FakeSandbox([ok(), ok(), ok(COLLECTED), ok(FREEZE)])
    rebuild(sandbox, stored, "/proj", "/proj/.venv")
    assert "-e" in sandbox.calls[1]["argv"]


def test_refused_pins_are_dropped_rather_than_fought_with():
    stored = recorded()
    sandbox = FakeSandbox(
        [ok(), fail(stderr="no solution"), ok(), ok(COLLECTED), ok(FREEZE)]
    )
    done = rebuild(sandbox, stored, "/proj", "/proj/.venv")
    assert done.ready and done.resolved_afresh
    assert "packaging==24.0" not in sandbox.calls[2]["argv"]


def test_a_rebuild_that_cannot_install_at_all_fails():
    stored = recorded()
    sandbox = FakeSandbox([ok(), fail(stderr="no solution"), fail(stderr="nope")])
    done = rebuild(sandbox, stored, "/proj", "/proj/.venv")
    assert not done.ready


def test_a_rebuild_that_cannot_collect_fails():
    stored = recorded()
    sandbox = FakeSandbox([ok(), ok(), fail(stdout="ERROR collecting")])
    done = rebuild(sandbox, stored, "/proj", "/proj/.venv")
    assert not done.ready and "collection failed" in done.error


def test_a_changed_suite_is_reported_as_drift():
    stored = recorded()
    sandbox = FakeSandbox([ok(), ok(), ok("9 tests collected"), ok(FREEZE)])
    done = rebuild(sandbox, stored, "/proj", "/proj/.venv")
    assert done.ready and done.drifted
    assert "manifest says 41" in done.describe()


def test_an_unchanged_suite_is_not_drift():
    stored = recorded()
    sandbox = FakeSandbox([ok(), ok(), ok(COLLECTED), ok(FREEZE)])
    assert not rebuild(sandbox, stored, "/proj", "/proj/.venv").drifted


def test_a_failed_rebuild_is_not_reported_as_drift():
    """Drift is a measurement; a rebuild that never collected made none."""
    stored = recorded()
    sandbox = FakeSandbox([ok(), ok(), fail(stdout="ERROR collecting")])
    assert not rebuild(sandbox, stored, "/proj", "/proj/.venv").drifted


def test_a_rebuilt_environment_collects_offline():
    stored = recorded()
    sandbox = FakeSandbox([ok(), ok(), ok(COLLECTED), ok(FREEZE)])
    rebuild(sandbox, stored, "/proj", "/proj/.venv")
    assert sandbox.calls[1]["network"] is True
    assert sandbox.calls[2]["network"] is False


def test_an_unparsable_closure_pins_nothing_the_toolchain_names():
    sandbox = FakeSandbox([ok(FREEZE), ok("warning: something else entirely")])
    stored = record(sandbox, built(), project="proj")
    names = [line.split("==")[0] for line in stored.pins]
    assert "crosshair-tool" not in names
    assert "z3-solver" in names


def test_the_closure_reads_a_real_environment():
    """A package the toolchain names only under an extra is not the toolchain's.

    Run against this interpreter, where Hypothesis is installed: it requires
    attrs outright and names django and numpy only under extras, so treating
    the extras as the toolchain's would refuse to pin a project that tests
    against either.
    """
    import os
    import sys

    from discovery.sandbox import LocalSandbox

    found = toolchain_closure(
        LocalSandbox(i_understand_this_is_unsafe=True), sys.executable, os.getcwd()
    )
    assert "hypothesis" in found and "attrs" in found
    assert "django" not in found and "numpy" not in found
    # pytest requires these on older interpreters only: conditional, but the
    # toolchain's own, so they stay in the closure whatever is running.
    assert "exceptiongroup" in found or "tomli" in found


def test_a_rebuild_reports_the_toolchain_it_actually_resolved():
    """The manifest records an older build's versions; the toolchain floats."""
    stored = recorded()
    stored.toolchain = {"crosshair-tool": "0.0.1"}
    newer = FREEZE.replace("crosshair-tool==0.0.78", "crosshair-tool==0.0.112")
    sandbox = FakeSandbox([ok(), ok(), ok(COLLECTED), ok(newer)])
    done = rebuild(sandbox, stored, "/proj", "/proj/.venv")
    assert done.toolchain["crosshair-tool"] == "0.0.112"


def test_a_rebuild_that_cannot_be_read_reports_no_toolchain():
    stored = recorded()
    sandbox = FakeSandbox([ok(), ok(), ok(COLLECTED), fail()])
    assert rebuild(sandbox, stored, "/proj", "/proj/.venv").toolchain == {}
