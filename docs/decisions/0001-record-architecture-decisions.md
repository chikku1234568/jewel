# 0001. Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-09-26

## Context

jewel is built step by step, pair-programming style. Choices (storage, cache, retrieval,
frontend, hosting) need to be reviewable and reversible, and the reasoning should survive
beyond chat history.

## Decision

Keep short ADRs in `docs/decisions/`, numbered sequentially, one decision per file, with
status *Proposed* until Srikar accepts it. Each Proposed ADR ends with *Open questions for
review*. Superseded ADRs are kept and linked, not deleted.

## Consequences

- Every non-trivial choice has a place to be challenged before code depends on it.
- Small overhead per decision; keep each ADR to about one page.
