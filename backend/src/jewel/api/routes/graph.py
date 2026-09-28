"""The signed-in user's graph."""

from fastapi import APIRouter, HTTPException, Request

from jewel.auth.dependencies import CurrentUser
from jewel.kg.neo4j_store import Neo4jGraphStore

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("")
def read_graph(request: Request, user: CurrentUser) -> dict:
    """Entities, documents, and triples for the signed-in user."""
    store = _store(request).load_user(str(user["id"]))
    subgraph = store.subgraph(str(user["id"]))
    return {
        "documents": [
            {"id": doc.id, "filename": doc.filename, "embedding_model": doc.embedding_model}
            for doc in subgraph.documents
        ],
        "entities": [
            {"id": entity.id, "name": entity.name, "type": entity.type}
            for entity in subgraph.entities
        ],
        "triples": [
            {
                "id": triple.id,
                "source_id": triple.source_id,
                "target_id": triple.target_id,
                "predicate": triple.predicate,
                "quote": triple.quote,
                "document_id": triple.document_id,
            }
            for triple in subgraph.triples
        ],
    }


def _store(request: Request) -> Neo4jGraphStore:
    driver = getattr(request.app.state, "neo4j", None)
    if driver is None:
        raise HTTPException(status_code=503, detail="Neo4j is not available")
    return Neo4jGraphStore(driver)
