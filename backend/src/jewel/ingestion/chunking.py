"""Split extracted text into overlapping chunks.

Build chunks (``build_chunks``) are the passages sent to the extraction model. They are
stored in Postgres ``document_chunks`` and ``read_document`` returns them. Chunks are not
graph nodes and are not embedded.
"""

import re
from dataclasses import dataclass

# Short passages, so one reply can list every fact instead of a handful of central ones.
# A blank line ends a passage when one falls in the window; otherwise a sentence does.
BUILD_CHUNK_SIZE = 1100
BUILD_CHUNK_OVERLAP = 150

_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")
_SENTENCE_BREAK = re.compile(r"[.!?][\"')\]]*\s+")


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
    """The build's passages, in ordinal order. Deterministic: same text, same chunks.

    Each passage stays near ``BUILD_CHUNK_SIZE``. The cut prefers a paragraph break in
    the second half of the window, then a sentence break, and only then a hard cut.
    The next passage repeats the tail so a fact on the boundary is seen twice.
    """
    if not text:
        return []
    if len(text) <= BUILD_CHUNK_SIZE:
        return [TextChunk(text, 0, len(text))]
    chunks: list[TextChunk] = []
    start = 0
    while start < len(text):
        hard = min(start + BUILD_CHUNK_SIZE, len(text))
        end = hard if hard == len(text) else _preferred_end(text, start, hard)
        if end <= start:
            end = hard
        chunks.append(TextChunk(text[start:end], start, end))
        if end >= len(text):
            break
        nxt = end - BUILD_CHUNK_OVERLAP
        if nxt <= start:
            nxt = end
        else:
            snapped = _snap_start(text, nxt, end)
            if start < snapped < end:
                nxt = snapped
        start = nxt
    return chunks


def _preferred_end(text: str, start: int, hard: int) -> int:
    """Latest paragraph or sentence break in the window, preferring the second half."""
    midpoint = start + (hard - start) // 2
    paragraph = _last_match_end(_PARAGRAPH_BREAK, text, midpoint, hard)
    if paragraph is not None:
        return paragraph
    sentence = _last_match_end(_SENTENCE_BREAK, text, midpoint, hard)
    if sentence is not None:
        return sentence
    sentence = _last_match_end(_SENTENCE_BREAK, text, start, hard)
    if sentence is not None and sentence > start:
        return sentence
    return hard


def _last_match_end(pattern: re.Pattern[str], text: str, lo: int, hi: int) -> int | None:
    last = None
    for match in pattern.finditer(text, lo, hi):
        last = match.end()
    return last


def _snap_start(text: str, nxt: int, end: int) -> int:
    """Move the next start onto a sentence boundary inside the overlap, when one exists."""
    match = _SENTENCE_BREAK.search(text, nxt, end)
    if match is not None:
        return match.end()
    return nxt
