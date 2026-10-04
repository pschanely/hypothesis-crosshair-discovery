"""Checks that a verdict knows what it is a verdict about.

A cached verdict is reusable only against the same solver, so the version
that keys it has to be read from the interpreter that will run the solver.
Under docker that interpreter is a path inside the container, and asking
the host about it reads as unknown -- which every verdict would then share,
leaving a CrossHair release unable to invalidate any of them.
"""

import sys
from typing import Dict, List, Optional, Sequence

from discovery.provenance import UNKNOWN, environment_versions, project_commit
from discovery.sandbox import ExecResult, Limits, Sandbox

PROBED = '{"python": "3.12.1", "crosshair": "0.0.112", "plugin": "0.0.30"}'


class FakeSandbox(Sandbox):
    def __init__(self, answer: ExecResult):
        self.answer = answer
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
        self.calls.append({"argv": list(argv), "cwd": cwd, "network": network})
        return self.answer


def test_the_versions_come_from_the_interpreter_the_solver_will_use():
    sandbox = FakeSandbox(ExecResult(0, PROBED, "", 0.0))
    found = environment_versions(["/work/.venv-ch/bin/python"], sandbox, "/host/proj")
    assert found == {"python": "3.12.1", "crosshair": "0.0.112", "plugin": "0.0.30"}
    assert sandbox.calls[0]["argv"][0] == "/work/.venv-ch/bin/python"
    assert sandbox.calls[0]["cwd"] == "/host/proj"


def test_reading_a_version_needs_no_network():
    sandbox = FakeSandbox(ExecResult(0, PROBED, "", 0.0))
    environment_versions(["/py"], sandbox, "/host/proj")
    assert sandbox.calls[0]["network"] is False


def test_an_interpreter_that_cannot_be_reached_reads_as_unknown():
    """Even when something readable came back with the failure."""
    sandbox = FakeSandbox(ExecResult(1, PROBED, "no such file", 0.0))
    found = environment_versions(["/work/.venv-ch/bin/python"], sandbox, "/proj")
    assert found == {"python": UNKNOWN, "crosshair": UNKNOWN, "plugin": UNKNOWN}


def test_an_unreadable_answer_reads_as_unknown():
    sandbox = FakeSandbox(ExecResult(0, "not json", "", 0.0))
    assert environment_versions(["/py"], sandbox, "/proj")["crosshair"] == UNKNOWN


def test_a_version_the_probe_did_not_report_reads_as_unknown():
    sandbox = FakeSandbox(ExecResult(0, '{"python": "3.12.1"}', "", 0.0))
    found = environment_versions(["/py"], sandbox, "/proj")
    assert found["python"] == "3.12.1"
    assert found["crosshair"] == UNKNOWN and found["plugin"] == UNKNOWN


def test_without_a_sandbox_the_host_interpreter_answers():
    found = environment_versions([sys.executable])
    assert found["python"] == ".".join(str(n) for n in sys.version_info[:3])


def test_a_directory_that_is_not_a_checkout_has_no_commit(tmp_path):
    assert project_commit(str(tmp_path)) == UNKNOWN
