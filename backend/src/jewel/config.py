"""Application settings, loaded from environment variables / ``.env``.

Only placeholders at step 1. The LLM provider is intentionally not chosen yet.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. See ``.env.example`` at the repo root."""

    model_config = SettingsConfigDict(env_prefix="JEWEL_", env_file=".env", extra="ignore")

    env: str = "local"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "change-me-please"
    redis_url: str = "redis://localhost:6379/0"
    llm_provider: str = "unset"  # TODO(step-N): pick a provider (open question).
    llm_model: str = "unset"
    embedding_model: str = "unset"


def get_settings() -> Settings:
    """Return settings (cache with ``functools.lru_cache`` once used widely)."""
    return Settings()
