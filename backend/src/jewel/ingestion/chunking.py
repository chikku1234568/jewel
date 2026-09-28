"""Split extracted text into overlapping chunks for the text-search comparison.

Chunks are not graph nodes.
"""

from dataclasses import dataclass


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
