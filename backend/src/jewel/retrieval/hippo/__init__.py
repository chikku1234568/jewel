"""Graph retriever: HippoRAG-2-inspired, time-aware Personalized PageRank.

Runs on the signed-in user's subgraph only; PageRank runs in Python (``networkx``) over
the subgraph pulled for the query. Neo4j Graph Data Science is not used.

1. Link the question to the user's entities (embedding search on ``:Entity``).
2. Keep relationships valid at the question time (default now; undated ones remain).
3. Rank candidate triples by similarity to the question; take a top-k.
4. Recognition memory: one model call (user's key) drops irrelevant triples.
5. Seed PageRank with the entities on the kept triples plus ``Document`` nodes weighted by
   similarity to the question, down-weighted relative to entities.
6. Return ranked entities, ``RELATED_TO`` relationships, and cited document passages.

The ``user_id`` constraint is applied before similarity search and before the subgraph
is pulled into Python.
"""
