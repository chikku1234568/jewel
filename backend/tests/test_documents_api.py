"""Document routes against a real Postgres and a temporary upload directory."""

from pathlib import Path

from jewel.documents.models import DOCX_MEDIA_TYPE, MAX_UPLOAD_BYTES
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
        set(d) == {"id", "filename", "uploaded_at", "status", "error", "build_done", "build_total"}
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
