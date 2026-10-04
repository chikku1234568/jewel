"""Upload bytes and Ask fields are refused before they reach a parser or a model host."""

import io
import zipfile

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from jewel.api.routes.ask import AskBody, clean_question
from jewel.documents.service import UploadRejected, check_upload
from jewel.kg.neo4j_schema import constraint_statements
from jewel.llm.choices import AgentChoice, EmbeddingChoice, make_agent_chat
from tests.fixtures import make_docx, make_pdf


def test_a_pdf_without_a_header_is_rejected() -> None:
    with pytest.raises(UploadRejected) as raised:
        check_upload("notes.pdf", b"<html>not a pdf</html>")
    assert raised.value.status_code == 422
    assert check_upload("notes.pdf", make_pdf(["hello"])).endswith(".pdf")


def test_text_with_a_null_or_bad_encoding_is_rejected() -> None:
    with pytest.raises(UploadRejected):
        check_upload("notes.txt", b"hello\x00")
    with pytest.raises(UploadRejected):
        check_upload("page.html", b"\xff\xfe not utf-8")
    assert check_upload("notes.md", b"# Hello\n") == ".md"


def test_a_truncated_office_package_is_rejected() -> None:
    with pytest.raises(UploadRejected) as raised:
        check_upload("slides.pptx", b"PK\x03\x04")
    assert raised.value.status_code == 422


def test_an_office_path_escape_is_rejected() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("../evil.xml", b"<x/>")
    with pytest.raises(UploadRejected):
        check_upload("letter.docx", buffer.getvalue())


def test_an_office_package_that_claims_a_huge_expansion_is_rejected() -> None:
    raw = bytearray(make_docx(["hello"]))
    start = raw.find(b"PK\x01\x02")
    assert start >= 0
    raw[start + 24 : start + 28] = (80 * 1024 * 1024).to_bytes(4, "little")
    with pytest.raises(UploadRejected):
        check_upload("letter.docx", bytes(raw))


def test_a_real_docx_still_passes_the_byte_check() -> None:
    assert check_upload("letter.docx", make_docx(["hello"])) == ".docx"


def test_question_rejects_controls_and_keeps_plain_text() -> None:
    assert clean_question("  where does he live?\n") == "where does he live?"
    with pytest.raises(ValidationError):
        AskBody.model_validate({"question": "where\x00", "api_key": "sk-test"})
    with pytest.raises(ValidationError):
        AskBody.model_validate({"question": "   ", "api_key": "sk-test"})
    with pytest.raises(ValidationError):
        AskBody.model_validate({"question": "where", "api_key": "sk-test", "extra": 1})


def test_api_base_must_be_public_https_and_the_key_a_single_token() -> None:
    body = AskBody.model_validate(
        {"question": "where does he live?", "api_key": "sk-test", "agent": {"api_key": "sk-agent"}}
    )
    assert body.base_url == "https://api.openai.com/v1"
    assert body.agent.base_url == "https://api.moonshot.ai/v1"
    for bad in (
        "http://api.openai.com/v1",
        "https://127.0.0.1/v1",
        "https://169.254.169.254/latest",
        "https://user:secret@api.openai.com/v1",
        "https://localhost/v1",
    ):
        with pytest.raises(ValidationError):
            EmbeddingChoice.model_validate(
                {
                    "provider": "api",
                    "model": "text-embedding-3-small",
                    "base_url": bad,
                    "api_key": "k",
                }
            )
    with pytest.raises(ValidationError):
        AgentChoice.model_validate(
            {"model": "kimi-k2.6", "base_url": "https://api.moonshot.ai/v1", "api_key": "a\nb"}
        )


def test_an_empty_ask_key_is_refused_even_when_the_server_has_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KIMI_API_KEY", "server-secret")
    choice = AgentChoice.model_validate(
        {"model": "kimi-k2.6", "base_url": "https://api.moonshot.ai/v1", "api_key": ""}
    )
    with pytest.raises(HTTPException) as raised:
        make_agent_chat(choice)
    assert raised.value.status_code == 400
    chat = make_agent_chat(
        AgentChoice.model_validate(
            {
                "model": "kimi-k2.6",
                "base_url": "https://api.moonshot.ai/v1",
                "api_key": "sk-user",
            }
        )
    )
    assert chat._api_key == "sk-user"


def test_neo4j_schema_names_every_node_kind() -> None:
    text = "\n".join(constraint_statements())
    for label in ("Document", "Entity", "Statement"):
        assert label in text
    assert "IF NOT EXISTS" in text
    assert "IS UNIQUE" in text
