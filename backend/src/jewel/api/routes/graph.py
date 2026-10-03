"""The signed-in user's graph."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from jewel.auth.dependencies import CurrentUser
from jewel.kg.neo4j_store import Neo4jGraphStore

router = APIRouter(prefix="/graph", tags=["graph"])

_MAX_RELATION_ID = 80


class DeleteRelations(BaseModel):
    """Ids of RELATED_TO edges to remove. There is no route that adds a relation."""

    ids: list[str] = Field(min_length=1, max_length=400)


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


@router.delete("/relations")
def delete_relations(body: DeleteRelations, request: Request, user: CurrentUser) -> dict:
    """Remove relations that belong to the signed-in user. Unknown ids are skipped."""
    ids: list[str] = []
    seen: set[str] = set()
    for raw in body.ids:
        item = raw.strip()
        if not item or item in seen:
            continue
        if len(item) > _MAX_RELATION_ID:
            raise HTTPException(status_code=400, detail="A relation id is not valid")
        seen.add(item)
        ids.append(item)
    if not ids:
        raise HTTPException(status_code=400, detail="Choose at least one relation")
    deleted = _store(request).delete_triples(str(user["id"]), ids)
    return {"deleted": deleted}


def _store(request: Request) -> Neo4jGraphStore:
    driver = getattr(request.app.state, "neo4j", None)
    if driver is None:
        raise HTTPException(status_code=503, detail="Neo4j is not available")
    return Neo4jGraphStore(driver)
