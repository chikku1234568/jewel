"""Graph retriever: HippoRAG-2-inspired, time-aware Personalized PageRank.

Runs on the signed-in user's subgraph only; PageRank runs in Python (``networkx``) over
the subgraph pulled for the query. Neo4j Graph Data Science is not used.

1. Keep facts valid at the question time (default now; undated ones remain).
2. Rank facts by similarity of ``subject predicate object`` to the question; take a top-k.
3. Recognition memory, when a chat model is passed: drop facts that do not answer. Ask does
   not pass one.
4. Seed PageRank on those fact nodes. Weight moves through the shared names to other facts.
5. Return the seed facts plus up to 8 more facts the walk scored, and the files that own them.

The ``user_id`` constraint is applied before similarity search and before the subgraph
is pulled into Python.
"""
