"""Build one parsed document into the user's graph.

The text is already extracted (status ``parsed``). This function does not read any
other document. A later upload calls it again for the new file only.
"""

from dataclasses import dataclass
from datetime import datetime

from jewel.kg.extraction import Extraction
from jewel.kg.memory_store import MemoryGraphStore
from jewel.llm.base import EmbeddingModel


@dataclass(frozen=True)
class ParsedDocument:
    id: str
    user_id: str
    filename: str
    text: str
    document_date: datetime | None = None


def build_document(
    document: ParsedDocument,
    extraction: Extraction,
    store: MemoryGraphStore,
    embedder: EmbeddingModel,
) -> None:
    """Embed this document's text, entities, and facts, then write them."""
    names = [entity.name for entity in extraction.entities]
    facts = [
        f"{triple.subject} {triple.predicate} {triple.object}" for triple in extraction.triples
    ]
    vectors = embedder.embed([document.text, *names, *facts])
    entity_embeddings = dict(zip(names, vectors[1 : 1 + len(names)], strict=True))
    triple_embeddings = vectors[1 + len(names) :]
    store.write_document(
        user_id=document.user_id,
        document_id=document.id,
        filename=document.filename,
        text=document.text,
        embedding=vectors[0],
        extraction=extraction,
        entity_embeddings=entity_embeddings,
        triple_embeddings=triple_embeddings,
        document_date=document.document_date,
    )
