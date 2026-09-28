# 0010. Redis dropped for this version

- **Status:** Accepted (settled by `docs/problem-statement.md`, 2026-09-28)
- **Supersedes:** [0003](0003-cache-redis.md)

## Context

The earlier plan cached model responses, embeddings and retrieval results. The product
spec says: "Cache: None in this version. Do not require Redis."

## Decision

No cache service in this version. The Redis service, the `redis` dependency, the
`jewel.cache` package and `JEWEL_REDIS_URL` are removed from the repository and the local
stack.

## Consequences

- Every model call is live and billed to the user's key; that is acceptable at personal
  scale.
- A cache can be reconsidered in a later version with its own ADR.
