"""The five visible progress steps from the problem statement.

Vocabulary only. Each LangGraph node emits start/done events for its step(s); the API
relays them to the frontend over Server-Sent Events (see docs/architecture.md section 4).
"""

from enum import StrEnum


class ProgressStep(StrEnum):
    PARSE_ORDERS = "Parse orders"
    INGEST_LABS = "Ingest labs"
    EVALUATE_RULE = "Evaluate the rule"
    INVALIDATE_DOSE = "Invalidate the dose"
    STATE_ACTIVE = "State what is still active"
