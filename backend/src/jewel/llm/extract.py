"""The one extraction prompt, and the call that sends a passage to the user's chat model.

Every extraction model is an OpenAI-compatible API. The user supplies the key on the
build request. There is no local model.
"""

import json

from jewel.llm.base import ChatModel
from jewel.llm.openai_chat import OpenAICompatibleChat

# Part of the extraction cache key, with the system prompt and the passage. No local
# model reads num_predict; it stays so a budget change misses rows cached under the old one.
EXTRACT_OPTIONS = {"temperature": 0, "num_predict": 8192}

EXTRACT_MAX_TOKENS = 8192

# One short reply per passage: a list of the triples to keep. Far smaller than extraction.
VERIFY_MAX_TOKENS = 2048

# The build recognizes this request without looking at the extraction prompt.
VERIFICATION_REQUEST_PREFIX = "Check these triples.\n"

_VERIFY_SYSTEM = (
    "You check triples against the quote each one carries. Use only that quote. "
    "Outside knowledge does not count. Keep a triple only when its quote states that "
    "the subject stands in that relation to the object. A quote that merely contains "
    "those words is not enough. If the quote has more than one reading, do not keep "
    'the triple. Return one JSON object and nothing else: {"keep":[1]}. The numbers '
    "are the n values of the triples to keep. Omit every triple you are not sure about. "
    'If none qualify, return {"keep":[]}.'
)

# One call lists entities, resolves pronouns, and writes triples. The build may send one
# follow-up for lines that call left unresolved (``ingestion/live.py``). The quote rule is
# enforced again in code: ``parse_extraction`` drops any triple whose quote is not an exact
# substring of the chunk. The worked example cannot leak into a graph: its quotes are not
# in the user's passage, so the same check would drop them.
_EXTRACT_SYSTEM = (
    "You build a knowledge graph from one passage of a user's document. "
    "Return one JSON object and nothing else: no prose and no Markdown code fences. Shape: "
    '{"entities":[{"name":"string","type":"person|organization|place|concept|other"}],'
    '"triples":[{"subject":"string","predicate":"string","object":"string","quote":"string"}]}. '
    "Work in this order. "
    "1. List every entity in the passage: every person, organization, and place, and the "
    "concepts the passage is about. A person named once, or only in a list of parties, is "
    "still an entity. Write each name as the passage writes it. "
    "2. Write one triple for every fact the passage states. The subject and object are "
    "names from that entity list, or the literal amount, date, duration, or list item the "
    "passage writes. The predicate is a short verb phrase. "
    '3. Resolve pronouns and references such as "she", "it", "the tenant", or "the company" '
    "to the name they refer to in the passage. Never use a pronoun as a subject or object. "
    "4. Every quote is copied verbatim from the passage, character for character, "
    "including any Markdown symbols inside it: the sentence or clause that states the fact. "
    "Do not paraphrase, shorten, correct, or join text from different places. A triple "
    "whose quote is not an exact copy of passage text is discarded. "
    "5. There is no maximum and no ranking. Include every named person, every amount, "
    "every date, every duration, and each item of a list as its own triple. The object of "
    "an amount or a date is the figure or the date copied as written. "
    'If the passage states no facts, return {"entities":[],"triples":[]}. '
    "Example passage: "
    '"Ada Lovelace worked with Charles Babbage in London. She wrote the first published '
    'algorithm for his Analytical Engine." '
    "Example output: "
    '{"entities":[{"name":"Ada Lovelace","type":"person"},'
    '{"name":"Charles Babbage","type":"person"},{"name":"London","type":"place"},'
    '{"name":"Analytical Engine","type":"concept"}],'
    '"triples":[{"subject":"Ada Lovelace","predicate":"worked with",'
    '"object":"Charles Babbage",'
    '"quote":"Ada Lovelace worked with Charles Babbage in London."},'
    '{"subject":"Ada Lovelace","predicate":"wrote the first published algorithm for",'
    '"object":"Analytical Engine",'
    '"quote":"She wrote the first published algorithm for his Analytical Engine."}]}. '
    'In the second triple "She" became "Ada Lovelace", but the quote kept the passage\'s '
    "own words."
)


def extract_document(chat: ChatModel, text: str) -> str:
    """Ask the user's extraction model for entities and triples in one passage.

    The larger output budget is for this call only. The agent's answer calls keep the
    client default.
    """
    if isinstance(chat, OpenAICompatibleChat):
        return chat.complete(_EXTRACT_SYSTEM, text, max_tokens=EXTRACT_MAX_TOKENS)
    return chat.complete(_EXTRACT_SYSTEM, text)


def recovery_user_text(sentences: list[str]) -> str:
    """The one follow-up message: only the lines the first pass left unresolved.

    The preface is not part of the passage. ``parse_extraction`` checks quotes against
    the passage, so a quote copied from this preface is discarded.
    """
    lines = "\n".join(sentences)
    return (
        "These lines were left uncovered. "
        "Extract every fact they state, including every named person. "
        "Each quote must be copied verbatim from these lines.\n\n"
        f"{lines}"
    )


def verification_user_text(triples: list) -> str:
    """One passage's triples, numbered, for the attribution check.

    The quote is the passage's own characters, including its line breaks, so the
    checker sees the span that will be stored.
    """
    items = [
        {
            "n": index,
            "subject": triple.subject,
            "predicate": triple.predicate,
            "object": triple.object,
            "quote": triple.quote,
        }
        for index, triple in enumerate(triples, start=1)
    ]
    return VERIFICATION_REQUEST_PREFIX + json.dumps(items, ensure_ascii=False)


def verify_triples(chat: ChatModel, text: str) -> str:
    """Ask which of these triples the quote itself states. Not an extraction call."""
    if isinstance(chat, OpenAICompatibleChat):
        return chat.complete(_VERIFY_SYSTEM, text, max_tokens=VERIFY_MAX_TOKENS)
    return chat.complete(_VERIFY_SYSTEM, text)
