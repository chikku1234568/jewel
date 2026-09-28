"""Entity and triple extraction.

The model returns JSON. It is data, never code or a database query. A triple is kept
only when its quote is copied from the document text.

Graph construction calls a local open-source model (Qwen via Ollama). The user's API
key is not used here.
"""

import json
import re

from pydantic import BaseModel, Field, ValidationError

from jewel.kg.schema import EntityType

_SENTENCE = re.compile(r"[^.!?]+[.!?]?")
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_TYPES = {"person", "organization", "place", "concept", "other"}


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
        if triple.quote in source_text:
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
    if quote and quote not in source_text:
        return None
    if not quote:
        quote = _sentence_containing(source_text, subject, obj)
    if not subject or not obj or not quote:
        return None
    return {"subject": subject, "predicate": predicate, "object": obj, "quote": quote}


def _sentence_containing(source_text: str, subject: str, obj: str) -> str:
    sentences = [part.strip() for part in _SENTENCE.findall(source_text) if part.strip()]
    for sentence in sentences:
        if subject and obj and subject in sentence and obj in sentence:
            return sentence
    for sentence in sentences:
        if (subject and subject in sentence) or (obj and obj in sentence):
            return sentence
    return ""


def _strip_fence(payload: str) -> str:
    text = payload.strip()
    if text.startswith("```"):
        text = _FENCE.sub("", text).strip()
    return text
