"""Cache interface (stub). Cache decision: Redis via redis-py (ADR 0003, Accepted).

Planned uses: LLM responses keyed by (model, prompt hash), embeddings keyed by
(model, text hash), and retrieval results keyed by (question hash, t_query, graph version).
"""

from typing import Protocol


class Cache(Protocol):
    def get(self, key: str) -> bytes | None: ...

    def set(self, key: str, value: bytes, ttl_seconds: int | None = None) -> None: ...
