"""Agent state (stub).

Planned fields: ``question``, ``user_id`` (bound by the application, not visible to the
model as a parameter), ``as_of`` (optional question time, default now), ``tool_trace``
(ordered tool calls with arguments and result summaries), ``tool_calls_used`` (cap 4),
``returned_document_ids`` (what ``read_document`` may open), ``citations`` (document id and
quote pairs from tool results), and ``answer``.
"""
