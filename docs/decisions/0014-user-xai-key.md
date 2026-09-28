# 0014. User-supplied xAI key through one OpenAI-compatible client

- **Status:** Accepted (settled by `docs/problem-statement.md`, 2026-09-28)

## Decision

- Each user pastes their own xAI API key. The server stores ciphertext only, encrypted
  with `KEY_ENCRYPTION_SECRET`; the key is never logged, never in the frontend bundle,
  never returned in full (the client may show that a key is saved and its last four
  characters).
- All model calls (extraction, embeddings, recognition filter, agent, comparison) are
  server-side through **one OpenAI-compatible client** at `https://api.x.ai/v1` with that
  key. No second SDK, no project key serving user traffic. A developer key in the
  environment is for automated tests only.
- Model ids are settings (`JEWEL_LLM_MODEL`, `JEWEL_EMBEDDING_MODEL`), empty in the
  scaffold and chosen from https://docs.x.ai at implementation time.
- "Check key" makes one cheap authenticated call. Deleting the key stops new model calls
  and keeps the graph.
- The base URL is fixed in this version (whether a later version adds an override is an
  open item).

## Consequences

- Uploads work without a key; graph building waits for one.
- The LLM SDK is added in the pass that first imports it.
