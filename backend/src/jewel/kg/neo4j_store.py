"""Neo4j graph store. Neo4j 5.x Community, official ``neo4j`` driver.

Every statement takes ``user_id`` as a parameter. The driver is not opened at import.
Write rules match ``MemoryGraphStore``: one document at a time, entities reused by
case-folded name inside that user, no cross-user merge.
"""

from jewel.kg.records import name_key

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
    d.document_date = $document_date
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
    valid_at: $valid_at
}]->(b)
"""

_DROP_UNMENTIONED = """
MATCH (e:Entity {user_id: $user_id})
WHERE NOT (e)-[:MENTIONS {user_id: $user_id}]->(:Document {user_id: $user_id})
DETACH DELETE e
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
                    quote=entity.name,
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
                )
            session.run(_DROP_UNMENTIONED, user_id=user_id)
