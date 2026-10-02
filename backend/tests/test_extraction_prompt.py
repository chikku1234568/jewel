"""The extraction prompt and its output budget. No model is called."""

import io
import json
import urllib.request

import pytest

from jewel.ingestion.live import build_parsed_text
from jewel.kg.extraction import parse_extraction
from jewel.kg.memory_store import MemoryGraphStore
from jewel.llm.hashing import HashingEmbedder
from jewel.llm.ollama import _EXTRACT_SYSTEM, EXTRACT_OPTIONS, extract_document
from jewel.llm.openai_chat import OpenAICompatibleChat, _body

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
            return _RAW

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
    [system] = systems
    assert "verbatim" in system
    assert "at most 8" not in system
    assert "at most 20 triples" in system
    assert "pronoun" in system.lower()
    assert '"entities"' in system and '"triples"' in system


def test_the_worked_example_cannot_leak_into_a_users_graph() -> None:
    """The example's quotes are not in the user's passage, so the quote gate drops them."""
    passage = _EXTRACT_SYSTEM.split('Example passage: "', 1)[1].split('" ', 1)[0]
    example = _EXTRACT_SYSTEM.split("Example output: ", 1)[1].rsplit("}. ", 1)[0] + "}"
    # The example is itself valid output for its own passage...
    assert len(parse_extraction(example, passage).triples) == 2
    # ...and yields nothing against anyone else's text.
    assert parse_extraction(example, PASSAGE).triples == []


def test_ollama_extraction_budget_is_4096_tokens() -> None:
    assert EXTRACT_OPTIONS["num_predict"] == 4096


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


def test_api_extraction_asks_for_4096_tokens_and_answers_keep_1024(sent: list[dict]) -> None:
    chat = OpenAICompatibleChat("kimi-k2.6", "http://host.invalid/v1", "test-key")
    extract_document(chat, PASSAGE)
    chat.complete("answer the question", "question")
    extraction, answer = sent
    assert extraction["max_tokens"] == 4096
    assert answer["max_tokens"] == 1024
    for body in sent:
        assert body["thinking"] == {"type": "disabled"}
        assert "temperature" not in body


def test_kimi_k3_keeps_low_reasoning_and_no_temperature() -> None:
    payload = _body("kimi-k3", "system", "passage", 4096)
    assert payload["reasoning_effort"] == "low"
    assert payload["max_tokens"] == 4096
    assert "thinking" not in payload
    assert "temperature" not in payload
