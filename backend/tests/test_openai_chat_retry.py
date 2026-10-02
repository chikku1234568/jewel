"""HTTP 429 retry, other HTTP errors, and Stop winning over a retry. No host is called."""

import io
import json
import threading
import time
import urllib.request
from email.message import Message
from urllib.error import HTTPError, URLError

import pytest

from jewel.ingestion.live import build_parsed_text
from jewel.kg.memory_store import MemoryGraphStore
from jewel.llm import openai_chat
from jewel.llm.hashing import HashingEmbedder
from jewel.llm.openai_chat import OpenAICompatibleChat

_RAW = (
    '{"entities":[{"name":"alarm code","type":"concept"}],'
    '"triples":[{"subject":"alarm code","predicate":"is","object":"4412",'
    '"quote":"The alarm code is 4412."}]}'
)


def _http_error(code: int, retry_after: str | None = None) -> HTTPError:
    headers = Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return HTTPError("http://host.invalid/v1/chat/completions", code, "error", headers, None)


def _ok() -> io.BytesIO:
    return io.BytesIO(json.dumps({"choices": [{"message": {"content": _RAW}}]}).encode())


class Replies(list):
    """Scripted host: each urlopen pops the next item, an exception or a response."""

    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def urlopen(self, request, timeout):
        self.calls += 1
        reply = self.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest.fixture
def replies(monkeypatch: pytest.MonkeyPatch) -> Replies:
    scripted = Replies()
    monkeypatch.setattr(urllib.request, "urlopen", scripted.urlopen)
    return scripted


@pytest.fixture
def no_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(openai_chat, "_rate_limit_delay", lambda exc, retry: 0.0)


def _chat() -> OpenAICompatibleChat:
    return OpenAICompatibleChat("kimi-k2.6", "http://host.invalid/v1", "test-key")


def test_429_waits_and_retries(replies: Replies, no_wait: None) -> None:
    replies.extend([_http_error(429), _http_error(429), _ok()])
    assert _chat().complete("system", "passage") == _RAW
    assert replies.calls == 3


def test_429_retries_are_capped(replies: Replies, no_wait: None) -> None:
    replies.extend([_http_error(429)] * 10)
    with pytest.raises(RuntimeError, match=r"\(429\)"):
        _chat().complete("system", "passage")
    assert replies.calls == 1 + openai_chat._RATE_LIMIT_RETRIES


@pytest.mark.parametrize("code", [400, 401, 500, 503])
def test_other_http_errors_fail_at_once(replies: Replies, code: int) -> None:
    replies.extend([_http_error(code), _ok()])
    with pytest.raises(RuntimeError, match=rf"\({code}\)"):
        _chat().complete("system", "passage")
    assert replies.calls == 1


def test_connection_errors_still_retry(replies: Replies, monkeypatch: pytest.MonkeyPatch) -> None:
    replies.extend([URLError("refused"), _ok()])
    chat = _chat()
    # The connection backoff is 1 s; skip it without touching the retry logic.
    monkeypatch.setattr(chat._stopped, "wait", lambda delay: False)
    assert chat.complete("system", "passage") == _RAW
    assert replies.calls == 2


def test_retry_after_is_honoured_and_capped() -> None:
    assert openai_chat._rate_limit_delay(_http_error(429, "3"), 0) == 3.0
    assert openai_chat._rate_limit_delay(_http_error(429, "600"), 0) == 30.0
    # No header: exponential backoff with jitter, still capped.
    assert 4.0 <= openai_chat._rate_limit_delay(_http_error(429), 2) <= 5.0
    assert openai_chat._rate_limit_delay(_http_error(429), 20) == 30.0


def test_stop_ends_a_backoff_wait_and_no_retry_follows(replies: Replies) -> None:
    replies.extend([_http_error(429, "30"), _ok()])
    chat = _chat()
    threading.Timer(0.05, chat.abort).start()
    started = time.monotonic()
    with pytest.raises(RuntimeError, match="stopped"):
        chat.complete("system", "passage")
    assert time.monotonic() - started < 5  # did not sit out the 30 s Retry-After
    assert replies.calls == 1


def _build(chat) -> MemoryGraphStore:
    store = MemoryGraphStore()
    build_parsed_text(
        document_id="doc",
        user_id="user",
        filename="paper.txt",
        text=("The alarm code is 4412. " * 400),  # three passages
        document_date=None,
        chat=chat,
        embedder=HashingEmbedder(),
        store=store,
    )
    return store


def test_one_bad_passage_does_not_fail_the_file() -> None:
    calls = {"n": 0}
    lock = threading.Lock()

    class Chat:
        model = "fake-api"

        def complete(self, system: str, user: str, **_kwargs) -> str:
            with lock:
                calls["n"] += 1
                first = calls["n"] == 1
            if first:
                raise RuntimeError("extraction request failed (500)")
            return _RAW

    assert _build(Chat()).subgraph("user").triples
    assert calls["n"] == 3


def test_every_passage_failing_surfaces_the_error() -> None:
    class Chat:
        model = "fake-api"

        def complete(self, system: str, user: str, **_kwargs) -> str:
            raise RuntimeError("extraction request failed (500)")

    with pytest.raises(RuntimeError, match=r"\(500\)"):
        _build(Chat())
