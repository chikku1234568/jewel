"""Neo4j graph store (stub). Storage decision: Neo4j 5.x Community (ADR 0002, Accepted).

Modelling (see docs/architecture.md section 5):

* Clinical nodes (``:Patient``, ``:MedicationOrder``, ``:LabObservation``,
  ``:ClinicalProtocolRule``) and relationships (``:PRESCRIBED_DOSE``, ...) are native
  Neo4j labels / relationship types.
* Temporal properties: ``valid_at`` / ``invalid_at`` on relationships (Neo4j
  ``DATETIME``), ``collected_at`` on ``:LabObservation``.
* Raw episode text lives on ``:Episode`` nodes (provenance); every written node or
  relationship records the ``episode_id`` it came from.
* Embeddings are ``LIST<FLOAT>`` properties on ``:Entity`` / ``:Episode`` nodes indexed
  with Neo4j's native vector index (Community indexes LIST properties; native VECTOR
  properties need Enterprise block format).

TODO(step-N): ``Neo4jGraphStore`` (official ``neo4j`` Python driver) with
``add_node``, ``open_edge``, ``close_edge`` (set ``invalid_at``), ``subgraph_valid_at(t)``,
and ``vector_search(index, embedding, k)``. All writes go through
``jewel.kg.permissions.GraphWriter`` first; agents never get a raw driver/session.
"""
