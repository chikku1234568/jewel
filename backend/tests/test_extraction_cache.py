"""Extraction cache keys and hits. No database and no model call on a hit."""

import threading

from jewel.ingestion.extraction_cache import MemoryExtractionCache, extraction_key
from jewel.ingestion.live import BuildCancelled, build_parsed_text
from jewel.kg.memory_store import MemoryGraphStore
from jewel.llm.hashing import HashingEmbedder
from jewel.llm.ollama import OllamaChat
from jewel.llm.openai_chat import OpenAICompatibleChat, _body

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


def _max_in_flight(chat_base: type, needed: int, wait: float) -> int:
    """Build a 16-passage file and return how many chat calls were in flight at once.

    Each call waits (up to ``wait`` seconds) until ``needed`` calls are inside together, so
    the API answer does not depend on sleep timing: the pool lets them overlap or it does not.
    """
    state = {"inside": 0, "max_inside": 0}
    lock = threading.Lock()
    enough = threading.Event()

    class Chat(chat_base):
        model = "kimi-k2.6"

        def __init__(self) -> None:  # no host, no key
            pass

        def complete(self, system: str, user: str, **_kwargs) -> str:
            with lock:
                state["inside"] += 1
                state["max_inside"] = max(state["max_inside"], state["inside"])
                if state["inside"] >= needed:
                    enough.set()
            enough.wait(timeout=wait)
            with lock:
                state["inside"] -= 1
            return _RAW

    text = (PASSAGE + " ") * 2200  # about 16 passages of 3500 characters
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
    return state["max_inside"]


def test_eight_api_calls_are_in_flight_together() -> None:
    assert _max_in_flight(OpenAICompatibleChat, needed=8, wait=5) == 8


def test_ollama_runs_one_passage_at_a_time() -> None:
    # With one worker needed=2 is never met, so each call waits out a short timeout.
    assert _max_in_flight(OllamaChat, needed=2, wait=0.05) == 1


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
