"""Mutations for the durable queue and the resume journal."""

from mutation.runner import Mutation, Suite

SUITE = Suite(
    label="journal",
    module="discovery/store.py",
    tests=["tests/test_journal.py", "tests/test_driver.py", "tests/test_store.py"],
    mutations=[
        Mutation(
            "a failure is recorded without the solver that produced it",
            '        args: List[Any] = [run_id]\n        if version:\n            sql += " AND version = ?"\n            args.append(version)',
            "        args: List[Any] = [run_id]",
        ),
        Mutation(
            "a run with no known version matches no failures at all",
            '        if version:\n            sql += " AND version = ?"',
            '        if version is not None:\n            sql += " AND version = ?"',
        ),
        Mutation(
            "a failure is kept for one version only, whichever came last",
            "    PRIMARY KEY (run_id, nodeid, version)",
            "    PRIMARY KEY (run_id, nodeid)",
        ),
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
