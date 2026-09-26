"""Node and edge kinds from the problem statement.

Only the vocabulary lives here at step 1. Pydantic models for nodes/edges (with
``valid_at`` / ``invalid_at`` on edges and ``collected_at`` on labs) come later;
see ``docs/architecture.md`` section 5.
"""

from enum import StrEnum


class NodeKind(StrEnum):
    PATIENT = "Patient"
    MEDICATION_ORDER = "MedicationOrder"
    LAB_OBSERVATION = "LabObservation"
    CLINICAL_PROTOCOL_RULE = "ClinicalProtocolRule"
    # Retrieval-support nodes (proposal, HippoRAG-2 style), not part of the clinical schema:
    EPISODE = "Episode"  # passage node: one per ingested source, holds raw text (provenance)
    ENTITY = "Entity"  # phrase node from LLM triple extraction


class EdgeKind(StrEnum):
    PRESCRIBED_DOSE = "PRESCRIBED_DOSE"
    HAS_BIOMARKER_VALUE = "HAS_BIOMARKER_VALUE"
    CONTRAINDICATES = "CONTRAINDICATES"
    TRIGGERS_SAFETY_HOLD = "TRIGGERS_SAFETY_HOLD"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"
    # Retrieval-support edges (proposal):
    MENTIONED_IN = "MENTIONED_IN"  # entity/node -> episode (provenance)
    RELATED_TO = "RELATED_TO"  # open (e1, r, e2) triple from extraction
