"""Turns Kimi chat completions into the agent's tool-or-answer decisions."""

import json
import re

from jewel.agents.graph import Decision, ToolRequest

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_SYSTEM = (
    "You answer questions about a user's documents by searching their knowledge graph. "
    "Return JSON only. To search, return "
    '{"tool":{"name":"search_graph","arguments":{"query":"..."}}}. '
    'To read a document id that a search returned, return {"tool":{"name":"read_document",'
    '"arguments":{"document_id":"..."}}}. '
    'When you can answer, return {"answer":"..."}. Quote the documents. Do not invent facts.'
)


class KimiDecider:
    """One chat call per turn. The user id is never sent."""

    def __init__(self, chat) -> None:
        self._chat = chat

    def __call__(self, question: str, observations: list[str], force_answer: bool) -> Decision:
        system = _SYSTEM
        if force_answer:
            system += " You must answer now. Do not call a tool."
        user = json.dumps({"question": question, "observations": observations})
        raw = self._chat.complete(system, user)
        return _parse(raw, force_answer)


def _parse(payload: str, force_answer: bool) -> Decision:
    text = payload.strip()
    if text.startswith("```"):
        text = _FENCE.sub("", text).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return Decision(answer=payload.strip())
    if force_answer or data.get("answer"):
        return Decision(answer=str(data.get("answer") or payload.strip()))
    tool = data.get("tool") or {}
    name = tool.get("name")
    if name in {"search_graph", "read_document"}:
        arguments = tool.get("arguments") if isinstance(tool.get("arguments"), dict) else {}
        return Decision(tool=ToolRequest(name=name, arguments=arguments))
    return Decision(answer=str(data))
