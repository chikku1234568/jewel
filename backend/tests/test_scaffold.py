"""Scaffold invariants that need no network, database, or model."""

from jewel.api.app import app
from jewel.config import LLM_BASE_URL, Settings
from jewel.documents.models import DocumentStatus
from jewel.kg.schema import NodeLabel, RelationshipType


def test_only_health_is_mounted() -> None:
    assert set(app.openapi()["paths"]) == {"/health"}


def test_llm_base_url_is_xai_and_model_ids_are_not_hardcoded() -> None:
    settings = Settings(_env_file=None)
    assert LLM_BASE_URL == "https://api.x.ai/v1"
    assert settings.llm_base_url == LLM_BASE_URL
    assert settings.llm_model == ""
    assert settings.embedding_model == ""


def test_graph_vocabulary() -> None:
    assert {label.value for label in NodeLabel} == {"Document", "Entity"}
    assert {rel.value for rel in RelationshipType} == {"MENTIONS", "RELATED_TO"}


def test_document_status_values() -> None:
    assert [s.value for s in DocumentStatus] == [
        "stored",
        "waiting_for_key",
        "parsing",
        "extracting",
        "ready",
        "failed",
    ]
