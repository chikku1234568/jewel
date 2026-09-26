"""Rule R1 (stub): therapeutic enoxaparin twice daily vs. creatinine clearance.

From the problem statement: "therapeutic enoxaparin twice daily is not valid for
administration when creatinine clearance is below 30 mL/min. That closes the 100 mg
twice-daily edge. It does not mean the drug is banned at every dose, and it does not
write a replacement order."

TODO(step-N): implement as a pure function over (active PRESCRIBED_DOSE, latest
creatinine clearance) returning a verdict with the specimen time. The threshold
(30 mL/min) is a frozen constant, also stored as a ClinicalProtocolRule node.
"""
