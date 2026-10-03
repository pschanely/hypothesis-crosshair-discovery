"""Mutations for failure clustering."""

from mutation.runner import Mutation, Suite

SUITE = Suite(
    label="cluster",
    module="discovery/cluster.py",
    tests=["tests/test_cluster.py"],
    mutations=[
        Mutation(
            "outermost frame instead of innermost",
            "    path, line = found[-1]",
            "    path, line = found[0]",
        ),
        Mutation(
            "library frames count as project code",
            "    if any(marker in normalized for marker in _FOREIGN_PATH_MARKERS):\n        return False",
            "    if False:\n        return False",
        ),
        Mutation(
            "numbers are not normalized out",
            '    return _NUMBER_RE.sub("N", collapsed)[:_MESSAGE_LIMIT]',
            "    return collapsed[:_MESSAGE_LIMIT]",
        ),
        Mutation(
            "every message normalizes the same",
            '    return _NUMBER_RE.sub("N", collapsed)[:_MESSAGE_LIMIT]',
            '    return "MSG"',
        ),
        Mutation(
            "the frame is not part of the identity",
            "        key = (signature.exception_type, signature.frame, signature.message)",
            "        key = (signature.exception_type, signature.message)",
        ),
        Mutation(
            "the exception type is not part of the identity",
            "        key = (signature.exception_type, signature.frame, signature.message)",
            "        key = (signature.frame, signature.message)",
        ),
        Mutation(
            "passing verdicts are clustered too",
            "        if not item.exception_type:\n            continue",
            "        if False:\n            continue",
        ),
        Mutation(
            "clusters come back unordered",
            "    return sorted(found.values(), key=lambda c: (-c.size, c.signature.describe()))",
            "    return sorted(found.values(), key=lambda c: c.signature.describe())",
        ),
        Mutation(
            "addresses are not scrubbed",
            "    for pattern, replacement in _SCRUB:\n        text = pattern.sub(replacement, text)",
            "    for pattern, replacement in []:\n        text = pattern.sub(replacement, text)",
        ),
    ],
)
