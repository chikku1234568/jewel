"""``answer`` node (stub).

Runs the question ("Is the current order for enoxaparin 100 mg twice daily valid for
immediate administration?") through (a) temporal graph retrieval over relationships
valid at ``now`` and (b) the naive RAG baseline over raw episode text, and returns both
answers with provenance for the side-by-side view. Read-only: no graph writes.
"""
