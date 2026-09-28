"""State for one question. The model sees the question and the tool observations only."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ToolTraceEntry:
    name: str
    arguments: dict
    summary: str


@dataclass
class AgentResult:
    question: str
    user_id: str
    as_of: datetime
    tool_trace: list[ToolTraceEntry] = field(default_factory=list)
    tool_calls_used: int = 0
    returned_document_ids: list[str] = field(default_factory=list)
    answer: str = ""
    highlight_entity_ids: list[str] = field(default_factory=list)
    highlight_relationship_ids: list[str] = field(default_factory=list)
