"""OpenAI-compatible chat for triple extraction. The key is not stored or logged."""

import json
import time
import urllib.request
from urllib.error import HTTPError, URLError


class OpenAICompatibleChat:
    """POST {base_url}/chat/completions. Temperature is omitted so strict hosts accept it."""

    def __init__(self, model: str, base_url: str, api_key: str) -> None:
        self.model = model.strip()
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key.strip()
        if not self.model or not self._api_key or not self.base_url:
            raise ValueError("model, base URL, and api key are required")

    def complete(self, system: str, user: str) -> str:
        body = json.dumps(_body(self.model, system, user)).encode()
        last_error: Exception | None = None
        for attempt in range(3):
            request = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=body,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    payload = json.loads(response.read().decode())
                message = payload["choices"][0]["message"]
                content = message.get("content") if isinstance(message, dict) else None
                if not content:
                    if isinstance(message, dict) and message.get("reasoning_content"):
                        raise RuntimeError("kimi returned thinking text and no answer")
                    raise RuntimeError("extraction model returned an empty answer")
                return str(content)
            except HTTPError as exc:
                raise RuntimeError(f"extraction request failed ({exc.code})") from exc
            except (URLError, TimeoutError) as exc:
                last_error = exc
                time.sleep(1 + attempt)
        reason = getattr(last_error, "reason", last_error)
        raise RuntimeError(f"extraction host is not reachable ({reason})") from last_error


def _body(model: str, system: str, user: str) -> dict:
    """Kimi K2.6 thinks by default and burns the request timeout. Turn that off."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if model.startswith("kimi-k2.6"):
        payload["thinking"] = {"type": "disabled"}
        payload["max_tokens"] = 1024
    elif model.startswith("kimi-k3"):
        payload["reasoning_effort"] = "low"
        payload["max_tokens"] = 1024
    return payload
