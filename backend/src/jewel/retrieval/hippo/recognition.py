"""Recognition memory: one model call that drops triples, and does not answer.

The call uses whichever chat model the caller passes (Kimi during agent tests).
Extraction does not go through this path.
"""

import json

from jewel.kg.records import GraphTriple
from jewel.llm.base import ChatModel

_SYSTEM = (
    "You filter triples for a question. Return JSON "
    '{"keep": [<indexes of triples that help answer the question>]}. '
    "Do not answer the question."
)


def filter_triples(
    question: str,
    triples: list[GraphTriple],
    chat: ChatModel,
) -> list[GraphTriple]:
    """Keep the triples the model marks relevant. An empty list means none survived."""
    if not triples:
        return []
    listing = [
        {"index": index, "triple": f"{triple.quote}"} for index, triple in enumerate(triples)
    ]
    raw = chat.complete(_SYSTEM, json.dumps({"question": question, "triples": listing}))
    try:
        payload = json.loads(raw)
        keep = payload["keep"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return triples
    chosen: list[GraphTriple] = []
    for index in keep:
        if isinstance(index, int) and 0 <= index < len(triples):
            chosen.append(triples[index])
    return chosen
