"""Parser interface."""

from typing import Protocol


class ParseError(Exception):
    """The file could not be turned into text. ``str(exc)`` is safe to show the user."""


class DocumentParser(Protocol):
    """Extract plain text from an uploaded PDF, ``.txt``, ``.md`` or ``.docx`` file."""

    def extract_text(self, data: bytes, filename: str) -> str:
        """Return the document text (may be empty). Raise ``ParseError`` on bad input.

        Implementations must not call a model.
        """
        ...
