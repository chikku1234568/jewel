"""OpenAI-compatible chat for triple extraction and the agent. The key is not stored or logged.

Retries, in one place:

* A connection error or timeout is retried up to ``_CONNECTION_ATTEMPTS`` times in total.
* HTTP 429 (rate limited) waits and is retried up to ``_RATE_LIMIT_RETRIES`` times. The
  wait is the host's ``Retry-After`` when it sends one, otherwise an exponential backoff
  with jitter, and never longer than ``_MAX_BACKOFF_SECONDS``.
* Any other HTTP error fails at once. Retrying a 400 or 401 cannot succeed.

``abort()`` stops a build: it ends any backoff wait immediately and refuses further
attempts, so Stop wins over a retry. A request already on the wire still finishes.
"""

import json
import random
import threading
import urllib.request
from urllib.error import HTTPError, URLError

DEFAULT_MAX_TOKENS = 1024
"""Output cap for Kimi calls unless the caller asks for more (extraction asks for 8192)."""

_CONNECTION_ATTEMPTS = 3
_RATE_LIMIT_RETRIES = 5
_MAX_BACKOFF_SECONDS = 30.0


class OpenAICompatibleChat:
    """POST {base_url}/chat/completions. Temperature is omitted so strict hosts accept it."""

    def __init__(self, model: str, base_url: str, api_key: str) -> None:
        self.model = model.strip()
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key.strip()
        self._stopped = threading.Event()
        if not self.model or not self._api_key or not self.base_url:
            raise ValueError("model, base URL, and api key are required")

    def abort(self) -> None:
        """Stop retrying. Called by the Stop route; one chat object serves one build."""
        self._stopped.set()

    def complete(self, system: str, user: str, *, max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
        """One chat completion. ``max_tokens`` is sent to Kimi models only (see ``_body``)."""
        message = self._send(_body(self.model, system, user, max_tokens))
        content = message.get("content")
        if not content:
            if message.get("reasoning_content"):
                raise RuntimeError("kimi returned thinking text and no answer")
            raise RuntimeError("extraction model returned an empty answer")
        return str(content)

    def chat(
        self,
        messages: list[dict],
        *,
        tools: list[dict] | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> dict:
        """One turn of a tool-calling conversation; returns the assistant message dict.

        Used by the agent (``jewel.agents.chat_model``). Same retries and Kimi settings
        as ``complete``. The reply may hold ``tool_calls`` and no ``content``.
        """
        payload = _payload(self.model, messages, max_tokens)
        if tools:
            payload["tools"] = tools
        return self._send(payload)

    def _send(self, payload: dict) -> dict:
        body = json.dumps(payload).encode()
        connection_failures = 0
        rate_limited = 0
        while True:
            if self._stopped.is_set():
                raise RuntimeError("extraction request stopped")
            try:
                return self._post(body)
            except HTTPError as exc:  # before URLError: HTTPError is a subclass of it
                if exc.code != 429 or rate_limited >= _RATE_LIMIT_RETRIES:
                    raise RuntimeError(f"extraction request failed ({exc.code})") from exc
                delay = _rate_limit_delay(exc, rate_limited)
                rate_limited += 1
            except (URLError, TimeoutError) as exc:
                connection_failures += 1
                if connection_failures >= _CONNECTION_ATTEMPTS:
                    reason = getattr(exc, "reason", exc)
                    raise RuntimeError(f"extraction host is not reachable ({reason})") from exc
                delay = float(connection_failures)  # 1 s, then 2 s
            # Event.wait returns True as soon as abort() is called, so Stop does not sit
            # out the rest of a backoff.
            if self._stopped.wait(delay):
                raise RuntimeError("extraction request stopped")

    def _post(self, body: bytes) -> dict:
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode())
        message = payload["choices"][0]["message"]
        if not isinstance(message, dict):
            raise RuntimeError("extraction model returned an empty answer")
        return message


def _rate_limit_delay(exc: HTTPError, retry: int) -> float:
    """Seconds to wait before retry number ``retry`` (0-based) after a 429.

    Honour ``Retry-After`` (seconds) when present. Otherwise back off 1, 2, 4, 8... seconds
    plus up to one second of jitter, so eight workers that were limited together do not
    all come back in the same instant. Always capped.
    """
    header = exc.headers.get("Retry-After") if exc.headers is not None else None
    try:
        wait = float(header) if header is not None else None
    except ValueError:
        wait = None  # an HTTP-date; fall back to our own backoff
    if wait is None or wait < 0:
        wait = 2.0**retry + random.uniform(0.0, 1.0)
    return min(wait, _MAX_BACKOFF_SECONDS)


def _body(model: str, system: str, user: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> dict:
    """A system + user request (extraction, or any single-turn call)."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    return _payload(model, messages, max_tokens)


def _payload(model: str, messages: list[dict], max_tokens: int = DEFAULT_MAX_TOKENS) -> dict:
    """Kimi K2.6 thinks by default and burns the request timeout. Turn that off.

    Kimi models get an explicit ``max_tokens``; other hosts keep their own default. No
    ``temperature`` is sent, because Kimi rejects values other than its fixed one.
    """
    payload: dict = {"model": model, "messages": messages}
    if model.startswith("kimi-k2.6"):
        payload["thinking"] = {"type": "disabled"}
        payload["max_tokens"] = max_tokens
    elif model.startswith("kimi-k3"):
        payload["reasoning_effort"] = "low"
        payload["max_tokens"] = max_tokens
    return payload
