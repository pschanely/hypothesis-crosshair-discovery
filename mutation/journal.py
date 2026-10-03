"""Mutations for the durable queue and the resume journal."""

from mutation.runner import Mutation, Suite

SUITE = Suite(
    label="journal",
    module="discovery/store.py",
    tests=["tests/test_journal.py"],
    mutations=[
        Mutation(
            "resume forgets prior verdicts",
            "    for known in journal.completed():",
            "    for known in []:",
            path="discovery/cli.py",
        ),
        Mutation(
            "cache is never consulted",
            "        payload = self.store.cached(self.key(nodeid))",
            "        payload = None",
            path="discovery/cli.py",
        ),
        Mutation(
            "refresh is ignored",
            "        if self.refresh:\n            return None",
            "        if False:\n            return None",
            path="discovery/cli.py",
        ),
        Mutation(
            "attempts are unbounded",
            "        if attempts > max_attempts:",
            "        if False:",
        ),
        Mutation(
            "work is keyed without the run",
            "    PRIMARY KEY (run_id, kind, key)",
            "    PRIMARY KEY (kind, key)",
        ),
        Mutation(
            "the key ignores the commit",
            "        [commit_sha, nodeid, crosshair_version, plugin_version, python_version]",
            "        [nodeid, crosshair_version, plugin_version, python_version]",
        ),
        Mutation(
            "a lost claim is never re-offered",
            "            self.run_id, store_mod.RUN_TEST, time.time(), lease_seconds=0.0",
            "            self.run_id, store_mod.RUN_TEST, time.time()",
            path="discovery/cli.py",
        ),
    ],
)
