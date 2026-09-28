# 0007. LangGraph orchestration and graph-writer permission layer

> **Superseded (2026-09-28)** by [0013](0013-single-langgraph-agent.md). The multi-agent design and its write-permission layer were removed. Kept for history only; not part of the active decision set.

- **Status:** Superseded by [0013](0013-single-langgraph-agent.md) on 2026-09-28 (previously: Proposed, for review)

## Context

Three role-restricted agents must run in order; five progress steps must be visible; agents
may only write their own node/relationship kinds; the model writes the status sentence but
never decides the threshold.

## Proposed decision

- **LangGraph `StateGraph`, fixed sequence:**
  `START -> parse -> ehr_order_agent -> lab_monitor_agent -> pharmacologist_agent -> answer -> END`.
  The only branch (rule passes / fails) is deterministic Python inside
  `pharmacologist_agent`.
- **State:** typed object with run id, `now`, episode ids, parse output, written refs, rule
  verdicts, closed edges, status sentence, answers, progress events, write log
  (full table in `docs/architecture.md` section 4.1).
- **Progress:** nodes emit custom stream events; FastAPI relays them to the browser via
  Server-Sent Events (`GET /runs/{id}/events`).
- **Permissions:** each agent receives a `GraphWriter` scoped to its role. It checks
  `(agent, operation, kind)` against the matrix before issuing parameterised Cypher, logs
  every attempt, and raises on violation. Closing a `PRESCRIBED_DOSE` additionally requires
  a failing verdict from the frozen rule, with `invalid_at` = specimen time.

## Alternatives

- **Supervisor pattern** (LLM routes to agents): more "agentic" but non-deterministic order,
  could skip/repeat agents, harder to guarantee five steps.
- **Plain Python pipeline:** simplest, but loses LangGraph streaming/checkpointing and the
  requested stack.

## Consequences

- Deterministic, testable demo; progress steps map directly onto nodes.
- Permission guarantees do not depend on prompt compliance.

## Open questions for review

1. Fixed sequence OK, or does Srikar want a supervisor for showcase value?
2. Should `parse` be a LangGraph node (as proposed) or happen at upload time in the API?
3. Use LangGraph checkpointing (resume a run) or keep runs stateless?
4. SSE acceptable for progress, or WebSockets?
