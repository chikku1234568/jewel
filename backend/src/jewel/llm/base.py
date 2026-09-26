"""LLM interfaces. The provider is not chosen yet (open question)."""

from typing import Protocol


class ChatModel(Protocol):
    def complete(self, system: str, user: str) -> str:
        """Return a completion. Implementations should be cacheable by prompt hash."""
        ...


class EmbeddingModel(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text."""
        ...
