"""Document routes against a real Postgres and a temporary upload directory."""

import json
import time
from pathlib import Path

import pytest

from jewel.api.routes import documents as documents_routes
from jewel.auth.users import upsert_user
from jewel.documents import repository
from jewel.documents.models import DOCX_MEDIA_TYPE, MAX_UPLOAD_BYTES
from jewel.ingestion.chunking import chunk_text
from jewel.kg.memory_store import MemoryGraphStore
from jewel.llm.hashing import HashingEmbedder
from jewel.parsing.markdown import MarkItDownParser
from tests.conftest import make_client, sign_in
from tests.fixtures import make_docx, make_pdf, make_pptx


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


def test_corrupt_pptx_fails_but_row_and_file_remain(client, db, settings, upload_dir) -> None:
    sign_in(client, db, settings, "sub-a", "alice@example.com")
    response = upload(client, "slides.pptx", b"PK\x03\x04")
    assert response.status_code == 201
    assert response.json()["status"] == "failed"
    assert response.json()["error"] == "Could not read this .pptx file"
    assert count_rows(db) == 1
    assert len(stored_files(upload_dir)) == 1


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


def test_pdf_over_50_pages_is_rejected_and_not_stored(
    client, db, settings, upload_dir, monkeypatch
) -> None:
    sign_in(client, db, settings, "sub-a", "alice@example.com")

    # The pypdf page count must reject the file before MarkItDown is ever called.
    def no_conversion(*_args, **_kwargs):
        raise AssertionError("MarkItDown ran on an over-cap PDF")

    monkeypatch.setattr(MarkItDownParser, "extract_text", no_conversion)
    response = upload(client, "long.pdf", make_pdf([f"page {i}" for i in range(51)]))
    assert response.status_code == 422
    assert "50" in response.json()["detail"]
    assert count_rows(db) == 0
    assert stored_files(upload_dir) == []


def test_pdf_with_50_pages_is_accepted(client, db, settings) -> None:
    sign_in(client, db, settings, "sub-a", "alice@example.com")
    response = upload(client, "fifty.pdf", make_pdf([f"page {i}" for i in range(50)]))
    assert response.json()["status"] == "parsed"


def test_second_upload_does_not_touch_the_first(client, db, settings) -> None:
    sign_in(client, db, settings, "sub-a", "alice@example.com")
    first = upload(client, "one.txt", b"first file").json()
    before = db.execute("SELECT * FROM documents WHERE id = %s", (first["id"],)).fetchone()
    upload(client, "two.txt", b"second file")
    after = db.execute("SELECT * FROM documents WHERE id = %s", (first["id"],)).fetchone()
    assert before == after


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
        if row["status"] != "extracting":
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
    chunks = [chunk.text for chunk in chunk_text(text, size=3500, overlap=200)]
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
