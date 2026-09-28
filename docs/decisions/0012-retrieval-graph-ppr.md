# 0012. Retrieval: HippoRAG-2-inspired, time-aware Personalized PageRank in networkx

- **Status:** Accepted (settled by `docs/problem-statement.md`, 2026-09-28)
- **Supersedes:** [0004](0004-retrieval-approach.md)

## Decision

`search_graph` runs this pipeline on the signed-in user's subgraph only, with the
`user_id` constraint applied before similarity search and before the subgraph is pulled
into Python:

1. Link the question to the user's entities (embedding search on `:Entity`).
2. Keep relationships valid at the question time (default now; undated ones remain).
3. Rank candidate triples by similarity to the question; take a top-k.
4. Recognition memory (from HippoRAG 2): one model call with the user's key drops
   irrelevant triples. It filters; it does not answer.
5. Seed Personalized PageRank with the entities on the kept triples plus `Document`
   nodes weighted by similarity to the question and down-weighted relative to entities.
   PageRank runs in **networkx**. Neo4j Graph Data Science is not used.
6. Return ranked entities, `RELATED_TO` relationships (predicate, endpoints, quote,
   document id, times) and the cited documents with a passage of raw text.

Reference: Gutiérrez et al., "From RAG to Memory: Non-Parametric Continual Learning for
Large Language Models" (HippoRAG 2), arXiv:2502.14802.

## Consequences

- networkx is added as a dependency in the pass that implements this; it is not declared
  in the scaffold.
- No retriever comparison, trained retriever or GNN in this version. The only baseline is
  the on-demand text-search comparison.
