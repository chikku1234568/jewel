"""Word ``.docx`` parsing with python-docx: paragraph text, then table cell text."""

import io
import zipfile

import docx
from docx.opc.exceptions import PackageNotFoundError

from jewel.parsing.base import ParseError


class DocxParser:
    def extract_text(self, data: bytes, filename: str) -> str:
        try:
            document = docx.Document(io.BytesIO(data))
        except (PackageNotFoundError, zipfile.BadZipFile, KeyError, ValueError) as exc:
            raise ParseError("Could not read this .docx file") from exc
        parts = [paragraph.text for paragraph in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                cells = [cell.text for cell in row.cells if cell.text]
                if cells:
                    parts.append("\t".join(cells))
        return "\n".join(parts)
