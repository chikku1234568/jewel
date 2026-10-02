"""Split extracted text into overlapping chunks.

Build chunks (``build_chunks``) are the passages sent to the extraction model. They are
stored in Postgres ``document_chunks`` and ``read_document`` returns them. Chunks are not
graph nodes and are not embedded.
"""

from dataclasses import dataclass

# A 7B model will not emit valid JSON for a whole paper. A few pages at a time will.
BUILD_CHUNK_SIZE = 3500
BUILD_CHUNK_OVERLAP = 200


@dataclass(frozen=True)
class TextChunk:
    text: str
    start: int
    end: int


def chunk_text(text: str, size: int = 800, overlap: int = 100) -> list[TextChunk]:
    """Return chunks with character offsets. A short text is one chunk."""
    if size <= overlap:
        raise ValueError("size must be greater than overlap")
    if not text:
        return []
    if len(text) <= size:
        return [TextChunk(text, 0, len(text))]
    chunks: list[TextChunk] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(TextChunk(text[start:end], start, end))
        if end == len(text):
            break
        start = end - overlap
    return chunks


def build_chunks(text: str) -> list[TextChunk]:
    """The build's passages, in ordinal order. Deterministic: same text, same chunks."""
    return chunk_text(text, size=BUILD_CHUNK_SIZE, overlap=BUILD_CHUNK_OVERLAP)
