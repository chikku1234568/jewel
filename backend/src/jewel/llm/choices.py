"""Turn a request body into an embedder. The API key stays on this object only."""

import ipaddress
import re
from urllib.parse import urlparse

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from jewel.llm.embedders import DEFAULT_MODEL, OpenAIEmbedder
from jewel.llm.openai_chat import OpenAICompatibleChat

_MODEL_NAME = re.compile(r"^[A-Za-z0-9._:/-]{1,80}$")
_PUBLIC_HOST = "API base URL must be https and a public host."


def clean_model_name(value: str) -> str:
    """A model id, with no spaces or header characters."""
    value = value.strip()
    if not _MODEL_NAME.fullmatch(value):
        raise ValueError("Model id must be 1 to 80 letters, digits, or . _ : / -")
    return value


def clean_api_key(value: str) -> str:
    """The bearer token. Empty is allowed; a newline would be injected into the header."""
    value = value.strip()
    if len(value) > 400 or any(ord(char) < 33 or ord(char) == 127 for char in value):
        raise ValueError("API key must be a single token of at most 400 characters.")
    return value


def clean_api_base(value: str) -> str:
    """https URL with a public host. The server fetches this URL with the caller's key."""
    value = value.strip().rstrip("/")
    if len(value) > 200:
        raise ValueError("API base URL is too long.")
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme != "https"
        or not host
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError(_PUBLIC_HOST)
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal")):
        raise ValueError(_PUBLIC_HOST)
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError(_PUBLIC_HOST)
    return value


class AgentChoice(BaseModel):
    """Who writes the answer. Empty api_key uses KIMI_API_KEY on the server."""

    model_config = ConfigDict(extra="forbid")

    model: str = "kimi-k2.6"
    base_url: str = "https://api.moonshot.ai/v1"
    api_key: str = Field(default="", repr=False)

    @field_validator("model")
    @classmethod
    def _model(cls, value: str) -> str:
        return clean_model_name(value)

    @field_validator("base_url")
    @classmethod
    def _base(cls, value: str) -> str:
        return clean_api_base(value)

    @field_validator("api_key")
    @classmethod
    def _key(cls, value: str) -> str:
        return clean_api_key(value)


class ExtractionChoice(BaseModel):
    """Who reads the file and writes triples. The user supplies the API key."""

    model_config = ConfigDict(extra="forbid")

    provider: str = "api"
    model: str = "kimi-k2.6"
    base_url: str = "https://api.moonshot.ai/v1"
    api_key: str = Field(default="", repr=False)

    @field_validator("provider")
    @classmethod
    def _provider(cls, value: str) -> str:
        if value != "api":
            raise ValueError("Extraction needs an API provider.")
        return value

    @field_validator("model")
    @classmethod
    def _model(cls, value: str) -> str:
        return clean_model_name(value)

    @field_validator("base_url")
    @classmethod
    def _base(cls, value: str) -> str:
        return clean_api_base(value)

    @field_validator("api_key")
    @classmethod
    def _key(cls, value: str) -> str:
        return clean_api_key(value)


class EmbeddingChoice(BaseModel):
    """Who embeds the file and the question. The user supplies the API key."""

    model_config = ConfigDict(extra="forbid")

    provider: str = "api"
    model: str = "text-embedding-3-small"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = Field(default="", repr=False)

    @field_validator("provider")
    @classmethod
    def _provider(cls, value: str) -> str:
        if value != "api":
            raise ValueError("Embedding needs an API provider.")
        return value

    @field_validator("model")
    @classmethod
    def _model(cls, value: str) -> str:
        return clean_model_name(value)

    @field_validator("base_url")
    @classmethod
    def _base(cls, value: str) -> str:
        return clean_api_base(value)

    @field_validator("api_key")
    @classmethod
    def _key(cls, value: str) -> str:
        return clean_api_key(value)


def make_agent_chat(choice: AgentChoice):
    """OpenAI-compatible chat for the answer agent. Defaults to server-side Kimi."""
    import os

    key = choice.api_key.strip() or os.environ.get("KIMI_API_KEY", "").strip()
    model = choice.model.strip() or "kimi-k2.6"
    base = choice.base_url.strip() or "https://api.moonshot.ai/v1"
    if not key:
        raise HTTPException(status_code=400, detail="An API key is required for the agent")
    return OpenAICompatibleChat(model, base, key)


def make_chat(choice: ExtractionChoice):
    """OpenAI-compatible chat for extraction. The request must carry the user's key."""
    if choice.provider == "local":
        raise HTTPException(
            status_code=400,
            detail="Extraction needs an API key. A local model is not available.",
        )
    if choice.provider != "api":
        raise HTTPException(status_code=400, detail="Unknown extraction provider")
    if not choice.api_key.strip():
        raise HTTPException(
            status_code=400, detail="An API key is required for this extraction model"
        )
    if not choice.model.strip() or not choice.base_url.strip():
        raise HTTPException(status_code=400, detail="Extraction model and base URL are required")
    return OpenAICompatibleChat(choice.model.strip(), choice.base_url.strip(), choice.api_key)


def make_embedder(choice: EmbeddingChoice):
    """OpenAI-compatible embeddings. The request must carry the user's key."""
    if choice.provider == "local":
        raise HTTPException(
            status_code=400,
            detail="Embedding needs an API key. A local model is not available.",
        )
    if choice.provider != "api":
        raise HTTPException(status_code=400, detail="Unknown embedding provider")
    if not choice.api_key.strip():
        raise HTTPException(
            status_code=400, detail="An API key is required for this embedding model"
        )
    if not choice.model.strip() or not choice.base_url.strip():
        raise HTTPException(status_code=400, detail="Model and base URL are required")
    return OpenAIEmbedder(choice.model.strip(), choice.base_url.strip(), choice.api_key)


def stored_model(documents) -> str:
    """The model a user's graph was built with. Older graphs count as the default."""
    found = {doc.embedding_model or DEFAULT_MODEL for doc in documents}
    if len(found) > 1:
        names = ", ".join(sorted(found))
        raise HTTPException(
            status_code=409,
            detail=(
                f"This graph mixes embedding models ({names}). Rebuild the files with one model."
            ),
        )
    return next(iter(found), DEFAULT_MODEL)


def require_same_model(documents, choice: EmbeddingChoice) -> None:
    used = stored_model(documents)
    if choice.model != used:
        raise HTTPException(
            status_code=409,
            detail=f"This graph was built with {used}. Ask with that same model.",
        )
