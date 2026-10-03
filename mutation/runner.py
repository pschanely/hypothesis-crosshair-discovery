"""Applies one suite's mutations and reports which the tests caught."""

import glob
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import List, Optional, Sequence

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: A restored file can keep bytecode compiled from the mutated source when the
#: two happen to match in size and timestamp, which scores a mutation against
#: code that is no longer there.
ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}


@dataclass
class Mutation:
    """One wrong behaviour, and the exact source that would produce it."""

    label: str
    old: str
    new: str
    #: Defaults to the suite's module; set it to mutate a different file.
    path: Optional[str] = None


@dataclass
class Suite:
    label: str
    #: Repository-relative path of the module these mutations rewrite.
    module: str
    #: Repository-relative test files that should object.
    tests: Sequence[str]
    mutations: Sequence[Mutation]


def drop_bytecode() -> None:
    for cached in glob.glob(f"{REPO}/**/__pycache__", recursive=True):
        shutil.rmtree(cached, ignore_errors=True)


def _run_tests(suite: Suite) -> bool:
    done = subprocess.run(
        [sys.executable, "-m", "pytest", *suite.tests, "-q", "--no-header"],
        cwd=REPO,
        capture_output=True,
        text=True,
        env=ENV,
    )
    return done.returncode != 0


def run(suite: Suite, verbose: bool = True) -> List[str]:
    """Apply each mutation in turn; return the labels nothing objected to."""
    escaped = []
    for mutation in suite.mutations:
        target = os.path.join(REPO, mutation.path or suite.module)
        drop_bytecode()
        shutil.copy(target, target + ".bak")
        try:
            text = open(target).read()
            if text.count(mutation.old) != 1:
                if verbose:
                    print(f"STALE   {mutation.label} ({text.count(mutation.old)} hits)")
                escaped.append(mutation.label)
                continue
            open(target, "w").write(text.replace(mutation.old, mutation.new))
            caught = _run_tests(suite)
            if verbose:
                print(f"{'caught ' if caught else 'ESCAPED'} {mutation.label}")
            if not caught:
                escaped.append(mutation.label)
        finally:
            shutil.move(target + ".bak", target)
    drop_bytecode()
    return escaped
