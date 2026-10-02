"""Parsers: MarkItDown for PDF / Office / HTML, UTF-8 for .txt and .md."""

import pytest

from jewel.parsing import ParseError, parser_for, pdf_page_count
from tests.fixtures import make_docx, make_pdf, make_pptx, make_xlsx


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
    # MarkItDown renders a Word table as a Markdown table.
    assert "| Key | Sam |" in text


def test_empty_docx_yields_no_text() -> None:
    text = parser_for(".docx").extract_text(make_docx([]), "empty.docx")
    assert text.strip() == ""


def test_not_a_docx_raises_parse_error() -> None:
    with pytest.raises(ParseError):
        parser_for(".docx").extract_text(b"plain text, not a zip", "fake.docx")


def test_pptx_becomes_markdown() -> None:
    text = parser_for(".pptx").extract_text(make_pptx(["Sam holds the warehouse key"]), "a.pptx")
    assert "Sam holds the warehouse key" in text


def test_xlsx_becomes_a_markdown_table() -> None:
    data = make_xlsx([["Holder", "Item"], ["Sam", "warehouse key"]])
    text = parser_for(".xlsx").extract_text(data, "a.xlsx")
    assert "| Sam | warehouse key |" in text


def test_html_drops_scripts_and_keeps_headings() -> None:
    data = b"<html><head><script>alert(1)</script></head><body><h1>Keys</h1><p>Sam.</p></body>"
    text = parser_for(".html").extract_text(data, "a.html")
    assert text.startswith("# Keys")
    assert "alert" not in text
    assert parser_for(".htm").extract_text(data, "a.htm") == text


def test_corrupt_pptx_raises_parse_error() -> None:
    with pytest.raises(ParseError):
        parser_for(".pptx").extract_text(b"PK\x03\x04 not really", "broken.pptx")


@pytest.mark.parametrize("extension", [".zip", ".png", ".mp3", ".doc", ".csv", ""])
def test_unsupported_extension(extension: str) -> None:
    with pytest.raises(ParseError):
        parser_for(extension)
