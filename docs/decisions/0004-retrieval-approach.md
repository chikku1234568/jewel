# 0004. Retrieval: HippoRAG-2-inspired temporal Personalized PageRank

> **Superseded (2026-09-28)** by [0012](0012-retrieval-graph-ppr.md). Retrieval is now settled by the product spec. Kept for history only; not part of the active decision set.

- **Status:** Superseded by [0012](0012-retrieval-graph-ppr.md) on 2026-09-28 (previously: Proposed. **Zeus's suggestion, pending user input.** Srikar will bring his)
  own ideas on dynamic retrievers; this ADR is a starting point, not a decision.

## Context

KG construction via LLM `(e1, r, e2)` triple extraction is standard. Retrieval is the
interesting part. User constraints: dynamic, query-time, **no training, no GNNs**; not a
latency-first framework like Graphiti; must respect temporal validity (only relationships
valid at the query time). The showcase must beat naive RAG on a question whose key
evidence (the lab) never names the drug.

## Suggested design

Adapt **HippoRAG 2** (Gutiérrez et al., "From RAG to Memory: Non-Parametric Continual
Learning for Large Language Models", ICML 2025, arXiv:2502.14802; code:
github.com/OSU-NLP-Group/HippoRAG) and make every step time-aware:

1. Extract query entities (LLM) and link them to KG nodes (Neo4j vector index).
2. Restrict to relationships valid at `t_query`.
3. Retrieve top-k valid triples by embedding similarity to the query.
4. **Recognition memory:** an LLM keeps only relevant triples.
5. Seed weights: phrase nodes from the filtered triples; `:Episode` passage nodes weighted
   by query similarity and down-weighted (HippoRAG 2 uses a small passage weight factor).
6. **Personalized PageRank** over the time-valid subgraph plus passage nodes.
7. Return ranked facts/relationships/episodes with provenance (raw text on `:Episode`).
8. Generate the answer, stating the as-of time.

See `docs/architecture.md` section 7 for the pipeline diagram.

### Sub-question: where PPR runs

- **A. Neo4j Graph Data Science:** project only time-valid relationships, then
  `gds.pageRank.stream` with `sourceNodes` given as `[[node, bias], ...]` (biased
  personalized PageRank is documented). GDS Community Edition is free, includes all
  algorithms, and is limited to 4 CPU cores; the Neo4j-built jar also contains closed-source
  components, while the open sources build as GPLv3 "OpenGDS". Installed in Docker via
  `NEO4J_PLUGINS='["graph-data-science"]'` (GDS version must match the Neo4j version).
- **B. Python:** pull the time-valid subgraph and run networkx `pagerank(personalization=...)`
  or python-igraph. Simplest at demo size.

## Other dynamic, training-free options to consider

- **HippoRAG (v1)** (NeurIPS 2024, arXiv:2405.14831): PPR from query entities over an
  entity graph, no passage nodes or recognition filter.
- **LightRAG** (Guo et al., arXiv:2410.05779): dual-level retrieval (low-level entities and
  relations, high-level themes) combining graph and vectors; incremental updates.
- **Think-on-Graph** (Sun et al., ICLR 2024): LLM-guided iterative beam search over the KG;
  training-free; more LLM calls per query. A temporal variant would only expand along
  relationships valid at `t_query`.
- **Temporal propagation / path search** ideas from recent temporal GraphRAG papers, e.g.
  STAR-RAG (arXiv:2510.16715, PPR over a time-aligned rule graph, training-free) and DyG-RAG
  (arXiv:2507.13396, time-aware random walks over an event graph).

## Consequences (if adopted)

- More LLM calls per query than naive RAG (NER + recognition filter + answer); mitigated by
  the Redis cache.
- Temporal correctness comes from filtering the graph, not from prompting, which is exactly
  what the showcase needs to demonstrate.

## Open questions for review

1. Which retriever(s) does Srikar want to try? Should the code support pluggable retrievers
   so several can be compared side by side with the naive baseline?
2. PPR in Neo4j GDS or in Python?
3. Keep open `RELATED_TO` triples and `:Entity` phrase nodes alongside the typed clinical
   schema, or retrieve over the typed schema only?
4. Should retrieval also expose a `t_query` slider in the UI ("what was valid at time X")?
