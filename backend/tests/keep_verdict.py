"""Test chats answer the attribution check by keeping every listed triple."""

import json

from jewel.llm.extract import VERIFICATION_REQUEST_PREFIX


def keep_all_verdict(user: str) -> str | None:
    """The keep-list for a verification request, or None when ``user`` is an extraction."""
    if not user.startswith(VERIFICATION_REQUEST_PREFIX):
        return None
    items = json.loads(user.removeprefix(VERIFICATION_REQUEST_PREFIX))
    return json.dumps({"keep": [item["n"] for item in items]})
