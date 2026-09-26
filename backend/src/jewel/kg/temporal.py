"""Temporal semantics (stub).

"Valid now" means the relationship has started and has not been closed:

    valid_at <= t  AND  (invalid_at IS NULL OR invalid_at > t)

Planned Cypher fragment (single source of truth, reused by the graph answer, the
graph view, and retrieval):

    MATCH (a)-[r]->(b)
    WHERE r.valid_at <= $t AND (r.invalid_at IS NULL OR r.invalid_at > $t)

TODO(step-N): expose the predicate as a Cypher snippet and a Python function so both
the database path and any in-Python PPR path agree on what is active at ``t``.
"""
