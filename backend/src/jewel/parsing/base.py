"""Parser interface."""

from typing import Protocol


class DocumentParser(Protocol):
    """Extract plain text from an uploaded document before it becomes an episode."""

    def extract_text(self, data: bytes, filename: str) -> str:
        """Return the document text. Implementations must not call an LLM."""
        ...
