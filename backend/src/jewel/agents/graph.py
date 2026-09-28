"""One tool-using agent.

The loop is the contract LangGraph's ``create_agent`` will host: the model chooses
``search_graph`` or ``read_document``, at most four times, then answers. This module
does not import LangGraph yet, so it can be tested without that package and without
colliding on the shared lockfile. The model is given the question and tool observations.
It is not given the user id, a database session, or an API key.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from jewel.agents.state import AgentResult, ToolTraceEntry
from jewel.agents.tools import ToolError, read_document, search_graph
from jewel.kg.memory_store import MemoryGraphStore
from jewel.llm.base import EmbeddingModel

MAX_TOOL_CALLS = 4


@dataclass(frozen=True)
class ToolRequest:
    name: str
    arguments: dict


@dataclass(frozen=True)
class Decision:
    """Either a tool call or a final answer."""

    answer: str | None = None
    tool: ToolRequest | None = None


Decider = Callable[[str, list[str], bool], Decision]


def run_agent(
    *,
    question: str,
    user_id: str,
    store: MemoryGraphStore,
    embedder: EmbeddingModel,
    decider: Decider,
    as_of: datetime,
) -> AgentResult:
    """Run the loop. ``decider`` sees the question and observations, not ``user_id``."""
    result = AgentResult(question=question, user_id=user_id, as_of=as_of)
    observations: list[str] = []
    allowed: set[str] = set()
    while result.tool_calls_used < MAX_TOOL_CALLS:
        decision = decider(question, list(observations), False)
        if decision.tool is None:
            result.answer = decision.answer or ""
            return result
        summary = _call_tool(decision.tool, result, store, embedder, allowed, observations)
        result.tool_trace.append(
            ToolTraceEntry(
                name=decision.tool.name, arguments=decision.tool.arguments, summary=summary
            )
        )
        result.tool_calls_used += 1
    forced = decider(question, list(observations), True)
    result.answer = forced.answer or ""
    return result


def _call_tool(
    tool: ToolRequest,
    result: AgentResult,
    store: MemoryGraphStore,
    embedder: EmbeddingModel,
    allowed: set[str],
    observations: list[str],
) -> str:
    if tool.name == "search_graph":
        query = str(tool.arguments.get("query", result.question))
        found = search_graph(store, embedder, result.user_id, query, result.as_of)
        allowed.update(hit.document_id for hit in found.documents)
        result.returned_document_ids = sorted(allowed)
        result.highlight_entity_ids = found.entity_ids
        result.highlight_relationship_ids = found.relationship_ids
        docs = ", ".join(f"{hit.filename} id={hit.document_id}" for hit in found.documents[:8])
        quotes = " | ".join(triple.quote for triple in found.triples[:8])
        summary = f"documents: {docs}. quotes: {quotes}"
        observations.append(summary)
        return summary
    if tool.name == "read_document":
        document_id = str(tool.arguments.get("document_id", ""))
        try:
            text = read_document(store, result.user_id, document_id, allowed)
        except ToolError as exc:
            observations.append(str(exc))
            return str(exc)
        observations.append(text[:240])
        return "opened document"
    observations.append("unknown tool")
    return "unknown tool"
