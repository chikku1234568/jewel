"""Clinical Pharmacologist agent (stub).

May write: CONTRAINDICATES, TRIGGERS_SAFETY_HOLD, REQUIRES_REVIEW, and ``invalid_at``
on a PRESCRIBED_DOSE that a frozen rule fails (set to the specimen time).
May not: prescribe, change the dose, invent a threshold.
The rule verdict comes from ``jewel.rules`` (deterministic); the LLM only writes the
short status sentence.
Progress steps: 3. Evaluate the rule, 4. Invalidate the dose, 5. State what is still active.
"""
