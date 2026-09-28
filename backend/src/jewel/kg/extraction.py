"""Entity and triple extraction with the user's key (stub).

The model returns JSON validated into this schema (data, never code or Cypher):

* Entity: ``name`` (surface form), ``type`` in ``person | organization | place |
  concept | other``.
* Triple: ``subject`` and ``object`` (entity names), ``predicate`` (short phrase, stored as
  a property), ``quote`` (span copied from the document text), optional character offsets.

TODO(later pass): prompt, Pydantic validation, and dropping triples whose quote does not
occur in the extracted text.
"""
