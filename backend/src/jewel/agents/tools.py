"""The only two tools. User id is bound by the caller, never by the model."""

from collections import Counter
from collections.abc import Callable, Iterable
from datetime import datetime

from jewel.agents.state import KeptTriple
from jewel.ingestion.chunking import build_chunks
from jewel.kg.memory_store import MemoryGraphStore
from jewel.llm.base import ChatModel, EmbeddingModel
from jewel.retrieval.hippo.pipeline import RetrievalResult, retrieve

MAX_CHUNKS_PER_READ = 3

ChunkSource = Callable[[str], dict[int, str]]
"""Stored build chunks of one document (by ordinal) for the bound user."""


class ToolError(PermissionError):
    """The model asked for something this run is not allowed to open."""


def search_graph(
    store: MemoryGraphStore,
    embedder: EmbeddingModel,
    user_id: str,
    query: str,
    as_of: datetime,
    chat: ChatModel | None = None,
) -> RetrievalResult:
    """Run the retriever on this user's graph as it stands now."""
    return retrieve(store, embedder, user_id, query, as_of, chat)


def read_document(
    store: MemoryGraphStore,
    user_id: str,
    document_id: str,
    allowed_document_ids: set[str],
    kept_triples: Iterable[KeptTriple] = (),
    stored_chunks: ChunkSource | None = None,
) -> list[str]:
    """Return up to three source chunks of a document this run's search returned.

    The chunks chosen are the ones the search's kept triples came from, most triples
    first. A graph built before chunk ordinals were stored has none; then the document
    text is re-chunked exactly as the build chunked it, and the chunks that contain the
    kept quotes are returned, most quotes first. There is no similarity search here:
    only chunks the graph walk already pointed at are opened.
    """
    if document_id not in allowed_document_ids:
        raise ToolError("that document was not returned by search")
    text = store.document_text(user_id, document_id)
    if text is None:
        raise ToolError("that document is not in this user's graph")
    mine = [triple for triple in kept_triples if triple.document_id == document_id]

    by_ordinal = Counter(t.chunk_ordinal for t in mine if t.chunk_ordinal is not None)
    if by_ordinal:
        chunks = stored_chunks(document_id) if stored_chunks is not None else {}
        # Most triples first; ties go to the earlier chunk so the order is stable.
        ranked = sorted(by_ordinal, key=lambda ordinal: (-by_ordinal[ordinal], ordinal))
        found = []
        for ordinal in ranked:
            chunk = chunks.get(ordinal)
            if chunk is None:
                continue
            # A failed rebuild replaces chunk rows before the graph is rewritten. An
            # ordinal that no longer contains its quote belongs to that older graph,
            # so it is skipped and the quote match below runs instead.
            quotes = [triple.quote for triple in mine if triple.chunk_ordinal == ordinal]
            if quotes and not any(quote in chunk for quote in quotes):
                continue
            found.append(chunk)
        if found:
            return found[:MAX_CHUNKS_PER_READ]

    # No ordinals (an older graph), or their rows are missing: match quotes instead.
    quotes = {triple.quote for triple in mine}
    scored = [
        (sum(quote in chunk.text for quote in quotes), ordinal, chunk.text)
        for ordinal, chunk in enumerate(build_chunks(text))
    ]
    scored = [item for item in scored if item[0] > 0]
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [chunk for _count, _ordinal, chunk in scored[:MAX_CHUNKS_PER_READ]]
