"""Run every mutation suite, or the ones named on the command line."""

import importlib
import pkgutil
import sys
from typing import Dict, List

import mutation
from mutation.runner import Suite, run


def suites() -> Dict[str, Suite]:
    found = {}
    for info in pkgutil.iter_modules(mutation.__path__):
        if info.name in ("runner", "__main__"):
            continue
        module = importlib.import_module(f"mutation.{info.name}")
        suite = getattr(module, "SUITE", None)
        if isinstance(suite, Suite):
            found[info.name] = suite
    return dict(sorted(found.items()))


def main(argv: List[str]) -> int:
    every = suites()
    chosen = argv or list(every)
    unknown = [name for name in chosen if name not in every]
    if unknown:
        print(f"no such suite: {', '.join(unknown)}", file=sys.stderr)
        print(f"available: {', '.join(every)}", file=sys.stderr)
        return 2

    failed = {}
    for name in chosen:
        print(f"\n=== {name} ===")
        escaped = run(every[name])
        if escaped:
            failed[name] = escaped

    print()
    if not failed:
        print(f"{len(chosen)} suite(s): every mutation caught")
        return 0
    for name, escaped in failed.items():
        print(f"{name}: {len(escaped)} escaped -- {', '.join(escaped)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
