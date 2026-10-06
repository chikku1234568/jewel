"""Per-account limits for upload, build, and Ask.

One process keeps the counts in memory. A restart clears them. The window is one hour.
These stop a script from filling the request threads. They are not a bill.
"""

import threading
import time

from fastapi import HTTPException, Request

UPLOAD = "upload"
BUILD = "build"
ASK = "ask"

# (how many, window seconds)
DEFAULT_LIMITS: dict[str, tuple[int, int]] = {
    UPLOAD: (30, 3600),
    BUILD: (20, 3600),
    ASK: (60, 3600),
}

_LABELS = {
    UPLOAD: "uploads",
    BUILD: "builds",
    ASK: "questions",
}


class RateLimiter:
    """A sliding window per account and action."""

    def __init__(self, limits: dict[str, tuple[int, int]] | None = None) -> None:
        self._limits = dict(DEFAULT_LIMITS if limits is None else {**DEFAULT_LIMITS, **limits})
        self._hits: dict[tuple[str, str], list[float]] = {}
        self._lock = threading.Lock()

    def check(self, user_id: str, action: str) -> None:
        limit, window = self._limits[action]
        now = time.monotonic()
        with self._lock:
            key = (user_id, action)
            recent = [stamp for stamp in self._hits.get(key, []) if now - stamp < window]
            if len(recent) >= limit:
                label = _LABELS.get(action, action)
                hours = window / 3600
                span = "this hour" if hours == 1 else f"{hours:g} hours"
                raise HTTPException(
                    status_code=429,
                    detail=f"Limit reached: {limit} {label} {span}. Try again later.",
                )
            recent.append(now)
            self._hits[key] = recent


def enforce(request: Request, user_id: object, action: str) -> None:
    """Count this call. Raise 429 when the account is over its limit."""
    limiter: RateLimiter | None = getattr(request.app.state, "limits", None)
    if limiter is not None:
        limiter.check(str(user_id), action)
