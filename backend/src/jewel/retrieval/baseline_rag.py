"""Text-search comparison, ``compare_text``.

Not a tool and not an agent. Ranks the user's chunks by cosine similarity and
ignores relationships and time. The answer call sits on top of these chunks later.
"""

from jewel.retrieval.hippo.linking import cosine


def rank_chunks(
    query: list[float],
    chunks: list[tuple[str, str, list[float]]],
    k: int = 5,
) -> list[tuple[str, str, float]]:
    """Return up to ``k`` ``(document_id, text, score)`` triples, best first.

    ``chunks`` items are ``(document_id, text, embedding)``. A score of zero is dropped,
    so a chunk that shares no tokens with the query is absent.
    """
    scored = [
        (document_id, text, cosine(query, embedding)) for document_id, text, embedding in chunks
    ]
    scored = [item for item in scored if item[2] > 0]
    scored.sort(key=lambda item: item[2], reverse=True)
    return scored[:k]
