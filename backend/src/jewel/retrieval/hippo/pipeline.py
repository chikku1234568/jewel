"""Retriever behind ``search_graph``.

Runs on one user's subgraph. PageRank uses the graph as it is at question time, so a
document written after an earlier one is visible on the next question without
reprocessing the earlier document.
"""

from dataclasses import dataclass
from datetime import datetime

from jewel.kg.memory_store import MemoryGraphStore
from jewel.kg.records import GraphDocument, GraphTriple
from jewel.kg.temporal import is_valid_at
from jewel.llm.base import ChatModel, EmbeddingModel
from jewel.retrieval.ask_log import log_event
from jewel.retrieval.hippo.linking import cosine, top_matches
from jewel.retrieval.hippo.ppr import personalized_pagerank, statement_graph
from jewel.retrieval.hippo.recognition import filter_triples

_TOP_K = 8
# Facts the walk adds beyond the similarity hits. A name with many facts does not
# empty the whole neighborhood into the prompt.
_EXTRA_K = 8


@dataclass(frozen=True)
class RankedDocument:
    document_id: str
    filename: str
    passage: str
    score: float


@dataclass(frozen=True)
class RetrievalResult:
    documents: list[RankedDocument]
    triples: list[GraphTriple]
    entity_ids: list[str]
    relationship_ids: list[str]


def retrieve(
    store: MemoryGraphStore,
    embedder: EmbeddingModel,
    user_id: str,
    query: str,
    as_of: datetime,
    chat: ChatModel | None = None,
) -> RetrievalResult:
    """Search ``user_id``'s graph. ``chat`` filters triples and does not answer."""
    subgraph = store.subgraph(user_id)
    embed_query = getattr(embedder, "embed_query", None)
    query_vector = embed_query(query) if embed_query else embedder.embed([query])[0]
    triples = [
        triple
        for triple in subgraph.triples
        if is_valid_at(triple.valid_at, triple.invalid_at, as_of)
    ]
    ranked = top_matches(
        query_vector,
        [(triple.id, triple.embedding) for triple in triples],
        _TOP_K,
    )
    by_id = {triple.id: triple for triple in triples}
    chosen = [by_id[triple_id] for triple_id, _score in ranked]
    if chat is not None:
        chosen = filter_triples(query, chosen, chat)
    if not chosen:
        log_event({"event": "search", "query": query, "fallback": "documents", "facts": []})
        return _dense_fallback(subgraph.documents, query_vector)
    seed_ids = {triple.id for triple in chosen}
    personalization = {
        triple.id: max(cosine(query_vector, triple.embedding), 0.0) for triple in chosen
    }
    graph = statement_graph([entity.id for entity in subgraph.entities], triples)
    scores = personalized_pagerank(graph, personalization)
    extras = [
        triple
        for triple in triples
        if triple.id not in seed_ids and scores.get(triple.id, 0.0) > 0.0
    ]
    extras.sort(key=lambda triple: scores[triple.id], reverse=True)
    kept_extras = extras[:_EXTRA_K]
    returned = [*chosen, *kept_extras]
    documents = _rank_documents(subgraph.documents, returned, scores)
    similarity = dict(ranked)
    for triple in kept_extras:
        if triple.embedding:
            similarity[triple.id] = cosine(query_vector, triple.embedding)
    _log_search(query, subgraph.documents, chosen, kept_extras, extras, scores, similarity)
    return RetrievalResult(
        documents=documents,
        triples=returned,
        entity_ids=_seed_entities(chosen),
        relationship_ids=[triple.id for triple in returned],
    )


def _log_search(
    query: str,
    documents: list[GraphDocument],
    seeds: list[GraphTriple],
    extras: list[GraphTriple],
    candidates: list[GraphTriple],
    scores: dict[str, float],
    similarity: dict[str, float],
) -> None:
    """Record which returned facts were similarity hits and which the walk added."""
    filenames = {document.id: document.filename for document in documents}
    seed_entities = set(_seed_entities(seeds))

    def row(triple: GraphTriple, role: str) -> dict:
        ends = {triple.source_id, triple.target_id}
        return {
            "role": role,
            "predicate": triple.predicate,
            "file": filenames.get(triple.document_id, triple.document_id),
            "chunk": triple.chunk_ordinal,
            "similarity": round(similarity.get(triple.id, 0.0), 4),
            "ppr": round(scores.get(triple.id, 0.0), 6),
            "shares_seed_entity": bool(ends & seed_entities),
        }

    log_event(
        {
            "event": "search",
            "query": query,
            "seed_count": len(seeds),
            "extra_candidates": len(candidates),
            "extras_kept": len(extras),
            "facts": [row(triple, "seed") for triple in seeds]
            + [row(triple, "extra") for triple in extras],
        }
    )


def _seed_entities(triples: list[GraphTriple]) -> list[str]:
    seen: list[str] = []
    for triple in triples:
        for entity_id in (triple.source_id, triple.target_id):
            if entity_id not in seen:
                seen.append(entity_id)
    return seen


def _dense_fallback(documents: list[GraphDocument], query_vector: list[float]) -> RetrievalResult:
    scored = [
        (document, max(cosine(query_vector, document.embedding), 0.0)) for document in documents
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    ranked = [
        RankedDocument(document.id, document.filename, document.text, score)
        for document, score in scored
        if score > 0
    ]
    return RetrievalResult(documents=ranked, triples=[], entity_ids=[], relationship_ids=[])


def _rank_documents(
    documents: list[GraphDocument],
    triples: list[GraphTriple],
    scores: dict[str, float],
) -> list[RankedDocument]:
    """Files that own a returned fact, highest total fact-weight first."""
    totals: dict[str, float] = {}
    for triple in triples:
        weight = scores.get(triple.id, 0.0)
        totals[triple.document_id] = totals.get(triple.document_id, 0.0) + weight
    by_id = {document.id: document for document in documents}
    ranked = [
        RankedDocument(document_id, by_id[document_id].filename, by_id[document_id].text, score)
        for document_id, score in totals.items()
        if document_id in by_id and score > 0.0
    ]
    ranked.sort(key=lambda item: item.score, reverse=True)
    return ranked
