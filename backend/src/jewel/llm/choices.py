"""Turn a request body into an embedder. The API key stays on this object only."""

from fastapi import HTTPException
from pydantic import BaseModel, Field

from jewel.llm.embedders import DEFAULT_MODEL, LOCAL_MODELS, LocalEmbedder, OpenAIEmbedder
from jewel.llm.ollama import OllamaChat
from jewel.llm.openai_chat import OpenAICompatibleChat

LOCAL_EXTRACTION_MODELS = ("qwen2.5:7b-instruct",)


class AgentChoice(BaseModel):
    """Who writes the answer. Empty api_key uses KIMI_API_KEY on the server."""

    model: str = "kimi-k2.6"
    base_url: str = "https://api.moonshot.ai/v1"
    api_key: str = Field(default="", repr=False)


class ExtractionChoice(BaseModel):
    """Who reads the file and writes triples. Separate from the embedding model."""

    provider: str = "local"
    model: str = "qwen2.5:7b-instruct"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = Field(default="", repr=False)


class EmbeddingChoice(BaseModel):
    provider: str = "local"
    model: str = DEFAULT_MODEL
    base_url: str = "https://api.openai.com/v1"
    api_key: str = Field(default="", repr=False)


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
    """Local Ollama model, or an OpenAI-compatible chat call."""
    if choice.provider == "local":
        if choice.model not in LOCAL_EXTRACTION_MODELS:
            raise HTTPException(status_code=400, detail="Unknown local extraction model")
        return OllamaChat(model=choice.model)
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
    """Local fastembed model, or an OpenAI-compatible embeddings call."""
    if choice.provider == "local":
        if choice.model not in LOCAL_MODELS:
            raise HTTPException(status_code=400, detail="Unknown local embedding model")
        return LocalEmbedder(choice.model)
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
