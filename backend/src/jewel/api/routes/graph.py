"""Graph routes (stub, NOT mounted yet). Session required.

* ``GET /graph``: the caller's subgraph; optional ``document_id`` filter.
* ``DELETE /graph/entities/{id}``: delete a caller-owned entity.
* ``DELETE /graph/relationships/{id}``: delete a caller-owned relationship.

The user id always comes from the session, never from a client-supplied filter alone.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/graph", tags=["graph"])  # no endpoints yet
