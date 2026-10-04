"""Entry point for building environments the pipeline can then run in.

With a workspace, building an environment is idempotent: the first run
provisions and records a manifest, and a later container rebuilds from that
manifest instead of rediscovering the repairs.
"""

import argparse
import json
import os
import sys
from typing import List, Optional

from .manifest import Rebuilt, rebuild, record
from .provenance import project_commit, remote_url
from .provision import DEFAULT_PLUGIN, provision
from .sandbox import DockerSandbox, LocalSandbox, Sandbox
from .workspace import Workspace


def _sandbox(args) -> Sandbox:
    if args.sandbox == "docker":
        return DockerSandbox(image=args.image)
    return LocalSandbox(i_understand_this_is_unsafe=True)


def _as_json(done) -> dict:
    if isinstance(done, Rebuilt):
        return {
            "project": done.manifest.project,
            "ready": done.ready,
            "rebuilt": True,
            "collected": done.collected,
            "drifted": done.drifted,
            "resolved_afresh": done.resolved_afresh,
            "repairs": done.manifest.repairs,
            "error": done.error,
        }
    return {
        "project": done.project,
        "ready": done.ready,
        "rebuilt": False,
        "python": done.python,
        "pytest_args": done.pytest_args,
        "env": done.env,
        "repairs": done.repairs,
        "collected": done.collected,
        "error": done.error,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="discovery-provision",
        description=(
            "Build a virtual environment per project, repairing the harness "
            "where the failure is one that has been seen before."
        ),
    )
    parser.add_argument(
        "projects",
        nargs="+",
        help="project checkouts, or names of checkouts in the workspace",
    )
    parser.add_argument(
        "--plugin",
        default=DEFAULT_PLUGIN,
        help=(
            "the hypothesis-crosshair requirement to install into each "
            "environment: a released version by default, or a git specifier "
            "or checkout to test an unreleased change"
        ),
    )
    parser.add_argument("--sandbox", choices=("docker", "local"), default="docker")
    parser.add_argument("--image", default="python:3.12-slim")
    parser.add_argument("--python-version", default="3.12")
    parser.add_argument("--venv-name", default=".venv-ch")
    parser.add_argument(
        "--package", action="append", default=[], help="extra package to install"
    )
    parser.add_argument(
        "--workspace",
        default="",
        help=(
            "persistent directory holding checkouts and manifests; a project "
            "with a manifest is rebuilt from it rather than provisioned again"
        ),
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="provision from scratch even where a manifest exists",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    space = Workspace.from_environment(args.workspace)
    if space is not None:
        space.prepare()

    sandbox = _sandbox(args)
    plugin = os.path.abspath(args.plugin) if os.path.isdir(args.plugin) else args.plugin
    results = []
    for path in args.projects:
        project = os.path.abspath(path)
        if not os.path.isdir(project) and space is not None:
            project = space.checkout_dir(path)
        if not os.path.isdir(project):
            print(f"not a directory: {path}", file=sys.stderr)
            return 2
        name = os.path.basename(os.path.normpath(project))
        venv_dir = os.path.join(project, args.venv_name)

        stored = None if args.refresh or space is None else space.read_manifest(name)
        if stored is not None:
            done = rebuild(sandbox, stored, project, venv_dir, plugin=plugin)
        else:
            done = provision(
                sandbox,
                project,
                plugin,
                venv_dir=venv_dir,
                python_version=args.python_version,
                extra_packages=args.package,
            )
            if done.ready and space is not None:
                space.write_manifest(
                    record(
                        sandbox,
                        done,
                        project=name,
                        repo_url=remote_url(project),
                        commit=project_commit(project),
                        python_version=args.python_version,
                        plugin=args.plugin,
                    )
                )
        results.append(done)
        if not args.json:
            print(done.describe(), flush=True)
            for repair in getattr(done, "repairs", []):
                print(f"    repaired: {repair}", flush=True)

    ready = [r for r in results if r.ready]
    if args.json:
        print(json.dumps([_as_json(r) for r in results], indent=1))
    else:
        print(f"\n{len(ready)}/{len(results)} provisioned")
    return 0 if len(ready) == len(results) else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
