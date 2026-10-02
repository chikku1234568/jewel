"""Incremental graph build and the retriever. No network and no database."""

from datetime import datetime

import pytest

from jewel.agents.graph import run_agent
from jewel.agents.tools import ToolError, read_document
from jewel.ingestion.chunking import chunk_text
from jewel.ingestion.live import build_parsed_text
from jewel.ingestion.pipeline import ParsedDocument, build_document
from jewel.kg.extraction import ExtractedEntity, ExtractedTriple, Extraction, parse_extraction
from jewel.kg.memory_store import MemoryGraphStore
from jewel.kg.neo4j_store import Neo4jGraphStore
from jewel.kg.schema import EntityType
from jewel.llm.hashing import HashingEmbedder
from jewel.llm.kimi import kimi_is_configured
from jewel.retrieval.baseline_rag import rank_chunks
from jewel.retrieval.hippo.pipeline import retrieve
from jewel.retrieval.hippo.recognition import filter_triples
from tests.fake_chat import AIMessage, ScriptedChat, Turn, call, calls

JANUARY = datetime(2026, 1, 15)
FEBRUARY = datetime(2026, 2, 1)
MARCH = datetime(2026, 3, 2)
APRIL = datetime(2026, 4, 1)
JAN_TEXT = "The warehouse key is held by Sam. The alarm code is 4412."
MAR_TEXT = "The alarm code was rotated after the break-in."
USER = "user-a"
OTHER = "user-b"


def _entity(name: str, kind: EntityType = EntityType.CONCEPT) -> ExtractedEntity:
    return ExtractedEntity(name=name, type=kind)


def _january() -> Extraction:
    return Extraction(
        entities=[
            _entity("Sam", EntityType.PERSON),
            _entity("warehouse key"),
            _entity("alarm code"),
            _entity("4412"),
        ],
        triples=[
            ExtractedTriple(
                subject="warehouse key",
                predicate="held by",
                object="Sam",
                quote="The warehouse key is held by Sam.",
            ),
            ExtractedTriple(
                subject="alarm code",
                predicate="is",
                object="4412",
                quote="The alarm code is 4412.",
            ),
        ],
    )


def _march() -> Extraction:
    return Extraction(
        entities=[_entity("alarm code"), _entity("the break-in")],
        triples=[
            ExtractedTriple(
                subject="alarm code",
                predicate="was rotated after",
                object="the break-in",
                quote=MAR_TEXT,
            )
        ],
    )


def _build(
    store: MemoryGraphStore, user: str, document_id: str, text: str, when, extraction
) -> None:
    build_document(
        ParsedDocument(document_id, user, f"{document_id}.txt", text, when),
        extraction,
        store,
        HashingEmbedder(),
    )


def test_messy_model_json_keeps_the_usable_triple() -> None:
    payload = """
    Here is the graph:
    {"entities": ["alarm code", {"name": "Sam", "type": "event"}],
     "relationships": [
        {"head": "alarm code", "relation": "is", "tail": "4412", "quote": ""},
        {"subject": "nope"}
     ]}
    """
    parsed = parse_extraction(payload, JAN_TEXT)
    pairs = [(triple.subject, triple.object) for triple in parsed.triples]
    assert pairs == [("alarm code", "4412")]
    sam = next(entity for entity in parsed.entities if entity.name == "Sam")
    assert sam.type.value == "other"


def test_a_long_document_is_extracted_in_pieces() -> None:
    seen: list[int] = []

    class Chat:
        def complete(self, system: str, user: str) -> str:
            seen.append(len(user))
            return (
                '{"entities":[{"name":"alarm code","type":"concept"}],'
                '"triples":[{"subject":"alarm code","predicate":"is","object":"4412",'
                '"quote":"The alarm code is 4412."}]}'
            )

    text = (JAN_TEXT + " ") * 80
    store = MemoryGraphStore()
    build_parsed_text(
        document_id="paper",
        user_id=USER,
        filename="paper.txt",
        text=text,
        document_date=None,
        chat=Chat(),
        embedder=HashingEmbedder(),
        store=store,
    )
    assert len(seen) > 1
    assert max(seen) < len(text)
    assert store.subgraph(USER).triples


def test_quote_must_be_copied_from_the_document() -> None:
    payload = """
    {"entities": [{"name": "alarm code", "type": "concept"}],
     "triples": [
        {"subject": "alarm code", "predicate": "is", "object": "4412",
         "quote": "The alarm code is 4412."},
        {"subject": "alarm code", "predicate": "is", "object": "9999",
         "quote": "The alarm code is 9999."}
     ]}
    """
    parsed = parse_extraction(payload, JAN_TEXT)
    assert [triple.object for triple in parsed.triples] == ["4412"]


def test_second_upload_reuses_entities_and_keeps_the_first_document() -> None:
    store = MemoryGraphStore()
    seen: list[str] = []

    def extract(text: str) -> Extraction:
        seen.append(text)
        return _january() if "4412" in text else _march()

    for document_id, text, when in (("jan", JAN_TEXT, JANUARY), ("mar", MAR_TEXT, MARCH)):
        build_document(
            ParsedDocument(document_id, USER, f"{document_id}.txt", text, when),
            extract(text),
            store,
            HashingEmbedder(),
        )
    assert seen == [JAN_TEXT, MAR_TEXT]
    subgraph = store.subgraph(USER)
    alarm = [entity for entity in subgraph.entities if entity.name_key == "alarm code"]
    assert len(alarm) == 1
    assert {triple.document_id for triple in subgraph.triples} == {"jan", "mar"}
    assert {
        mention.document_id for mention in subgraph.mentions if mention.entity_id == alarm[0].id
    } == {
        "jan",
        "mar",
    }


def test_users_do_not_share_entities() -> None:
    store = MemoryGraphStore()
    _build(store, USER, "jan", JAN_TEXT, JANUARY, _january())
    _build(store, OTHER, "jan", JAN_TEXT, JANUARY, _january())
    own = {entity.id for entity in store.subgraph(USER).entities}
    other = {entity.id for entity in store.subgraph(OTHER).entities}
    assert own.isdisjoint(other)


def test_question_reaches_the_later_document_that_does_not_say_4412() -> None:
    store = MemoryGraphStore()
    _build(store, USER, "jan", JAN_TEXT, JANUARY, _january())
    _build(store, USER, "mar", MAR_TEXT, MARCH, _march())
    result = retrieve(store, HashingEmbedder(), USER, "Is the alarm code still 4412?", APRIL)
    found = {hit.document_id for hit in result.documents}
    assert "mar" in found
    assert "jan" in found


def test_edges_from_the_future_are_not_walked() -> None:
    store = MemoryGraphStore()
    _build(store, USER, "jan", JAN_TEXT, JANUARY, _january())
    _build(store, USER, "mar", MAR_TEXT, MARCH, _march())
    result = retrieve(store, HashingEmbedder(), USER, "4412", FEBRUARY)
    assert "mar" not in {hit.document_id for hit in result.documents}
    assert "jan" in {hit.document_id for hit in result.documents}


def test_text_search_for_the_code_misses_the_later_note() -> None:
    embedder = HashingEmbedder()
    query = embedder.embed(["4412"])[0]
    chunks = [
        ("jan", JAN_TEXT, embedder.embed([JAN_TEXT])[0]),
        ("mar", MAR_TEXT, embedder.embed([MAR_TEXT])[0]),
    ]
    ranked = rank_chunks(query, chunks)
    assert [item[0] for item in ranked] == ["jan"]


def test_recognition_can_drop_a_triple_without_answering() -> None:
    store = MemoryGraphStore()
    _build(store, USER, "jan", JAN_TEXT, JANUARY, _january())
    triples = store.subgraph(USER).triples

    class KeepFirst:
        def complete(self, system: str, user: str) -> str:
            assert "Do not answer" in system
            return '{"keep": [0]}'

    kept = filter_triples("4412", triples, KeepFirst())
    assert len(kept) == 1


def test_agent_searches_then_reads_only_a_returned_document() -> None:
    store = MemoryGraphStore()
    _build(store, USER, "jan", JAN_TEXT, JANUARY, _january())
    _build(store, USER, "mar", MAR_TEXT, MARCH, _march())

    def script(turn: Turn) -> AIMessage:
        if turn.tool_results == 0:
            return call("search_graph", query="4412")
        if turn.tool_results == 1:
            return call("read_document", document_id="mar")
        return AIMessage("The March note says the code was rotated.")

    model = ScriptedChat(script=script)
    result = run_agent(
        question="Is the alarm code still 4412?",
        user_id=USER,
        store=store,
        embedder=HashingEmbedder(),
        model=model,
        as_of=APRIL,
    )
    assert result.tool_calls_used == 2
    assert [entry.name for entry in result.tool_trace] == ["search_graph", "read_document"]
    assert "mar" in result.returned_document_ids
    assert result.highlight_entity_ids
    assert result.answer == "The March note says the code was rotated."
    # The model is offered exactly the two tools, and never sees the user id.
    assert model.turns[0].tool_names == ["search_graph", "read_document"]
    assert all(USER not in turn.text for turn in model.turns)
    with pytest.raises(ToolError):
        read_document(store, USER, "missing", set())


def test_agent_stops_at_four_tool_calls_and_then_answers() -> None:
    store = MemoryGraphStore()
    _build(store, USER, "jan", JAN_TEXT, JANUARY, _january())

    def script(turn: Turn) -> AIMessage:
        if not turn.tools:
            return AIMessage("January still states 4412.")
        return call("search_graph", query="4412")

    model = ScriptedChat(script=script)
    result = run_agent(
        question="4412",
        user_id=USER,
        store=store,
        embedder=HashingEmbedder(),
        model=model,
        as_of=APRIL,
    )
    assert result.tool_calls_used == 4
    assert result.answer == "January still states 4412."
    # Four turns with tools, then one with none, told to answer.
    assert [bool(turn.tools) for turn in model.turns] == [True] * 4 + [False]
    assert "Answer now" in str(model.turns[-1].messages[0].content)


def test_agent_runs_one_tool_per_turn_and_never_more_than_four() -> None:
    store = MemoryGraphStore()
    _build(store, USER, "jan", JAN_TEXT, JANUARY, _january())

    def script(turn: Turn) -> AIMessage:
        # A greedy model: three searches per turn, and a tool call even when told to answer.
        greedy = calls(*[("search_graph", {"query": f"q{n}"}) for n in range(3)])
        if not turn.tools:
            return AIMessage("answer", tool_calls=greedy.tool_calls)
        return greedy

    result = run_agent(
        question="4412",
        user_id=USER,
        store=store,
        embedder=HashingEmbedder(),
        model=ScriptedChat(script=script),
        as_of=APRIL,
    )
    assert result.tool_calls_used == 4
    assert [entry.arguments for entry in result.tool_trace] == [{"query": "q0"}] * 4
    assert result.answer == "answer"


def test_neo4j_writes_bind_the_user_id() -> None:
    class Session:
        def __init__(self) -> None:
            self.params: list[dict] = []

        def run(self, query: str, **params):
            assert "user-a" not in query
            assert params["user_id"] == USER
            self.params.append(params)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    class Driver:
        def __init__(self) -> None:
            self.session_obj = Session()

        def session(self):
            return self.session_obj

    driver = Driver()
    Neo4jGraphStore(driver).write_document(
        user_id=USER,
        document_id="jan",
        filename="jan.txt",
        text=JAN_TEXT,
        embedding=[0.1],
        extraction=_january(),
        entity_embeddings={entity.name: [0.1] for entity in _january().entities},
        triple_embeddings=[[0.2], [0.3]],
        document_date=JANUARY,
    )
    assert driver.session_obj.params


def test_chunk_offsets_cover_the_text() -> None:
    chunks = chunk_text("abcdefghij", size=4, overlap=1)
    assert chunks[0].text == "abcd"
    assert chunks[1].start == 3
    assert "".join(chunk.text[-1] for chunk in chunks)


def test_kimi_config_reads_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    assert kimi_is_configured() is False
    monkeypatch.setenv("KIMI_API_KEY", "present")
    assert kimi_is_configured() is True
