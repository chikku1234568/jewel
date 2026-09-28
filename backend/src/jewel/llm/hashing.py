"""Deterministic bag-of-tokens vectors for tests.

Not the production embedder. Production vectors are ``BAAI/bge-base-en-v1.5``.
"""

import hashlib
import math
import re

_TOKEN = re.compile(r"[a-z0-9]+")
_DIM = 64


class HashingEmbedder:
    """Normalized hashing vectors. Shared tokens land in the same dimensions."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [_embed_one(text) for text in texts]


def _embed_one(text: str) -> list[float]:
    vector = [0.0] * _DIM
    for token in _TOKEN.findall(text.lower()):
        slot = int(hashlib.sha256(token.encode()).hexdigest(), 16) % _DIM
        vector[slot] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]
