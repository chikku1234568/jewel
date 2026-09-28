"""Kimi (Moonshot) chat client for agent tests.

OpenAI-compatible chat completions at ``https://api.moonshot.ai/v1``. The key is read
from ``KIMI_API_KEY`` when a call is made. This module does not read ``.env`` by itself
and does not log the key. Extraction and embeddings do not use it.
"""

import json
import os
import urllib.request

KIMI_BASE_URL = "https://api.moonshot.ai/v1"
DEFAULT_KIMI_MODEL = "kimi-k2.6"


def kimi_is_configured() -> bool:
    """Return whether an agent test key is present in the environment."""
    return bool(os.environ.get("KIMI_API_KEY", "").strip())


def complete(system: str, user: str) -> str:
    """One chat completion. Raises if ``KIMI_API_KEY`` is missing."""
    key = os.environ.get("KIMI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("KIMI_API_KEY is not set")
    base = os.environ.get("KIMI_BASE_URL", KIMI_BASE_URL).rstrip("/")
    model = os.environ.get("KIMI_MODEL", DEFAULT_KIMI_MODEL)
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
    ).encode()
    request = urllib.request.Request(
        f"{base}/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode())
    return payload["choices"][0]["message"]["content"]
