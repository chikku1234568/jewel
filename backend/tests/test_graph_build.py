"""Incremental graph build and the retriever. No network and no database."""

import json
from datetime import datetime
from itertools import pairwise

import pytest

from jewel.agents.graph import MAX_TOOL_CALLS, run_agent
from jewel.agents.tools import ToolError, read_document
from jewel.ingestion.chunking import BUILD_CHUNK_SIZE, build_chunks, chunk_text
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
from tests.keep_verdict import keep_all_verdict

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
            verdict = keep_all_verdict(user)
            if verdict is not None:
                return verdict
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


def test_a_line_break_in_the_passage_is_kept_as_the_passages_own_span() -> None:
    source = "TENANT 1 : Mr. Alex Rivera, Aged 21 \nyears."
    payload = json.dumps(
        {
            "entities": [{"name": "Mr. Alex Rivera", "type": "person"}],
            "triples": [
                {
                    "subject": "Mr. Alex Rivera",
                    "predicate": "is aged",
                    "object": "21 years",
                    "quote": "TENANT 1 : Mr. Alex Rivera, Aged 21 years.",
                }
            ],
        }
    )
    parsed = parse_extraction(payload, source)
    assert len(parsed.triples) == 1
    assert parsed.triples[0].quote == source
    assert parsed.triples[0].quote in source


def test_a_quote_that_fits_two_spans_or_differs_in_case_is_dropped() -> None:
    wrapped = "The code is\n4412. The code is\n4412."
    twice = json.dumps(
        {
            "entities": [],
            "triples": [
                {
                    "subject": "code",
                    "predicate": "is",
                    "object": "4412",
                    "quote": "The code is 4412.",
                }
            ],
        }
    )
    assert parse_extraction(twice, wrapped).triples == []

    different_case = json.dumps(
        {
            "entities": [],
            "triples": [
                {
                    "subject": "alarm code",
                    "predicate": "is",
                    "object": "4412",
                    "quote": "the alarm code is 4412.",
                }
            ],
        }
    )
    assert parse_extraction(different_case, "The alarm code is 4412.").triples == []
    missing_comma = json.dumps(
        {
            "entities": [],
            "triples": [
                {
                    "subject": "alarm code",
                    "predicate": "is",
                    "object": "4412",
                    "quote": "The alarm code is 4412.",
                }
            ],
        }
    )
    assert parse_extraction(missing_comma, "The alarm code is, 4412.").triples == []


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


def test_the_walk_adds_a_fact_the_similarity_search_missed(monkeypatch, tmp_path) -> None:
    """A neighbor fact with no shared words still comes back, because it shares a name."""
    store = MemoryGraphStore()
    _build(store, USER, "lease", "Srikar lives in the flat.", None, _home())
    home, job, other = store.subgraph(USER).triples
    home.embedding = [1.0, 0.0]
    job.embedding = [0.0, 1.0]
    other.embedding = [0.0, 1.0]

    class TwoAxis:
        def embed(self, texts: list[str]) -> list[list[float]]:
            return [[1.0, 0.0] for _ in texts]

    log_path = tmp_path / "ask.log"
    monkeypatch.setenv("JEWEL_ASK_LOG", str(log_path))
    result = retrieve(store, TwoAxis(), USER, "where does he live", APRIL)
    predicates = [triple.predicate for triple in result.triples]
    assert predicates[0] == "lives in"
    assert "works as" in predicates
    assert "unrelated" not in predicates
    logged = log_path.read_text(encoding="utf-8")
    event = json.loads(logged.splitlines()[-1])
    facts = {fact["predicate"]: fact for fact in event["facts"]}
    assert event["query"] == "where does he live"
    assert facts["lives in"]["role"] == "seed"
    assert facts["works as"]["role"] == "extra"
    assert facts["works as"]["shares_seed_entity"] is True
    assert "unrelated" not in facts
    assert "Srikar lives" not in logged


def _home() -> Extraction:
    return Extraction(
        entities=[
            _entity("Srikar", EntityType.PERSON),
            _entity("the flat", EntityType.PLACE),
            _entity("engineer"),
            _entity("other"),
            _entity("thing"),
        ],
        triples=[
            ExtractedTriple(
                subject="Srikar",
                predicate="lives in",
                object="the flat",
                quote="Srikar lives in the flat.",
            ),
            ExtractedTriple(
                subject="Srikar",
                predicate="works as",
                object="engineer",
                quote="Srikar works as engineer.",
            ),
            ExtractedTriple(
                subject="other",
                predicate="unrelated",
                object="thing",
                quote="Something else.",
            ),
        ],
    )


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


def test_agent_stops_at_the_tool_cap_and_then_answers() -> None:
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
    assert result.tool_calls_used == MAX_TOOL_CALLS
    assert result.answer == "January still states 4412."
    # One turn with tools per call, then one with none, told to answer.
    assert [bool(turn.tools) for turn in model.turns] == [True] * MAX_TOOL_CALLS + [False]
    assert "Answer now" in str(model.turns[-1].messages[0].content)


def test_agent_runs_one_tool_per_turn_and_never_more_than_the_cap() -> None:
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
    assert result.tool_calls_used == MAX_TOOL_CALLS
    assert [entry.arguments for entry in result.tool_trace] == [{"query": "q0"}] * MAX_TOOL_CALLS
    assert result.answer == "answer"


def test_delete_user_detaches_only_that_users_nodes() -> None:
    class Session:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        def run(self, query: str, **params):
            self.calls.append((query, params))

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
    Neo4jGraphStore(driver).delete_user(USER)
    [(query, params)] = driver.session_obj.calls
    assert "DETACH DELETE" in query
    assert params == {"user_id": USER}
    assert USER not in query


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


def test_build_chunks_keep_paragraphs_whole_and_start_sentences_at_a_boundary() -> None:
    paragraph = "A" * 400
    text = "\n\n".join([paragraph] * 4)
    chunks = build_chunks(text)
    assert chunks[0].start == 0 and chunks[-1].end == len(text)
    assert all(len(chunk.text) <= BUILD_CHUNK_SIZE for chunk in chunks)
    pairs = list(pairwise(chunks))
    assert all(later.start > earlier.start for earlier, later in pairs)
    for earlier, later in pairs:
        assert earlier.start < later.start <= earlier.end
    for offset in range(0, len(text), 402):
        assert any(text[offset : offset + 400] in chunk.text for chunk in chunks)

    sentences = " ".join(f"Item {i} is stored in bay {i}." for i in range(80))
    pieces = build_chunks(sentences)
    assert len(pieces) > 1
    assert all(piece.text.startswith("Item ") for piece in pieces)
    assert all(piece.text.rstrip().endswith(".") for piece in pieces)
    assert all(len(piece.text) <= BUILD_CHUNK_SIZE for piece in pieces)


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
