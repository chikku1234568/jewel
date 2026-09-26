"""Shared LangGraph state (stub). Proposed, for review.

Planned fields (see docs/architecture.md section 4.1):

* ``run_id``, ``patient_id``
* ``episode_ids``: episodes to process (already persisted as ``:Episode`` nodes)
* ``parsed``: per-episode parse output (text, detected kind: order / note / lab)
* ``now``: the run's reference time used for "valid now" queries
* ``order_refs`` / ``lab_refs``: ids written by the EHR Order / Laboratory Monitor agents
* ``rule_verdicts``: output of ``jewel.rules`` (deterministic)
* ``closed_edges``: PRESCRIBED_DOSE relationships whose ``invalid_at`` was set
* ``status_sentence``: LLM-written one-liner (not a decision)
* ``question`` / ``graph_answer`` / ``baseline_answer``: filled by the ``answer`` node
* ``progress``: list of (step, status, timestamp) events
* ``write_log``: every attempted graph write with (agent, op, kind, allowed)
"""
