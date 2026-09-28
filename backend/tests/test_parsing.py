"""Parsers: PDF (pypdf), .txt / .md (UTF-8), .docx (python-docx)."""

import pytest

from jewel.parsing import ParseError, parser_for, pdf_page_count
from tests.fixtures import make_docx, make_pdf


def test_tiny_pdf_text() -> None:
    text = parser_for(".pdf").extract_text(make_pdf(["The alarm code is 4412."]), "a.pdf")
    assert "alarm code is 4412" in text


def test_pdf_page_count() -> None:
    assert pdf_page_count(make_pdf(["one", "two", None])) == 3


def test_pdf_without_text_layer_yields_no_text() -> None:
    text = parser_for(".pdf").extract_text(make_pdf([None, None]), "scan.pdf")
    assert text.strip() == ""


def test_corrupt_pdf_raises_parse_error() -> None:
    with pytest.raises(ParseError):
        parser_for(".pdf").extract_text(b"%PDF-1.4 not really", "broken.pdf")


def test_txt_utf8() -> None:
    data = "Warehouse key: Sam. Café ✓".encode()
    assert parser_for(".txt").extract_text(data, "a.txt") == "Warehouse key: Sam. Café ✓"


def test_md_utf8_with_bom() -> None:
    data = "\ufeff# Notes\n\n- item".encode()
    assert parser_for(".md").extract_text(data, "notes.md") == "# Notes\n\n- item"


def test_invalid_utf8_raises_parse_error() -> None:
    with pytest.raises(ParseError, match="UTF-8"):
        parser_for(".txt").extract_text(b"\xff\xfe\xfa", "bad.txt")


def test_docx_paragraphs_and_tables() -> None:
    data = make_docx(["First paragraph.", "Second paragraph."], table=[["Key", "Sam"]])
    text = parser_for(".docx").extract_text(data, "a.docx")
    assert "First paragraph." in text
    assert "Second paragraph." in text
    assert "Key\tSam" in text


def test_empty_docx_yields_no_text() -> None:
    text = parser_for(".docx").extract_text(make_docx([]), "empty.docx")
    assert text.strip() == ""


def test_not_a_docx_raises_parse_error() -> None:
    with pytest.raises(ParseError):
        parser_for(".docx").extract_text(b"plain text, not a zip", "fake.docx")


def test_unsupported_extension() -> None:
    with pytest.raises(ParseError):
        parser_for(".pptx")
