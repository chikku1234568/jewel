"""Application settings, loaded from environment variables / ``.env``.

Placeholders only. Secrets default to empty strings and nothing here is used to make a
network call yet. Model ids are deliberately empty: they are chosen at implementation
time from https://docs.x.ai and must not be frozen into code.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

LLM_BASE_URL = "https://api.x.ai/v1"
"""OpenAI-compatible xAI endpoint. Fixed in this version: there is no base-URL override."""


class Settings(BaseSettings):
    """Runtime configuration. See ``.env.example`` at the repo root."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = Field(default="local", validation_alias="JEWEL_ENV")

    # Google OAuth (identity scopes only: openid, email, profile).
    google_client_id: str = Field(default="", validation_alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(default="", validation_alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str = Field(default="", validation_alias="GOOGLE_REDIRECT_URI")

    # Server-side sessions and encryption of user API keys at rest.
    session_secret: str = Field(default="", validation_alias="SESSION_SECRET")
    key_encryption_secret: str = Field(default="", validation_alias="KEY_ENCRYPTION_SECRET")

    # Postgres: accounts, sessions, document rows, ciphertext keys, chunk rows.
    database_url: str = Field(default="", validation_alias="DATABASE_URL")

    # Neo4j 5.x Community: the per-user knowledge graph.
    neo4j_uri: str = Field(default="bolt://localhost:7687", validation_alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", validation_alias="NEO4J_USER")
    neo4j_password: str = Field(default="", validation_alias="NEO4J_PASSWORD")

    # Uploaded file bytes live on a local volume, addressed by opaque stored paths.
    upload_dir: str = Field(default="./data/uploads", validation_alias="JEWEL_UPLOAD_DIR")

    # Model ids (xAI, OpenAI-compatible). Empty until chosen from the current docs.
    llm_model: str = Field(default="", validation_alias="JEWEL_LLM_MODEL")
    embedding_model: str = Field(default="", validation_alias="JEWEL_EMBEDDING_MODEL")

    @property
    def llm_base_url(self) -> str:
        """Base URL for chat and embeddings. Not configurable in this version."""
        return LLM_BASE_URL


def get_settings() -> Settings:
    """Return settings (cache with ``functools.lru_cache`` once used widely)."""
    return Settings()
