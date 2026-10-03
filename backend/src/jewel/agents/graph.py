"""One tool-using agent, hosted by LangGraph (``langchain.agents.create_agent``).

LangGraph is only the control flow: a model turn, then a tool, then a model turn, until
the model answers. The two tools call the functions in ``jewel.agents.tools``; Personalized
PageRank stays in ``jewel.retrieval.hippo.ppr`` and Neo4j stays the document graph.

What the model sees: the system prompt, the question, and tool observations. What it
never sees: the user id, the graph store, the database, or an API key. Those travel in
``RunContext``, which LangGraph hands to each tool through ``ToolRuntime``; the runtime
parameter is not part of the tool schema sent to the model.

The cap is enforced by ``ToolBudget`` (middleware around every model call): one tool call
per model turn, at most ``MAX_TOOL_CALLS`` in a run, and once they are spent the model is
called with no tools and told to answer.
"""

from datetime import datetime

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain.tools import ToolRuntime, tool
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from jewel.agents.state import AgentResult, KeptTriple, ToolTraceEntry
from jewel.agents.tools import ChunkSource, ToolError, read_document, search_graph
from jewel.kg.memory_store import MemoryGraphStore
from jewel.llm.base import EmbeddingModel
from jewel.retrieval.ask_log import log_event

# One search and one read per part of a compound question, plus a retry, then it must stop.
MAX_TOOL_CALLS = 12

SYSTEM_PROMPT = (
    "You answer questions about a user's own documents. Use the tools; do not answer from "
    "memory. A question may have several parts. For every part that no quote has answered "
    "yet, call search_graph with a query for that part alone. It returns matching files, "
    "their ids, and the quoted sentences behind the facts it found. If a part is still "
    "missing, call search_graph again with a narrower query. read_document opens at most "
    "three passages of a file search_graph already returned, and only passages that "
    "contain those facts. It does not search the rest of the file. A missing part needs "
    "another search_graph, not another read. A filename is not a fact. Call one tool at "
    f"a time, up to {MAX_TOOL_CALLS} calls. Keep going until every part is answered by a "
    "quote or those calls are used up, and only then answer. Copy quotes from the "
    "observations, name the file each quote comes from, and for any part still missing "
    "say plainly that the documents do not answer it. Do not invent facts."
)
FORCE_ANSWER = " You have used all your tool calls. Answer now from what the tools returned."
_BUDGET_SPENT = "The tool budget is spent. Answer from the observations already returned."


class RunContext:
    """Per-question dependencies, bound by the caller. Never shown to the model.

    A plain class, not a dataclass: LangGraph's tool schema checks the context with a
    single ``isinstance``, while a dataclass would make pydantic validate each field, and
    it cannot validate the ``EmbeddingModel`` protocol.
    """

    def __init__(
        self,
        *,
        store: MemoryGraphStore,
        embedder: EmbeddingModel,
        result: AgentResult,
        stored_chunks: ChunkSource | None = None,
    ) -> None:
        self.store = store
        self.embedder = embedder
        self.result = result
        self.stored_chunks = stored_chunks
        # Document ids any search in this run returned; read_document opens only these.
        self.allowed: set[str] = set()


# ``runtime`` is injected by LangGraph and left out of the schema the model sees.
@tool("search_graph")
def search_graph_tool(query: str, runtime: ToolRuntime[RunContext]) -> str:
    """Search the graph for one part of the question.

    Returns filenames, document ids, and quotes. Call again with a narrower query when a
    part is still unanswered. A filename is not a fact.
    """
    context = runtime.context
    result = context.result
    if _over_budget(result):
        return _BUDGET_SPENT
    found = search_graph(context.store, context.embedder, result.user_id, query, result.as_of)
    context.allowed.update(hit.document_id for hit in found.documents)
    result.returned_document_ids = sorted(context.allowed)
    for triple in found.triples:
        kept = KeptTriple(triple.document_id, triple.chunk_ordinal, triple.quote)
        if kept not in result.kept_triples:
            result.kept_triples.append(kept)
    result.highlight_entity_ids = found.entity_ids
    result.highlight_relationship_ids = found.relationship_ids
    docs = ", ".join(f"{hit.filename} id={hit.document_id}" for hit in found.documents)
    quotes = " | ".join(triple.quote for triple in found.triples)
    summary = f"documents: {docs}. quotes: {quotes}"
    _trace(result, "search_graph", {"query": query}, summary)
    return summary


@tool("read_document")
def read_document_tool(document_id: str, runtime: ToolRuntime[RunContext]) -> str:
    """Open up to three passages that contain facts search_graph already returned.

    This does not search the rest of the file. A part with no quote needs another
    search_graph call.
    """
    context = runtime.context
    result = context.result
    if _over_budget(result):
        return _BUDGET_SPENT
    try:
        chunks = read_document(
            context.store,
            result.user_id,
            document_id,
            context.allowed,
            result.kept_triples,
            context.stored_chunks,
        )
    except ToolError as exc:
        _trace(result, "read_document", {"document_id": document_id}, str(exc))
        return str(exc)
    summary = f"opened {len(chunks)} {'passage' if len(chunks) == 1 else 'passages'}"
    log_event({"event": "read", "document_id": document_id, "passages": len(chunks)})
    _trace(result, "read_document", {"document_id": document_id}, summary)
    # The model sees the whole chunk text: no slicing, or it cannot check a quote.
    return _passages_observation(document_id, chunks)


class ToolBudget(AgentMiddleware):
    """At most ``limit`` tool calls per run, one per model turn; then the model must answer.

    The count is the number of tool results already in the conversation, so it cannot
    drift from what actually ran. A reply that asks for several tools at once keeps only
    the first, which keeps the trace in order and the cap exact.
    """

    def __init__(self, limit: int = MAX_TOOL_CALLS) -> None:
        super().__init__()
        self.limit = limit

    def wrap_model_call(self, request: ModelRequest, handler) -> ModelResponse:
        used = sum(isinstance(message, ToolMessage) for message in request.messages)
        if used < self.limit:
            return _keep_tool_calls(handler(request), 1)
        system = request.system_message.text if request.system_message else SYSTEM_PROMPT
        forced = request.override(tools=[], system_message=SystemMessage(system + FORCE_ANSWER))
        # No tools are offered, so a real model cannot call one; drop any it invents.
        return _keep_tool_calls(handler(forced), 0)


def run_agent(
    *,
    question: str,
    user_id: str,
    store: MemoryGraphStore,
    embedder: EmbeddingModel,
    model: BaseChatModel,
    as_of: datetime,
    stored_chunks: ChunkSource | None = None,
) -> AgentResult:
    """Answer one question. ``model`` sees the question and observations, not ``user_id``.

    ``stored_chunks`` reads this user's stored build chunks; it is bound by the caller.
    """
    result = AgentResult(question=question, user_id=user_id, as_of=as_of)
    log_event({"event": "ask", "question": question}, truncate=True)
    agent = create_agent(
        model,
        tools=[search_graph_tool, read_document_tool],
        system_prompt=SYSTEM_PROMPT,
        middleware=[ToolBudget(MAX_TOOL_CALLS)],
        context_schema=RunContext,
    )
    context = RunContext(store=store, embedder=embedder, result=result, stored_chunks=stored_chunks)
    state = agent.invoke({"messages": [HumanMessage(question)]}, context=context)
    final = state["messages"][-1]
    result.answer = final.text if isinstance(final, AIMessage) else ""
    result.tool_calls_used = len(result.tool_trace)
    return result


def _over_budget(result: AgentResult) -> bool:
    """True once this run has already finished ``MAX_TOOL_CALLS`` tool calls.

    ``ToolBudget`` removes the tools before this can run. The check stays here so a
    search or a read still does no work if a call arrives after that.
    """
    return len(result.tool_trace) >= MAX_TOOL_CALLS


def _trace(result: AgentResult, name: str, arguments: dict, summary: str) -> None:
    result.tool_trace.append(ToolTraceEntry(name=name, arguments=arguments, summary=summary))


def _keep_tool_calls(response: ModelResponse, limit: int) -> ModelResponse:
    messages = []
    for message in response.result:
        if isinstance(message, AIMessage) and (
            len(message.tool_calls) > limit or (limit == 0 and message.invalid_tool_calls)
        ):
            update = {"tool_calls": message.tool_calls[:limit]}
            if limit == 0:
                update["invalid_tool_calls"] = []
            message = message.model_copy(update=update)
        messages.append(message)
    return ModelResponse(result=messages, structured_response=response.structured_response)


def _passages_observation(document_id: str, chunks: list[str]) -> str:
    if not chunks:
        return f"document id={document_id}: no passage of it holds a quote the search kept"
    parts = [f"document id={document_id}, passage {n}:\n{text}" for n, text in enumerate(chunks, 1)]
    return "\n\n".join(parts)
