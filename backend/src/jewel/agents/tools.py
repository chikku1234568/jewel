"""Agent tools (stub). These two, and only these.

* ``search_graph(query: str, as_of: datetime | None)``: runs the retriever
  (``jewel.retrieval.hippo.pipeline``) on the signed-in user's subgraph. Returns ranked
  entities, ``RELATED_TO`` relationships (predicate, endpoints, quote, document id, times)
  and cited document passages. Emits a highlight event with the returned ids.
* ``read_document(document_id: str, span: tuple[int, int] | None)``: returns text from a
  document. Refuses ids that ``search_graph`` did not return in this run and ids the user
  does not own.

User id and API key are injected by the application, never by the model.
"""
