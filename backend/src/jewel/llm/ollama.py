"""Local chat model for graph construction. The user's API key is not used."""

import http.client
import json
import os
import threading
import urllib.request
from urllib.parse import urlparse

from jewel.llm.base import ChatModel

OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "qwen2.5:7b-instruct"

EXTRACT_OPTIONS = {"temperature": 0, "num_predict": 512}

_EXTRACT_SYSTEM = (
    "Extract a knowledge graph from the document. Return JSON only, with this shape: "
    '{"entities":[{"name":"string","type":"person|organization|place|concept|other"}],'
    '"triples":[{"subject":"string","predicate":"string","object":"string","quote":"string"}]}. '
    "Every quote must be copied verbatim from the passage, not paraphrased. "
    "Return at most 8 triples. Subject and object must appear in the passage."
)


class OllamaChat:
    """One JSON chat completion against a local Ollama server."""

    def __init__(self, model: str | None = None, base_url: str | None = None) -> None:
        self.model = model or os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
        self.base_url = (base_url or os.environ.get("OLLAMA_URL", OLLAMA_URL)).rstrip("/")
        self._conn: http.client.HTTPConnection | None = None
        self._conn_lock = threading.Lock()

    def abort(self) -> None:
        """Close the in-flight request and unload the model so generation stops."""
        with self._conn_lock:
            conn = self._conn
            self._conn = None
        if conn is not None:
            conn.close()
        request = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps({"model": self.model, "keep_alive": 0, "prompt": ""}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                response.read()
        except Exception:
            return

    def complete(self, system: str, user: str) -> str:
        body = json.dumps(
            {
                "model": self.model,
                "stream": False,
                "format": "json",
                "options": EXTRACT_OPTIONS,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
        ).encode()
        parsed = urlparse(self.base_url)
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port or 11434, timeout=300)
        with self._conn_lock:
            self._conn = conn
        try:
            conn.request(
                "POST",
                "/api/chat",
                body=body,
                headers={"Content-Type": "application/json"},
            )
            response = conn.getresponse()
            payload = json.loads(response.read().decode())
        except Exception as exc:
            raise RuntimeError("Ollama is not reachable at " + self.base_url) from exc
        finally:
            with self._conn_lock:
                if self._conn is conn:
                    self._conn = None
            conn.close()
        return str(payload["message"]["content"])


def extract_document(chat: ChatModel, text: str) -> str:
    """Ask the local model for entities and triples."""
    return chat.complete(_EXTRACT_SYSTEM, text)
