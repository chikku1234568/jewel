"""State for one question. The model sees the question and the tool observations only."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ToolTraceEntry:
    name: str
    arguments: dict
    summary: str


@dataclass(frozen=True)
class KeptTriple:
    """What ``read_document`` needs from a triple ``search_graph`` kept."""

    document_id: str
    chunk_ordinal: int | None
    quote: str


@dataclass
class AgentResult:
    question: str
    user_id: str
    as_of: datetime
    tool_trace: list[ToolTraceEntry] = field(default_factory=list)
    tool_calls_used: int = 0
    returned_document_ids: list[str] = field(default_factory=list)
    # Every triple any search in this run kept, in first-seen order, without repeats.
    kept_triples: list[KeptTriple] = field(default_factory=list)
    answer: str = ""
    highlight_entity_ids: list[str] = field(default_factory=list)
    highlight_relationship_ids: list[str] = field(default_factory=list)
