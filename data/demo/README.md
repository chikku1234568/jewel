# Demo corpus (not locked yet)

The showcase uses exactly **three synthetic episodes** for **one synthetic patient**:

| # | Episode | Source kind | Constraint |
|---|---|---|---|
| 1 | Signed medication order (enoxaparin 100 mg twice daily) | paste or document | Opens the `PRESCRIBED_DOSE` edge (`valid_at`) |
| 2 | Later progress note | paste or document | Context only |
| 3 | Lab panel with creatinine clearance < 30 mL/min | document (PDF) or paste | **Must not contain the drug name** (this is what defeats naive RAG) |

The exact sentences are intentionally **out of scope for step 1** ("Choosing the demo
sentences (later)" in [`docs/problem-statement.md`](../../docs/problem-statement.md)).
When they are written they will live here as `01-order.*`, `02-progress-note.*`,
`03-lab-panel.*` with author and authored-at metadata.

No real patient data may ever be added to this repository.
