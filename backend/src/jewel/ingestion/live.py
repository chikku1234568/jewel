"""Build one parsed document: the user's extraction API, then the chosen embedder."""

import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime

from jewel.ingestion.chunking import build_chunks
from jewel.ingestion.extraction_cache import ExtractionCache, extraction_key, verification_key
from jewel.ingestion.pipeline import ParsedDocument, build_document
from jewel.kg.extraction import (
    Extraction,
    ExtractionError,
    checked_triples,
    merge_extractions,
    parse_extraction,
    uncovered_sentences,
)
from jewel.llm.base import ChatModel, EmbeddingModel
from jewel.llm.extract import (
    extract_document,
    recovery_user_text,
    verification_user_text,
    verify_triples,
)

# Passages of one file sent to the user's extraction API at the same time. Bounded on
# purpose: wider mostly buys HTTP 429s, which the client then waits out
# (llm/openai_chat.py). _BUILD_LOCK still builds one file at a time.
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
    save_chunks: Callable[[list[str]], None] | None = None,
) -> int:
    """Extract this text only, write its nodes and edges, and return the triples written.

    ``save_chunks`` receives every chunk's text in ordinal order before the first model
    call, so the stored chunks always match the ordinals on the triples.
    """
    model = getattr(chat, "model", "unknown")
    chunks = build_chunks(text)
    if save_chunks is not None:
        save_chunks([chunk.text for chunk in chunks])
    total = len(chunks)
    if on_progress is not None:
        on_progress(0, total)
    parts = _extract_chunks(chat, model, chunks, cache, on_progress, cancel)
    extraction = merge_extractions(parts)
    if not extraction.triples:
        raise ExtractionError("no triples could be read from this document")
    if cancel is not None and cancel.is_set():
        raise BuildCancelled()
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
    return len(extraction.triples)


def _extract_chunks(chat, model, chunks, cache, on_progress, cancel) -> list[Extraction]:
    """Run up to eight passage calls at once.

    Futures finish in any order, so each one returns its chunk's ordinal together with
    the extraction, and every kept triple is stamped with that ordinal. The parts are
    returned in ordinal order so the merge keeps the earliest chunk's copy of a triple
    that two overlapping chunks both found.
    """
    if cancel is not None and cancel.is_set():
        raise BuildCancelled()
    workers = _API_WORKERS
    parts: list[tuple[int, Extraction]] = []
    done = 0
    last_error: Exception | None = None

    def run_one(ordinal: int, chunk) -> tuple[int, Extraction]:
        if cancel is not None and cancel.is_set():
            raise BuildCancelled()
        raw = _extract_passage(chat, model, chunk.text, cache)
        try:
            extraction = parse_extraction(raw, chunk.text)
            failed: ExtractionError | None = None
        except ExtractionError as exc:
            extraction = Extraction(entities=[], triples=[])
            failed = exc
        # One follow-up, inside this worker, for names and figures the first reply missed.
        # Quotes are checked against the whole chunk. Stop skips the second call.
        if cancel is None or not cancel.is_set():
            missing = uncovered_sentences(chunk.text, extraction)
            if missing:
                follow = _extract_passage(chat, model, recovery_user_text(missing), cache)
                try:
                    extra = parse_extraction(follow, chunk.text)
                except ExtractionError:
                    extra = None
                if extra is not None and (extra.triples or extra.entities):
                    extraction = merge_extractions([extraction, extra])
                    failed = None
        if failed is not None and not extraction.triples:
            raise failed
        # One attribution check for this passage. A triple stays only when the reply
        # clearly says the quote states that relation. Stop skips the call.
        if extraction.triples and (cancel is None or not cancel.is_set()):
            request = verification_user_text(extraction.triples)
            verdict = _verify_passage(chat, model, request, cache)
            extraction = checked_triples(extraction, verdict)
        return ordinal, _with_ordinal(extraction, ordinal)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_one, ordinal, chunk) for ordinal, chunk in enumerate(chunks)]
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
    parts.sort(key=lambda pair: pair[0])
    return [extraction for _ordinal, extraction in parts]


def _with_ordinal(extraction: Extraction, ordinal: int) -> Extraction:
    triples = [
        triple.model_copy(update={"chunk_ordinal": ordinal}) for triple in extraction.triples
    ]
    return Extraction(entities=extraction.entities, triples=triples)


def _verify_passage(chat: ChatModel, model: str, text: str, cache: ExtractionCache | None) -> str:
    key = verification_key(model, text)
    if cache is not None:
        cached = cache.get(key)
        if cached is not None:
            return cached
    raw = verify_triples(chat, text)
    if cache is not None:
        cache.put(key, model, raw)
    return raw


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
