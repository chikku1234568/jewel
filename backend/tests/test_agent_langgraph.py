"""The real chat adapter under ``create_agent``, against a scripted host. No network."""

import io
import json
import urllib.request
from datetime import datetime

import pytest

from jewel.agents.chat_model import ToolCallingChat, assistant_message
from jewel.agents.graph import (
    _BUDGET_SPENT,
    MAX_TOOL_CALLS,
    _over_budget,
    run_agent,
    search_graph_tool,
)
from jewel.agents.state import AgentResult, ToolTraceEntry
from jewel.ingestion.live import build_parsed_text
from jewel.kg.memory_store import MemoryGraphStore
from jewel.llm.hashing import HashingEmbedder
from jewel.llm.openai_chat import OpenAICompatibleChat
from tests.test_chunk_ordinals import ShuffledApiChat

USER = "user-a"
KEY = "sk-test-not-a-real-key"
TEXT = " ".join(f"Item {i} is stored in bay {i % 97}." for i in range(400))


def _tool_call(n: int, name: str, arguments: dict) -> dict:
    return {
        "id": f"call-{n}",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


class Host:
    """Answers /chat/completions from a script and keeps every request body."""

    def __init__(self, replies: list[dict]) -> None:
        self.replies = replies
        self.bodies: list[dict] = []
        self.headers: list[dict] = []

    def urlopen(self, request, timeout):
        self.bodies.append(json.loads(request.data))
        self.headers.append(dict(request.headers))
        message = self.replies.pop(0)
        return io.BytesIO(json.dumps({"choices": [{"message": message}]}).encode())


@pytest.fixture
def store() -> MemoryGraphStore:
    graph = MemoryGraphStore()
    build_parsed_text(
        document_id="inventory",
        user_id=USER,
        filename="inventory.txt",
        text=TEXT,
        document_date=None,
        chat=ShuffledApiChat(),
        embedder=HashingEmbedder(),
        store=graph,
    )
    return graph


def _run(monkeypatch: pytest.MonkeyPatch, store: MemoryGraphStore, replies: list[dict]):
    host = Host(replies)
    monkeypatch.setattr(urllib.request, "urlopen", host.urlopen)
    client = OpenAICompatibleChat("kimi-k2.6", "https://host.invalid/v1", KEY)
    result = run_agent(
        question="Where is item 42 stored?",
        user_id=USER,
        store=store,
        embedder=HashingEmbedder(),
        model=ToolCallingChat(client=client),
        as_of=datetime(2026, 4, 1),
    )
    return host, result


def test_kimi_tool_calls_round_trip_through_create_agent(
    monkeypatch: pytest.MonkeyPatch, store: MemoryGraphStore
) -> None:
    host, result = _run(
        monkeypatch,
        store,
        [
            {"content": "", "tool_calls": [_tool_call(1, "search_graph", {"query": "item 42"})]},
            {
                "content": None,
                "tool_calls": [_tool_call(2, "read_document", {"document_id": "inventory"})],
            },
            {"content": "Item 42 is stored in bay 42."},
        ],
    )
    assert result.answer == "Item 42 is stored in bay 42."
    assert [entry.name for entry in result.tool_trace] == ["search_graph", "read_document"]
    first, second, last = host.bodies
    for body in host.bodies:
        assert body["model"] == "kimi-k2.6"
        assert body["thinking"] == {"type": "disabled"}
        assert body["max_tokens"] == 1024  # the answer call keeps the default budget
        assert "temperature" not in body
        # Only the question and observations go out: no user id in any request.
        assert USER not in json.dumps(body)
    assert [tool["function"]["name"] for tool in first["tools"]] == [
        "search_graph",
        "read_document",
    ]
    # The hidden runtime argument is not part of the schema the model sees.
    schemas = json.dumps(first["tools"])
    assert "runtime" not in schemas and "user_id" not in schemas
    # The model's tool call and its result go back in OpenAI shape, paired by id.
    assert second["messages"][-2]["tool_calls"][0]["id"] == "call-1"
    tool_result = second["messages"][-1]
    assert tool_result["role"] == "tool"
    assert tool_result["tool_call_id"] == "call-1"
    assert tool_result["content"] == result.tool_trace[0].summary
    assert "passage 1:" in last["messages"][-1]["content"]
    # The key is a header on the request, never in a message.
    assert all(KEY not in json.dumps(body) for body in host.bodies)
    assert all(headers["Authorization"] == f"Bearer {KEY}" for headers in host.headers)


def test_after_the_tool_cap_the_host_is_asked_with_no_tools(
    monkeypatch: pytest.MonkeyPatch, store: MemoryGraphStore
) -> None:
    searches = [
        {"content": "", "tool_calls": [_tool_call(n, "search_graph", {"query": "item 42"})]}
        for n in range(MAX_TOOL_CALLS)
    ]
    host, result = _run(monkeypatch, store, [*searches, {"content": "Bay 42."}])
    assert result.tool_calls_used == MAX_TOOL_CALLS
    assert result.answer == "Bay 42."
    assert all("tools" in body for body in host.bodies[:-1])
    assert "tools" not in host.bodies[-1]
    assert "Answer now" in host.bodies[-1]["messages"][0]["content"]


def test_a_search_does_no_work_once_the_code_cap_is_spent(store: MemoryGraphStore) -> None:
    result = AgentResult(
        question="Where is item 42 stored?",
        user_id=USER,
        as_of=datetime(2026, 4, 1),
    )
    assert _over_budget(result) is False
    result.tool_trace = [
        ToolTraceEntry("search_graph", {"query": "item 42"}, "already ran")
        for _ in range(MAX_TOOL_CALLS)
    ]

    class Runtime:
        def __init__(self) -> None:
            self.context = type("Context", (), {})()
            self.context.result = result
            self.context.store = store

    answer = search_graph_tool.func("item 42", Runtime())
    assert answer == _BUDGET_SPENT
    assert len(result.tool_trace) == MAX_TOOL_CALLS
    assert result.returned_document_ids == []


def test_unparseable_tool_arguments_are_not_run() -> None:
    message = assistant_message(
        {
            "content": "",
            "tool_calls": [
                {"id": "a", "function": {"name": "search_graph", "arguments": "{not json"}},
                {"id": "b", "function": {"name": "search_graph", "arguments": '{"query":"x"}'}},
            ],
        }
    )
    assert [call["id"] for call in message.tool_calls] == ["b"]
    assert [call["id"] for call in message.invalid_tool_calls] == ["a"]


def test_an_empty_reply_is_an_error() -> None:
    with pytest.raises(RuntimeError, match="empty"):
        assistant_message({"content": ""})
    with pytest.raises(RuntimeError, match="thinking"):
        assistant_message({"content": "", "reasoning_content": "hmm"})
