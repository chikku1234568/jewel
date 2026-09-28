"""Link a question to entities and triples by cosine similarity."""


def cosine(left: list[float], right: list[float]) -> float:
    """Dot product. Callers pass vectors that are already normalized."""
    if len(left) != len(right) or not left:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True))


def top_matches(
    query: list[float],
    items: list[tuple[str, list[float]]],
    k: int,
) -> list[tuple[str, float]]:
    """Return up to ``k`` ``(id, score)`` pairs, highest score first."""
    scored = [(item_id, cosine(query, vector)) for item_id, vector in items]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [pair for pair in scored[:k] if pair[1] > 0]
