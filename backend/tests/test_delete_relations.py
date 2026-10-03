"""Deleting a relation removes that user's statement node and nothing else."""

from fastapi.testclient import TestClient

from jewel.api.app import app
from jewel.auth.dependencies import current_user
from jewel.kg.extraction import ExtractedEntity, ExtractedTriple, Extraction
from jewel.kg.memory_store import MemoryGraphStore
from jewel.kg.neo4j_store import Neo4jGraphStore
from jewel.kg.records import GraphTriple
from jewel.kg.schema import EntityType

USER = "user-a"
OTHER = "user-b"


def _extraction() -> Extraction:
    return Extraction(
        entities=[
            ExtractedEntity(name="Ada", type=EntityType.PERSON),
            ExtractedEntity(name="21 years", type=EntityType.OTHER),
        ],
        triples=[
            ExtractedTriple(
                subject="Ada",
                predicate="aged",
                object="21 years",
                quote="Ada aged 21 years.",
            )
        ],
    )


def _write(store: MemoryGraphStore, user_id: str) -> None:
    extraction = _extraction()
    store.write_document(
        user_id=user_id,
        document_id="note",
        filename="note.txt",
        text="Ada aged 21 years.",
        embedding=[0.1],
        extraction=extraction,
        entity_embeddings={entity.name: [0.2] for entity in extraction.entities},
        triple_embeddings=[[0.3]],
    )


def test_delete_triples_keeps_mentions_entities_and_other_users() -> None:
    store = MemoryGraphStore()
    _write(store, USER)
    _write(store, OTHER)
    own = store.subgraph(USER).triples[0].id
    # Same id on the other account must not be removed by this user's delete.
    store.triples.append(
        GraphTriple(
            id=own,
            user_id=OTHER,
            source_id="other-source",
            target_id="other-target",
            predicate="aged",
            quote="Ada aged 21 years.",
            document_id="note",
        )
    )

    deleted = store.delete_triples(USER, [own, "missing", own])

    assert deleted == 1
    assert store.subgraph(USER).triples == []
    assert len(store.subgraph(USER).mentions) == 2
    assert len(store.subgraph(USER).entities) == 2
    assert {triple.user_id for triple in store.triples if triple.id == own} == {OTHER}
    assert store.delete_triples(USER, []) == 0


def test_rebuilding_the_file_writes_the_extracted_relation_again() -> None:
    store = MemoryGraphStore()
    _write(store, USER)
    store.delete_triples(USER, [store.subgraph(USER).triples[0].id])
    assert store.subgraph(USER).triples == []
    _write(store, USER)
    assert [triple.predicate for triple in store.subgraph(USER).triples] == ["aged"]


def test_neo4j_delete_triples_binds_the_user_and_touches_only_statements() -> None:
    class Result:
        def __init__(self, deleted: int) -> None:
            self._deleted = deleted

        def single(self):
            return {"deleted": self._deleted}

    class Session:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        def run(self, query: str, **params):
            self.calls.append((query, params))
            return Result(1 if "Statement" in query else 0)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    class Driver:
        def __init__(self) -> None:
            self.session_obj = Session()

        def session(self):
            return self.session_obj

    driver = Driver()
    deleted = Neo4jGraphStore(driver).delete_triples(USER, ["rel-1"])
    assert deleted == 1
    assert len(driver.session_obj.calls) == 2
    statement_query, statement_params = driver.session_obj.calls[0]
    legacy_query, legacy_params = driver.session_obj.calls[1]
    assert "Statement" in statement_query
    assert "DETACH DELETE" in statement_query
    assert "RELATED_TO" in legacy_query
    assert "MENTIONS" not in statement_query
    assert "MENTIONS" not in legacy_query
    assert USER not in statement_query
    assert USER not in legacy_query
    assert statement_params == legacy_params == {"user_id": USER, "ids": ["rel-1"]}


def test_delete_relations_requires_sign_in(client) -> None:
    response = client.request("DELETE", "/graph/relations", json={"ids": ["rel-1"]})
    assert response.status_code == 401


def test_delete_relations_rejects_a_blank_id_and_reports_how_many_were_removed() -> None:
    class Result:
        def __init__(self, deleted: int) -> None:
            self._deleted = deleted

        def single(self):
            return {"deleted": self._deleted}

    class Session:
        def __init__(self) -> None:
            self.calls = 0

        def run(self, query: str, **params):
            assert params["user_id"] == USER
            assert params["ids"] == ["rel-1"]
            self.calls += 1
            return Result(1 if self.calls == 1 else 0)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    class Driver:
        def session(self):
            return Session()

    app.dependency_overrides[current_user] = lambda: {"id": USER, "email": "a@b.c", "name": "A"}
    try:
        with TestClient(app) as client:
            app.state.neo4j = Driver()
            blank = client.request("DELETE", "/graph/relations", json={"ids": ["  "]})
            assert blank.status_code == 400
            ok = client.request("DELETE", "/graph/relations", json={"ids": ["rel-1", "rel-1"]})
            assert ok.status_code == 200
            assert ok.json() == {"deleted": 1}
            missing = client.request("DELETE", "/graph/relations", json={})
            assert missing.status_code == 422
    finally:
        app.dependency_overrides.pop(current_user, None)
