"""Each kept triple remembers the build chunk it came from. No network and no database."""

import json
import random
import re
import threading
import time

from jewel.ingestion.chunking import build_chunks
from jewel.ingestion.live import build_parsed_text
from jewel.kg.memory_store import MemoryGraphStore
from jewel.kg.neo4j_store import Neo4jGraphStore
from jewel.llm.hashing import HashingEmbedder
from tests.keep_verdict import keep_all_verdict

USER = "user-a"
_FACT = re.compile(r"Item (\d+) is stored in bay (\d+)\.")


def _long_text() -> str:
    """About 12 chunks; every sentence is unique, so a quote pins down its chunk."""
    return " ".join(f"Item {i} is stored in bay {i % 97}." for i in range(1400))


class ShuffledApiChat:
    """API-shaped chat whose replies finish out of order (random short sleeps)."""

    model = "fake-api"

    def __init__(self) -> None:
        self._random = random.Random(7)
        self._lock = threading.Lock()

    def complete(self, system: str, user: str, **_kwargs) -> str:
        verdict = keep_all_verdict(user)
        if verdict is not None:
            return verdict
        with self._lock:
            delay = self._random.uniform(0, 0.02)
        time.sleep(delay)
        triples = [
            {
                "subject": f"Item {item}",
                "predicate": "is stored in",
                "object": f"bay {bay}",
                "quote": match.group(0),
            }
            for match in list(_FACT.finditer(user))[1:3]  # skip a possibly cut first one
            for item, bay in [match.groups()]
        ]
        return json.dumps({"entities": [], "triples": triples})


def test_parallel_workers_keep_the_chunk_ordinal_pairing() -> None:
    text = _long_text()
    saved: list[list[str]] = []
    store = MemoryGraphStore()
    kept = build_parsed_text(
        document_id="doc",
        user_id=USER,
        filename="inventory.txt",
        text=text,
        document_date=None,
        chat=ShuffledApiChat(),
        embedder=HashingEmbedder(),
        store=store,
        save_chunks=saved.append,
    )
    chunks = [chunk.text for chunk in build_chunks(text)]
    assert saved == [chunks]  # stored once, in ordinal order, before extraction
    triples = store.subgraph(USER).triples
    assert kept == len(triples) > 0
    assert {triple.chunk_ordinal for triple in triples} == set(range(len(chunks)))
    for triple in triples:
        assert triple.quote in chunks[triple.chunk_ordinal]


def test_chunks_are_saved_before_the_first_model_call() -> None:
    events: list[str] = []

    class Chat:
        model = "fake"

        def complete(self, system: str, user: str) -> str:
            events.append("model")
            verdict = keep_all_verdict(user)
            if verdict is not None:
                return verdict
            return (
                '{"entities":[],"triples":[{"subject":"a","predicate":"b","object":"c",'
                '"quote":"a b c"}]}'
            )

    build_parsed_text(
        document_id="doc",
        user_id=USER,
        filename="note.txt",
        text="a b c",
        document_date=None,
        chat=Chat(),
        embedder=HashingEmbedder(),
        store=MemoryGraphStore(),
        save_chunks=lambda texts: events.append("save"),
    )
    assert events == ["save", "model", "model"]


class _Session:
    """Records writes; answers the four load_user reads from canned rows."""

    def __init__(self, triple_rows: list[dict]) -> None:
        self.writes: list[dict] = []
        self._triple_rows = triple_rows

    def run(self, query: str, **params):
        self.writes.append(params)
        if "RETURN r.id AS id" in query:
            return self._triple_rows
        return []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Driver:
    def __init__(self, session: _Session) -> None:
        self._session = session

    def session(self) -> _Session:
        return self._session


def test_neo4j_writes_the_ordinal_and_load_user_reads_it_back() -> None:
    text = _long_text()
    session = _Session([])
    build_parsed_text(
        document_id="doc",
        user_id=USER,
        filename="inventory.txt",
        text=text,
        document_date=None,
        chat=ShuffledApiChat(),
        embedder=HashingEmbedder(),
        store=Neo4jGraphStore(_Driver(session)),
    )
    written = [params for params in session.writes if "predicate" in params]
    assert written and all(isinstance(params["chunk_ordinal"], int) for params in written)

    row = {
        "id": "t1",
        "source_id": "e1",
        "target_id": "e2",
        "predicate": "is stored in",
        "quote": "Item 3 is stored in bay 3.",
        "document_id": "doc",
        "embedding": [0.1],
        "valid_at": None,
    }
    old_edge = {**row, "id": "t0", "chunk_ordinal": None}  # built before chunks were stored
    new_edge = {**row, "chunk_ordinal": 4}
    loaded = Neo4jGraphStore(_Driver(_Session([old_edge, new_edge]))).load_user(USER)
    assert [triple.chunk_ordinal for triple in loaded.triples] == [None, 4]
