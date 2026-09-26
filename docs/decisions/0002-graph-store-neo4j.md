# 0002. Graph store: Neo4j 5.x Community

- **Status:** Accepted (decided by Srikar, 2026-09-26)
- **Supersedes:** the initial Postgres + pgvector proposal (never merged)

## Context

The spec needs a temporal knowledge graph: nodes (Patient, MedicationOrder,
LabObservation, ClinicalProtocolRule), relationships with `valid_at` / `invalid_at`,
`collected_at` on labs, raw episode text kept for provenance, embeddings for entity
linking and passage retrieval, and graph algorithms (Personalized PageRank) at query time.

## Decision

Use **Neo4j 5.x Community Edition** (Docker image `neo4j:5.26-community`, the 5.x LTS line)
as the single store:

- Clinical kinds are native labels / relationship types.
- `valid_at` / `invalid_at` are `DATETIME` properties on every clinical relationship;
  `collected_at` on `:LabObservation`; `recorded_at`, `written_by`, `episode_id` on every
  write (bitemporal audit).
- "Valid now": `r.valid_at <= $t AND (r.invalid_at IS NULL OR r.invalid_at > $t)`.
- Raw episode text is stored on `:Episode` nodes; everything links back to its episode.
- Embeddings are `LIST<FLOAT>` properties indexed with Neo4j's native vector index
  (`CREATE VECTOR INDEX`, `db.index.vector.queryNodes`). Community Edition supports
  vector indexes over `LIST` properties; native `VECTOR` properties need Enterprise
  block format, which we do not need.
- Python access via the official `neo4j` driver behind `jewel.kg.neo4j_store`; agents
  never get a raw session (see ADR 0007).

## Consequences

- Cypher makes multi-hop and temporal queries readable, and the Neo4j Browser gives a free
  graph inspection UI during development.
- Licence: Neo4j Community Edition is GPLv3. Running it as a separate server we talk to
  over Bolt is the normal pattern; review obligations if we ever distribute a modified Neo4j.
- Community Edition lacks clustering, hot backups and role-based access control
  (Enterprise features). Acceptable for a single-patient showcase; per-agent permissions
  are enforced in application code.
- PPR location is an open sub-question (ADR 0004): Neo4j Graph Data Science plugin vs
  Python (networkx/igraph) over the time-filtered subgraph.

## Alternatives considered

- **PostgreSQL + pgvector** (bitemporal tables, PPR in Python): very mature, permissive
  licence; graph queries are less natural. Not chosen.
- **Apache AGE** (Apache-2.0, openCypher on Postgres): smaller ecosystem.
- Not considered further: Kuzu (repository archived by its owner on 2025-10-10),
  Memgraph Community (BSL 1.1, not OSI open source), FalkorDB (SSPLv1, not OSI open source).

## Open questions for review

1. OK to pin `neo4j:5.26-community` (5.x LTS), or move to the newer calendar-versioned
   2025.x/2026.x releases?
2. Relationship endpoints in the schema diagram (e.g. `(Patient)-[:PRESCRIBED_DOSE]->(MedicationOrder)`)
   are proposals; confirm or adjust.
3. Hosting for Neo4j in the private showcase (self-hosted container vs Neo4j AuraDB Free);
   see ADR 0006.
