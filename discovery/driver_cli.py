"""Entry point for one scheduled run."""

import argparse
import os
import sys
import time
from typing import List, Optional

from .driver import drive, write_report
from .provision import DEFAULT_PLUGIN
from .sandbox import DockerSandbox, LocalSandbox, Sandbox
from .workspace import Workspace

#: Default length of a run, in minutes. A run is cut off, not hurried.
DEFAULT_WINDOW = 60


def _sandbox(args) -> Sandbox:
    if args.sandbox == "docker":
        return DockerSandbox(image=args.image)
    return LocalSandbox(i_understand_this_is_unsafe=True)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="discovery-run",
        description=(
            "Take each project as far as the window allows: restore its "
            "checkout, build its environment from the manifest, run its "
            "tests, and write a report."
        ),
    )
    parser.add_argument(
        "projects",
        nargs="*",
        help="workspace project names; every project with a manifest by default",
    )
    parser.add_argument(
        "--workspace",
        default="",
        help="persistent directory holding checkouts, manifests and the store",
    )
    parser.add_argument(
        "--minutes",
        type=float,
        default=DEFAULT_WINDOW,
        help="how long this run may take before it stops starting projects",
    )
    parser.add_argument("--sandbox", choices=("docker", "local"), default="docker")
    parser.add_argument("--image", default="discovery-target:3.12")
    parser.add_argument("--python-version", default="3.12")
    parser.add_argument("--plugin", default=DEFAULT_PLUGIN)
    parser.add_argument(
        "--clean-room",
        action="store_true",
        help=(
            "build a second environment without the plugin, so a finding can "
            "be replayed somewhere CrossHair never loaded. Without it, "
            "findings stay unvalidated rather than being claimed."
        ),
    )
    parser.add_argument(
        "--test-timeout",
        type=int,
        default=300,
        help=(
            "seconds one test may spend in the solver. Lower than the "
            "pipeline's own default, because a window holding several "
            "projects cannot give one test a quarter of an hour."
        ),
    )
    parser.add_argument(
        "--pipeline-arg",
        action="append",
        default=[],
        metavar="ARG",
        help="extra argument for each project's pipeline. Repeatable.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    space = Workspace.from_environment(args.workspace)
    if space is None:
        print(
            "no workspace: pass --workspace or set DISCOVERY_WORKSPACE",
            file=sys.stderr,
        )
        return 2
    space.prepare()

    projects = args.projects or [stored.project for stored in space.manifests()]
    if not projects:
        print(
            f"nothing to run: no project named, and no manifests in "
            f"{space.path('manifests')}",
            file=sys.stderr,
        )
        return 2

    report = drive(
        space,
        _sandbox(args),
        projects,
        deadline=time.time() + args.minutes * 60,
        image=args.image,
        plugin=(
            os.path.abspath(args.plugin) if os.path.isdir(args.plugin) else args.plugin
        ),
        python_version=args.python_version,
        clean_room=args.clean_room,
        pipeline_args=["--crosshair-timeout", str(args.test_timeout)]
        + list(args.pipeline_arg),
    )
    where = write_report(space, report)

    if args.json:
        import json

        print(json.dumps(report.as_dict(), indent=1, sort_keys=True))
    else:
        print("\n".join(report.describe()))
        print(f"\nreport: {where}")
    return 0 if all(attempt.ok for attempt in report.attempts) else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
