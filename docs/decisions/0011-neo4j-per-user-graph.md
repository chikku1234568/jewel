# 0011. Graph store: Neo4j 5.x Community, one per-user Document/Entity graph

- **Status:** Accepted (settled by `docs/problem-statement.md`, 2026-09-28)
- **Supersedes:** [0002](0002-graph-store-neo4j.md)

## Decision

- One Neo4j 5.x Community database (`neo4j:5.26-community`), official `neo4j` Python
  driver (declared, not imported yet).
- Labels: `Document` (passage node: raw text, filename, times, status, embedding) and
  `Entity` (`name`, `type`, `embedding`).
- Relationships: `MENTIONS` (Entity -> Document: `quote`, offsets, `valid_at`) and
  `RELATED_TO` (Entity -> Entity: `predicate` as a property, `quote`, offsets,
  `document_id`, `valid_at`, `invalid_at`).
- **Every node and relationship carries `user_id`; every read and write is constrained to
  the session user.** A missing predicate is a defect.
- Validity at `t`: `(r.valid_at IS NULL OR r.valid_at <= $t) AND (r.invalid_at IS NULL OR r.invalid_at > $t)`.
  Undated relationships stay valid; nothing closes edges automatically.
- Embeddings are `LIST<FLOAT>` properties with a Neo4j vector index (Community supports
  this); the Enterprise `VECTOR` property type is not required.
- Entity identity within one user: case-folded exact name match; never across users.

## Consequences

- Delete document removes its `MENTIONS`, its `RELATED_TO` rows, then orphaned entities
  for that user.
- Neo4j Community Edition is GPLv3 and runs as a separate server reached over Bolt.
