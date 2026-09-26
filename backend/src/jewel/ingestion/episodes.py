"""Episode model and ingestion service (stub).

TODO(step-N):
* ``Episode`` Pydantic model: id, source_kind (paste | document), author, authored_at,
  ingested_at, raw_text, content_hash.
* ``ingest_text(...)`` and ``ingest_document(...)`` (the latter via ``jewel.parsing``).
* Persist the raw text as an ``:Episode`` node in Neo4j so every edge can cite its episode.
"""
