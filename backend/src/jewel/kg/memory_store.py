"""In-memory graph with the same write rules Neo4j must follow.

A second document reuses an entity when the case-folded name matches inside that user.
It does not rewrite triples that belong to an earlier document. Rebuilding one document
replaces only that document's mentions and triples.
"""

from uuid import uuid4

from jewel.kg.extraction import Extraction
from jewel.kg.records import (
    GraphDocument,
    GraphEntity,
    GraphMention,
    GraphTriple,
    UserSubgraph,
    name_key,
)


class MemoryGraphStore:
    """Process-local graph. Tests and the retriever use this; Neo4j mirrors it."""

    def __init__(self) -> None:
        self.documents: dict[tuple[str, str], GraphDocument] = {}
        self.entities: dict[tuple[str, str], GraphEntity] = {}
        self.mentions: list[GraphMention] = []
        self.triples: list[GraphTriple] = []

    def write_document(
        self,
        *,
        user_id: str,
        document_id: str,
        filename: str,
        text: str,
        embedding: list[float],
        extraction: Extraction,
        entity_embeddings: dict[str, list[float]],
        triple_embeddings: list[list[float]],
        document_date=None,
        embedding_model: str = "",
    ) -> None:
        """Write one document. Earlier documents for this user stay as they are."""
        self.documents[(user_id, document_id)] = GraphDocument(
            id=document_id,
            user_id=user_id,
            filename=filename,
            text=text,
            embedding=embedding,
            document_date=document_date,
            embedding_model=embedding_model,
        )
        self.mentions = [
            mention
            for mention in self.mentions
            if not (mention.user_id == user_id and mention.document_id == document_id)
        ]
        self.triples = [
            triple
            for triple in self.triples
            if not (triple.user_id == user_id and triple.document_id == document_id)
        ]
        entity_ids: dict[str, str] = {}
        for entity in extraction.entities:
            key = name_key(entity.name)
            existing = self.entities.get((user_id, key))
            if existing is None:
                existing = GraphEntity(
                    id=str(uuid4()),
                    user_id=user_id,
                    name=entity.name,
                    name_key=key,
                    type=entity.type.value,
                    embedding=entity_embeddings[entity.name],
                )
                self.entities[(user_id, key)] = existing
            else:
                existing.embedding = entity_embeddings.get(entity.name, existing.embedding)
            entity_ids[entity.name] = existing.id
            self.mentions.append(
                GraphMention(
                    id=str(uuid4()),
                    user_id=user_id,
                    entity_id=existing.id,
                    document_id=document_id,
                    quote=_quote_for(entity.name, text, extraction),
                    valid_at=document_date,
                )
            )
        for triple, embedding in zip(extraction.triples, triple_embeddings, strict=True):
            source = entity_ids.get(triple.subject) or self._require_entity(user_id, triple.subject)
            target = entity_ids.get(triple.object) or self._require_entity(user_id, triple.object)
            self.triples.append(
                GraphTriple(
                    id=str(uuid4()),
                    user_id=user_id,
                    source_id=source,
                    target_id=target,
                    predicate=triple.predicate,
                    quote=triple.quote,
                    document_id=document_id,
                    embedding=embedding,
                    valid_at=document_date,
                    chunk_ordinal=triple.chunk_ordinal,
                )
            )
        self._drop_unmentioned(user_id)

    def subgraph(self, user_id: str) -> UserSubgraph:
        """Return only this user's elements."""
        return UserSubgraph(
            documents=[doc for doc in self.documents.values() if doc.user_id == user_id],
            entities=[entity for entity in self.entities.values() if entity.user_id == user_id],
            mentions=[mention for mention in self.mentions if mention.user_id == user_id],
            triples=[triple for triple in self.triples if triple.user_id == user_id],
        )

    def document_text(self, user_id: str, document_id: str) -> str | None:
        document = self.documents.get((user_id, document_id))
        if document is None:
            return None
        return document.text

    def delete_document(self, user_id: str, document_id: str) -> None:
        self.documents.pop((user_id, document_id), None)
        self.mentions = [
            mention
            for mention in self.mentions
            if not (mention.user_id == user_id and mention.document_id == document_id)
        ]
        self.triples = [
            triple
            for triple in self.triples
            if not (triple.user_id == user_id and triple.document_id == document_id)
        ]
        self._drop_unmentioned(user_id)

    def _require_entity(self, user_id: str, name: str) -> str:
        existing = self.entities.get((user_id, name_key(name)))
        if existing is None:
            raise KeyError(name)
        return existing.id

    def _drop_unmentioned(self, user_id: str) -> None:
        mentioned = {mention.entity_id for mention in self.mentions if mention.user_id == user_id}
        self.entities = {
            key: entity
            for key, entity in self.entities.items()
            if entity.user_id != user_id or entity.id in mentioned
        }


def _quote_for(name: str, text: str, extraction: Extraction) -> str:
    for triple in extraction.triples:
        if name in (triple.subject, triple.object) and triple.quote in text:
            return triple.quote
    start = text.find(name)
    if start >= 0:
        return text[start : start + len(name)]
    return name
