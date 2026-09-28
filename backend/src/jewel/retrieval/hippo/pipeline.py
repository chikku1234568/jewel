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
from jewel.retrieval.hippo.linking import cosine, top_matches
from jewel.retrieval.hippo.ppr import PASSAGE_PRIOR, personalized_pagerank, walk_graph
from jewel.retrieval.hippo.recognition import filter_triples

_TOP_K = 8


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
    mentions = [
        mention
        for mention in subgraph.mentions
        if is_valid_at(mention.valid_at, mention.invalid_at, as_of)
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
        return _dense_fallback(subgraph.documents, query_vector)
    frequency: dict[str, set[str]] = {}
    for mention in mentions:
        frequency.setdefault(mention.entity_id, set()).add(mention.document_id)
    seed_sum: dict[str, float] = {}
    seed_count: dict[str, int] = {}
    for triple in chosen:
        score = max(cosine(query_vector, triple.embedding), 0.0)
        for entity_id in (triple.source_id, triple.target_id):
            denom = max(len(frequency.get(entity_id, ())), 1)
            seed_sum[entity_id] = seed_sum.get(entity_id, 0.0) + score / denom
            seed_count[entity_id] = seed_count.get(entity_id, 0) + 1
    seeds = {entity_id: seed_sum[entity_id] / seed_count[entity_id] for entity_id in seed_sum}
    entity_ids = [entity.id for entity in subgraph.entities]
    document_ids = [document.id for document in subgraph.documents]
    edges: list[tuple[str, str, float]] = [
        (triple.source_id, triple.target_id, 1.0) for triple in triples
    ]
    edges.extend((mention.entity_id, mention.document_id, 1.0) for mention in mentions)
    graph = walk_graph(entity_ids, document_ids, edges)
    personalization = dict(seeds)
    for document in subgraph.documents:
        personalization[document.id] = PASSAGE_PRIOR * max(
            cosine(query_vector, document.embedding), 0.0
        )
    scores = personalized_pagerank(graph, personalization)
    documents = _rank_documents(subgraph.documents, scores)
    return RetrievalResult(
        documents=documents,
        triples=chosen,
        entity_ids=list(seeds),
        relationship_ids=[triple.id for triple in chosen],
    )


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
    documents: list[GraphDocument], scores: dict[str, float]
) -> list[RankedDocument]:
    ranked = [
        RankedDocument(document.id, document.filename, document.text, scores.get(document.id, 0.0))
        for document in documents
        if scores.get(document.id, 0.0) > 0
    ]
    ranked.sort(key=lambda item: item.score, reverse=True)
    return ranked
