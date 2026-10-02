"""Import checks: the new modules load and the removed modules are gone.

No test here calls Google, xAI, Neo4j or Postgres.
"""

import importlib
import importlib.util
import pkgutil

import pytest

import jewel

EXPECTED_MODULES = [
    "jewel.api.app",
    "jewel.api.routes.health",
    "jewel.api.routes.auth",
    "jewel.api.routes.keys",
    "jewel.api.routes.documents",
    "jewel.api.routes.graph",
    "jewel.api.routes.ask",
    "jewel.auth.google",
    "jewel.auth.sessions",
    "jewel.auth.api_keys",
    "jewel.auth.users",
    "jewel.auth.dependencies",
    "jewel.db.postgres",
    "jewel.documents.models",
    "jewel.documents.storage",
    "jewel.documents.repository",
    "jewel.documents.service",
    "jewel.parsing.markdown",
    "jewel.ingestion.pipeline",
    "jewel.ingestion.chunking",
    "jewel.parsing.base",
    "jewel.parsing.pdf",
    "jewel.parsing.text",
    "jewel.kg.schema",
    "jewel.kg.neo4j_store",
    "jewel.kg.temporal",
    "jewel.kg.extraction",
    "jewel.agents.graph",
    "jewel.agents.state",
    "jewel.agents.tools",
    "jewel.retrieval.baseline_rag",
    "jewel.retrieval.hippo.linking",
    "jewel.retrieval.hippo.recognition",
    "jewel.retrieval.hippo.ppr",
    "jewel.retrieval.hippo.pipeline",
    "jewel.llm.base",
    "jewel.config",
]

# Modules from the archived showcase that must not come back.
REMOVED_MODULES = [
    "jewel.kg.permissions",
    "jewel.agents.ehr_order",
    "jewel.agents.lab_monitor",
    "jewel.agents.pharmacologist",
    "jewel.agents.parse",
    "jewel.agents.answer",
    "jewel.agents.progress",
    "jewel.rules",
    "jewel.rules.enoxaparin_crcl",
    "jewel.cache",
    "jewel.cache.base",
    "jewel.ingestion.episodes",
]


def test_every_module_in_package_imports() -> None:
    names = [m.name for m in pkgutil.walk_packages(jewel.__path__, prefix="jewel.")]
    assert names, "no modules discovered"
    for name in names:
        importlib.import_module(name)


@pytest.mark.parametrize("name", EXPECTED_MODULES)
def test_expected_module_imports(name: str) -> None:
    importlib.import_module(name)


@pytest.mark.parametrize("name", REMOVED_MODULES)
def test_removed_module_is_not_importable(name: str) -> None:
    parent, _, _ = name.rpartition(".")
    try:
        spec = importlib.util.find_spec(name)
    except ModuleNotFoundError:
        spec = None  # parent package is gone too
    assert spec is None, f"{name} should have been removed (parent {parent})"
