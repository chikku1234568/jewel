# 0003. Cache: Redis

- **Status:** Accepted (decided by Srikar, 2026-09-26)

## Context

LLM calls (triple extraction, recognition filter, answers) and embeddings are the slow and
costly parts. A demo should replay deterministically and cheaply.

## Decision

Use **Redis** (official Docker image `redis:8-alpine`) with the **redis-py** client
(`redis` package) behind `jewel.cache.base.Cache`. Planned keys: LLM responses
(`llm:{model}:{sha256(prompt)}`), embeddings (`emb:{model}:{sha256(text)}`), retrieval
results (`ret:{sha256(question)}:{t_query}:{graph_version}`, where `graph_version` bumps on
every graph write so a closed edge is never served stale).

## Licensing note (verified 2026-09-26 against redis.io/legal/licenses)

- Redis <= 7.2: BSD-3-Clause. Redis 7.4: RSALv2 or SSPLv1 (source-available, not OSI).
- **Redis 8.0 and later ("Redis Open Source")**: tri-licensed; you choose **RSALv2, SSPLv1,
  or AGPLv3**. AGPLv3 is an OSI-approved open-source licence, added in May 2025.
- For an unmodified Redis used as a cache behind our API, none of these options is
  expected to be a practical constraint; if we ever modify Redis itself and offer it over
  a network, AGPLv3 obligations apply.

Drop-in alternative: **Valkey** (Linux Foundation fork of Redis 7.2, BSD-3-Clause) speaks the
same protocol, so swapping is a config change.

## Consequences

- One more container in docker-compose; trivial ops at demo scale.
- The cache interface keeps the backend testable without Redis (in-memory fake in tests).

## Open questions for review

1. Cache TTLs: keep LLM responses indefinitely for demo reproducibility, or expire them?
