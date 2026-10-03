"""Entity and triple extraction.

The model returns JSON. It is data, never code or a database query. A triple is kept
only when its quote is the same words, in order, as a span of the document. A difference
of spaces or line breaks is repaired to that span. Case and punctuation stay exact.

The chat call itself is in ``jewel.llm.extract``. The user supplies that model's API key
on the build request. This module only checks the JSON.
"""

import json
import re

from pydantic import BaseModel, Field, ValidationError

from jewel.kg.schema import EntityType

_SENTENCE = re.compile(r"[^.!?]+[.!?]?")
_WS = frozenset(" \t\r\n")
_CLAUSE_SPLIT = re.compile(r"\n+|(?<=[.!?])\s+")
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_TYPES = {"person", "organization", "place", "concept", "other"}
# A follow-up is owed when one of these is stated and the first pass did not record it.
_TITLE_NAME = re.compile(r"\b(?:Mr|Mrs|Ms|Miss|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*")
_MULTI_CAP = re.compile(r"\b[A-Z][a-z]+(?:-[A-Z][a-z]+)?(?:\s+[A-Z][a-z]+(?:-[A-Z][a-z]+)?)+")
_ALLCAPS_NAME = re.compile(r"\b[A-Z]{2,}(?:\s+[A-Z]{2,})+\b")
_MID_CAP = re.compile(r"(?<=\s)[A-Z][a-zA-Z]{2,}\b")
_NUMBER = re.compile(r"\b\d{1,4}(?:[./-]\d{1,4})+\b|\b\d+(?:[.,]\d+)*(?:st|nd|rd|th)?\b")
_MONTH = re.compile(
    r"\b(?:January|JANUARY|February|FEBRUARY|March|MARCH|April|APRIL|May|MAY|"
    r"June|JUNE|July|JULY|August|AUGUST|September|SEPTEMBER|October|OCTOBER|"
    r"November|NOVEMBER|December|DECEMBER|Monday|MONDAY|Tuesday|TUESDAY|"
    r"Wednesday|WEDNESDAY|Thursday|THURSDAY|Friday|FRIDAY|Saturday|SATURDAY|"
    r"Sunday|SUNDAY)\b"
)
_CURRENCY_WORD = re.compile(r"\b(?:pounds?|dollars?|euros?|USD|GBP|EUR)\b", re.IGNORECASE)
_NAME_STOP = frozenset(
    [
        "and",
        "the",
        "for",
        "with",
        "from",
        "this",
        "that",
        "these",
        "those",
        "also",
        "not",
        "but",
        "any",
        "all",
        "each",
        "its",
        "his",
        "her",
        "their",
        "who",
        "when",
        "where",
        "what",
        "which",
        "while",
        "after",
        "before",
        "between",
        "during",
        "into",
        "onto",
        "upon",
        "than",
        "then",
        "once",
        "only",
        "such",
        "both",
        "some",
        "many",
        "most",
        "other",
        "same",
        "over",
        "under",
        "about",
        "above",
        "below",
        "across",
        "against",
        "without",
        "within",
        "per",
        "via",
    ]
)


class ExtractionError(ValueError):
    """The model output was not the extraction schema."""


class ExtractedEntity(BaseModel):
    name: str = Field(min_length=1)
    type: EntityType


class ExtractedTriple(BaseModel):
    subject: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    object: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    start: int | None = None
    end: int | None = None
    # Which build chunk (0-based) the quote was checked against. Set by the build, never
    # read from model output.
    chunk_ordinal: int | None = None


class Extraction(BaseModel):
    entities: list[ExtractedEntity]
    triples: list[ExtractedTriple]


def parse_extraction(payload: str, source_text: str) -> Extraction:
    """Keep every triple that can be checked against ``source_text``.

    One bad entity or triple is dropped. The rest of the model's JSON is kept.
    """
    raw = _load_json(payload)
    entities: list[ExtractedEntity] = []
    for item in _entity_items(raw):
        try:
            entities.append(ExtractedEntity.model_validate(item))
        except ValidationError:
            continue
    triples: list[ExtractedTriple] = []
    for item in _triple_items(raw, source_text):
        try:
            triple = ExtractedTriple.model_validate(item)
        except ValidationError:
            continue
        if triple.quote in source_text:  # repair already stored the passage's own span
            triples.append(triple)
    known = {entity.name for entity in entities}
    for triple in triples:
        for name in (triple.subject, triple.object):
            if name not in known:
                entities.append(ExtractedEntity(name=name, type=EntityType.CONCEPT))
                known.add(name)
    linked = {triple.subject for triple in triples} | {triple.object for triple in triples}
    kept = [entity for entity in entities if entity.name in linked or entity.name in source_text]
    return Extraction(entities=kept, triples=triples)


def checked_triples(extraction: Extraction, payload: str) -> Extraction:
    """Drop triples the attribution check did not clearly keep.

    ``payload`` is the checker's JSON, ``{"keep": [1, 2]}``, with 1-based ``n`` values.
    A reply that is not that list drops every triple. An empty list is a clear answer
    and also drops every triple. Entities are unchanged.
    """
    numbers = _keep_numbers(payload, len(extraction.triples))
    if numbers is None:
        triples: list[ExtractedTriple] = []
    else:
        triples = [
            triple for index, triple in enumerate(extraction.triples, start=1) if index in numbers
        ]
    return Extraction(entities=extraction.entities, triples=triples)


def uncovered_sentences(source_text: str, extraction: Extraction) -> list[str]:
    """Lines whose names, amounts, or dates the first pass did not record.

    A line is kept back when every such token already appears in an entity, subject, or
    object, and some kept quote overlaps the line. A number that was quoted does not
    come back, so a one-sentence passage is not sent twice.
    """
    blob = _mention_blob(extraction)
    quotes = [triple.quote for triple in extraction.triples]
    missing: list[str] = []
    seen: set[str] = set()
    for sentence in _clauses(source_text):
        if sentence in seen or not _needs_another_pass(sentence, blob, quotes):
            continue
        seen.add(sentence)
        missing.append(sentence)
    return missing


def merge_extractions(parts: list[Extraction]) -> Extraction:
    """Combine chunk extractions. The same name, and the same triple, are kept once."""
    entities: dict[str, ExtractedEntity] = {}
    triples: list[ExtractedTriple] = []
    seen: set[tuple[str, str, str, str]] = set()
    for part in parts:
        for entity in part.entities:
            entities.setdefault(entity.name, entity)
        for triple in part.triples:
            key = (triple.subject, triple.predicate, triple.object, triple.quote)
            if key not in seen:
                seen.add(key)
                triples.append(triple)
    return Extraction(entities=list(entities.values()), triples=triples)


def _keep_numbers(payload: str, count: int) -> set[int] | None:
    try:
        raw = _load_json(payload)
    except ExtractionError:
        return None
    keep = raw.get("keep")
    if not isinstance(keep, list):
        return None
    numbers: set[int] = set()
    for value in keep:
        number = _as_index(value, count)
        if number is not None:
            numbers.add(number)
    return numbers


def _as_index(value: object, count: int) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        if not value.strip().isdigit():
            return None
        value = int(value.strip())
    if isinstance(value, int) and 1 <= value <= count:
        return value
    return None


def _load_json(payload: str) -> dict:
    text = _strip_fence(payload)
    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ExtractionError("extraction output was not JSON") from None
        try:
            raw = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ExtractionError("extraction output was not JSON") from exc
    if isinstance(raw, list):
        return {"triples": raw}
    if not isinstance(raw, dict):
        raise ExtractionError("extraction output was not JSON")
    return raw


def _entity_items(raw: dict) -> list[dict]:
    items = []
    for entity in raw.get("entities") or []:
        if isinstance(entity, str) and entity.strip():
            items.append({"name": entity.strip(), "type": "concept"})
            continue
        if not isinstance(entity, dict):
            continue
        name = entity.get("name") or entity.get("entity") or entity.get("label")
        if not name or not str(name).strip():
            continue
        kind = str(entity.get("type") or "concept")
        items.append({"name": str(name).strip(), "type": kind if kind in _TYPES else "other"})
    return items


def _triple_items(raw: dict, source_text: str) -> list[dict]:
    items = []
    for triple in raw.get("triples") or raw.get("relationships") or []:
        repaired = _repair_triple(triple, source_text)
        if repaired is not None:
            items.append(repaired)
    return items


def _repair_triple(triple: object, source_text: str) -> dict | None:
    if not isinstance(triple, dict):
        return None
    subject = str(triple.get("subject") or triple.get("head") or triple.get("source") or "").strip()
    obj = str(triple.get("object") or triple.get("tail") or triple.get("target") or "").strip()
    predicate = triple.get("predicate") or triple.get("relation") or triple.get("relationship")
    predicate = str(predicate or "related to").strip()
    quote = str(triple.get("quote") or "").strip()
    if quote:
        located = _locate_quote(quote, source_text)
        if located is None:
            return None
        quote = located
    if not quote:
        quote = _sentence_containing(source_text, subject, obj)
    if not subject or not obj or not quote:
        return None
    return {"subject": subject, "predicate": predicate, "object": obj, "quote": quote}


def _locate_quote(quote: str, source_text: str) -> str | None:
    """The passage span ``quote`` refers to, or None.

    An exact substring is returned unchanged. Otherwise the quote matches a span
    when both become the same string after each run of spaces, tabs, and line
    breaks is collapsed to one space. One such span is returned as the passage's
    own characters. Zero or several spans do not match.
    """
    if quote in source_text:
        return quote
    folded = _collapse(quote)
    if not folded:
        return None
    collapsed, origins = _collapse_map(source_text)
    spans: list[str] = []
    start = 0
    while True:
        found = collapsed.find(folded, start)
        if found < 0:
            break
        origin_start = origins[found]
        origin_end = origins[found + len(folded) - 1] + 1
        spans.append(source_text[origin_start:origin_end])
        start = found + 1
    if len(spans) == 1:
        return spans[0]
    return None


def _collapse(text: str) -> str:
    return _collapse_map(text)[0]


def _collapse_map(text: str) -> tuple[str, list[int]]:
    """Text with each whitespace run collapsed to one space, and each character's origin.

    Leading and trailing runs are removed. A kept space records the first character
    of that run. Every other character records its own index.
    """
    chars: list[str] = []
    origins: list[int] = []
    index = 0
    length = len(text)
    while index < length:
        if text[index] in _WS:
            run = index
            index += 1
            while index < length and text[index] in _WS:
                index += 1
            if chars and index < length:
                chars.append(" ")
                origins.append(run)
            continue
        chars.append(text[index])
        origins.append(index)
        index += 1
    return "".join(chars), origins


def _sentence_containing(source_text: str, subject: str, obj: str) -> str:
    sentences = [part.strip() for part in _SENTENCE.findall(source_text) if part.strip()]
    for sentence in sentences:
        if subject and obj and subject in sentence and obj in sentence:
            return sentence
    for sentence in sentences:
        if (subject and subject in sentence) or (obj and obj in sentence):
            return sentence
    return ""


def _clauses(text: str) -> list[str]:
    return [part.strip() for part in _CLAUSE_SPLIT.split(text) if part.strip()]


def _mention_blob(extraction: Extraction) -> str:
    parts = [entity.name for entity in extraction.entities]
    for triple in extraction.triples:
        parts.extend((triple.subject, triple.object))
    return "\n".join(parts)


def _needs_another_pass(sentence: str, blob: str, quotes: list[str]) -> bool:
    names = _name_spans(sentence)
    tokens = _fact_tokens(sentence)
    if not names and not tokens:
        return False
    if any(not _has_phrase(blob, name) for name in names):
        return True
    if any(not _has_phrase(blob, token) for token in tokens):
        return True
    return not any(sentence in quote or quote in sentence for quote in quotes if quote)


def _name_spans(sentence: str) -> list[str]:
    found = [match.group(0).strip() for match in _TITLE_NAME.finditer(sentence)]
    found.extend(match.group(0).strip() for match in _MULTI_CAP.finditer(sentence))
    found.extend(match.group(0).strip() for match in _ALLCAPS_NAME.finditer(sentence))
    for match in _MID_CAP.finditer(sentence):
        word = match.group(0)
        if word.casefold() not in _NAME_STOP:
            found.append(word)
    found.sort(key=len, reverse=True)
    kept: list[str] = []
    for name in found:
        if any(name != longer and name in longer for longer in kept):
            continue
        kept.append(name)
    return kept


def _fact_tokens(sentence: str) -> list[str]:
    tokens: list[str] = []
    for pattern in (_NUMBER, _MONTH, _CURRENCY_WORD):
        tokens.extend(match.group(0) for match in pattern.finditer(sentence))
    return tokens


def _has_phrase(blob: str, phrase: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", blob) is not None


def _strip_fence(payload: str) -> str:
    text = payload.strip()
    if text.startswith("```"):
        text = _FENCE.sub("", text).strip()
    return text
