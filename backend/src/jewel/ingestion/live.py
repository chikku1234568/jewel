"""Build one parsed document with the local model and the local embedder."""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime

from jewel.ingestion.chunking import chunk_text
from jewel.ingestion.extraction_cache import ExtractionCache, extraction_key
from jewel.ingestion.pipeline import ParsedDocument, build_document
from jewel.kg.extraction import ExtractionError, merge_extractions, parse_extraction
from jewel.llm.base import ChatModel, EmbeddingModel
from jewel.llm.ollama import OllamaChat, extract_document

# A 7B model will not emit valid JSON for a whole paper. A few pages at a time will.
_EXTRACT_CHUNK = 3500
_EXTRACT_OVERLAP = 200
# Passages of one file sent to an API host at the same time. Bounded on purpose: wider
# mostly buys HTTP 429s, which the client then waits out (llm/openai_chat.py). Ollama
# runs one passage at a time on this machine. _BUILD_LOCK still builds one file at a time.
_API_WORKERS = 8


class BuildCancelled(Exception):
    """The user stopped this build. Passages already in flight may still finish."""


def build_parsed_text(
    *,
    document_id: str,
    user_id: str,
    filename: str,
    text: str,
    document_date: date | datetime | None,
    chat: ChatModel,
    embedder: EmbeddingModel,
    store,
    cache: ExtractionCache | None = None,
    on_progress=None,
    cancel: threading.Event | None = None,
) -> None:
    """Extract this text only, then write its nodes and edges."""
    model = getattr(chat, "model", "unknown")
    chunks = list(chunk_text(text, size=_EXTRACT_CHUNK, overlap=_EXTRACT_OVERLAP))
    total = len(chunks)
    if on_progress is not None:
        on_progress(0, total)
    parts = _extract_chunks(chat, model, chunks, cache, on_progress, cancel)
    extraction = merge_extractions(parts)
    if not extraction.triples:
        raise ExtractionError("no triples could be read from this document")
    build_document(
        ParsedDocument(
            id=document_id,
            user_id=user_id,
            filename=filename,
            text=text,
            document_date=_as_datetime(document_date),
        ),
        extraction,
        store,
        embedder,
    )


def _extract_chunks(chat, model, chunks, cache, on_progress, cancel) -> list:
    """Run passage calls together. Local Ollama stays one at a time."""
    if cancel is not None and cancel.is_set():
        raise BuildCancelled()
    workers = 1 if isinstance(chat, OllamaChat) else _API_WORKERS
    parts = []
    done = 0
    last_error: Exception | None = None

    def run_one(chunk):
        if cancel is not None and cancel.is_set():
            raise BuildCancelled()
        raw = _extract_passage(chat, model, chunk.text, cache)
        return parse_extraction(raw, chunk.text)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_one, chunk) for chunk in chunks]
        try:
            for future in as_completed(futures):
                if cancel is not None and cancel.is_set():
                    raise BuildCancelled()
                try:
                    parts.append(future.result())
                except BuildCancelled:
                    raise
                except Exception as exc:
                    if cancel is not None and cancel.is_set():
                        raise BuildCancelled() from exc
                    last_error = exc
                done += 1
                if on_progress is not None:
                    on_progress(done, len(chunks))
        except BuildCancelled:
            for future in futures:
                future.cancel()
            raise
    if not parts and last_error is not None:
        raise last_error
    return parts


def _extract_passage(chat: ChatModel, model: str, text: str, cache: ExtractionCache | None) -> str:
    key = extraction_key(model, text)
    if cache is not None:
        cached = cache.get(key)
        if cached is not None:
            return cached
    raw = extract_document(chat, text)
    if cache is not None:
        cache.put(key, model, raw)
    return raw


def _as_datetime(value: date | datetime | None) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return datetime(value.year, value.month, value.day)
