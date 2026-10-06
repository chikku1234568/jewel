"""Document routes against a real Postgres and a temporary upload directory."""

import io
import json
import threading
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import pytest

from jewel.agents.state import AgentResult
from jewel.api.limits import BUILD, RateLimiter
from jewel.api.routes import ask as ask_routes
from jewel.api.routes import documents as documents_routes
from jewel.auth.users import upsert_user
from jewel.documents import repository
from jewel.documents.build_queue import RESTART_ERROR, fail_interrupted
from jewel.documents.models import DOCX_MEDIA_TYPE, MAX_UPLOAD_BYTES
from jewel.ingestion.chunking import build_chunks
from jewel.kg.memory_store import MemoryGraphStore
from jewel.llm.embedders import DEFAULT_MODEL
from jewel.llm.hashing import HashingEmbedder
from jewel.parsing.markdown import MarkItDownParser
from tests.conftest import make_client, sign_in
from tests.fixtures import make_docx, make_pdf, make_pptx
from tests.keep_verdict import keep_all_verdict


def upload(client, filename: str, data: bytes, content_type: str = "application/octet-stream"):
    return client.post("/documents", files={"file": (filename, data, content_type)})


def stored_files(upload_dir: Path) -> list[Path]:
    return [p for p in upload_dir.iterdir() if p.is_file()]


def count_rows(db) -> int:
    return db.execute("SELECT count(*) AS n FROM documents").fetchone()["n"]


def test_routes_require_a_session(client) -> None:
    assert client.get("/documents").status_code == 401
    assert upload(client, "a.txt", b"hello").status_code == 401
    some_id = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/documents/{some_id}").status_code == 401
    assert client.delete(f"/documents/{some_id}").status_code == 401


def test_upload_pdf_and_docx_are_parsed(client, db, settings, upload_dir) -> None:
    sign_in(client, db, settings, "sub-a", "alice@example.com")

    pdf = upload(client, "Lease 2026.pdf", make_pdf(["The warehouse key is held by Sam."]))
    assert pdf.status_code == 201, pdf.text
    body = pdf.json()
    assert body["status"] == "parsed"
    assert body["error"] is None
    assert body["filename"] == "Lease 2026.pdf"
    assert "extracted_text" not in body

    word = upload(client, "letter.docx", make_docx(["The alarm code was rotated."]))
    assert word.status_code == 201
    assert word.json()["status"] == "parsed"

    detail = client.get(f"/documents/{word.json()['id']}").json()
    assert detail["media_type"] == DOCX_MEDIA_TYPE
    assert "alarm code was rotated" in detail["extracted_text"]
    assert detail["document_date"] is None

    library = client.get("/documents").json()
    assert {d["filename"] for d in library} == {"Lease 2026.pdf", "letter.docx"}
    assert all(
        set(d)
        == {
            "id",
            "filename",
            "uploaded_at",
            "status",
            "error",
            "build_done",
            "build_total",
            "triples_kept",
        }
        for d in library
    )
    assert len(stored_files(upload_dir)) == 2


def test_txt_and_md_are_parsed(client, db, settings) -> None:
    sign_in(client, db, settings, "sub-a", "alice@example.com")
    for name in ("notes.txt", "notes.md"):
        response = upload(client, name, b"# Heading\nSam holds the key.", "text/plain")
        assert response.json()["status"] == "parsed"


def test_stored_path_is_opaque(client, db, settings, upload_dir) -> None:
    sign_in(client, db, settings, "sub-a", "alice@example.com")
    upload(client, "../../etc/passwd.txt", b"not really")
    row = db.execute("SELECT filename, stored_path FROM documents").fetchone()
    assert row["filename"] == "passwd.txt"
    assert len(row["stored_path"]) == 32 and "/" not in row["stored_path"]
    assert (upload_dir / row["stored_path"]).is_file()


def test_pdf_without_text_fails_but_row_and_file_remain(client, db, settings, upload_dir) -> None:
    sign_in(client, db, settings, "sub-a", "alice@example.com")
    response = upload(client, "scan.pdf", make_pdf([None]))
    assert response.status_code == 201
    assert response.json()["status"] == "failed"
    assert response.json()["error"] == "No text could be extracted"
    assert count_rows(db) == 1
    assert len(stored_files(upload_dir)) == 1


def test_empty_docx_fails(client, db, settings) -> None:
    sign_in(client, db, settings, "sub-a", "alice@example.com")
    response = upload(client, "blank.docx", make_docx([]))
    assert response.json()["status"] == "failed"
    assert response.json()["error"] == "No text could be extracted"


def test_corrupt_pdf_fails_with_parse_error(client, db, settings, upload_dir) -> None:
    sign_in(client, db, settings, "sub-a", "alice@example.com")
    response = upload(client, "broken.pdf", b"%PDF-1.4 garbage")
    assert response.status_code == 201
    assert response.json()["status"] == "failed"
    assert response.json()["error"]
    assert len(stored_files(upload_dir)) == 1


def test_pptx_and_html_are_parsed_to_markdown(client, db, settings) -> None:
    sign_in(client, db, settings, "sub-a", "alice@example.com")
    slides = upload(client, "deck.pptx", make_pptx(["Sam holds the warehouse key"]))
    page = upload(client, "page.html", b"<html><body><h2>Keys</h2><p>Sam.</p></body></html>")
    for response in (slides, page):
        assert response.status_code == 201, response.text
        assert response.json()["status"] == "parsed"
    detail = client.get(f"/documents/{page.json()['id']}").json()
    assert detail["extracted_text"].startswith("## Keys")  # stored as Markdown


def test_corrupt_pptx_is_rejected_and_not_stored(client, db, settings, upload_dir) -> None:
    sign_in(client, db, settings, "sub-a", "alice@example.com")
    response = upload(client, "slides.pptx", b"PK\x03\x04")
    assert response.status_code == 422
    assert count_rows(db) == 0
    assert stored_files(upload_dir) == []


def test_disallowed_type_is_rejected_and_not_stored(client, db, settings, upload_dir) -> None:
    sign_in(client, db, settings, "sub-a", "alice@example.com")
    for name in ("archive.zip", "photo.png", "old.doc", "talk.mp3"):
        response = upload(client, name, b"PK\x03\x04")
        assert response.status_code == 415
    assert count_rows(db) == 0
    assert stored_files(upload_dir) == []


def test_over_20_mb_is_rejected_and_not_stored(client, db, settings, upload_dir) -> None:
    sign_in(client, db, settings, "sub-a", "alice@example.com")
    response = upload(client, "big.txt", b"a" * (MAX_UPLOAD_BYTES + 1), "text/plain")
    assert response.status_code == 413
    assert count_rows(db) == 0
    assert stored_files(upload_dir) == []


def test_exactly_20_mb_is_accepted(client, db, settings) -> None:
    sign_in(client, db, settings, "sub-a", "alice@example.com")
    response = upload(client, "edge.txt", b"a" * MAX_UPLOAD_BYTES, "text/plain")
    assert response.status_code == 201
    assert response.json()["status"] == "parsed"


def test_pdf_over_20_pages_is_rejected_and_not_stored(
    client, db, settings, upload_dir, monkeypatch
) -> None:
    sign_in(client, db, settings, "sub-a", "alice@example.com")

    # The pypdf page count must reject the file before MarkItDown is ever called.
    def no_conversion(*_args, **_kwargs):
        raise AssertionError("MarkItDown ran on an over-cap PDF")

    monkeypatch.setattr(MarkItDownParser, "extract_text", no_conversion)
    response = upload(client, "long.pdf", make_pdf([f"page {i}" for i in range(21)]))
    assert response.status_code == 422
    assert "20" in response.json()["detail"]
    assert count_rows(db) == 0
    assert stored_files(upload_dir) == []


def test_pdf_with_20_pages_is_accepted(client, db, settings) -> None:
    sign_in(client, db, settings, "sub-a", "alice@example.com")
    response = upload(client, "twenty.pdf", make_pdf([f"page {i}" for i in range(20)]))
    assert response.json()["status"] == "parsed"


def test_second_upload_does_not_touch_the_first(client, db, settings) -> None:
    sign_in(client, db, settings, "sub-a", "alice@example.com")
    first = upload(client, "one.txt", b"first file").json()
    before = db.execute("SELECT * FROM documents WHERE id = %s", (first["id"],)).fetchone()
    upload(client, "two.txt", b"second file")
    after = db.execute("SELECT * FROM documents WHERE id = %s", (first["id"],)).fetchone()
    assert before == after


def test_delete_library_clears_only_that_account(app, db, settings, upload_dir) -> None:
    alice, bob = make_client(app), make_client(app)
    sign_in(alice, db, settings, "sub-a", "alice@example.com")
    sign_in(bob, db, settings, "sub-b", "bob@example.com")
    upload(alice, "alice.txt", b"Alice's notes")
    bob_doc = upload(bob, "bob.txt", b"Bob's private notes").json()

    assert alice.delete("/documents").status_code == 204
    assert alice.get("/documents").json() == []
    assert bob.get(f"/documents/{bob_doc['id']}").json()["extracted_text"] == "Bob's private notes"
    assert len(stored_files(upload_dir)) == 1


def test_delete_removes_row_and_file(client, db, settings, upload_dir) -> None:
    sign_in(client, db, settings, "sub-a", "alice@example.com")
    doc = upload(client, "one.txt", b"first file").json()
    assert client.delete(f"/documents/{doc['id']}").status_code == 204
    assert count_rows(db) == 0
    assert stored_files(upload_dir) == []
    assert client.get(f"/documents/{doc['id']}").status_code == 404


def test_unknown_or_malformed_id_is_404(client, db, settings) -> None:
    sign_in(client, db, settings, "sub-a", "alice@example.com")
    assert client.get("/documents/00000000-0000-0000-0000-000000000000").status_code == 404
    assert client.get("/documents/not-a-uuid").status_code == 404
    assert client.delete("/documents/not-a-uuid").status_code == 404


def test_user_a_cannot_see_or_delete_user_b_documents(app, db, settings, upload_dir) -> None:
    alice, bob = make_client(app), make_client(app)
    sign_in(alice, db, settings, "sub-a", "alice@example.com")
    sign_in(bob, db, settings, "sub-b", "bob@example.com")

    bob_doc = upload(bob, "bob.txt", b"Bob's private notes").json()

    assert alice.get("/documents").json() == []
    assert alice.get(f"/documents/{bob_doc['id']}").status_code == 404
    assert alice.delete(f"/documents/{bob_doc['id']}").status_code == 404

    # Bob's row and file are untouched.
    assert bob.get(f"/documents/{bob_doc['id']}").json()["extracted_text"] == "Bob's private notes"
    assert len(stored_files(upload_dir)) == 1
    assert [d["id"] for d in bob.get("/documents").json()] == [bob_doc["id"]]


def test_library_json_includes_triples_kept(client, db, settings) -> None:
    sign_in(client, db, settings, "sub-a", "alice@example.com")
    upload(client, "one.txt", b"first file")
    [row] = client.get("/documents").json()
    assert row["triples_kept"] == 0


class _FakeChat:
    """API-shaped extraction chat: one triple per passage, quoting that passage."""

    model = "fake-api"

    def complete(self, system: str, user: str, **_kwargs) -> str:
        verdict = keep_all_verdict(user)
        if verdict is not None:
            return verdict
        sentence = user.split(". ")[1] + "."  # a whole sentence, never cut at a chunk edge
        subject, _, rest = sentence.partition(" holds ")
        triple = {"subject": subject, "predicate": "holds", "object": rest, "quote": sentence}
        return json.dumps({"entities": [], "triples": [triple]})


@pytest.fixture
def offline_build(app, monkeypatch: pytest.MonkeyPatch) -> MemoryGraphStore:
    """Run the real build route and background thread with no model and no Neo4j."""
    graph = MemoryGraphStore()

    class Driver:
        def close(self) -> None:
            pass

    monkeypatch.setattr(documents_routes, "make_chat", lambda choice: _FakeChat())
    monkeypatch.setattr(documents_routes, "make_embedder", lambda choice: HashingEmbedder())
    monkeypatch.setattr(documents_routes.GraphDatabase, "driver", lambda *a, **k: Driver())
    monkeypatch.setattr(documents_routes, "Neo4jGraphStore", lambda driver: graph)
    app.state.neo4j = Driver()  # the route only checks that a driver exists
    return graph


def _wait_for_build(client, document_id: str) -> dict:
    for _ in range(100):
        row = next(d for d in client.get("/documents").json() if d["id"] == document_id)
        if row["status"] not in ("waiting", "extracting"):
            return row
        time.sleep(0.05)
    raise AssertionError("build did not finish")


def test_build_stores_chunks_and_counts_triples_kept(
    client, db, settings, offline_build: MemoryGraphStore
) -> None:
    user = sign_in(client, db, settings, "sub-a", "alice@example.com")
    text = " ".join(f"Person {i} holds key {i}." for i in range(600))  # several chunks
    doc = upload(client, "keys.txt", text.encode(), "text/plain").json()

    assert client.post(f"/documents/{doc['id']}/build").status_code == 200
    row = _wait_for_build(client, doc["id"])

    assert row["status"] == "ready", row["error"]
    chunks = [chunk.text for chunk in build_chunks(text)]
    stored = db.execute(
        "SELECT ordinal, text, user_id FROM document_chunks WHERE document_id = %s "
        "ORDER BY ordinal",
        (doc["id"],),
    ).fetchall()
    assert [r["text"] for r in stored] == chunks
    assert [r["ordinal"] for r in stored] == list(range(len(chunks)))
    assert {r["user_id"] for r in stored} == {user["id"]}

    triples = offline_build.subgraph(str(user["id"])).triples
    assert row["triples_kept"] == len(triples) == len(chunks)
    assert all(t.quote in chunks[t.chunk_ordinal] for t in triples)
    assert row["build_done"] == row["build_total"] == len(chunks)

    # The chunk reader the ask route binds is scoped to the owner.
    assert repository.chunk_texts(db, user["id"], doc["id"]) == dict(enumerate(chunks))
    bob = upsert_user(db, "sub-b", "bob@example.com", "Bob")
    assert repository.chunk_texts(db, bob["id"], doc["id"]) == {}
    assert repository.chunk_texts(db, user["id"], "not-a-uuid") == {}


def test_ask_keeps_its_shape_and_reads_the_stored_chunks(
    client, db, settings, offline_build: MemoryGraphStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /ask through create_agent, with a scripted Kimi host and no Neo4j."""
    user = sign_in(client, db, settings, "sub-a", "alice@example.com")
    text = " ".join(f"Person {i} holds key {i}." for i in range(600))
    doc = upload(client, "keys.txt", text.encode(), "text/plain").json()
    client.post(f"/documents/{doc['id']}/build")
    assert _wait_for_build(client, doc["id"])["status"] == "ready"

    class Store:
        def __init__(self, driver) -> None:
            pass

        def load_user(self, user_id: str) -> MemoryGraphStore:
            assert user_id == str(user["id"])
            return offline_build

    def tool_call(name: str, arguments: dict) -> dict:
        function = {"name": name, "arguments": json.dumps(arguments)}
        return {
            "content": "",
            "tool_calls": [{"id": name, "type": "function", "function": function}],
        }

    replies = [
        tool_call("search_graph", {"query": "Who holds key 7?"}),
        tool_call("read_document", {"document_id": doc["id"]}),
        {"content": "Person 7 holds key 7."},
    ]
    sent: list[dict] = []

    def urlopen(request, timeout):
        sent.append(json.loads(request.data))
        reply = {"choices": [{"message": replies.pop(0)}]}
        return io.BytesIO(json.dumps(reply).encode())

    monkeypatch.setattr(ask_routes, "Neo4jGraphStore", Store)
    monkeypatch.setattr(ask_routes, "make_embedder", lambda choice: HashingEmbedder())
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)

    response = client.post(
        "/ask",
        json={
            "question": "Who holds key 7?",
            # The test embedder has no model name, so the graph counts as the legacy default.
            "model": DEFAULT_MODEL,
            "api_key": "sk-embed",
            "agent": {"api_key": "sk-test"},
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {
        "answer",
        "tool_calls_used",
        "trace",
        "highlight_entity_ids",
        "highlight_relationship_ids",
    }
    assert body["answer"] == "Person 7 holds key 7."
    assert body["tool_calls_used"] == 2
    assert [entry["name"] for entry in body["trace"]] == ["search_graph", "read_document"]
    # The read observation is a stored chunk row, read from Postgres for this user.
    stored = repository.chunk_texts(db, user["id"], doc["id"])
    assert any(chunk in sent[-1]["messages"][-1]["content"] for chunk in stored.values())
    assert all(str(user["id"]) not in json.dumps(request) for request in sent)


def test_delete_removes_the_stored_chunks(
    client, db, settings, offline_build: MemoryGraphStore
) -> None:
    sign_in(client, db, settings, "sub-a", "alice@example.com")
    doc = upload(client, "keys.txt", b"Intro. Sam holds the key. Outro.", "text/plain").json()
    client.post(f"/documents/{doc['id']}/build")
    assert _wait_for_build(client, doc["id"])["status"] == "ready"
    assert db.execute("SELECT count(*) AS n FROM document_chunks").fetchone()["n"] == 1

    assert client.delete(f"/documents/{doc['id']}").status_code == 204
    assert db.execute("SELECT count(*) AS n FROM document_chunks").fetchone()["n"] == 0


class _GateChat(_FakeChat):
    """Blocks inside the model call so a test can see who is extracting."""

    def __init__(self, release: threading.Event) -> None:
        self.release = release
        self.began = threading.Event()

    def complete(self, system: str, user: str, **kwargs) -> str:
        self.began.set()
        assert self.release.wait(5), "build stayed blocked"
        return super().complete(system, user, **kwargs)


def _patch_gated_build(app, monkeypatch: pytest.MonkeyPatch, release: threading.Event) -> list:
    chats: list[_GateChat] = []

    def make_chat(_choice) -> _GateChat:
        chat = _GateChat(release)
        chats.append(chat)
        return chat

    class Driver:
        def close(self) -> None:
            pass

    monkeypatch.setattr(documents_routes, "make_chat", make_chat)
    monkeypatch.setattr(documents_routes, "make_embedder", lambda choice: HashingEmbedder())
    monkeypatch.setattr(documents_routes.GraphDatabase, "driver", lambda *a, **k: Driver())
    monkeypatch.setattr(documents_routes, "Neo4jGraphStore", lambda driver: MemoryGraphStore())
    app.state.neo4j = Driver()
    return chats


def test_two_accounts_extract_together_and_the_third_waits(
    app, db, settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = threading.Event()
    chats = _patch_gated_build(app, monkeypatch, release)
    alice, bob, cara = make_client(app), make_client(app), make_client(app)
    sign_in(alice, db, settings, "sub-a", "alice@example.com")
    sign_in(bob, db, settings, "sub-b", "bob@example.com")
    sign_in(cara, db, settings, "sub-c", "cara@example.com")
    text = " ".join(f"Person {i} holds key {i}." for i in range(30)).encode()
    alice_doc = upload(alice, "a.txt", text, "text/plain").json()
    bob_doc = upload(bob, "b.txt", text, "text/plain").json()
    cara_doc = upload(cara, "c.txt", text, "text/plain").json()

    assert alice.post(f"/documents/{alice_doc['id']}/build").status_code == 200
    assert chats[0].began.wait(5)
    assert bob.post(f"/documents/{bob_doc['id']}/build").json()["status"] == "extracting"
    assert chats[1].began.wait(5)
    waiting = cara.post(f"/documents/{cara_doc['id']}/build")
    assert waiting.status_code == 200, waiting.text
    assert waiting.json()["status"] == "waiting"
    assert chats[0].began.is_set() and chats[1].began.is_set()
    assert not chats[2].began.is_set()

    release.set()
    alice_row = _wait_for_build(alice, alice_doc["id"])
    assert alice_row["status"] == "ready", alice_row["error"]
    bob_row = _wait_for_build(bob, bob_doc["id"])
    assert bob_row["status"] == "ready", bob_row["error"]
    cara_row = _wait_for_build(cara, cara_doc["id"])
    assert cara_row["status"] == "ready", cara_row["error"]


def test_one_account_builds_one_file_at_a_time(
    app, db, settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = threading.Event()
    chats = _patch_gated_build(app, monkeypatch, release)
    alice = make_client(app)
    sign_in(alice, db, settings, "sub-a", "alice@example.com")
    # Different wording from the other queue test. The extraction cache is shared, so the
    # same passage would skip the model call and the gate would never open.
    passage = " ".join(f"Item {i} holds box {i}." for i in range(30)).encode()
    first = upload(alice, "a.txt", passage, "text/plain").json()
    second = upload(alice, "b.txt", passage, "text/plain").json()

    assert alice.post(f"/documents/{first['id']}/build").json()["status"] == "extracting"
    assert chats[0].began.wait(5)
    queued = alice.post(f"/documents/{second['id']}/build")
    assert queued.json()["status"] == "waiting"
    assert chats[0].began.is_set()
    assert not chats[1].began.is_set()

    stopped = alice.post(f"/documents/{second['id']}/stop")
    assert stopped.json()["status"] == "failed"
    assert stopped.json()["error"] == "stopped"

    release.set()
    first_row = _wait_for_build(alice, first["id"])
    assert first_row["status"] == "ready", first_row["error"]
    assert alice.get("/documents").json()
    second_row = next(row for row in alice.get("/documents").json() if row["id"] == second["id"])
    assert second_row["status"] == "failed"


def test_a_restart_fails_an_unfinished_build(db) -> None:
    from jewel.auth.users import upsert_user as add_user
    from jewel.documents import repository as repo

    user = add_user(db, "sub-a", "alice@example.com", "Alice")
    document_id = repo.insert_document(db, user["id"], "a.txt", "text/plain", "ab" * 16)
    repo.mark_waiting(db, document_id)
    fail_interrupted(db)
    row = repo.get_document(db, user["id"], document_id)
    assert row is not None
    assert row["status"] == "failed"
    assert row["error"] == RESTART_ERROR


def test_upload_limit_returns_429(app, db, settings) -> None:
    app.state.limits = RateLimiter({"upload": (2, 3600)})
    client = make_client(app)
    sign_in(client, db, settings, "sub-a", "alice@example.com")
    assert upload(client, "a.txt", b"Sam holds the key.", "text/plain").status_code == 201
    assert upload(client, "b.txt", b"Ada holds the map.", "text/plain").status_code == 201
    rejected = upload(client, "c.txt", b"Bea holds the book.", "text/plain")
    assert rejected.status_code == 429
    assert "uploads" in rejected.json()["detail"]
    # The cap is per account. Bob still has his own two uploads.
    bob = make_client(app)
    sign_in(bob, db, settings, "sub-b", "bob@example.com")
    assert upload(bob, "bob.txt", b"Bob holds the lamp.", "text/plain").status_code == 201


def test_a_second_click_while_building_does_not_spend_the_build_limit(
    app, db, settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = threading.Event()
    _patch_gated_build(app, monkeypatch, release)
    calls: list[str] = []
    limiter = RateLimiter({"build": (1, 3600)})
    real_check = limiter.check

    def spy(user_id: str, action: str) -> None:
        calls.append(action)
        real_check(user_id, action)

    limiter.check = spy  # type: ignore[method-assign]
    app.state.limits = limiter
    alice = make_client(app)
    sign_in(alice, db, settings, "sub-a", "alice@example.com")
    passage = " ".join(f"Crate {i} holds reel {i}." for i in range(30)).encode()
    doc = upload(alice, "a.txt", passage, "text/plain").json()

    assert alice.post(f"/documents/{doc['id']}/build").json()["status"] == "extracting"
    again = alice.post(f"/documents/{doc['id']}/build")
    assert again.status_code == 409
    assert calls.count(BUILD) == 1

    release.set()
    assert _wait_for_build(alice, doc["id"])["status"] == "ready"


def test_build_limit_returns_429(app, db, settings, offline_build: MemoryGraphStore) -> None:
    app.state.limits = RateLimiter({"build": (1, 3600)})
    client = make_client(app)
    sign_in(client, db, settings, "sub-a", "alice@example.com")
    passage = " ".join(f"Drawer {i} holds coin {i}." for i in range(30)).encode()
    first = upload(client, "a.txt", passage, "text/plain").json()
    second = upload(client, "b.txt", passage, "text/plain").json()
    assert client.post(f"/documents/{first['id']}/build").status_code == 200
    rejected = client.post(f"/documents/{second['id']}/build")
    assert rejected.status_code == 429
    assert "builds" in rejected.json()["detail"]
    assert _wait_for_build(client, first["id"])["status"] == "ready", "first build"


def _ask_body() -> dict:
    return {
        "question": "Who holds the key?",
        "model": DEFAULT_MODEL,
        "api_key": "sk-embed",
        "agent": {"api_key": "sk-test"},
    }


def test_an_empty_graph_does_not_spend_the_ask_limit(
    app, db, settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    app.state.limits = RateLimiter({"ask": (1, 3600)})
    app.state.neo4j = object()

    class Store:
        def __init__(self, driver) -> None:
            pass

        def load_user(self, user_id: str) -> MemoryGraphStore:
            return MemoryGraphStore()

    monkeypatch.setattr(ask_routes, "Neo4jGraphStore", Store)
    client = make_client(app)
    sign_in(client, db, settings, "sub-a", "alice@example.com")
    assert client.post("/ask", json=_ask_body()).status_code == 409
    # A second try is still "build something first", not the hourly cap.
    assert client.post("/ask", json=_ask_body()).status_code == 409


def test_ask_limit_returns_429(app, db, settings, monkeypatch: pytest.MonkeyPatch) -> None:
    app.state.limits = RateLimiter({"ask": (1, 3600)})
    app.state.neo4j = object()

    class Doc:
        embedding_model = DEFAULT_MODEL

    class Store:
        def __init__(self, driver) -> None:
            self.documents = {"one": Doc()}

        def load_user(self, user_id: str) -> "Store":
            return self

    def answer(**kwargs) -> AgentResult:
        return AgentResult(
            question=kwargs["question"],
            user_id=kwargs["user_id"],
            as_of=datetime.now(UTC),
            answer="The key is in the drawer.",
        )

    monkeypatch.setattr(ask_routes, "Neo4jGraphStore", Store)
    monkeypatch.setattr(ask_routes, "make_embedder", lambda choice: HashingEmbedder())
    monkeypatch.setattr(ask_routes, "run_agent", answer)
    client = make_client(app)
    sign_in(client, db, settings, "sub-a", "alice@example.com")
    assert client.post("/ask", json=_ask_body()).status_code == 200
    rejected = client.post("/ask", json=_ask_body())
    assert rejected.status_code == 429
    assert "questions" in rejected.json()["detail"]
