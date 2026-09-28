"""Provider-agnostic model interfaces.

Implemented later by a single OpenAI-compatible client aimed at ``https://api.x.ai/v1``
(``jewel.config.LLM_BASE_URL``), constructed per request with the signed-in user's
decrypted key. One client, no second SDK. Model ids come from ``JEWEL_LLM_MODEL`` and
``JEWEL_EMBEDDING_MODEL``.
"""

from typing import Protocol


class ChatModel(Protocol):
    def complete(self, system: str, user: str) -> str:
        """Return a completion."""
        ...


class EmbeddingModel(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text."""
        ...
