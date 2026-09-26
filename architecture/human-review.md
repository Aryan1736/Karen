# Karen's Ear — Human Review & Override Architecture

## 1. Document Identity
* **System:** Karen's Ear Emergency Intelligence System
* **Layer:** Layer 1 — Technical Architecture Specification (SOP)
* **Status:** PROPOSED & APPROVED FOR ARCHITECTURE
* **Authority:** Follows `gemini.md` (Project Constitution v1.1)

---

## 2. Core Philosophy & Invariant
> **AI provides advisory predictions; the human operator exercises ultimate tactical authority. Every human modification is immutable, attributed, and auditable.**

In high-stakes emergency operations, automated models cannot replace human accountability. Karen's Ear enforces strict separation between:
1. **Raw Machine Prediction:** What the ML model inferred (preserved untouched for model evaluation, drift detection, and retrospective analysis).
2. **Current Operational State:** The live tactical reality as approved or modified by the human operator.
3. **Audit Trail:** An append-only ledger recording who modified what, when, and why.

---

## 3. Human Review Workflow

```text
Incoming Incident
       │
       ▼
[ Confidence Evaluation ]
       ├── If Confidence >= 0.60 & No Conflicts ──► Status: ACTIVE (Standard Queue)
       └── If Confidence < 0.60 OR Conflicts ────► Status: NEEDS_REVIEW (Yellow Attention Flag)
       │
       ▼
[ Operator Inspection in Command Center ]
       ├── Inspects raw source reports & timestamps
       ├── Evaluates extracted location and map pin
       ├── Reviews factor contributions & AI explanation
       │
       ▼
[ Operator Actions ]
  ┌─────────────────┬──────────────────┬─────────────────┬─────────────────┐
  ▼                 ▼                  ▼                 ▼                 ▼
[ Verify & Accept ] [ Field Override ] [ Change Priority] [ Split / Unfuse ] [ Resolve / False ]
  - Marks incident    - Corrects text    - Manual override  - Decouples       - Closes incident
    VERIFIED            or coordinates     to CRITICAL etc    unrelated report  - Preserves audit
  │                 │                  │                 │                 │
  └─────────────────┴──────────────────┴─────────────────┴─────────────────┘
                                       │
                                       ▼
                       [ Record Audit Log Transaction ]
                                       │
                                       ▼
                       [ Broadcast State Update (WS/SSE) ]
```

---

## 4. Operator Override Capabilities

Operators have full authority to override the following fields through the UI drawer:

1. **Urgency Tier:** Override AI-predicted urgency (`LOW` $\to$ `CRITICAL`).
2. **People at Risk Count:** Increase or decrease casualty/victim count based on direct radio dispatches.
3. **Location & Coordinates:** Correct misspelled addresses or manually drag map pin to true GPS coordinates.
4. **Incident Type:** Reclassify hazard (e.g. from `FLOOD` to `STRUCTURAL_COLLAPSE` after wall failure).
5. **Priority Score & Level:** Force priority level or score based on command directives.
6. **Incident State:** Transition to `VERIFIED`, `ESCALATED`, `RESOLVED`, or `FALSE_REPORT`.

---

## 5. Audit Logging Specification

Every operator modification executes a database transaction that writes to `audit_logs` before mutating the `incidents` table.

### 5.1 Audit Schema Contract
```json
{
  "override_id": "ovr-781b-9021",
  "incident_id": "inc-9831a2",
  "operator_id": "dispatcher_aryan_01",
  "field": "urgency",
  "previous_value": "MEDIUM",
  "new_value": "CRITICAL",
  "reason": "Fire department radio confirms 2 people trapped under rising waters in basement",
  "created_at": "2026-09-26T14:15:00Z"
}
```

### 5.2 Mandatory Audit Fields
* **`operator_id`:** Non-empty string identifying the logged-in dispatcher or console operator.
* **`reason`:** Mandatory explanation string (minimum 5 characters) explaining *why* the AI was overridden. Submitting an empty reason is rejected by backend validation.
* **`created_at`:** ISO-8601 UTC timestamp generated server-side.

---

## 6. Separation of Concerns in Database Storage

The `incidents` table maintains an active override status without wiping the underlying ML prediction:

```json
{
  "incident_id": "inc-9831a2",
  "urgency": "CRITICAL",
  "human_override": {
    "active": true,
    "updated_by": "dispatcher_aryan_01",
    "updated_at": "2026-09-26T14:15:00Z",
    "reason": "Radio confirms 2 people trapped under rising waters in basement"
  }
}
```

Meanwhile, the original record in `ml_predictions` remains:
```json
{
  "report_id": "rep-4410",
  "urgency": {
    "label": "MEDIUM",
    "confidence": 0.58
  }
}
```

This separation allows evaluation scripts (`tools/evaluate_model.py`) to measure model accuracy against human ground truth without corrupting active incident state.
