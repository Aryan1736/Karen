# Karen's Ear — REST & Real-Time API Contracts Specification

## 1. Document Identity
* **System:** Karen's Ear Emergency Intelligence System
* **Layer:** Layer 1 — Technical Architecture Specification (SOP)
* **Status:** PROPOSED & APPROVED FOR ARCHITECTURE
* **Authority:** Follows `gemini.md` (Project Constitution v1.1)

---

## 2. API Design Principles
1. **Canonical Envelope:** Every response uses the standardized envelope from `gemini.md` Section 6.6.
2. **ISO-8601 UTC:** All timestamps strictly use format `YYYY-MM-DDTHH:MM:SSZ`.
3. **Idempotency:** Report ingestion supports an optional `Idempotency-Key` or relies on `report_id` to prevent double-processing.
4. **Zero Silent Failures:** Error states always provide an explicit code, message, and `request_id`.
5. **No Hallucinated Types:** Enums and schemas strictly reflect the canonical contracts.

---

## 3. Standard Response & Error Envelopes

### 3.1 Standard Success Envelope
```json
{
  "success": true,
  "data": {},
  "error": null,
  "request_id": "req-18a7b93c",
  "timestamp": "2026-09-26T14:20:00Z"
}
```

### 3.2 Standard Error Envelope
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR | NOT_FOUND | ML_INFERENCE_TIMEOUT | INTERNAL_ERROR",
    "message": "Human-readable explanation of error",
    "details": []
  },
  "request_id": "req-18a7b93c",
  "timestamp": "2026-09-26T14:20:00Z"
}
```

---

## 4. REST Endpoint Specifications

### 4.1 Ingestion Endpoints

#### `POST /reports`
* **Purpose:** Ingest a single raw emergency dispatch (from operator, citizen, field radio, or simulator).
* **Request Headers:**
  * `Content-Type: application/json`
  * `Idempotency-Key: <optional-uuid>`
* **Request Body:**
  ```json
  {
    "report_id": "rep-4410",
    "text": "Flash flooding near Rasulgarh underpass. 4 people trapped in a white van with rising water.",
    "source": "manual",
    "is_synthetic": false,
    "reported_at": "2026-09-26T14:19:45Z",
    "location_hint": {
      "raw_text": "Rasulgarh underpass",
      "latitude": 20.2961,
      "longitude": 85.8245,
      "precision": "approximate"
    },
    "metadata": {
      "caller_phone": "+91-9876543210"
    }
  }
  ```
* **Response Status:** `201 Created`
* **Response Data:**
  ```json
  {
    "report_id": "rep-4410",
    "incident_id": "inc-9831a2",
    "is_new_incident": true,
    "relationship": "NEW",
    "processing_status": "SUCCESS"
  }
  ```
* **Error Codes:** `422 Unprocessable Entity` (schema invalid), `503 Service Unavailable` (DB offline).

#### `GET /reports/{id}`
* **Purpose:** Retrieve immutable record of an ingested report.
* **Response Status:** `200 OK`
* **Response Data:** Full raw report object.

---

### 4.2 Incident Management Endpoints

#### `GET /incidents`
* **Purpose:** Retrieve prioritized incidents for the Command Center queue and map.
* **Query Parameters:**
  * `status`: filter by state (e.g. `ACTIVE,NEEDS_REVIEW,VERIFIED`)
  * `level`: filter by priority tier (`CRITICAL,HIGH,MEDIUM,LOW`)
  * `limit`: pagination limit (default: 50, max: 200)
  * `offset`: pagination offset (default: 0)
* **Response Status:** `200 OK`
* **Response Data:**
  ```json
  {
    "incidents": [ /* array of Canonical Incident objects sorted by priority.score DESC */ ],
    "total_count": 14,
    "critical_count": 3
  }
  ```

#### `GET /incidents/{id}`
* **Purpose:** Retrieve full incident detail including all fused source reports, factor breakdowns, and audit history.
* **Response Status:** `200 OK`
* **Response Data:**
  ```json
  {
    "incident": { /* Canonical Incident Object */ },
    "source_reports": [ /* Array of Raw Report Objects */ ],
    "audit_trail": [ /* Array of Human Override Log Objects */ ]
  }
  ```

#### `POST /incidents/{id}/review`
* **Purpose:** Operator updates incident state (`VERIFIED`, `ESCALATED`, `RESOLVED`, `FALSE_REPORT`).
* **Request Body:**
  ```json
  {
    "operator_id": "dispatcher_aryan",
    "target_status": "VERIFIED",
    "notes": "Confirmed by NDRF field squad on site."
  }
  ```
* **Response Status:** `200 OK`
* **Response Data:** Updated canonical incident object.

#### `POST /incidents/{id}/override`
* **Purpose:** Operator overrides a specific attribute with mandatory audit attribution.
* **Request Body:**
  ```json
  {
    "operator_id": "dispatcher_aryan",
    "field": "urgency | people_at_risk | location | priority_score",
    "new_value": "CRITICAL",
    "reason": "Direct visual confirmation from traffic CCTV footage."
  }
  ```
* **Response Status:** `200 OK`
* **Response Data:** Updated incident object with `human_override` block active.

#### `GET /incidents/{id}/timeline`
* **Purpose:** Retrieve chronological timeline of all events tied to an incident (arrival of initial report, subsequent corroborations, AI priority updates, operator actions).
* **Response Status:** `200 OK`
* **Response Data:**
  ```json
  {
    "incident_id": "inc-9831a2",
    "events": [
      {
        "event_id": "ev-01",
        "type": "INITIAL_REPORT",
        "timestamp": "2026-09-26T14:19:45Z",
        "description": "Report rep-4410 ingested from manual dispatcher."
      },
      {
        "event_id": "ev-02",
        "type": "CORROBORATING_REPORT",
        "timestamp": "2026-09-26T14:21:10Z",
        "description": "Report rep-4412 added by distinct caller. Priority increased to 84.5."
      }
    ]
  }
  ```

---

### 4.3 Simulator & System Endpoints

#### `POST /simulation/start`
* **Purpose:** Trigger synthetic emergency stream playback for demonstrations or load testing.
* **Request Body:**
  ```json
  {
    "scenario_id": "flood_bhubaneswar_01",
    "rate_per_minute": 20,
    "total_reports": 50,
    "duplicate_probability": 0.40
  }
  ```
* **Response Status:** `200 OK`
* **Response Data:** `{"simulation_id": "sim-881", "status": "RUNNING"}`

#### `POST /simulation/stop`
* **Purpose:** Halt active simulation stream.
* **Response Status:** `200 OK`
* **Response Data:** `{"simulation_id": "sim-881", "status": "STOPPED"}`

#### `GET /health`
* **Purpose:** Liveness & readiness check for cloud hosting (Render).
* **Response Status:** `200 OK`
* **Response Data:**
  ```json
  {
    "status": "HEALTHY",
    "database": "CONNECTED",
    "ml_runtime": "READY",
    "version": "1.0.0"
  }
  ```
