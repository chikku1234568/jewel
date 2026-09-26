"""FastAPI application factory.

Step 1 exposes ``GET /health`` only. Planned routers (not implemented):

* ``POST /episodes``: paste text or upload a document, stored as an episode
* ``POST /runs``: run EHR Order -> Laboratory Monitor -> Clinical Pharmacologist,
  streaming the five progress steps (SSE)
* ``POST /ask``: graph answer (temporal PPR retrieval) and naive-RAG baseline
* ``GET /graph``: subgraph valid at ``as_of`` for the graph view
"""

from fastapi import FastAPI

from jewel import __version__
from jewel.api.routes import health


def create_app() -> FastAPI:
    app = FastAPI(
        title="jewel",
        version=__version__,
        description="Pharmacotherapy regimen lab alert showcase. Not for clinical use.",
    )
    app.include_router(health.router)
    return app


app = create_app()
