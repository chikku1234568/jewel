"""In-memory shape of one user's graph. Neo4j stores the same fields."""

from dataclasses import dataclass, field
from datetime import datetime


def name_key(name: str) -> str:
    """Identity key for an entity inside one user. Display spelling is kept separately."""
    return " ".join(name.casefold().split())


@dataclass
class GraphDocument:
    id: str
    user_id: str
    filename: str
    text: str
    embedding: list[float]
    document_date: datetime | None = None


@dataclass
class GraphEntity:
    id: str
    user_id: str
    name: str
    name_key: str
    type: str
    embedding: list[float]


@dataclass
class GraphMention:
    id: str
    user_id: str
    entity_id: str
    document_id: str
    quote: str
    valid_at: datetime | None = None
    invalid_at: datetime | None = None


@dataclass
class GraphTriple:
    id: str
    user_id: str
    source_id: str
    target_id: str
    predicate: str
    quote: str
    document_id: str
    embedding: list[float] = field(default_factory=list)
    valid_at: datetime | None = None
    invalid_at: datetime | None = None


@dataclass
class UserSubgraph:
    """Every element already belongs to one user."""

    documents: list[GraphDocument]
    entities: list[GraphEntity]
    mentions: list[GraphMention]
    triples: list[GraphTriple]
