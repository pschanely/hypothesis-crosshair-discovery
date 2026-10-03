"""Mutations for the recorded repository index."""

from mutation.runner import Mutation, Suite

SUITE = Suite(
    label="known_repos",
    module="discovery/known_repos.py",
    tests=["tests/test_known_repos.py"],
    mutations=[
        Mutation(
            "entries with no recorded tests are kept",
            "    carrying = [entry for entry in every if entry.nodeids]",
            "    carrying = list(every)",
        ),
        Mutation(
            "an array dependency no longer sorts last",
            "            bool(entry.opaque_dependencies),\n            -len(entry.nodeids),",
            "            -len(entry.nodeids),",
        ),
        Mutation(
            "test count no longer orders the queue",
            "            -len(entry.nodeids),\n            entry.name,",
            "            entry.name,",
        ),
        Mutation(
            "what provisioning supplies is taken from the index too",
            "            if name and name not in PROVISIONED_SEPARATELY and name not in seen:",
            "            if name and name not in seen:",
        ),
        Mutation(
            "a slash stays in the candidate name",
            '            name=self.name.replace("/", "__"),',
            "            name=self.name,",
        ),
        Mutation(
            "recorded node ids are dropped",
            "            known_nodeids=list(self.nodeids),",
            "            known_nodeids=[],",
        ),
        Mutation(
            "the repository url loses its owner",
            '        return f"{DEFAULT_HOST}/{self.name}"',
            '        return f"{DEFAULT_HOST}/{self.name.split(chr(47))[-1]}"',
        ),
        Mutation(
            "a trailing comment stays part of the name",
            '    for separator in (";", "[", "(", "=", "<", ">", "!", "~", " ", "#"):',
            '    for separator in (";", "[", "(", "=", "<", ">", "!", "~", " "):',
            path="discovery/pypi.py",
        ),
        Mutation(
            "a dashed distribution matches by prefix rather than exactly",
            '            if name.replace("-", "_") in OPAQUE_IMPORTS',
            "            if any(name.startswith(o[:3]) for o in OPAQUE_IMPORTS)",
        ),
        Mutation(
            "the budget is ignored",
            "    chosen = ranked[:budget] if budget else ranked",
            "    chosen = ranked",
        ),
    ],
)
