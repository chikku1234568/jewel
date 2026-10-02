"""One question against the signed-in user's graph."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import Field

from jewel.agents.graph import run_agent
from jewel.agents.kimi_decider import KimiDecider
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


class AskBody(EmbeddingChoice):
    question: str = Field(min_length=1, max_length=2000)
    agent: AgentChoice = AgentChoice()


@router.post("")
def ask(body: AskBody, request: Request, user: CurrentUser, conn: DbConn) -> dict:
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
        decider=KimiDecider(make_agent_chat(body.agent)),
        as_of=datetime.now(UTC),
        # Bound to the session user here; the model only ever names a document id.
        stored_chunks=lambda document_id: repository.chunk_texts(conn, user["id"], document_id),
    )
    return {
        "answer": result.answer,
        "tool_calls_used": result.tool_calls_used,
        "trace": [{"name": entry.name, "summary": entry.summary} for entry in result.tool_trace],
        "highlight_entity_ids": result.highlight_entity_ids,
        "highlight_relationship_ids": result.highlight_relationship_ids,
    }
