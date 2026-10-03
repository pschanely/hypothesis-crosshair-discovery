"""Mutations for the clone-and-survey probe."""

from mutation.runner import Mutation, Suite

SUITE = Suite(
    label="probe",
    module="discovery/probe.py",
    tests=["tests/test_probe.py"],
    mutations=[
        Mutation(
            "a checkout is left behind after being read",
            "        if not keep:\n            shutil.rmtree(dest, ignore_errors=True)",
            "        if False:\n            shutil.rmtree(dest, ignore_errors=True)",
        ),
        Mutation(
            "keep is ignored and the checkout is always removed",
            "        if not keep:\n            shutil.rmtree(dest, ignore_errors=True)",
            "        shutil.rmtree(dest, ignore_errors=True)",
        ),
        Mutation(
            "a stale checkout is cloned into rather than replaced",
            "    shutil.rmtree(dest, ignore_errors=True)\n    started = time.monotonic()",
            "    started = time.monotonic()",
        ),
        Mutation(
            "a failed clone raises instead of being reported",
            "    except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:",
            "    except ValueError as exc:",
        ),
        Mutation(
            "git's failure is not noticed at all",
            "    if done.returncode != 0:",
            "    if False:",
        ),
        Mutation(
            "a project with no tests counts as worth provisioning",
            "        return self.assessment is not None and self.assessment.runnable",
            "        return self.assessment is not None",
        ),
        Mutation(
            "a failed probe counts as worth provisioning",
            "        return self.assessment is not None and self.assessment.runnable",
            "        return not self.error",
        ),
        Mutation(
            "the full history is fetched",
            "CLONE_DEPTH = 1",
            "CLONE_DEPTH = 0",
        ),
        Mutation(
            "describe hides how many tests were found",
            '            f"{self.candidate.name}: score {found.score}, {found.units} property "\n            f"tests  {self.candidate.repo_url}"',
            '            f"{self.candidate.name}: ok"',
        ),
        Mutation(
            "an oversized checkout is read anyway",
            "    if max_megabytes and size > max_megabytes:",
            "    if False:",
        ),
        Mutation(
            "an oversized checkout is left on disk",
            '        shutil.rmtree(dest, ignore_errors=True)\n        return ProbeResult(\n            candidate,\n            error=f"checkout is {size}MB, over the {max_megabytes}MB budget",',
            '        return ProbeResult(\n            candidate,\n            error=f"checkout is {size}MB, over the {max_megabytes}MB budget",',
        ),
        Mutation(
            "checkout size is never measured",
            "    size = checkout_megabytes(dest)",
            "    size = 0",
        ),
    ],
)
