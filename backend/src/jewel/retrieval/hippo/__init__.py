"""HippoRAG-2-inspired, time-aware retrieval (no GNN, no training; query-time only).

Status: Zeus's suggestion, pending user input (ADR 0004, Proposed). The user will bring
their own ideas on dynamic retrievers; keep this package swappable behind
``retrieval.hippo.pipeline.retrieve``.

Pipeline (see docs/architecture.md section 7):
query -> entity linking -> recognition-memory triple filter -> seed weights ->
Personalized PageRank over the subgraph valid at ``t_query`` -> ranked facts with
episode provenance -> answer.
"""
