"""Process isolation for running untrusted third-party test suites.

Two backends: :class:`DockerSandbox` is the supported one, and
:class:`LocalSandbox` runs directly on the host for development only. The
local backend must be requested explicitly; nothing selects it by default.
"""

import os
import shutil
import signal
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence


@dataclass
class ExecResult:
    returncode: int
    stdout: str
    stderr: str
    duration: float
    timed_out: bool = False

    @property
    def killed_by_signal(self) -> Optional[int]:
        return -self.returncode if self.returncode < 0 else None


@dataclass
class Limits:
    """Resource ceilings applied to every sandboxed process."""

    wall_seconds: int = 900
    memory_mb: int = 4096
    cpus: float = 1.0
    pids: int = 256
    output_bytes: int = 4_000_000


class Sandbox(ABC):
    def inside(self, cwd: str, path: str) -> str:
        """The path as a command run from ``cwd`` will see it.

        A backend that relocates the working directory has to translate the
        paths it is handed, or a command is told to look somewhere that
        exists only outside it.
        """
        return path

    @abstractmethod
    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: str,
        env: Optional[Dict[str, str]] = None,
        network: bool = False,
        limits: Optional[Limits] = None,
    ) -> ExecResult: ...


#: The user a container runs as when none is named.
#:
#: Files a container writes into the mounted workspace are owned by whoever
#: wrote them, so running as the invoking user keeps the workspace usable
#: afterwards. Only a root invoker falls back to nobody, which then has to
#: be able to write the workspace.
NOBODY = "65534:65534"


def default_user() -> str:
    uid, gid = os.getuid(), os.getgid()
    return NOBODY if uid == 0 else f"{uid}:{gid}"


#: Names the run a container belongs to.
RUN_LABEL = "discovery-run"


def reap_containers(label: str, docker: str = "docker") -> int:
    """Remove the containers a run left behind, and report how many.

    Killing a container client does not stop its container: the daemon
    keeps it, so a run the deadline cut off would otherwise leave a solver
    running on the machine with nothing watching it.
    """
    if not label:
        return 0
    try:
        listed = subprocess.run(
            [docker, "ps", "-q", "--filter", f"label={RUN_LABEL}={label}"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return 0
    ids = [line.strip() for line in listed.stdout.splitlines() if line.strip()]
    if not ids:
        return 0
    try:
        subprocess.run(
            [docker, "rm", "--force", *ids],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except (OSError, subprocess.SubprocessError):
        return 0
    return len(ids)


def writable_directory(path: str) -> str:
    """Make a directory the sandboxed user can write into.

    A container running as nobody cannot write a directory root created,
    and the orchestrator runs as root often enough -- in CI, in a container
    of its own -- that a run would fail there and nowhere else.
    """
    os.makedirs(path, exist_ok=True)
    if os.getuid() == 0:
        os.chmod(path, 0o777)
    return path


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit // 2] + "\n...[truncated]...\n" + text[-limit // 2 :]


class DockerSandbox(Sandbox):
    """Runs each command in a throwaway, locked-down container.

    Network access is off unless a caller explicitly asks for it, which only
    the dependency-installation step does.
    """

    def __init__(
        self,
        image: str,
        *,
        workdir_mount: str = "/work",
        docker: str = "docker",
        user: str = "",
        mounts: Optional[Dict[str, str]] = None,
        label: str = "",
        extra_args: Sequence[str] = (),
    ) -> None:
        self.image = image
        self.workdir_mount = workdir_mount
        self.docker = docker
        self.user = user or default_user()
        #: Host directories mounted into every container besides the working
        #: directory. A run needs somewhere to write its reports that is not
        #: the project it is testing.
        self.mounts = dict(mounts or {})
        #: Marks every container this sandbox starts as belonging to one
        #: run, so a run cut off partway can take its containers with it.
        self.label = label
        self.extra_args = list(extra_args)

    def inside(self, cwd: str, path: str) -> str:
        """The path as the container sees it, through whichever mount holds it.

        A path under none of them is not visible to the container at all, so
        naming one is an error here rather than a command that cannot find
        the file.
        """
        for outside, there in [(cwd, self.workdir_mount), *self.mounts.items()]:
            relative = os.path.relpath(os.path.abspath(path), os.path.abspath(outside))
            if relative != os.pardir and not relative.startswith(os.pardir + os.sep):
                return os.path.normpath(os.path.join(there, relative))
        raise ValueError(f"{path} is not mounted into the sandbox")

    def build_argv(
        self,
        argv: Sequence[str],
        *,
        cwd: str,
        env: Optional[Dict[str, str]] = None,
        network: bool = False,
        limits: Optional[Limits] = None,
    ) -> List[str]:
        limits = limits or Limits()
        cmd = [
            self.docker,
            "run",
            "--rm",
            "--interactive=false",
            f"--network={'bridge' if network else 'none'}",
            "--read-only",
            "--tmpfs=/tmp:rw,noexec,nosuid,size=1g",
            f"--tmpfs={self.workdir_mount}/.scratch:rw,nosuid,size=1g",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            f"--pids-limit={limits.pids}",
            f"--memory={limits.memory_mb}m",
            f"--memory-swap={limits.memory_mb}m",
            f"--cpus={limits.cpus}",
            f"--user={self.user}",
            f"--volume={cwd}:{self.workdir_mount}:rw",
            f"--workdir={self.workdir_mount}",
        ]
        for outside, there in sorted(self.mounts.items()):
            cmd.append(f"--volume={outside}:{there}:rw")
        if self.label:
            cmd.append(f"--label={RUN_LABEL}={self.label}")
        for key, value in sorted((env or {}).items()):
            cmd.append(f"--env={key}={value}")
        cmd.extend(self.extra_args)
        cmd.append(self.image)
        cmd.extend(argv)
        return cmd

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: str,
        env: Optional[Dict[str, str]] = None,
        network: bool = False,
        limits: Optional[Limits] = None,
    ) -> ExecResult:
        limits = limits or Limits()
        cmd = self.build_argv(argv, cwd=cwd, env=env, network=network, limits=limits)
        return _spawn(cmd, cwd=None, env=os.environ.copy(), limits=limits)


class LocalSandbox(Sandbox):
    """Runs commands directly on the host. Provides no isolation.

    Intended for developing the pipeline against code you already trust.
    """

    def __init__(self, *, i_understand_this_is_unsafe: bool = False) -> None:
        if not i_understand_this_is_unsafe:
            raise RuntimeError(
                "LocalSandbox provides no isolation and must be requested "
                "explicitly with i_understand_this_is_unsafe=True"
            )

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: str,
        env: Optional[Dict[str, str]] = None,
        network: bool = False,
        limits: Optional[Limits] = None,
    ) -> ExecResult:
        limits = limits or Limits()
        merged = os.environ.copy()
        merged.update(env or {})
        return _spawn(list(argv), cwd=cwd, env=merged, limits=limits)


def _rlimit_setter(limits: Limits):
    def apply() -> None:
        os.setsid()
        try:
            import resource

            soft = limits.memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (soft, soft))
            resource.setrlimit(resource.RLIMIT_NPROC, (limits.pids, limits.pids))
        except Exception:
            pass

    return apply


def _spawn(
    cmd: List[str], *, cwd: Optional[str], env: Dict[str, str], limits: Limits
) -> ExecResult:
    """Run to completion, escalating a timeout straight to SIGKILL.

    CrossHair installs a bytecode tracer, and a wedged tracer may never run a
    SIGTERM handler, so the whole process group is killed outright.
    """
    started = time.monotonic()
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        preexec_fn=_rlimit_setter(limits),
    )
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=limits.wall_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        stdout, stderr = proc.communicate()
    return ExecResult(
        returncode=proc.returncode,
        stdout=_truncate(stdout or "", limits.output_bytes),
        stderr=_truncate(stderr or "", limits.output_bytes),
        duration=time.monotonic() - started,
        timed_out=timed_out,
    )


def docker_available(docker: str = "docker") -> bool:
    if shutil.which(docker) is None:
        return False
    probe = subprocess.run(
        [docker, "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    return probe.returncode == 0
