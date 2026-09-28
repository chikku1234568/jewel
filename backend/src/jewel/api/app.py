"""FastAPI application factory.

Only ``GET /health`` is mounted. The HTTP surface from ``docs/problem-statement.md`` is
named below and stubbed in ``jewel.api.routes``; none of those routers is mounted yet.
A session is required on every route except health and the Google start/callback routes.

==========================================  ==================================================
Route                                       Purpose
==========================================  ==================================================
``GET /health``                             Process up (mounted)
``GET /auth/google``                        Start OAuth
``GET /auth/google/callback``               Finish OAuth, set the session cookie
``POST /auth/logout``                       Delete the session
``GET /me``                                 Email, name, whether a key is saved, key hint
``PUT /me/api-key``                         Store a key (ciphertext only)
``DELETE /me/api-key``                      Delete it
``POST /me/api-key/check``                  Provider accepts the stored key, or an error
``POST /documents``                         Multipart upload
``GET /documents``                          The library
``GET /documents/{id}``                     Metadata plus extracted text for the owner
``POST /documents/{id}/build``              Run or retry ingestion
``DELETE /documents/{id}``                  Delete the file and its exclusive graph data
``GET /graph``                              The caller's subgraph, optional ``document_id``
``DELETE /graph/entities/{id}``             Caller-owned entity
``DELETE /graph/relationships/{id}``        Caller-owned relationship
``POST /ask``                               Start an agent run, returns a run id
``GET /ask/{run_id}/events``                SSE: tool calls, highlights, answer, errors
``POST /ask/{run_id}/compare``              Text-search answer for the same question
==========================================  ==================================================
"""

from fastapi import FastAPI

from jewel import __version__
from jewel.api.routes import health


def create_app() -> FastAPI:
    app = FastAPI(
        title="jewel",
        version=__version__,
        description="A personal live knowledge graph over your own documents.",
    )
    app.include_router(health.router)
    # Not mounted yet (scaffold): auth, keys, documents, graph, ask.
    return app


app = create_app()
