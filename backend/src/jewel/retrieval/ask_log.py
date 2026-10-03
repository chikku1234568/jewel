"""One local file of Ask searches, with similarity hits separated from walk additions.

The Steps view shows every returned quote in one line and omits the query, so a later
look cannot tell a PageRank neighbor from a similarity hit. Set ``JEWEL_ASK_LOG`` to
``0`` to turn this off. A relative path is resolved from the repository root.
"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
_DEFAULT = _REPO / "data" / "ask-retrieval.log"


def _path() -> Path | None:
    raw = os.environ.get("JEWEL_ASK_LOG")
    if raw is None:
        return _DEFAULT
    raw = raw.strip()
    if raw in {"", "0", "off"}:
        return None
    path = Path(raw)
    return path if path.is_absolute() else _REPO / path


def log_event(event: dict, *, truncate: bool = False) -> None:
    """Append one JSON object. Failures here must not change the answer."""
    path = _path()
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({"ts": datetime.now(UTC).isoformat(), **event}, ensure_ascii=False)
        with path.open("w" if truncate else "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        return
