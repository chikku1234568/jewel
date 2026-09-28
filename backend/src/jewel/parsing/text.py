"""Plain-text and Markdown parsing: UTF-8 (a leading BOM is dropped), kept as-is."""

from jewel.parsing.base import ParseError


class TextParser:
    def extract_text(self, data: bytes, filename: str) -> str:
        try:
            return data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ParseError("File is not valid UTF-8 text") from exc
