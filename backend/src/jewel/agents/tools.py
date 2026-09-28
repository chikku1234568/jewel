"""The only two tools. User id is bound by the caller, never by the model."""

from datetime import datetime

from jewel.kg.memory_store import MemoryGraphStore
from jewel.llm.base import ChatModel, EmbeddingModel
from jewel.retrieval.hippo.pipeline import RetrievalResult, retrieve


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
    span: tuple[int, int] | None = None,
) -> str:
    """Return text only for a document this run's search returned and the user owns."""
    if document_id not in allowed_document_ids:
        raise ToolError("that document was not returned by search")
    text = store.document_text(user_id, document_id)
    if text is None:
        raise ToolError("that document is not in this user's graph")
    if span is None:
        return text
    start, end = span
    return text[start:end]
