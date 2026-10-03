"""The extraction prompt and its output budget. No model is called."""

import io
import json
import urllib.request

import pytest

from jewel.ingestion.live import build_parsed_text
from jewel.kg.extraction import (
    ExtractionError,
    checked_triples,
    parse_extraction,
    uncovered_sentences,
)
from jewel.kg.memory_store import MemoryGraphStore
from jewel.llm.extract import _EXTRACT_SYSTEM, extract_document
from jewel.llm.hashing import HashingEmbedder
from jewel.llm.openai_chat import OpenAICompatibleChat, _body
from tests.keep_verdict import keep_all_verdict

PASSAGE = "The alarm code is 4412."
_RAW = (
    '{"entities":[{"name":"alarm code","type":"concept"}],'
    '"triples":[{"subject":"alarm code","predicate":"is","object":"4412",'
    '"quote":"The alarm code is 4412."}]}'
)


def test_the_prompt_sent_to_the_model_asks_for_verbatim_quotes() -> None:
    systems: list[str] = []

    class Chat:
        model = "fake"

        def complete(self, system: str, user: str) -> str:
            systems.append(system)
            verdict = keep_all_verdict(user)
            return verdict if verdict is not None else _RAW

    build_parsed_text(
        document_id="doc",
        user_id="user",
        filename="note.txt",
        text=PASSAGE,
        document_date=None,
        chat=Chat(),
        embedder=HashingEmbedder(),
        store=MemoryGraphStore(),
    )
    extraction, check = systems
    assert "verbatim" in extraction
    assert "at most" not in extraction
    assert "no maximum" in extraction
    assert "every named person" in extraction
    assert "pronoun" in extraction.lower()
    assert '"entities"' in extraction and '"triples"' in extraction
    assert "more than one reading" in check
    assert "Outside knowledge" in check


def test_the_worked_example_cannot_leak_into_a_users_graph() -> None:
    """The example's quotes are not in the user's passage, so the quote gate drops them."""
    passage = _EXTRACT_SYSTEM.split('Example passage: "', 1)[1].split('" ', 1)[0]
    example = _EXTRACT_SYSTEM.split("Example output: ", 1)[1].rsplit("}. ", 1)[0] + "}"
    # The example is itself valid output for its own passage...
    assert len(parse_extraction(example, passage).triples) == 2
    # ...and yields nothing against anyone else's text.
    assert parse_extraction(example, PASSAGE).triples == []


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Capture request bodies instead of calling a host."""
    bodies: list[dict] = []

    def fake_urlopen(request: urllib.request.Request, timeout: float):
        bodies.append(json.loads(request.data))
        reply = {"choices": [{"message": {"content": _RAW}}]}
        return io.BytesIO(json.dumps(reply).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return bodies


def test_api_extraction_asks_for_8192_tokens_and_answers_keep_1024(sent: list[dict]) -> None:
    chat = OpenAICompatibleChat("kimi-k2.6", "http://host.invalid/v1", "test-key")
    extract_document(chat, PASSAGE)
    chat.complete("answer the question", "question")
    extraction, answer = sent
    assert extraction["max_tokens"] == 8192
    assert answer["max_tokens"] == 1024
    for body in sent:
        assert body["thinking"] == {"type": "disabled"}
        assert "temperature" not in body


_TWO_PEOPLE = "Alex Rivera and Jordan Blake signed on 1 January. The rent is 500 pounds a month."
_FIRST_PASS = (
    '{"entities":[{"name":"Alex Rivera","type":"person"}],'
    '"triples":[{"subject":"Alex Rivera","predicate":"signed on","object":"1 January",'
    '"quote":"Alex Rivera and Jordan Blake signed on 1 January."}]}'
)
_FOLLOW_UP = (
    '{"entities":[{"name":"Jordan Blake","type":"person"},{"name":"rent","type":"concept"}],'
    '"triples":['
    '{"subject":"Jordan Blake","predicate":"signed on","object":"1 January",'
    '"quote":"Alex Rivera and Jordan Blake signed on 1 January."},'
    '{"subject":"rent","predicate":"is","object":"500 pounds a month",'
    '"quote":"The rent is 500 pounds a month."},'
    '{"subject":"note","predicate":"says","object":"uncovered",'
    '"quote":"These lines were left uncovered."}]}'
)


def test_a_quoted_number_is_not_sent_back() -> None:
    assert uncovered_sentences(PASSAGE, parse_extraction(_RAW, PASSAGE)) == []


def test_a_missing_name_and_an_unquoted_amount_are_sent_back() -> None:
    missing = uncovered_sentences(_TWO_PEOPLE, parse_extraction(_FIRST_PASS, _TWO_PEOPLE))
    assert any("Jordan Blake" in sentence for sentence in missing)
    assert any("500" in sentence for sentence in missing)


def test_a_follow_up_keeps_the_missed_name_and_drops_a_preface_quote() -> None:
    calls: list[str] = []

    class Chat:
        model = "fake"

        def complete(self, system: str, user: str) -> str:
            verdict = keep_all_verdict(user)
            if verdict is not None:
                calls.append(user)
                return verdict
            calls.append(user)
            return _FIRST_PASS if len(calls) == 1 else _FOLLOW_UP

    store = MemoryGraphStore()
    build_parsed_text(
        document_id="doc",
        user_id="user",
        filename="note.txt",
        text=_TWO_PEOPLE,
        document_date=None,
        chat=Chat(),
        embedder=HashingEmbedder(),
        store=store,
    )
    assert len(calls) == 3
    assert calls[1].startswith("These lines were left uncovered.")
    assert calls[2].startswith("Check these triples.")
    assert "Jordan Blake" in calls[1] and "500" in calls[1]
    graph = store.subgraph("user")
    names = {entity.name for entity in graph.entities}
    by_id = {entity.id: entity.name for entity in graph.entities}
    objects = {by_id[triple.target_id] for triple in graph.triples}
    assert "Jordan Blake" in names
    assert "500 pounds a month" in objects
    assert all("left uncovered" not in triple.quote for triple in graph.triples)


def test_a_triple_the_checker_omits_is_dropped() -> None:
    extraction = parse_extraction(_RAW, PASSAGE)
    second = extraction.triples[0].model_copy(update={"object": "9988", "quote": PASSAGE})
    both = extraction.model_copy(update={"triples": [extraction.triples[0], second]})
    kept = checked_triples(both, '{"keep":[1]}')
    assert [triple.object for triple in kept.triples] == ["4412"]
    assert checked_triples(both, '{"keep":[]}').triples == []
    assert checked_triples(both, "nope").triples == []
    assert checked_triples(both, '{"triples":[]}').triples == []


def test_the_check_drops_a_relation_it_does_not_list() -> None:
    passage = "The alarm code is 4412. The door code is 9988."
    both = (
        '{"entities":[],"triples":['
        '{"subject":"alarm code","predicate":"is","object":"4412",'
        '"quote":"The alarm code is 4412."},'
        '{"subject":"door code","predicate":"is","object":"9988",'
        '"quote":"The door code is 9988."}]}'
    )

    class Chat:
        model = "fake"

        def complete(self, system: str, user: str) -> str:
            if user.startswith("Check these triples."):
                return '{"keep":[1]}'
            return both

    store = MemoryGraphStore()
    build_parsed_text(
        document_id="doc",
        user_id="user",
        filename="note.txt",
        text=passage,
        document_date=None,
        chat=Chat(),
        embedder=HashingEmbedder(),
        store=store,
    )
    graph = store.subgraph("user")
    by_id = {entity.id: entity.name for entity in graph.entities}
    assert {by_id[triple.target_id] for triple in graph.triples} == {"4412"}


def test_an_unreadable_attribution_check_keeps_nothing() -> None:
    class Chat:
        model = "fake"

        def complete(self, system: str, user: str) -> str:
            if user.startswith("Check these triples."):
                return "nope"
            return _RAW

    with pytest.raises(ExtractionError, match="no triples"):
        build_parsed_text(
            document_id="doc",
            user_id="user",
            filename="note.txt",
            text=PASSAGE,
            document_date=None,
            chat=Chat(),
            embedder=HashingEmbedder(),
            store=MemoryGraphStore(),
        )


def test_kimi_k3_keeps_low_reasoning_and_no_temperature() -> None:
    payload = _body("kimi-k3", "system", "passage", 4096)
    assert payload["reasoning_effort"] == "low"
    assert payload["max_tokens"] == 4096
    assert "thinking" not in payload
    assert "temperature" not in payload
