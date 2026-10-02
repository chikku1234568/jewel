"""read_document returns the source chunks of a searched document. No network, no database."""

from datetime import datetime

import pytest

from jewel.agents.graph import run_agent
from jewel.agents.state import KeptTriple
from jewel.agents.tools import MAX_CHUNKS_PER_READ, ToolError, read_document
from jewel.ingestion.chunking import build_chunks
from jewel.ingestion.live import build_parsed_text
from jewel.kg.memory_store import MemoryGraphStore
from jewel.llm.hashing import HashingEmbedder
from tests.fake_chat import AIMessage, ScriptedChat, Turn, call
from tests.test_chunk_ordinals import ShuffledApiChat

USER = "user-a"
OTHER = "user-b"
APRIL = datetime(2026, 4, 1)


def _inventory(i: int) -> str:
    return f"Item {i} is stored in bay {i % 97}."


TEXT = " ".join(_inventory(i) for i in range(1400))  # about 12 chunks
CHUNKS = [chunk.text for chunk in build_chunks(TEXT)]


def _middle_sentences(ordinal: int, count: int) -> list[str]:
    """Whole sentences from the middle of a chunk, so no other (overlapping) chunk has them."""
    sentences = CHUNKS[ordinal].split(". ")[10 : 10 + count]
    assert all(sum(f"{s}." in chunk for chunk in CHUNKS) == 1 for s in sentences)
    return [f"{sentence}." for sentence in sentences]


def _store_with(document_id: str, user: str = USER, store: MemoryGraphStore | None = None):
    """Build TEXT into a graph; return the store and the stored chunks by ordinal."""
    store = store or MemoryGraphStore()
    saved: list[list[str]] = []
    build_parsed_text(
        document_id=document_id,
        user_id=user,
        filename=f"{document_id}.txt",
        text=TEXT,
        document_date=None,
        chat=ShuffledApiChat(),
        embedder=HashingEmbedder(),
        store=store,
        save_chunks=saved.append,
    )
    return store, dict(enumerate(saved[0]))


def test_a_chunk_row_that_lost_its_quote_is_not_opened() -> None:
    """A failed rebuild can leave new chunk rows under an older graph's ordinals."""
    store, stored = _store_with("inventory")
    quote = _middle_sentences(3, 1)[0]
    kept = [KeptTriple("inventory", 0, quote)]
    opened = read_document(
        store, USER, "inventory", {"inventory"}, kept, lambda _document_id: stored
    )
    assert opened
    assert quote in opened[0]
    assert stored[0] not in opened


def test_agent_reads_full_chunk_text_of_a_document_its_search_returned() -> None:
    store, stored = _store_with("inventory")

    def script(turn: Turn) -> AIMessage:
        if turn.tool_results == 0:
            return call("search_graph", query="Where is item 42?")
        if turn.tool_results == 1:
            return call("read_document", document_id="inventory")
        return AIMessage("done")

    model = ScriptedChat(script=script)
    result = run_agent(
        question="Where is item 42 stored?",
        user_id=USER,
        store=store,
        embedder=HashingEmbedder(),
        model=model,
        as_of=APRIL,
        stored_chunks=lambda document_id: stored if document_id == "inventory" else {},
    )
    assert result.kept_triples
    assert all(triple.chunk_ordinal is not None for triple in result.kept_triples)
    opened = model.turns[-1].observations[1]
    # The stored chunk rows are what the model sees, whole: no 240-character slice.
    chosen = [stored[t.chunk_ordinal] for t in result.kept_triples]
    assert any(len(chunk) > 240 and chunk in opened for chunk in chosen)
    assert 1 <= opened.count("passage ") <= MAX_CHUNKS_PER_READ
    assert result.tool_trace[1].summary.startswith("opened ")


def test_agent_cannot_open_a_document_its_search_did_not_return() -> None:
    store, stored = _store_with("inventory")
    _store_with("theirs", user=OTHER, store=store)

    def script(turn: Turn) -> AIMessage:
        if turn.tool_results == 0:
            return call("read_document", document_id="inventory")  # before any search
        if turn.tool_results == 1:
            return call("search_graph", query="Where is item 42?")
        if turn.tool_results == 2:
            return call("read_document", document_id="theirs")
        return AIMessage("done")

    model = ScriptedChat(script=script)
    result = run_agent(
        question="Where is item 42 stored?",
        user_id=USER,
        store=store,
        embedder=HashingEmbedder(),
        model=model,
        as_of=APRIL,
        stored_chunks=lambda _id: stored,
    )
    refused = "that document was not returned by search"
    observations = model.turns[-1].observations
    assert observations[0] == refused
    assert observations[2] == refused
    assert result.returned_document_ids == ["inventory"]
    assert not any(chunk in "\n".join(observations) for chunk in stored.values())


def test_read_rejects_any_document_the_search_did_not_return() -> None:
    store, stored = _store_with("mine")
    _store_with("also-mine", store=store)
    _store_with("theirs", user=OTHER, store=store)
    kept = [KeptTriple("mine", 0, _inventory(1))]
    with pytest.raises(ToolError):
        read_document(store, USER, "also-mine", {"mine"}, kept, lambda _id: stored)
    with pytest.raises(ToolError):
        read_document(store, USER, "theirs", {"mine"}, kept, lambda _id: stored)
    # Even if a search had somehow listed it, another user's document is not in this graph.
    with pytest.raises(ToolError):
        read_document(store, USER, "theirs", {"theirs"}, kept, lambda _id: stored)
    assert read_document(store, USER, "mine", {"mine"}, kept, lambda _id: stored)


def test_chunks_with_the_most_kept_triples_come_first_and_at_most_three() -> None:
    store, stored = _store_with("inventory")
    kept = [
        *[KeptTriple("inventory", 5, quote) for quote in _middle_sentences(5, 3)],
        *[KeptTriple("inventory", 2, quote) for quote in _middle_sentences(2, 2)],
        KeptTriple("inventory", 7, _middle_sentences(7, 1)[0]),
        KeptTriple("inventory", 1, _middle_sentences(1, 1)[0]),
        *[KeptTriple("elsewhere", 9, f"q9-{n}") for n in range(5)],  # another document
    ]
    chunks = read_document(store, USER, "inventory", {"inventory"}, kept, lambda _id: stored)
    # 5 (three triples), 2 (two), then the tie at one triple goes to the earlier chunk.
    assert chunks == [stored[5], stored[2], stored[1]]


def test_older_graph_without_ordinals_rechunks_and_matches_quotes() -> None:
    store, _stored = _store_with("inventory")
    quotes = [*_middle_sentences(9, 3), *_middle_sentences(2, 2), *_middle_sentences(5, 1)]
    quotes += _middle_sentences(11, 1)  # a fourth matching chunk, past the cap of three
    kept = [KeptTriple("inventory", None, quote) for quote in quotes]
    chunks = read_document(store, USER, "inventory", {"inventory"}, kept, stored_chunks=None)
    # Most quotes first; the tie at one quote goes to the earlier chunk.
    assert chunks == [CHUNKS[9], CHUNKS[2], CHUNKS[5]]


def test_no_kept_quote_in_the_document_opens_nothing() -> None:
    store, stored = _store_with("inventory")
    kept = [KeptTriple("inventory", None, "a sentence that is not in the file")]
    assert read_document(store, USER, "inventory", {"inventory"}, kept, lambda _id: stored) == []
