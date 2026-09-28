"""FastAPI application factory.

Mounted in this pass:

==========================================  ==================================================
Route                                       Purpose
==========================================  ==================================================
``GET /health``                             Process up
``GET /auth/google``                        Start OAuth
``GET /auth/google/callback``               Finish OAuth, set the session cookie
``POST /auth/logout``                       Delete the session
``GET /me``                                 Email and name of the signed-in user
``POST /documents``                         Multipart upload (stored, then parsed)
``GET /documents``                          The caller's library
``GET /documents/{id}``                     Metadata plus extracted text for the owner
``DELETE /documents/{id}``                  Delete the row and the file for the owner
==========================================  ==================================================

Not mounted (other passes): ``/documents/{id}/build``, ``/graph``, ``/ask``, key routes.
A session is required on every route except health and the Google start/callback routes.

CORS allows credentials from exactly one origin, ``JEWEL_FRONTEND_URL``, so the Vite
app can send the session cookie with ``fetch(..., {credentials: "include"})``.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from jewel import __version__
from jewel.api.routes import auth, documents, health
from jewel.config import Settings, get_settings
from jewel.db.postgres import apply_schema, connect

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if settings.database_url:
            with connect(settings.database_url) as conn:
                apply_schema(conn)
        else:
            logger.warning("DATABASE_URL is not set; sign-in and documents are unavailable")
        yield

    app = FastAPI(
        title="jewel",
        version=__version__,
        description="A personal live knowledge graph over your own documents.",
        lifespan=lifespan,
    )
    if settings.frontend_url:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[settings.frontend_url],
            allow_credentials=True,
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["Content-Type"],
        )
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(documents.router)
    return app


app = create_app()
