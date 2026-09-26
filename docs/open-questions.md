# Open questions for Srikar

Decisions needed before (or during) the next steps. Already decided: **Neo4j 5.x
Community** for storage ([ADR 0002](decisions/0002-graph-store-neo4j.md)) and **Redis** for
caching ([ADR 0003](decisions/0003-cache-redis.md)).

## Retrieval (user input pending)

1. Which dynamic, training-free retriever(s) do you want to try? The HippoRAG-2-inspired
   temporal PPR is only Zeus's suggestion ([ADR 0004](decisions/0004-retrieval-approach.md)).
2. Should retrievers be pluggable so several can be compared against the naive baseline?
3. PPR location: Neo4j Graph Data Science (`gds.pageRank` with `sourceNodes`) or Python
   (networkx / igraph) over the time-filtered subgraph?
4. Keep open `(e1, r, e2)` triples and `:Entity` phrase nodes next to the typed clinical
   schema, or retrieve over the typed schema only?

## LangGraph design (user review pending)

5. Fixed sequential graph (recommended) vs supervisor? ([ADR 0007](decisions/0007-langgraph-orchestration.md))
6. Is `parse` a graph node (proposed) or done at upload time?
7. LangGraph checkpointing (resumable runs) needed?
8. SSE for progress events OK?

## Graph schema

9. Relationship endpoints (proposed in `architecture.md` section 5):
   `(Patient)-[:PRESCRIBED_DOSE]->(MedicationOrder)`,
   `(Patient)-[:HAS_BIOMARKER_VALUE]->(LabObservation)`,
   `(ClinicalProtocolRule)-[:CONTRAINDICATES]->(MedicationOrder)`,
   `(LabObservation)-[:TRIGGERS_SAFETY_HOLD]->(MedicationOrder)`,
   `(MedicationOrder)-[:REQUIRES_REVIEW]->(Patient)`. Confirm or change.
10. Is creatinine clearance given directly in the lab text, or computed (e.g.
    Cockcroft-Gault from creatinine, age, weight, sex)? If computed, which agent owns the
    calculation (proposal: Laboratory Monitor, deterministic code) and where do the inputs
    come from?
11. What is "now" in the demo: wall-clock time, or a pinned demo clock for reproducibility?

## Models and parsing

12. LLM provider and model for extraction / recognition filter / answers?
13. Embedding model (and dimension, needed for the Neo4j vector index)?
14. PDF parser: pypdf or pdfplumber to start, docling later if layouts get complex?

## Product and hosting

15. Frontend: Vite SPA (proposed) vs Next.js; Cytoscape.js vs react-force-graph; UI kit?
    ([ADR 0005](decisions/0005-frontend-framework.md))
16. Hosting and budget; what "private URL" must mean (shared password, SSO, unguessable
    link)? ([ADR 0006](decisions/0006-deployment.md))
17. Demo episodes: who writes the three synthetic notes, and when (explicitly out of scope
    for now, see [`data/demo/README.md`](../data/demo/README.md))?
18. Repository licence (currently none / private)?
