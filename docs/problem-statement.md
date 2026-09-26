# Pharmacotherapy regimen lab alert

The problem is a signed medication order that stays active after a later lab makes that dose unsafe. Notes and documents land in a temporal knowledge graph. Agents may only write what their role allows. A question about administration is answered from edges that are still valid, not from a search over the original text.

## Problem

A clinical pharmacist must decide whether a patient's current high-dose anticoagulant order is still safe to give after a new lab result. The order, a later progress note, and a lab panel arrive as separate text and documents. The lab panel does not name the drug. The graph has to connect the lab to a frozen dosing rule and close the administration edge. A retriever that only finds the signed order will say the dose is still fine.

This is a showcase on a private URL. It is not a medical device and not clinical advice. The patient is synthetic.

## Flow

```text
text or document
  → parse
  → episode in a temporal KG
  → agents write only their own node and edge types
  → question answered from edges that are valid at "now"
```

Time is part of the graph. An order has `valid_at`. A lab has `collected_at`. A closed dose has `invalid_at` set to the specimen time. "Valid now" means the edge has started and has not been closed.

## Ingestion

In scope:

- Paste plain text.
- Upload a document (PDF or similar) and extract its text before it becomes an episode.
- Each source is one episode: who wrote it, when, and the raw text kept beside the graph so a hop can be checked.
- The demo corpus is three episodes. The exact notes are not locked yet. One is the order, one is a progress note, one is the lab. The lab text must not contain the drug name.

Out of scope for ingestion: live EHR, fax, images of handwriting, HL7, and any real patient record.

## Graph

| Kind | What it is |
|---|---|
| Patient | One synthetic patient |
| MedicationOrder | The signed order |
| LabObservation | A biomarker and its value |
| ClinicalProtocolRule | A frozen rule, not something the model invents |
| PRESCRIBED_DOSE | Dose, route, frequency. `valid_at`, `invalid_at` |
| HAS_BIOMARKER_VALUE | Lab result on the patient |
| CONTRAINDICATES | Rule fires on the active dose |
| TRIGGERS_SAFETY_HOLD | Hold written by the pharmacologist |
| REQUIRES_REVIEW | Optional pointer that a human must look. Not a new order |

The first rule, fixed in code or as a stored rule node: therapeutic enoxaparin twice daily is not valid for administration when creatinine clearance is below 30 mL/min. That closes the 100 mg twice-daily edge. It does not mean the drug is banned at every dose, and it does not write a replacement order.

## Agents

| Agent | May write | May not |
|---|---|---|
| EHR Order | Patient, MedicationOrder, the opening PRESCRIBED_DOSE | Read labs, apply rules, close a dose |
| Laboratory Monitor | LabObservation, biomarker values, clearance | Change any medication edge |
| Clinical Pharmacologist | CONTRAINDICATES, TRIGGERS_SAFETY_HOLD, `invalid_at` on a dose the frozen rule fails, REQUIRES_REVIEW | Prescribe, change the dose, invent a threshold |

The model writes the short status sentence. It does not decide the threshold.

## Task and question

Correlate active orders with labs, apply the frozen rule, and close the dose edge if the rule fails.

After the run the chat is asked: "Is the current order for enoxaparin 100 mg twice daily valid for immediate administration?"

The graph answer is no, as of the specimen time, because clearance is below 30. The progress steps are:

1. Parse orders
2. Ingest labs
3. Evaluate the rule
4. Invalidate the dose
5. State what is still active

The proof it is not retrieval: the same question over the raw notes returns the signed order, because the lab never says the drug name.

## Scope

In:

- Private showcase URL.
- Text paste and document upload into the graph.
- One patient, one order, one lab, one frozen rule.
- Three agents with the write limits above.
- A progress list of those five steps.
- The closed edge visible after the answer.
- A line on the page that this is not for clinical use.

Out:

- Choosing the demo sentences (later).
- A second drug, a second patient, or a task menu.
- The pharmacologist writing a new prescription.
- Accounts, billing, a public board, WhatsApp, or a live hospital feed.
- Treating this as a product a ward would run.

## Done

A private URL where a document and a paste become episodes, three agents run in order, the twice-daily edge shows an `invalid_at`, and the answer is no. A retrieval over the same text still says the order is fine.
