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

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


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
    """Validate model JSON and drop triples whose quote is not in ``source_text``."""
    try:
        raw = json.loads(_strip_fence(payload))
        parsed = Extraction.model_validate(raw)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ExtractionError("extraction output did not match the schema") from exc
    kept = [triple for triple in parsed.triples if triple.quote in source_text]
    names = {triple.subject for triple in kept} | {triple.object for triple in kept}
    entities = [
        entity for entity in parsed.entities if entity.name in names or entity.name in source_text
    ]
    return Extraction(entities=entities, triples=kept)


def _strip_fence(payload: str) -> str:
    text = payload.strip()
    if text.startswith("```"):
        text = _FENCE.sub("", text).strip()
    return text
