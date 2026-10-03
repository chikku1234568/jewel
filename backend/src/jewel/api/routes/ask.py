"""One question against the signed-in user's graph."""

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from jewel.agents.chat_model import ToolCallingChat
from jewel.agents.graph import MAX_TOOL_CALLS, run_agent
from jewel.auth.dependencies import CurrentUser
from jewel.db.postgres import DbConn
from jewel.documents import repository
from jewel.kg.neo4j_store import Neo4jGraphStore
from jewel.llm.choices import (
    AgentChoice,
    EmbeddingChoice,
    make_agent_chat,
    make_embedder,
    require_same_model,
)

router = APIRouter(prefix="/ask", tags=["ask"])

# C0 controls other than tab and newline, plus DEL. A question is text, not a header
# or a file. Prompt text is still only a question: the tools ignore it as an instruction.
_CONTROL = {ord(char) for char in "\t\n\r"}


def clean_question(value: str) -> str:
    """Strip the question and refuse nulls and other control characters."""
    value = value.strip()
    if any((ord(char) < 32 and ord(char) not in _CONTROL) or ord(char) == 127 for char in value):
        raise ValueError("Question must be plain text.")
    if not value:
        raise ValueError("Question is empty.")
    return value


class AskBody(EmbeddingChoice):
    question: str = Field(min_length=1, max_length=2000)
    agent: AgentChoice = AgentChoice()

    @field_validator("question")
    @classmethod
    def _question(cls, value: str) -> str:
        return clean_question(value)


class AskTraceStep(BaseModel):
    """One tool the answer model called, as shown in the Steps list."""

    model_config = ConfigDict(extra="ignore")

    name: Literal["search_graph", "read_document"]
    summary: str


class AskResponse(BaseModel):
    """The only fields Ask returns. The key, the user id, and the graph store are absent."""

    model_config = ConfigDict(extra="ignore")

    answer: str
    tool_calls_used: int = Field(ge=0, le=MAX_TOOL_CALLS)
    trace: list[AskTraceStep]
    highlight_entity_ids: list[str]
    highlight_relationship_ids: list[str]


@router.post("", response_model=AskResponse)
def ask(body: AskBody, request: Request, user: CurrentUser, conn: DbConn) -> AskResponse:
    """Search the user's current graph and answer. A new file is visible after it is built."""
    driver = getattr(request.app.state, "neo4j", None)
    if driver is None:
        raise HTTPException(status_code=503, detail="Neo4j is not available")
    store = Neo4jGraphStore(driver).load_user(str(user["id"]))
    if not store.documents:
        raise HTTPException(status_code=409, detail="Build a document before asking")
    require_same_model(store.documents.values(), body)
    embedder = make_embedder(body)
    result = run_agent(
        question=body.question,
        user_id=str(user["id"]),
        store=store,
        embedder=embedder,
        # The answer call keeps the default 1024-token budget; Kimi thinking stays off.
        model=ToolCallingChat(client=make_agent_chat(body.agent)),
        as_of=datetime.now(UTC),
        # Bound to the session user here; the model only ever names a document id.
        stored_chunks=lambda document_id: repository.chunk_texts(conn, user["id"], document_id),
    )
    return AskResponse(
        answer=result.answer,
        tool_calls_used=result.tool_calls_used,
        trace=[AskTraceStep(name=entry.name, summary=entry.summary) for entry in result.tool_trace],
        highlight_entity_ids=result.highlight_entity_ids,
        highlight_relationship_ids=result.highlight_relationship_ids,
    )
