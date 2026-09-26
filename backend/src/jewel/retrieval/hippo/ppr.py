"""Personalized PageRank over the time-filtered subgraph (stub).

Open sub-question (ADR 0004), two implementation options:

A. Neo4j Graph Data Science: project only relationships valid at ``t_query`` (Cypher
   projection with the temporal predicate) plus ``:Episode`` nodes, then call
   ``gds.pageRank.stream`` with ``sourceNodes`` as ``[[node, bias], ...]`` for biased
   personalization. GDS Community Edition is free (GPLv3 sources, "OpenGDS"; the
   Neo4j-distributed jar also contains closed-source parts) and is capped at 4 cores.
B. Pull the time-filtered subgraph into Python and run PPR with networkx
   (``pagerank(personalization=...)``) or python-igraph. Fine for a tiny demo graph.

TODO(step-N): reset vector = entity seeds from recognition-filtered triples +
episode nodes weighted by query similarity (down-weighted, HippoRAG 2 style).
"""
