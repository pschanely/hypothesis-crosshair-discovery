"""Mutations for the triage queue and schema gate."""

from mutation.runner import Mutation, Suite

SUITE = Suite(
    label="triage",
    module="discovery/triage.py",
    tests=["tests/test_triage.py"],
    mutations=[
        Mutation(
            "unknown categories are accepted",
            '        category = TriageCategory(payload["category"])',
            '        category = payload["category"]',
        ),
        Mutation(
            "confidence range is not checked",
            "    if not MIN_CONFIDENCE <= confidence <= MAX_CONFIDENCE:",
            "    if False:",
        ),
        Mutation(
            "a bool passes as confidence",
            "    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):",
            "    if not isinstance(confidence, (int, float)):",
        ),
        Mutation(
            "missing fields are not checked",
            '    missing = {"category", "confidence", "reasoning"} - set(payload)',
            "    missing = set()",
        ),
        Mutation(
            "empty reasoning is accepted",
            "    if not isinstance(reasoning, str) or not reasoning.strip():",
            "    if not isinstance(reasoning, str):",
        ),
        Mutation(
            "evidence shape is not checked",
            "    if not isinstance(evidence, list) or any(not isinstance(e, str) for e in evidence):",
            "    if False:",
        ),
        Mutation(
            "a rejected answer is recorded anyway",
            "            outcome.rejected[item.key] = reason\n            store.abandon(run_id, store_mod.TRIAGE_CLUSTER, item.key, reason)\n            continue",
            "            outcome.rejected[item.key] = reason\n            store.abandon(run_id, store_mod.TRIAGE_CLUSTER, item.key, reason)\n            store.record_triage(run_id, item.key, parse_verdict(answer_fallback()))\n            continue",
        ),
        Mutation(
            "a raising decider stops the batch",
            "        except Exception as exc:",
            "        except TriageSchemaError as exc:",
        ),
        Mutation(
            "the budget is ignored",
            "    for _ in range(max(0, budget)):",
            "    while True:",
        ),
        Mutation(
            "the signature key ignores the frame",
            "        [signature.exception_type, signature.frame, signature.message]",
            "        [signature.exception_type, signature.message]",
        ),
        Mutation(
            "clusters are re-offered after being decided",
            "        self.retire(run_id, TRIAGE_CLUSTER, signature)",
            "        pass",
            path="discovery/store.py",
        ),
        Mutation(
            "the category filter is ignored",
            '        if category:\n            sql += " AND category = ?"\n            args.append(category)',
            "        if False:\n            pass",
            path="discovery/store.py",
        ),
    ],
)
