"""Scaffold invariants that need no network, database, or model."""

from jewel.api.app import app
from jewel.config import LLM_BASE_URL, Settings
from jewel.documents.models import DocumentStatus
from jewel.kg.schema import NodeLabel, RelationshipType

MOUNTED = {
    "/health",
    "/auth/google",
    "/auth/google/callback",
    "/auth/logout",
    "/me",
    "/documents",
    "/documents/{document_id}",
    "/documents/{document_id}/build",
    "/documents/{document_id}/stop",
    "/graph",
    "/graph/relations",
    "/ask",
}


def test_only_this_pass_routes_are_mounted() -> None:
    paths = set(app.openapi()["paths"])
    assert paths == MOUNTED
    assert not any(path.startswith("/me/api-key") for path in paths)


def test_llm_base_url_is_xai_and_model_ids_are_not_hardcoded() -> None:
    settings = Settings(_env_file=None)
    assert LLM_BASE_URL == "https://api.x.ai/v1"
    assert settings.llm_base_url == LLM_BASE_URL
    assert settings.llm_model == ""
    assert settings.embedding_model == ""


def test_graph_vocabulary() -> None:
    assert {label.value for label in NodeLabel} == {"Document", "Entity", "Statement"}
    assert {rel.value for rel in RelationshipType} == {"MENTIONS", "ABOUT", "RELATED_TO"}


def test_document_status_values() -> None:
    assert [s.value for s in DocumentStatus] == [
        "stored",
        "parsing",
        "parsed",
        "failed",
        "extracting",
        "ready",
    ]
    assert "waiting_for_key" not in {s.value for s in DocumentStatus}
