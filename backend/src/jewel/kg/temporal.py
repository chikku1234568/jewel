"""Validity predicate used by retrieval.

A relationship is valid at ``t`` when it has started (or is undated) and has not been
closed. ``AND`` binds tighter than ``OR``, so the groups are parenthesised:

    (valid_at is None or valid_at <= t) and (invalid_at is None or invalid_at > t)

Undated relationships stay valid. Nothing here closes an edge on its own.
"""

from datetime import datetime


def is_valid_at(
    valid_at: datetime | None,
    invalid_at: datetime | None,
    at: datetime,
) -> bool:
    """Return whether a relationship is still valid at ``at``."""
    started = valid_at is None or valid_at <= at
    open_ended = invalid_at is None or invalid_at > at
    return started and open_ended
