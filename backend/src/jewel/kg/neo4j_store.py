"""Neo4j graph store (stub). Neo4j 5.x Community, official ``neo4j`` driver.

Rules for every query (a missing ``user_id`` predicate is a defect, not a default):

* Every node and relationship is written with ``user_id``; every read matches on the
  ``user_id`` taken from the session.
* Entity identity within one user: case-fold ``name`` and reuse on exact match. Never
  merge across users.
* Embeddings are ``LIST<FLOAT>`` properties with a Neo4j vector index (dimension from the
  embedding model settings). The Enterprise ``VECTOR`` property type is not required.
* Delete document: remove its ``MENTIONS``, the ``RELATED_TO`` rows whose ``document_id``
  is that document, then entities with no remaining ``MENTIONS`` for that user.

The driver is declared in ``pyproject.toml`` but not imported yet.

TODO(later pass): ``Neo4jGraphStore`` with user-scoped ``write_document``,
``upsert_entity``, ``write_mention``, ``write_relationship``, ``subgraph``,
``delete_entity``, ``delete_relationship``, ``delete_document``, ``vector_search``.
"""
