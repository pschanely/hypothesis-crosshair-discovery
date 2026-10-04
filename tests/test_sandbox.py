import os
import subprocess

import pytest

from discovery.sandbox import (
    NOBODY,
    DockerSandbox,
    Limits,
    LocalSandbox,
    default_user,
    reap_containers,
    writable_directory,
)


def argv(**kwargs):
    box = DockerSandbox(image="python:3.12-slim")
    return box.build_argv(["python", "-m", "pytest"], cwd="/srv/proj", **kwargs)


def test_execution_has_no_network_by_default():
    assert "--network=none" in argv()


def test_network_is_only_available_when_asked_for():
    assert "--network=bridge" in argv(network=True)


@pytest.mark.parametrize(
    "flag",
    [
        "--rm",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--user=65534:65534",
    ],
)
def test_hardening_flags_are_always_present(flag):
    assert flag in argv()


def test_resource_ceilings_are_applied():
    line = argv(limits=Limits(memory_mb=512, cpus=2.0, pids=64))
    assert "--memory=512m" in line
    assert "--memory-swap=512m" in line  # no swap escape hatch
    assert "--cpus=2.0" in line
    assert "--pids-limit=64" in line


def test_the_container_runtime_socket_is_never_mounted():
    assert not any("docker.sock" in token for token in argv())


def test_environment_is_passed_explicitly():
    assert "--env=HCD_BACKEND=crosshair" in argv(env={"HCD_BACKEND": "crosshair"})


def test_local_sandbox_must_be_requested_deliberately():
    with pytest.raises(RuntimeError, match="no isolation"):
        LocalSandbox()
    assert LocalSandbox(i_understand_this_is_unsafe=True) is not None


def test_a_path_in_the_working_directory_is_seen_at_the_mount():
    sandbox = DockerSandbox(image="img")
    assert sandbox.inside("/host/proj", "/host/proj/.venv/bin/python") == (
        "/work/.venv/bin/python"
    )


def test_the_working_directory_itself_is_the_mount():
    assert DockerSandbox(image="img").inside("/host/proj", "/host/proj") == "/work"


def test_a_path_in_another_mount_is_seen_through_it():
    sandbox = DockerSandbox(image="img", mounts={"/host/runs": "/run"})
    assert sandbox.inside("/host/proj", "/host/runs/a/report.json") == (
        "/run/a/report.json"
    )


def test_a_path_in_no_mount_is_refused_rather_than_handed_over():
    """A command told to use an unmounted path cannot find it, and says
    something unrecognizable about why."""
    with pytest.raises(ValueError):
        DockerSandbox(image="img").inside("/host/proj", "/host/elsewhere/x")


def test_every_mount_is_given_to_the_container():
    sandbox = DockerSandbox(image="img", mounts={"/host/runs": "/run"})
    argv = sandbox.build_argv(["true"], cwd="/host/proj")
    assert "--volume=/host/runs:/run:rw" in argv


def test_a_local_run_sees_paths_as_they_are():
    sandbox = LocalSandbox(i_understand_this_is_unsafe=True)
    assert sandbox.inside("/host/proj", "/anywhere/else") == "/anywhere/else"


def test_containers_do_not_run_as_root(monkeypatch):
    monkeypatch.setattr(os, "getuid", lambda: 0)
    monkeypatch.setattr(os, "getgid", lambda: 0)
    assert default_user() == NOBODY


def test_containers_run_as_whoever_started_them(monkeypatch):
    monkeypatch.setattr(os, "getuid", lambda: 1000)
    monkeypatch.setattr(os, "getgid", lambda: 1001)
    assert default_user() == "1000:1001"
    argv = DockerSandbox(image="img").build_argv(["true"], cwd="/host/proj")
    assert "--user=1000:1001" in argv


def test_root_leaves_a_run_directory_the_container_can_write(monkeypatch, tmp_path):
    monkeypatch.setattr(os, "getuid", lambda: 0)
    where = writable_directory(str(tmp_path / "run"))
    assert os.stat(where).st_mode & 0o777 == 0o777


def test_an_ordinary_user_owns_what_they_create(monkeypatch, tmp_path):
    monkeypatch.setattr(os, "getuid", lambda: 1000)
    where = writable_directory(str(tmp_path / "run"))
    assert os.stat(where).st_mode & 0o777 != 0o777


def test_a_container_is_marked_with_the_run_it_belongs_to():
    sandbox = DockerSandbox(image="img", label="alpha-2812594e")
    assert "--label=discovery-run=alpha-2812594e" in sandbox.build_argv(
        ["true"], cwd="/host/proj"
    )


def test_an_unlabelled_run_marks_nothing():
    argv = DockerSandbox(image="img").build_argv(["true"], cwd="/host/proj")
    assert not [arg for arg in argv if arg.startswith("--label")]


def test_a_run_takes_its_containers_with_it(monkeypatch):
    calls = []

    class Done:
        stdout = "abc123\ndef456\n"

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return Done()

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert reap_containers("alpha-2812594e") == 2
    assert "label=discovery-run=alpha-2812594e" in calls[0]
    assert calls[1][:3] == ["docker", "rm", "--force"]
    assert calls[1][3:] == ["abc123", "def456"]


def test_a_run_that_left_no_containers_removes_nothing(monkeypatch):
    class Done:
        stdout = "\n"

    monkeypatch.setattr(subprocess, "run", lambda argv, **kw: Done())
    assert reap_containers("alpha") == 0


def test_nothing_is_reaped_without_a_run_to_reap_for(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: pytest.fail("an empty label would match every container"),
    )
    assert reap_containers("") == 0


def test_a_runtime_that_cannot_be_reached_reaps_nothing(monkeypatch):
    def explode(*a, **k):
        raise OSError("no docker here")

    monkeypatch.setattr(subprocess, "run", explode)
    assert reap_containers("alpha") == 0
