"""Mutations for process isolation and the paths a container can see."""

from mutation.runner import Mutation, Suite

SUITE = Suite(
    label="sandbox",
    module="discovery/sandbox.py",
    tests=["tests/test_sandbox.py"],
    mutations=[
        Mutation(
            "a container reaches the network whether or not it asked",
            "f\"--network={'bridge' if network else 'none'}\",",
            'f"--network=bridge",',
        ),
        Mutation(
            "the image filesystem is writable",
            '            "--read-only",\n',
            "",
        ),
        Mutation(
            "capabilities are kept",
            '            "--cap-drop=ALL",\n',
            "",
        ),
        Mutation(
            "privileges can be gained",
            '            "--security-opt=no-new-privileges",\n',
            "",
        ),
        Mutation(
            "a path outside every mount is handed over anyway",
            '        raise ValueError(f"{path} is not mounted into the sandbox")',
            "        return path",
        ),
        Mutation(
            "extra mounts are never given to the container",
            '        for outside, there in sorted(self.mounts.items()):\n            cmd.append(f"--volume={outside}:{there}:rw")',
            "        pass",
        ),
        Mutation(
            "every path is resolved through the working directory alone",
            "        for outside, there in [(cwd, self.workdir_mount), *self.mounts.items()]:",
            "        for outside, there in [(cwd, self.workdir_mount)]:",
        ),
        Mutation(
            "a container is not marked with the run it belongs to",
            '        if self.label:\n            cmd.append(f"--label={RUN_LABEL}={self.label}")',
            "        pass",
        ),
        Mutation(
            "an unlabelled run reaps every container on the machine",
            "    if not label:\n        return 0",
            "    if False:\n        return 0",
        ),
        Mutation(
            "containers are listed but never removed",
            '        subprocess.run(\n            [docker, "rm", "--force", *ids],',
            '        subprocess.run(\n            [docker, "ps", *ids],',
        ),
        Mutation(
            "every container is reaped, not the run's own",
            '            [docker, "ps", "-q", "--filter", f"label={RUN_LABEL}={label}"],',
            '            [docker, "ps", "-q"],',
        ),
        Mutation(
            "a runtime that cannot be reached raises instead of reaping nothing",
            "    except (OSError, subprocess.SubprocessError):\n        return 0\n    ids = [",
            "    except KeyboardInterrupt:\n        return 0\n    ids = [",
        ),
        Mutation(
            "a container runs as root when root starts it",
            '    return NOBODY if uid == 0 else f"{uid}:{gid}"',
            '    return f"{uid}:{gid}"',
        ),
        Mutation(
            "a run directory root made is left unwritable for the container",
            "    if os.getuid() == 0:\n        os.chmod(path, 0o777)",
            "    pass",
        ),
        Mutation(
            "every run directory is made world writable",
            "    if os.getuid() == 0:",
            "    if True:",
        ),
        Mutation(
            "the local sandbox needs no acknowledgement",
            "        if not i_understand_this_is_unsafe:",
            "        if False:",
        ),
    ],
)
