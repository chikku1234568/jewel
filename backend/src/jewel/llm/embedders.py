"""Embedding models for graph build and search.

Local models run through fastembed. An OpenAI-compatible key is used only when the
user picks an API model. The key is not stored.
"""

import json
import math
import urllib.request
from urllib.error import HTTPError, URLError

LOCAL_MODELS = (
    "BAAI/bge-base-en-v1.5",
    "BAAI/bge-large-en-v1.5",
    "nomic-ai/nomic-embed-text-v1.5",
    "intfloat/multilingual-e5-large",
)
API_MODELS = ("text-embedding-3-small", "text-embedding-3-large")
DEFAULT_MODEL = "BAAI/bge-base-en-v1.5"

_PASSAGE_PREFIX = {
    "nomic-ai/nomic-embed-text-v1.5": "search_document: ",
    "intfloat/multilingual-e5-large": "passage: ",
}
_QUERY_PREFIX = {
    "nomic-ai/nomic-embed-text-v1.5": "search_query: ",
    "intfloat/multilingual-e5-large": "query: ",
}


class LocalEmbedder:
    """A fastembed model. The weights download on first use."""

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        if model not in LOCAL_MODELS:
            raise ValueError(model)
        self.model = model
        self._inner = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        prefix = _PASSAGE_PREFIX.get(self.model, "")
        return self._embed([prefix + text for text in texts])

    def embed_query(self, text: str) -> list[float]:
        prefix = _QUERY_PREFIX.get(self.model, "")
        return self._embed([prefix + text])[0]

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if self._inner is None:
            from fastembed import TextEmbedding

            self._inner = TextEmbedding(model_name=self.model)
        vectors = []
        for raw in self._inner.embed(texts):
            values = [float(item) for item in raw]
            norm = math.sqrt(sum(value * value for value in values)) or 1.0
            vectors.append([value / norm for value in values])
        return vectors


class OpenAIEmbedder:
    """POST {base_url}/embeddings with the user's key."""

    def __init__(self, model: str, base_url: str, api_key: str) -> None:
        self.model = model.strip()
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key.strip()
        if not self.model or not self._api_key:
            raise ValueError("model and api key are required")

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text])[0]

    def _embed(self, texts: list[str]) -> list[list[float]]:
        body = json.dumps({"model": self.model, "input": texts}).encode()
        request = urllib.request.Request(
            f"{self.base_url}/embeddings",
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = json.loads(response.read().decode())
        except HTTPError as exc:
            raise RuntimeError(f"embedding request failed ({exc.code})") from exc
        except URLError as exc:
            raise RuntimeError("embedding host is not reachable") from exc
        rows = sorted(payload["data"], key=lambda row: row["index"])
        return [_normalize(row["embedding"]) for row in rows]


def _normalize(values: list[float]) -> list[float]:
    vector = [float(value) for value in values]
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]
