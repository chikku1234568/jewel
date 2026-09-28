"""Extraction cache keys and hits. No database and no model call on a hit."""

import threading
import time

from jewel.ingestion.extraction_cache import MemoryExtractionCache, extraction_key
from jewel.ingestion.live import BuildCancelled, build_parsed_text
from jewel.kg.memory_store import MemoryGraphStore
from jewel.llm.hashing import HashingEmbedder
from jewel.llm.openai_chat import _body

PASSAGE = "The alarm code is 4412."
_RAW = (
    '{"entities":[{"name":"alarm code","type":"concept"}],'
    '"triples":[{"subject":"alarm code","predicate":"is","object":"4412",'
    '"quote":"The alarm code is 4412."}]}'
)


def test_kimi_k2_6_extraction_does_not_use_thinking_mode() -> None:
    payload = _body("kimi-k2.6", "system", "passage")
    assert payload["thinking"] == {"type": "disabled"}
    assert payload["max_tokens"] == 1024


def test_key_changes_when_model_or_text_changes() -> None:
    base = extraction_key("qwen", PASSAGE)
    assert extraction_key("qwen", PASSAGE) == base
    assert extraction_key("other", PASSAGE) != base
    assert extraction_key("qwen", PASSAGE + " ") != base


def test_length_prefixes_stop_field_boundaries_from_colliding() -> None:
    """model 'ab' + text 'c' must not match model 'a' + text 'bc'."""
    assert extraction_key("ab", "c") != extraction_key("a", "bc")


def test_second_build_of_the_same_passage_does_not_call_the_model() -> None:
    calls = {"n": 0}

    class Chat:
        model = "fake"

        def complete(self, system: str, user: str) -> str:
            calls["n"] += 1
            return _RAW

    cache = MemoryExtractionCache()
    for _ in range(2):
        build_parsed_text(
            document_id="doc",
            user_id="user",
            filename="note.txt",
            text=PASSAGE,
            document_date=None,
            chat=Chat(),
            embedder=HashingEmbedder(),
            store=MemoryGraphStore(),
            cache=cache,
        )
    assert calls["n"] == 1
    assert len(cache.rows) == 1


def test_api_extraction_runs_passages_together() -> None:
    state = {"inside": 0, "max_inside": 0}
    lock = threading.Lock()

    class Chat:
        model = "kimi-k2.6"

        def complete(self, system: str, user: str) -> str:
            with lock:
                state["inside"] += 1
                state["max_inside"] = max(state["max_inside"], state["inside"])
            time.sleep(0.05)
            with lock:
                state["inside"] -= 1
            return _RAW

    text = (PASSAGE + " ") * 400
    build_parsed_text(
        document_id="doc",
        user_id="user",
        filename="paper.txt",
        text=text,
        document_date=None,
        chat=Chat(),
        embedder=HashingEmbedder(),
        store=MemoryGraphStore(),
    )
    assert state["max_inside"] > 1


def test_stop_cancels_the_remaining_passages() -> None:
    cancel = threading.Event()

    class Chat:
        model = "kimi-k2.6"

        def complete(self, system: str, user: str) -> str:
            cancel.set()
            return _RAW

    text = (PASSAGE + " ") * 400
    try:
        build_parsed_text(
            document_id="doc",
            user_id="user",
            filename="paper.txt",
            text=text,
            document_date=None,
            chat=Chat(),
            embedder=HashingEmbedder(),
            store=MemoryGraphStore(),
            cancel=cancel,
        )
    except BuildCancelled:
        return
    raise AssertionError("build should have stopped")
