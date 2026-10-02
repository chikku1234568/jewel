"""Neo4j graph store. Neo4j 5.x Community, official ``neo4j`` driver.

Every statement takes ``user_id`` as a parameter. The driver is not opened at import.
Write rules match ``MemoryGraphStore``: one document at a time, entities reused by
case-folded name inside that user, no cross-user merge.
"""

from datetime import datetime

from jewel.kg.memory_store import MemoryGraphStore, _quote_for
from jewel.kg.records import (
    GraphDocument,
    GraphEntity,
    GraphMention,
    GraphTriple,
    name_key,
)

_DELETE_DOCUMENT_EDGES = """
MATCH (e:Entity {user_id: $user_id})-[m:MENTIONS {user_id: $user_id, document_id: $document_id}]->
      (d:Document {user_id: $user_id, id: $document_id})
DELETE m
"""

_DELETE_DOCUMENT_TRIPLES = """
MATCH (a:Entity {user_id: $user_id})-[r:RELATED_TO {user_id: $user_id, document_id: $document_id}]->
      (b:Entity {user_id: $user_id})
DELETE r
"""

_UPSERT_DOCUMENT = """
MERGE (d:Document {user_id: $user_id, id: $document_id})
SET d.filename = $filename,
    d.raw_text = $text,
    d.embedding = $embedding,
    d.document_date = $document_date,
    d.embedding_model = $embedding_model
"""

_UPSERT_ENTITY = """
MERGE (e:Entity {user_id: $user_id, name_key: $name_key})
ON CREATE SET e.id = $id, e.name = $name, e.type = $type
SET e.embedding = $embedding
"""

_WRITE_MENTION = """
MATCH (e:Entity {user_id: $user_id, name_key: $name_key})
MATCH (d:Document {user_id: $user_id, id: $document_id})
CREATE (e)-[:MENTIONS {
    user_id: $user_id,
    id: $id,
    document_id: $document_id,
    quote: $quote,
    valid_at: $valid_at
}]->(d)
"""

_WRITE_TRIPLE = """
MATCH (a:Entity {user_id: $user_id, name_key: $source_key})
MATCH (b:Entity {user_id: $user_id, name_key: $target_key})
CREATE (a)-[:RELATED_TO {
    user_id: $user_id,
    id: $id,
    document_id: $document_id,
    predicate: $predicate,
    quote: $quote,
    embedding: $embedding,
    valid_at: $valid_at,
    chunk_ordinal: $chunk_ordinal
}]->(b)
"""

_DROP_UNMENTIONED = """
MATCH (e:Entity {user_id: $user_id})
WHERE NOT (e)-[:MENTIONS {user_id: $user_id}]->(:Document {user_id: $user_id})
DETACH DELETE e
"""

_DELETE_DOCUMENT_NODE = """
MATCH (d:Document {user_id: $user_id, id: $document_id})
DETACH DELETE d
"""

_READ_DOCUMENTS = """
MATCH (d:Document {user_id: $user_id})
RETURN d.id AS id, d.filename AS filename, d.raw_text AS text,
       d.embedding AS embedding, d.document_date AS document_date,
       d.embedding_model AS embedding_model
"""

_READ_ENTITIES = """
MATCH (e:Entity {user_id: $user_id})
RETURN e.id AS id, e.name AS name, e.name_key AS name_key, e.type AS type,
       e.embedding AS embedding
"""

_READ_MENTIONS = """
MATCH (e:Entity {user_id: $user_id})-[m:MENTIONS {user_id: $user_id}]->
      (d:Document {user_id: $user_id})
RETURN m.id AS id, e.id AS entity_id, d.id AS document_id, m.quote AS quote, m.valid_at AS valid_at
"""

_READ_TRIPLES = """
MATCH (a:Entity {user_id: $user_id})-[r:RELATED_TO {user_id: $user_id}]->
      (b:Entity {user_id: $user_id})
RETURN r.id AS id, a.id AS source_id, b.id AS target_id, r.predicate AS predicate,
       r.quote AS quote, r.document_id AS document_id, r.embedding AS embedding,
       r.valid_at AS valid_at, r.chunk_ordinal AS chunk_ordinal
"""


class Neo4jGraphStore:
    """Thin Cypher writer. Query text never interpolates a user id."""

    def __init__(self, driver) -> None:
        self._driver = driver

    def write_document(
        self,
        *,
        user_id: str,
        document_id: str,
        filename: str,
        text: str,
        embedding: list[float],
        extraction,
        entity_embeddings: dict[str, list[float]],
        triple_embeddings: list[list[float]],
        document_date=None,
        embedding_model: str = "",
    ) -> None:
        from uuid import uuid4

        date = document_date.isoformat() if document_date is not None else None
        with self._driver.session() as session:
            for statement in (_DELETE_DOCUMENT_EDGES, _DELETE_DOCUMENT_TRIPLES):
                session.run(statement, user_id=user_id, document_id=document_id)
            session.run(
                _UPSERT_DOCUMENT,
                user_id=user_id,
                document_id=document_id,
                filename=filename,
                text=text,
                embedding=embedding,
                document_date=date,
                embedding_model=embedding_model,
            )
            for entity in extraction.entities:
                session.run(
                    _UPSERT_ENTITY,
                    user_id=user_id,
                    name_key=name_key(entity.name),
                    id=str(uuid4()),
                    name=entity.name,
                    type=entity.type.value,
                    embedding=entity_embeddings[entity.name],
                )
                session.run(
                    _WRITE_MENTION,
                    user_id=user_id,
                    name_key=name_key(entity.name),
                    document_id=document_id,
                    id=str(uuid4()),
                    quote=_quote_for(entity.name, text, extraction),
                    valid_at=date,
                )
            for triple, triple_embedding in zip(extraction.triples, triple_embeddings, strict=True):
                session.run(
                    _WRITE_TRIPLE,
                    user_id=user_id,
                    source_key=name_key(triple.subject),
                    target_key=name_key(triple.object),
                    id=str(uuid4()),
                    document_id=document_id,
                    predicate=triple.predicate,
                    quote=triple.quote,
                    embedding=triple_embedding,
                    valid_at=date,
                    chunk_ordinal=triple.chunk_ordinal,  # null is not stored by Neo4j
                )
            session.run(_DROP_UNMENTIONED, user_id=user_id)

    def delete_document(self, user_id: str, document_id: str) -> None:
        """Remove one document's edges and any entity that no longer has a mention."""
        with self._driver.session() as session:
            session.run(_DELETE_DOCUMENT_TRIPLES, user_id=user_id, document_id=document_id)
            session.run(_DELETE_DOCUMENT_NODE, user_id=user_id, document_id=document_id)
            session.run(_DROP_UNMENTIONED, user_id=user_id)

    def load_user(self, user_id: str) -> MemoryGraphStore:
        """Read one user's graph into the in-memory store the retriever walks."""
        store = MemoryGraphStore()
        with self._driver.session() as session:
            for row in session.run(_READ_DOCUMENTS, user_id=user_id):
                store.documents[(user_id, row["id"])] = GraphDocument(
                    id=row["id"],
                    user_id=user_id,
                    filename=row["filename"] or "",
                    text=row["text"] or "",
                    embedding=_vector(row["embedding"]),
                    document_date=_parse_time(row["document_date"]),
                    embedding_model=row["embedding_model"] or "",
                )
            for row in session.run(_READ_ENTITIES, user_id=user_id):
                key = row["name_key"] or name_key(row["name"] or "")
                store.entities[(user_id, key)] = GraphEntity(
                    id=row["id"],
                    user_id=user_id,
                    name=row["name"] or "",
                    name_key=key,
                    type=row["type"] or "other",
                    embedding=_vector(row["embedding"]),
                )
            for row in session.run(_READ_MENTIONS, user_id=user_id):
                store.mentions.append(
                    GraphMention(
                        id=row["id"],
                        user_id=user_id,
                        entity_id=row["entity_id"],
                        document_id=row["document_id"],
                        quote=row["quote"] or "",
                        valid_at=_parse_time(row["valid_at"]),
                    )
                )
            for row in session.run(_READ_TRIPLES, user_id=user_id):
                store.triples.append(
                    GraphTriple(
                        id=row["id"],
                        user_id=user_id,
                        source_id=row["source_id"],
                        target_id=row["target_id"],
                        predicate=row["predicate"] or "",
                        quote=row["quote"] or "",
                        document_id=row["document_id"],
                        embedding=_vector(row["embedding"]),
                        valid_at=_parse_time(row["valid_at"]),
                        chunk_ordinal=_ordinal(row["chunk_ordinal"]),
                    )
                )
        return store


def _vector(value) -> list[float]:
    if not value:
        return []
    return [float(item) for item in value]


def _ordinal(value) -> int | None:
    """Edges written before chunks were stored have no ordinal property (null)."""
    return None if value is None else int(value)


def _parse_time(value) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None
