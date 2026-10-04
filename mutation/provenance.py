"""Mutations for what a verdict is a verdict about."""

from mutation.runner import Mutation, Suite

SUITE = Suite(
    label="provenance",
    module="discovery/provenance.py",
    tests=["tests/test_provenance.py"],
    mutations=[
        Mutation(
            "the version is asked of the host, not of the sandbox",
            "        if sandbox is not None:\n            done = sandbox.run(",
            "        if False:\n            done = sandbox.run(",
        ),
        Mutation(
            "reading a version is allowed the network",
            "                argv, cwd=cwd, network=False, limits=Limits(wall_seconds=120)",
            "                argv, cwd=cwd, network=True, limits=Limits(wall_seconds=120)",
        ),
        Mutation(
            "the probe runs somewhere other than the project",
            "                argv, cwd=cwd, network=False, limits=Limits(wall_seconds=120)",
            '                argv, cwd="/", network=False, limits=Limits(wall_seconds=120)',
        ),
        Mutation(
            "an interpreter that could not be reached reports a version anyway",
            "    if done.returncode != 0:\n        return blank",
            "    if False:\n        return blank",
        ),
        Mutation(
            "an unreadable answer raises instead of reading as unknown",
            "    except (ValueError, IndexError):\n        return blank",
            "    except KeyboardInterrupt:\n        return blank",
        ),
        Mutation(
            "a missing version reads as something rather than unknown",
            "    return {name: str(found.get(name, UNKNOWN)) for name in blank}",
            '    return {name: str(found.get(name, "")) for name in blank}',
        ),
        Mutation(
            "a directory that is not a checkout reports a commit",
            '            ["git", "-C", project_dir, "rev-parse", "HEAD"],\n            capture_output=True,\n            text=True,\n            timeout=30,\n        )\n    except (OSError, subprocess.SubprocessError):\n        return UNKNOWN\n    return done.stdout.strip() if done.returncode == 0 else UNKNOWN',
            '            ["git", "-C", project_dir, "rev-parse", "HEAD"],\n            capture_output=True,\n            text=True,\n            timeout=30,\n        )\n    except (OSError, subprocess.SubprocessError):\n        return UNKNOWN\n    return done.stdout.strip()',
        ),
    ],
)
