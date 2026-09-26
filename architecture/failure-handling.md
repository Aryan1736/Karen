# Karen's Ear — Failure Handling & Graceful Degradation Architecture

## 1. Document Identity
* **System:** Karen's Ear Emergency Intelligence System
* **Layer:** Layer 1 — Technical Architecture Specification (SOP)
* **Status:** PROPOSED & APPROVED FOR ARCHITECTURE
* **Authority:** Follows `gemini.md` (Project Constitution v1.1)

---

## 2. Fundamental Reliability Invariant
> **AI failure does NOT equal system failure. Never discard an emergency report because an ML or extraction component fails.**

In life-safety operations, losing a distress message because an NLP service timed out or crashed is completely unacceptable. The system must degrade gracefully through deterministic fallback pathways.

```text
[ Incoming Emergency Report ]
             │
             ▼
   [ Fast Ingestion & DB Persistence ] ──► (Guaranteed written to raw_reports)
             │
             ▼
   [ Attempt ML Analysis ]
             │
      ┌──────┴──────┐
      ▼             ▼
   SUCCESS       FAILURE / TIMEOUT / CRASH
      │             │
      │             ▼
      │    [ Fallback Pathway ]
      │    - Mark processing_status = "FAILED"
      │    - Create baseline Incident with status = "NEEDS_REVIEW"
      │    - Assign default triage priority (e.g. 50.0 MEDIUM)
      │    - Flag for immediate human inspection
      │             │
      └──────┬──────┘
             ▼
   [ Operator Command Center ]
   (Raw report text is ALWAYS readable and actionable)
```

---

## 3. Failure Modes & Deterministic Fallback Matrix

| Failure Mode | Root Cause | Immediate Fallback Action | Incident State | Data Integrity Impact |
| :--- | :--- | :--- | :--- | :--- |
| **1. ML Runtime Unavailable** | Torch/model process crash or OOM on Render. | Catch exception, bypass ML, create placeholder prediction record with `processing_status: "FAILED"`. | `NEEDS_REVIEW` | Raw report preserved. Operator manually triages. |
| **2. ML Inference Timeout** | CPU spiked by high concurrent report burst (> 2.0s). | Python `asyncio.wait_for` timeout triggers fallback, aborts hanging thread. | `NEEDS_REVIEW` | Report safe in DB; worker recycled. |
| **3. Malformed Model Output** | Unexpected JSON format or missing required keys. | Pydantic validation fails; log error diagnostic; populate defaults (`null`). | `NEEDS_REVIEW` | Warning appended to `ml_predictions.warnings`. |
| **4. Low-Confidence Prediction** | Noisy text, slang, or ambiguous phrasing ($Conf < 0.60$). | Process normal output; apply -10.0 priority penalty; set status. | `NEEDS_REVIEW` | Yellow warning badge rendered on UI card. |
| **5. Database Unavailable** | PostgreSQL network partition or connection limit. | Backend returns HTTP 503; in-memory buffer / retry loop up to 3 attempts with exponential backoff. | N/A | Return error envelope with request ID. |
| **6. Invalid Raw Report** | Empty string, oversized payload (> 10KB), or binary junk. | Reject at FastAPI validation with HTTP 422 Unprocessable Entity. | Rejected | Prevents DB bloat and worker disruption. |
| **7. Duplicate Processing** | Network retry sending identical report twice. | Idempotency check via report hash or `report_id` unique constraint. | Deduplicated | Returns existing incident link without reprocessing. |
| **8. Unknown Location** | Report says "near market" with no geocodable point. | **Strict No-Hallucination:** Store text `"near market"`, coordinates `null`, precision `"approximate"`. | `ACTIVE` | Displays in queue with text badge; excluded from map pin. |
| **9. Semantic Ambiguity** | Similarity score falls in grey zone ($0.75 - 0.84$). | Treat as `RELATED` rather than merging destructive facts; flag incident. | `NEEDS_REVIEW` | Both reports visible to operator to confirm or separate. |
| **10. Partial Extraction** | Extracted urgency and hazard, but failed entity count. | Emit extracted fields, set failed fields to `null`, status `"PARTIAL"`. | `ACTIVE` | Usable intelligence surfaced immediately. |
| **11. Real-Time Disconnect** | Operator's WebSocket connection drops. | Frontend automatically attempts reconnection every 3s; polls `/incidents` on resume. | Active | Queue synchronizes on reconnect; no data lost. |

---

## 4. Circuit Breakers & Resource Guards

1. **Memory Ceiling Guard (Render 512MB / Starter Limit):**
   * Pre-load model weights once during application startup lifespan (`@asynccontextmanager`).
   * Never re-load or instantiate new `SentenceTransformer` objects per request.
   * Restrict maximum input text length to 4,000 characters to prevent quadratic memory expansion.
2. **Deterministic Fallback Priority Generator:**
   * If priority engine cannot calculate a score due to missing ML output:
     $$\text{Fallback Score} = 50.0 \quad (\text{Level: MEDIUM})$$
     $$\text{Explanation} = \text{"Automated ML scoring unavailable; routed to operator for manual triage."}$$
3. **Audit Trail for Failures:**
   * All fallback transitions and failed ML attempts are logged in `ml_predictions.warnings` and backend console logs with unique `request_id`.
