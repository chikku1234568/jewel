"""Validity predicate used by retrieval (stub).

A relationship is valid at time ``t`` when it has started (or is undated) and has not
been closed::

    (r.valid_at IS NULL OR r.valid_at <= $t)
    AND (r.invalid_at IS NULL OR r.invalid_at > $t)

``valid_at`` is the document date when there is one, otherwise null (undated statements
stay valid). ``invalid_at`` is null unless the user deletes or a later write explicitly
closes the relationship. There is no rule engine that closes edges. ``t`` defaults to now.

TODO(later pass): expose the predicate once, as a Cypher fragment and a Python function.
"""
