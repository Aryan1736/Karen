# Karen's Ear — Layer 2 Navigation & Orchestration Architecture

## 1. Document Identity
* **System:** Karen's Ear Emergency Intelligence System
* **Layer:** Layer 2 — Navigation / Decision Orchestration Layer
* **Status:** PROPOSED & APPROVED FOR ARCHITECTURE
* **Authority:** Follows `gemini.md` (Project Constitution v1.1)

---

## 2. Role of the Navigation Layer

The **Navigation Layer** is the stateful orchestrator of Karen's Ear. It connects Layer 1 SOPs (architectural rules, formulas, and data contracts) with Layer 3 Tools (deterministic functions, ML inference modules, database transactions, and event broadcasters).

### Golden Rule of Navigation
> **Layer 2 does not invent business logic; it strictly executes the state machine transitions defined in Layer 1 SOPs.**

```text
                  Layer 1: Architecture SOPs
            (Formulas, Rules, Contracts, Fallbacks)
                              │
                              ▼
                 ┌─────────────────────────┐
                 │   LAYER 2: NAVIGATION   │
                 │   (Orchestration /      │
                 │    State Transitions)   │
                 └────────────┬────────────┘
                              │
                              ▼
                    Layer 3: Atomic Tools
            (ML Engine, DB Store, Scorer, Broadcaster)
```

---

## 3. End-to-End Orchestration State Machine

Every report follows an explicit, deterministic sequence of state transitions:

```text
[ S1: REPORT_RECEIVED ]
           │
           ▼
[ S2: VALIDATE_REPORT ] ──────────(Invalid)──────────► [ REJECT_422 ]
           │
        (Valid)
           ▼
[ S3: PERSIST_RAW_REPORT ] ───────(DB Down)──────────► [ RETRY_OR_503 ]
           │
        (Persisted)
           ▼
[ S4: RUN_ML_ANALYSIS ] ──────────(Timeout/OOM)──────► [ S4_FALLBACK: FAILED_ML ]
           │                                                    │
        (Success)                                               │
           ▼                                                    │
[ S5: VALIDATE_ML_OUTPUT ]                                      │
           │                                                    │
        (Validated)                                             │
           ▼                                                    ▼
[ S6: FIND_RELATED_INCIDENTS ] ◄────────────────────────────────┘
           │
     (Match Found?)
      ├── YES ──► [ S7A: FUSE_INTO_EXISTING_INCIDENT ]
      └── NO  ──► [ S7B: SPAWN_NEW_INCIDENT ]
           │
           ▼
[ S8: CALCULATE_CORROBORATION ]
           │
           ▼
[ S9: CALCULATE_PRIORITY ]
           │
           ▼
[ S10: PERSIST_INCIDENT_STATE ]
           │
           ▼
[ S11: EMIT_REALTIME_UPDATE ]
           │
           ▼
[ S12: COMPLETED ]
```

---

## 4. State Transition Table

| State ID & Name | Input | Output | Success Condition | Failure Condition | Next State |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **S1: REPORT_RECEIVED** | Raw HTTP JSON payload | Ingestion context with `request_id` | Payload has valid JSON structure | Malformed JSON syntax | `S2: VALIDATE_REPORT` (or 400 error) |
| **S2: VALIDATE_REPORT** | Raw dictionary | Typed `RawReport` Pydantic object | Text length $\in [3, 4000]$, valid source enum | Text too short/long, invalid enum | `S3: PERSIST_RAW_REPORT` (or 422 error) |
| **S3: PERSIST_RAW_REPORT** | `RawReport` | Database write confirmation | Inserted into `raw_reports` | DB connection failure | `S4: RUN_ML_ANALYSIS` (or retry/503) |
| **S4: RUN_ML_ANALYSIS** | Clean text string | Model raw predictions + 384d embedding | Model execution completes in $< 2.0\text{s}$ | Process crash, OOM, or timeout | `S5: VALIDATE_ML_OUTPUT` (or `S4_FALLBACK`) |
| **S4_FALLBACK** | Error details | Default fallback predictions (`processing_status: "FAILED"`) | Fallback record generated safely | Uncaught exception | `S6: FIND_RELATED_INCIDENTS` |
| **S5: VALIDATE_ML_OUTPUT** | Raw ML predictions | Typed `MLOutput` object | Required fields present, scores normalized | Malformed dictionary structure | `S6: FIND_RELATED_INCIDENTS` |
| **S6: FIND_RELATED_INCIDENTS** | Embedding + Location + Time | Candidate incidents with similarity scores | Active incidents retrieved from PostgreSQL | DB query timeout | `S7A` if $C_{\text{score}} \ge \tau_{\text{corrob}}$, else `S7B` |
| **S7A: FUSE_EXISTING** | Candidate incident + new report | Updated incident linkage record | Report linked with `DUPLICATE` or `CORROBORATING` | Foreign key conflict | `S8: CALCULATE_CORROBORATION` |
| **S7B: SPAWN_NEW** | New report + ML output | Newly initialized Incident record | Incident created with status `ACTIVE` / `NEEDS_REVIEW` | Insert failure | `S8: CALCULATE_CORROBORATION` |
| **S8: CALCULATE_CORROBORATION** | Incident report history | Updated `corroboration_score` | Count of distinct senders computed via formula | Corrupt linkage records | `S9: CALCULATE_PRIORITY` |
| **S9: CALCULATE_PRIORITY** | Incident features + corroboration | Canonical Priority payload with factor breakdown | Deterministic formula executes, score $\in [0, 100]$ | Missing required factors (fallback: 50.0) | `S10: PERSIST_INCIDENT_STATE` |
| **S10: PERSIST_INCIDENT_STATE** | Updated incident + priority log | Transaction commit confirmation | Atomic commit to `incidents` and `priority_calculations` | Serialization failure (retry once) | `S11: EMIT_REALTIME_UPDATE` |
| **S11: EMIT_REALTIME_UPDATE** | Event payload (`INCIDENT_UPDATED`) | WebSocket broadcast delivery | Sent to active WebSocket connections | WS buffer full (non-fatal, log warning) | `S12: COMPLETED` |
| **S12: COMPLETED** | Ingestion context | HTTP 201 Created response envelope | JSON response returned to caller with `request_id` | Network socket closed | End |

---

## 5. Human Review Navigation Flow

When an operator reviews or overrides an incident, a secondary navigation loop is triggered:

```text
[ OPERATOR_OVERRIDE_RECEIVED ]
             │
             ▼
[ VALIDATE_OVERRIDE ] (Ensure reason string >= 5 chars, field is overridable)
             │
             ▼
[ RECORD_AUDIT_LOG ] (Append-only write to audit_logs)
             │
             ▼
[ APPLY_INCIDENT_MUTATION ] (Update incidents table with human_override block)
             │
             ▼
[ RECALCULATE_PRIORITY ] (If priority-impacting field changed, update score)
             │
             ▼
[ BROADCAST_OVERRIDE_EVENT ] (Notify all connected dispatchers)
```
