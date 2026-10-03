"""Suites that break the code deliberately, to check the tests notice.

A test that cannot fail is not a test. Each suite names a plausible wrong
behaviour, rewrites the source to produce it, and runs the tests that should
object. A mutation nothing objects to is a gap, and this has found several --
tests that passed because a fixture happened to be ordered conveniently, a
sort key that could never change an outcome, a guard with nothing behind it.

Anchors are exact source text, so reformatting breaks them. A suite reports a
stale anchor as a failure rather than skipping it, because a suite that
quietly checks nothing is worse than one that is red.
"""
