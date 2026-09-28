# 0013. One LangGraph tool-using agent

- **Status:** Accepted (settled by `docs/problem-statement.md`, 2026-09-28)
- **Supersedes:** [0007](0007-langgraph-orchestration.md)

## Decision

- **One agent**, LangGraph as the runtime: a tool-using loop, not a fixed
  `retrieve -> answer` function and not a supervisor over specialists. Ingestion is a
  fixed pipeline, not agents.
- **Tools, only these:** `search_graph(query, optional time)` and
  `read_document(document_id, optional span)`. `read_document` refuses ids that search did
  not return and ids the user does not own.
- **Cap:** after at most 4 tool calls the agent must answer.
- **Isolation:** the agent receives no Neo4j session, no query-string parameter and no
  API key; the application binds user id and key outside the model.
- **Trace:** Server-Sent Events (`GET /ask/{run_id}/events`) stream tool name,
  arguments, short result summary, highlight ids after each `search_graph`, then the
  answer and citations. Citations must match tool results.
- No agent writes into the graph.

## Consequences

- LangGraph is added as a dependency in the pass that implements the agent.
- User isolation is enforced by `user_id` in queries, not by agent permission roles.
