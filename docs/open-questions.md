# Open questions

Only these three items are open. Everything else is settled by
[`problem-statement.md`](problem-statement.md).

1. **Model ids.** The exact chat model id and embedding model id (`JEWEL_LLM_MODEL`,
   `JEWEL_EMBEDDING_MODEL`). Read https://docs.x.ai when implementing; the embedding
   dimension also sets the Neo4j vector index dimension.
2. **Hosting.** Where the deployed instance will be hosted
   ([ADR 0006](decisions/0006-deployment.md)).
3. **Base-URL override.** Whether a later version may add a base-URL override. This
   version does not: the client always uses `https://api.x.ai/v1`.
