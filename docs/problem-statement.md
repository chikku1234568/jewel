# jewel — a personal live knowledge graph

A person signs in with Google, uploads their own documents, and gets a knowledge graph of those files. They can click through the graph with no question typed. They can save their own xAI API key and ask one agent questions. The agent searches that graph, and the screen shows the search.

This file is the product spec. It replaces the pharmacotherapy showcase completely. The old spec is archived at [problem-statement-pharmacotherapy.md](problem-statement-pharmacotherapy.md) and must not be scaffolded from.

This pass is a **scaffold revamp**: repository structure, docs, and documented placeholders. Do not implement OAuth, extraction, retrieval, or the agent yet. Section [Scaffold this pass](#scaffold-this-pass) is the checklist.

The product is free. There is no billing, no team plan, and no shared workspace. The model bill is the user's key. The graph belongs to that user.

## Purpose

Two jobs, both required.

1. **Useful to one person.** They load a set of their own files (notes, papers, letters, a lease and a later letter) and can see how the files connect. They can ask a question that depends on more than one file and read an answer that points at the words it used.
2. **Show the agent and the retriever.** The answer is produced by one tool-using agent. The search it calls is a graph retriever (HippoRAG-2-inspired, time-aware Personalized PageRank). The screen shows each tool call and lights up the subgraph that came back. A single hidden retrieval call does not meet this job.

Ingestion is a fixed pipeline. Question answering is the agent. Do not turn ingestion into a team of agents.

## The person

One account, one graph, their files. A student, a reader, or the person building jewel, working through a pile of documents they already have.

They are not a clinic, a pharmacy, or a company buying seats. The product does not interpret a document as medical, legal, or financial advice, and it does not tell anyone to act. A short line on the page says that answers cite the user's files and are not advice.

## What done means for the product

A person can do all of the following on their own account.

- Sign in with Google and sign out. A second Google account cannot see the first account's files, graph, key, or questions.
- Save an xAI API key, see that a key is saved without seeing the secret again, delete it, and check that the provider accepts it.
- Upload a PDF, a `.txt`, or a `.md` file before or after saving a key. The library shows the file and its status.
- After a key is present, the file is parsed, triples are extracted, and the graph updates without a separate batch step.
- Open the graph, pan and zoom, click a node, read the sentence it came from, and see its neighbors. Filter the graph to one document from the library.
- Delete a node or an edge they do not want. Deleting a document removes the mentions and triples that exist only because of that document, and removes entities that no longer have any mention.
- Ask a question. See the agent's tool calls, see the graph highlight the returned nodes and edges, and read an answer whose citations are document passages the tools returned.
- Open a comparison that answers the same question from text chunks only, with no graph.

No clinical scenario, drug, or dosing rule remains in the interface, the default copy, or the repository fixtures.

## Flow

```text
Google sign-in
  → library (empty until they upload)
  → optional: save xAI API key
  → upload PDF / txt / md
  → file stored immediately
  → when a key exists: parse → extract triples → embed → write their graph
  → library + graph they can click
  → question
  → one agent calls search_graph and, when it needs the passage, read_document
  → answer, tool trace, highlighted subgraph, citations
```

Text-search comparison is a separate action on the same question. It does not go through the agent.

## Accounts

Google is the only sign-in. Scopes are `openid`, `email`, and `profile`. The app does not request Gmail or Drive.

Use the authorization-code flow. The server checks the ID token (`iss`, `aud`, `exp`) and stores a session. The browser gets an `httpOnly`, `Secure`, `SameSite=Lax` session cookie. The session id is random and stored on the server. The OAuth `state` value is stored on the server for the round trip. Logout deletes the session.

There are no passwords, no second provider, and no guest mode.

Environment (names the scaffold should already expect):

| Variable | Role |
|---|---|
| `GOOGLE_CLIENT_ID` | Google OAuth client |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client |
| `GOOGLE_REDIRECT_URI` | Authorized redirect |
| `SESSION_SECRET` | Session signing / randomness material |

Local development uses a localhost redirect URI. The scaffold does not ship a fake logged-in user.

## API keys

The user pastes an xAI API key. The server stores ciphertext only, encrypted with an application secret (`KEY_ENCRYPTION_SECRET`). The key is never written to logs, never put in the frontend bundle, and never returned in full. The client may show that a key is saved and the last four characters.

Calls use the OpenAI-compatible API at `https://api.x.ai/v1` with that key, server-side. One client. No second SDK. Model ids are settings (`JEWEL_LLM_MODEL`, `JEWEL_EMBEDDING_MODEL`), chosen at implementation time from the current docs at https://docs.x.ai. Placeholders must not freeze a guessed model id into code.

A "Check key" action performs one cheap authenticated call with the stored key and reports success or failure.

Extraction, embeddings, and the agent all use this key. There is no project key that serves user traffic. A developer key in the environment is for automated tests only and must not be used when handling a signed-in user's documents.

The library accepts uploads with no key. Graph building waits until a key exists, then the user can run it (and can retry a failed file). The UI says that building the graph spends their key.

Deleting the key stops new model calls. It does not delete the graph already built.

## Documents

In:

- PDF, plain text, and Markdown.
- One file is one document: owner, original filename, media type, upload time, optional document date, extracted text, status.
- Status values: `stored`, `waiting_for_key`, `parsing`, `extracting`, `ready`, `failed`. A failure keeps the file and stores an error string the library can show. Retry starts the pipeline again.
- Size cap: 20 MB per file. PDF cap: 50 pages. Over-cap uploads fail with a clear error and are not stored.
- The raw extracted text is kept, because a click and a citation have to be checkable against the file.

Out:

- Images of handwriting, office formats other than PDF and text, email import, Drive import, and a folder watcher.
- A default corpus loaded into a new account. A new account has an empty library.

The document date is optional, taken from a date the user sets or from a single obvious date in the file. If there is no date, the document is undated and its statements stay valid. The product does not invent a date.

## Ingestion pipeline

Fixed steps, same order every time, for one document, for one user. Not an agent. No role split.

1. Parse to text (PDF through a `DocumentParser`; text and Markdown read as text).
2. Chunk the text for the text-search index only.
3. Ask the model for entities and triples, validated into the schema below. The model output is data. It is not code and not Cypher.
4. Embed the document and each entity.
5. Write nodes and relationships scoped to that user.

Extraction schema:

| Field | Meaning |
|---|---|
| Entity `name` | Surface form |
| Entity `type` | One of `person`, `organization`, `place`, `concept`, `other` |
| Triple `subject`, `object` | Entity names |
| Triple `predicate` | Short phrase, stored as a property, not as a Neo4j relationship type |
| Triple `quote` | A span copied from the document text |
| Triple offsets | Character offsets into the extracted text when the model returns them |

Entity identity inside one user: case-fold the name and reuse an existing entity on exact match. Do not merge across users. Do not build a broader entity-resolution system.

## Knowledge graph

One Neo4j database. Every node and every relationship carries `user_id`. Every read and every write is constrained to the signed-in user. Missing that predicate is a defect, not a default.

| Label | What it is |
|---|---|
| `Document` | One uploaded file. Holds raw text, filename, times, status, embedding. This is the passage node. |
| `Entity` | A phrase node: `name`, `type`, `embedding`. |

| Relationship | From → to | Properties |
|---|---|---|
| `MENTIONS` | Entity → Document | `quote`, offsets, `valid_at` |
| `RELATED_TO` | Entity → Entity | `predicate`, `quote`, offsets, `document_id`, `valid_at`, `invalid_at` |

`valid_at` is the document date when the document has one, otherwise null (undated, treated as valid). `invalid_at` is null unless the user deletes or a later write explicitly closes the relationship. There is no rule engine that closes edges. There is no dosing rule, no protocol node, and no agent whose job is to invalidate facts.

"Valid at t" (single predicate, used by retrieval):

```cypher
r.valid_at IS NULL OR r.valid_at <= $t
AND (r.invalid_at IS NULL OR r.invalid_at > $t)
```

Undated relationships (`valid_at` null) stay in the valid set.

Embeddings are `LIST<FLOAT>` properties with a Neo4j vector index. The dimension comes from the embedding model settings. Do not require the Enterprise `VECTOR` property type.

Provenance: every `RELATED_TO` and `MENTIONS` points at the document and the quote. The graph view and the answer both use that quote.

The user may delete an entity or a relationship from the graph view. Delete document removes its `MENTIONS` and the `RELATED_TO` rows whose `document_id` is that document, then removes entities that have no remaining `MENTIONS` for that user.

Clinical labels (`Patient`, `MedicationOrder`, `LabObservation`, `ClinicalProtocolRule`, `PRESCRIBED_DOSE`, `HAS_BIOMARKER_VALUE`, `CONTRAINDICATES`, `TRIGGERS_SAFETY_HOLD`, `REQUIRES_REVIEW`) are not part of this product.

## Retriever

`search_graph` runs this pipeline on **that user's** subgraph only. Personalized PageRank runs in Python (`networkx`) over the subgraph pulled for the query. Neo4j Graph Data Science is not used.

1. Link the question to the user's entities (embedding search on `:Entity`).
2. Keep relationships that are valid at the question time. The question time defaults to now. Undated relationships remain.
3. Rank candidate triples by similarity to the question and take a top-k.
4. Seed Personalized PageRank with the entities on the kept triples, plus `Document` nodes weighted by similarity to the question and down-weighted relative to entities.
5. Return ranked entities, `RELATED_TO` relationships (predicate, endpoints, quote, document id, times), and the documents those relationships cite, with a passage of the raw text.

The recognition-memory step from HippoRAG 2 (a model pass that drops irrelevant triples before PageRank) is part of this retriever, one call, using the user's key. It filters candidates. It does not answer the question.

The retriever never sees another user's nodes. Apply the `user_id` constraint before similarity search and before the subgraph is pulled into Python.

## The agent

One agent. LangGraph is the runtime: a tool-using loop, not a fixed `retrieve → answer` function, and not a supervisor over several specialists.

Tools, and only these:

| Tool | Behavior |
|---|---|
| `search_graph` | Runs the retriever. Arguments: the query string the agent wrote, and an optional time. Returns entities, relationships, and document passages. |
| `read_document` | Arguments: a document id returned by `search_graph`, and an optional span. Returns text from that document. Refuses ids that search did not return and ids the user does not own. |

The agent may call `search_graph` more than once. It calls `read_document` when it needs a longer passage than the quote. After at most **4** tool calls it must answer.

The answer cites document ids and quotes that appeared in tool results. The UI drops a citation that does not match a tool result.

The UI shows the trace in order: tool name, the arguments, a short result summary (counts and document names, not a hidden chain). When a `search_graph` result arrives, the graph view highlights those node and relationship ids until the next search or until the user clears it.

The agent does not receive a Neo4j session, a Cypher string parameter, or the API key. The application binds the user id and the key outside the model.

Stream the trace and the answer to the browser with Server-Sent Events.

## Text-search comparison

`compare_text` is not a tool and not an agent. The same question, the same model, the same embedding model. Chunks of the user's document text, top-k by cosine similarity, then one answer. It ignores relationships and time.

The user opens it from the answer they already have. The panel shows that answer and the chunks it used. This is how a reader sees when the graph path and the text path disagree. It is one control, not a second product.

## Interface

Three regions on one page, after sign-in. Words on the page are **Documents**, **Graph**, and **Ask**. The words HippoRAG, PageRank, episode, and Cypher do not appear in the interface. "Search graph" and "Read document" are the right names in the trace.

**Documents.** Filename, upload time, status, error on failure, retry. Open the extracted text. Choosing a document filters the graph to entities mentioned in it. Empty copy tells them to upload a file. It does not offer a sample patient or a sample corpus.

**Graph.** Cytoscape.js, pan and zoom, labeled nodes, edges labeled with the predicate. Click a node: name, type, quote, source filename. Click an edge: predicate, quote, source filename, times when present. Highlight from the agent is visible on this same view. Delete is available on the thing they clicked.

**Ask.** A question box. Disabled, with an explanation, when no key is saved or when no document is `ready`. After a run: the trace, the answer, citations that jump to the document text, and the text-search comparison control.

**Key.** A place to paste, check, and delete the key. The paste field is empty whenever a key is already saved.

**Account.** Google name and email, sign out.

Chrome around the page includes one plain sentence: answers quote the user's documents and are not medical, legal, or financial advice. Remove the pharmacotherapy banner and the five clinical progress steps.

A signed-out visit shows sign-in and that sentence. It does not show a graph.

## Tenancy and secrets

- Every document, chunk, node, relationship, key, and question trace is stored against the user id.
- Graph queries take the user id from the session, not from a client-supplied filter alone. A client may send an id; the server still applies the session user.
- Tests must cover: user A cannot read or delete user B's document, graph neighborhood, or key status beyond "a key exists" for themselves; `read_document` rejects a document id from another user; the retriever's candidate set is empty of other users' entities.
- API keys at rest are ciphertext. Session cookies are httpOnly. Logs omit document text and keys.
- Uploaded files live on a local volume in this version, addressed by an opaque stored path, not by a user-controlled path.

## Stores and runtime

| Piece | Choice |
|---|---|
| Backend | Python 3.11+, FastAPI, Pydantic, uv |
| Agent runtime | LangGraph, one tool-using agent |
| Graph | Neo4j 5.x Community (`neo4j:5.26-community`), official `neo4j` driver |
| Accounts, sessions, document rows, ciphertext keys, chunk rows | Postgres |
| File bytes | Local volume |
| PageRank | `networkx` |
| PDF | `DocumentParser` interface; pypdf first |
| LLM and embeddings | OpenAI-compatible client, base URL `https://api.x.ai/v1`, user's key |
| Frontend | The existing Vite + React + TypeScript app. Graph view: Cytoscape.js |
| Cache | None in this version. Do not require Redis. |

Postgres is new and required. Redis leaves the local stack. Neo4j stays.

Deployment hosting is still open. Local `docker compose` must include Neo4j, Postgres, the backend, and the frontend, and must not depend on Redis.

## HTTP surface the placeholders should name

Session required on every route except health and the Google start/callback routes.

| Route | Purpose |
|---|---|
| `GET /health` | Process up. Already exists. Keep it. |
| `GET /auth/google` | Start OAuth. |
| `GET /auth/google/callback` | Finish OAuth, set the cookie. |
| `POST /auth/logout` | Delete the session. |
| `GET /me` | Email, name, whether a key is saved, key hint. |
| `PUT /me/api-key` | Store a key. |
| `DELETE /me/api-key` | Delete it. |
| `POST /me/api-key/check` | Provider accepts the stored key, or an error. |
| `POST /documents` | Multipart upload. |
| `GET /documents` | The library. |
| `GET /documents/{id}` | Metadata plus extracted text when the caller owns it. |
| `POST /documents/{id}/build` | Run or retry ingestion. |
| `DELETE /documents/{id}` | Delete the file and its exclusive graph data. |
| `GET /graph` | The caller's subgraph. Optional `document_id` filter. |
| `DELETE /graph/entities/{id}` | Caller-owned entity. |
| `DELETE /graph/relationships/{id}` | Caller-owned relationship. |
| `POST /ask` | Start an agent run. Returns a run id. |
| `GET /ask/{run_id}/events` | SSE: tool calls, highlights, answer, errors. |
| `POST /ask/{run_id}/compare` | Text-search answer for that same question. |

## Test fixture

Tests and a developer fixture only. Never inserted into a new account.

Two short text documents:

1. Dated January. "The warehouse key is held by Sam. The alarm code is 4412."
2. Dated March. "The alarm code was rotated after the break-in." This file does not contain "Sam" or "4412".

A graph question about whether the alarm code is still 4412 can reach the March document through the shared alarm-code entity. A chunk search for "4412" ranks the January document and can miss the March document. The fixture exists so later tests can show that split. It is not a demo mode in the UI.

No patient, drug, or lab fixture.

## In scope

- Google sign-in, server sessions, sign-out.
- One user, their key, their files, their graph.
- Upload, status, retry, delete.
- Fixed ingestion pipeline and the graph schema above.
- Clickable graph, per-document filter, delete node or edge.
- One tool-using agent, the retriever described above, visible trace, citations, highlight.
- Text-search comparison on demand.
- User isolation enforced in queries and covered by tests.
- The sentence that answers are not advice.

## Out of scope

- The pharmacotherapy scenario, clinical agents, write-permission roles, frozen clinical rules, and the "not for clinical use" showcase framing.
- More than one agent, a supervisor, or an agent that writes into the graph.
- Billing, teams, sharing, public graphs, Gmail, Drive, and live inbox sync.
- A retriever bake-off, Neo4j Graph Data Science, and a trained or GNN retriever.
- Redis, a second model provider, and a model id hardcoded as permanent.
- Editing arbitrary graph structure by drawing new edges by hand. Delete and document upload are the edits. Renaming can wait.
- Choosing hosting, a custom domain, or a production password policy beyond Google and the session cookie.

## Decisions this spec settles

| Topic | Decision |
|---|---|
| Product | Personal live graph over the user's files, plus one visible agent |
| Price | Free. User pays the model provider with their own key |
| Auth | Google OAuth, identity scopes only |
| Model host | `https://api.x.ai/v1`, OpenAI-compatible, key from the user |
| Orchestration | LangGraph, one agent, tools `search_graph` and `read_document`, cap of 4 tool calls |
| Retrieval | HippoRAG-2-inspired pipeline in the Retriever section, PageRank in networkx |
| Baseline | On-demand chunk search, not an agent |
| Graph store | Neo4j 5.x Community, `user_id` on every element |
| App data | Postgres |
| Cache | Not in this version |
| Frontend | Existing Vite + React + TypeScript app, Cytoscape.js for the graph |
| Time | Optional document date. Undated statements stay valid. No automatic invalidation rules |

Still open, and fine to leave open in docs:

- The exact chat model id and embedding model id (read https://docs.x.ai when implementing).
- Where the deployed instance will be hosted.
- Whether a later version may add a base-URL override. This version does not.

## Scaffold this pass

Revamp the existing `jewel/` tree so a reader of the code sees this product and not the pharmacotherapy showcase. Structure, module docstrings, route names, docs, and the placeholder page. No live Google call, no live Neo4j writes, no real agent.

### Backend modules

Keep the package layout under `backend/src/jewel/`. Change it as follows.

| Path | Action |
|---|---|
| `api/routes/health.py` | Keep |
| `api/app.py` | Docstring lists the routes in the HTTP section. Still mount health only |
| `api/routes/auth.py`, `documents.py`, `graph.py`, `ask.py`, `keys.py` | New stubs. Each names its routes and states they are not mounted yet |
| `auth/` | New stub package: Google OAuth and server sessions, as specified under Accounts |
| `documents/` | New stub package: upload records, status values, local file path |
| `ingestion/` | Replace the clinical episode stub with the fixed pipeline (parse, chunk, extract, embed, write) |
| `parsing/` | Keep the parser interface. Docstrings say PDF, txt, and md |
| `kg/schema.py` | Replace clinical enums with `Document`, `Entity`, `MENTIONS`, `RELATED_TO` |
| `kg/neo4j_store.py`, `kg/temporal.py`, `kg/extraction.py` | Keep the modules. Rewrite docstrings to this graph, the validity predicate, and user-scoped writes |
| `kg/permissions.py` | Remove. User isolation is `user_id` on queries, not an agent permission matrix. Do not leave a clinical matrix behind "for later" |
| `agents/graph.py` | One LangGraph agent stub: tools, the 4-call cap, SSE trace |
| `agents/state.py` | Question, user id, tool trace, citations, answer. Drop clinical run fields |
| `agents/tools.py` | New stub for `search_graph` and `read_document` |
| `agents/ehr_order.py`, `lab_monitor.py`, `pharmacologist.py`, `parse.py`, `answer.py`, `progress.py` | Remove |
| `rules/` | Remove the package, including `enoxaparin_crcl.py` |
| `retrieval/hippo/` | Keep. Docstrings describe the Retriever section. PageRank is networkx, not GDS |
| `retrieval/baseline_rag.py` | Keep. Docstring describes the on-demand comparison |
| `llm/base.py` | Provider-agnostic interface implemented later by one OpenAI-compatible client aimed at `https://api.x.ai/v1` |
| `cache/` | Remove. Redis is not part of this version |
| `config.py` | Settings for Google, session, key encryption, Postgres, Neo4j, model names, base URL default `https://api.x.ai/v1` |

Dependencies in `pyproject.toml`: add comments or dependencies only for libraries this scaffold already imports. Do not add LangGraph, networkx, pypdf, or an LLM SDK until a later pass imports them. Postgres client and Neo4j driver may be declared because the stores are decided; if the stubs do not import them, document that the way the current file documents Neo4j and Redis. Remove Redis from the declared runtime set if nothing imports it.

Tests: keep `GET /health`. Update import tests so they load the new modules and fail if the removed clinical modules are still importable. Do not call Google, xAI, Neo4j, or Postgres.

### Frontend

Replace the placeholder page. Regions, in order: the advice sentence, sign-in (inert), Documents, Graph, Ask. Copy describes an empty library and a graph that appears after a file is built. Delete the five clinical steps and `NotForClinicalUseBanner`. Do not add Cytoscape until the graph is implemented; the Graph region is an empty state that names what will be there.

### Infra

`infra/docker-compose.yml`: Neo4j, Postgres, backend, frontend. Remove the Redis service and `JEWEL_REDIS_URL`. Backend env gains `DATABASE_URL` and the Google, session, and key-encryption variables as empty defaults. Compose stays a placeholder stack.

### Data

Replace `data/demo/` clinical instructions with `data/fixtures/README.md` describing the two warehouse-key texts. Do not present those texts as a built-in user demo.

### Docs to rewrite in this same pass

| Doc | What it should say |
|---|---|
| `README.md` | This product, the scaffold status, how to run health and the placeholder page. No enoxaparin walkthrough |
| `docs/architecture.md` | System sketch derived from this file: sign-in, ingestion pipeline, graph, retriever, one agent, UI regions, stores. Mark settled decisions as settled |
| `docs/open-questions.md` | Only the three open items listed above |
| `docs/decisions/` | New or superseded records: Google OAuth; Postgres for app data; Redis dropped for this version; retrieval accepted as the pipeline in this file (Python PageRank); LangGraph accepted as the single agent; clinical write-permission ADR superseded and removed from the active set |
| Diagrams | Replace clinical sequence and schema diagrams with ingestion, the agent loop, and the `Document` / `Entity` schema, when the diagram tooling already in the repo makes that cheap. Stale clinical PNGs should not remain as the current picture |

### Do not do in this pass

- Implement OAuth, upload parsing, Cypher, PageRank, or a model call.
- Mount the new routes on the app. Health stays the only live route.
- Add a sample login, a sample graph, or clinical seed data.
- Re-open a retriever bake-off or a multi-agent design in the new docs.
