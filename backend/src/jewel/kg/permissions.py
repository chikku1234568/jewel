"""Per-agent write permissions, enforced in code, never trusted to the LLM (stub).

Matrix (from the problem statement; see docs/architecture.md section 6):

* EHR Order: Patient, MedicationOrder, opening PRESCRIBED_DOSE
* Laboratory Monitor: LabObservation, HAS_BIOMARKER_VALUE (incl. clearance)
* Clinical Pharmacologist: CONTRAINDICATES, TRIGGERS_SAFETY_HOLD, REQUIRES_REVIEW,
  and ``invalid_at`` on a PRESCRIBED_DOSE only when a frozen rule fails

TODO(step-N): a ``GraphWriter`` wrapper that checks (agent, operation, kind) against
the matrix and raises ``PermissionError`` on violation; log every attempt.
"""
