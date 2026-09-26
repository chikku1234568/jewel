"""LangGraph wiring (stub). Proposed, for review.

Recommended: a fixed sequential graph (not a free-form supervisor), because the spec
requires the agents to run in order and the five progress steps to be deterministic:

    START -> parse -> ehr_order_agent -> lab_monitor_agent -> pharmacologist_agent -> answer -> END

Each agent node receives a ``GraphWriter`` scoped to its role (``jewel.kg.permissions``),
never a raw Neo4j session. Node start/finish events are streamed (LangGraph streaming)
and relayed to the frontend as SSE progress events (``jewel.agents.progress``).

TODO(step-N): build the ``StateGraph`` over ``jewel.agents.state``.
"""
