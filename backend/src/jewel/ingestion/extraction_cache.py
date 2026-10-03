"""Cache of extraction-model output for one passage.

The key is a SHA-256 over length-prefixed fields: model name, system prompt, generation
settings, and the exact passage. A change to any of those misses. The stored value is
the raw model text, so a later parser improvement can re-read it without another call.

Postgres holds the cache. Redis is not used: each value is written once and read again
only when that same passage is built, and the API is a single process.
"""

import hashlib
import json
import threading
from typing import Protocol

from jewel.llm.extract import _EXTRACT_SYSTEM, _VERIFY_SYSTEM, EXTRACT_OPTIONS, VERIFY_MAX_TOKENS


class ExtractionCache(Protocol):
    def get(self, cache_key: str) -> str | None: ...

    def put(self, cache_key: str, model: str, response: str) -> None: ...


def extraction_key(model: str, text: str) -> str:
    """Stable id for one passage under the current extraction prompt and settings."""
    payload = b"".join(
        (
            _field("model", model),
            _field("system", _EXTRACT_SYSTEM),
            _field("options", json.dumps(EXTRACT_OPTIONS, sort_keys=True, separators=(",", ":"))),
            _field("text", text),
        )
    )
    return hashlib.sha256(payload).hexdigest()


def verification_key(model: str, text: str) -> str:
    """Stable id for one attribution check. A different prompt or triple list misses."""
    payload = b"".join(
        (
            _field("model", model),
            _field("system", _VERIFY_SYSTEM),
            _field(
                "options",
                json.dumps(
                    {"max_tokens": VERIFY_MAX_TOKENS, **EXTRACT_OPTIONS},
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            ),
            _field("text", text),
        )
    )
    return hashlib.sha256(payload).hexdigest()


def _field(label: str, value: str) -> bytes:
    raw = value.encode()
    return label.encode() + b"\0" + len(raw).to_bytes(8, "big") + raw


class MemoryExtractionCache:
    """Process-local stand-in used by tests."""

    def __init__(self) -> None:
        self.rows: dict[str, tuple[str, str]] = {}
        self._lock = threading.Lock()

    def get(self, cache_key: str) -> str | None:
        with self._lock:
            row = self.rows.get(cache_key)
        return None if row is None else row[1]

    def put(self, cache_key: str, model: str, response: str) -> None:
        with self._lock:
            self.rows.setdefault(cache_key, (model, response))


class PostgresExtractionCache:
    """Shared cache. Inserts are idempotent if two builds race on the same passage."""

    def __init__(self, conn) -> None:
        self._conn = conn
        self._lock = threading.Lock()

    def get(self, cache_key: str) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT response FROM extraction_cache WHERE cache_key = %s",
                (cache_key,),
            ).fetchone()
        return None if row is None else row["response"]

    def put(self, cache_key: str, model: str, response: str) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO extraction_cache (cache_key, model, response)
                VALUES (%s, %s, %s)
                ON CONFLICT (cache_key) DO NOTHING
                """,
                (cache_key, model, response),
            )
