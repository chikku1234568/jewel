"""Ingestion pipeline orchestration (stub).

TODO(later pass): ``build_document(user_id, document_id)``:

1. Parse to text (``jewel.parsing``: PDF via ``DocumentParser``; txt/md read as text).
   Status ``parsing``.
2. Chunk the text for the text-search index only (``jewel.ingestion.chunking``).
3. Extract entities and triples with the user's key (``jewel.kg.extraction``), validated
   into the schema. Model output is data, never code or Cypher. Status ``extracting``.
4. Embed the document and each entity.
5. Write ``Document`` / ``Entity`` nodes and ``MENTIONS`` / ``RELATED_TO`` relationships,
   all carrying ``user_id`` (``jewel.kg.neo4j_store``). Status ``ready``.

Any failure sets ``failed`` with an error string and keeps the file; retry starts again.
"""
