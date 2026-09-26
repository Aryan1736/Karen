# Karen's Ear — Developer API Contract Specification

> **Target Audience:** Aryan (ML), Daksh (Backend), Pankaj (Evaluation/Simulator), Srinivash (Frontend)  
> **Authority:** Implementation-facing contract derived from `gemini.md` (v1.2) and `architecture/api-contracts.md`.  
> **Status:** FROZEN FOR SPRINT IMPLEMENTATION

---

## 1. Global Transport & Communication Standards

1. **Protocol:** HTTPS (REST) and WSS (WebSockets TLS 1.3).
2. **Character Encoding:** UTF-8.
3. **Timestamps:** ISO-8601 UTC format strictly: `YYYY-MM-DDTHH:MM:SSZ` (e.g., `2026-09-26T14:35:00Z`).
4. **Identifiers:** UUIDv4 strings or deterministic prefixed keys (e.g., `rep-uuid`, `inc-uuid`, `req-uuid`).
5. **Tracing Header:** Clients may send `X-Request-Id: <uuid>`. Backend will echo or generate `request_id` in every response envelope.
6. **Operator Header:** Frontend sends `X-Operator-Id: <string>` for review and override operations.

---

## 2. Canonical Response Envelopes

Every JSON response returned by the backend MUST use the canonical envelope defined in `gemini.md` Section 6.6.

### 2.1 Success Envelope
```json
{
  "success": true,
  "data": {},
  "error": null,
  "request_id": "req-9c81b2a4-f182-491a",
  "timestamp": "2026-09-26T14:35:00Z"
}
```

### 2.2 Error Envelope
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Field 'text' must be between 3 and 4000 characters.",
    "details": [
      {
        "field": "text",
        "issue": "String too short (received 1 char, min 3)"
      }
    ]
  },
  "request_id": "req-9c81b2a4-f182-491a",
  "timestamp": "2026-09-26T14:35:00Z"
}
```

### 2.3 Standard HTTP Status Codes
* `200 OK`: Request succeeded. Returned on successful GET, PUT, or mutation requests.
* `201 Created`: Ingestion or resource creation succeeded (e.g. `POST /reports`).
* `400 Bad Request`: Malformed JSON or syntax failure.
* `404 Not Found`: Target resource (`report_id` or `incident_id`) does not exist.
* `422 Unprocessable Entity`: Request payload failed Pydantic schema validation.
* `500 Internal Server Error`: Unhandled server exception (returns safe error envelope without secret leakage).
* `503 Service Unavailable`: PostgreSQL database or dependent runtime unreachable.

---

## 3. Simulator & Ingestion Interface

### `POST /reports`
Used by the Frontend (manual entry), Simulator (Pankaj), or external dispatch channels.

* **Request Body:**
```json
{
  "report_id": "rep-4410",
  "text": "Flash flooding near Rasulgarh underpass. 4 people trapped in a white van with rising water.",
  "source": "manual",
  "is_synthetic": false,
  "reported_at": "2026-09-26T14:35:00Z",
  "location_hint": {
    "raw_text": "Rasulgarh underpass",
    "latitude": 20.2961,
    "longitude": 85.8245,
    "precision": "approximate"
  },
  "metadata": {
    "caller_id": "+91-9876543210"
  }
}
```
*Field Specifications:*
* `report_id` (string, required): Client-generated or empty string (backend generates UUID if omitted).
* `text` (string, required): 3 to 4,000 characters.
* `source` (string, required): Enum: `"manual"` | `"simulator"` | `"dataset"` | `"other"`.
* `is_synthetic` (boolean, required): Must be `true` for simulator dispatches, `false` for manual dispatches.
* `reported_at` (string, required): ISO-8601 UTC timestamp.
* `location_hint` (object, optional, nullable):
  * `raw_text` (string | null)
  * `latitude` (number | null)
  * `longitude` (number | null)
  * `precision` (string): `"exact"` | `"approximate"` | `"unknown"`
* `metadata` (object, optional): Arbitrary key-value dictionary.

* **Response (`201 Created`):**
```json
{
  "success": true,
  "data": {
    "report_id": "rep-4410",
    "incident_id": "inc-9831a2",
    "is_new_incident": true,
    "relationship": "INITIAL",
    "processing_status": "SUCCESS"
  },
  "error": null,
  "request_id": "req-9c81b2a4-f182-491a",
  "timestamp": "2026-09-26T14:35:01Z"
}
```

---

## 4. Backend $\leftrightarrow$ ML Pipeline Internal Interface

Within Daksh's backend and Aryan's ML pipeline:

### 4.1 Backend $\to$ ML Request Contract
```python
from ml.pipeline import inference_engine

result = inference_engine.analyze(
    report=text,
    report_id=report_id,
    location_hint=location_hint,
)
"""
Invokes Aryan's ML/NLP pipeline via the sole canonical public entry point.
Must return a dictionary strictly adhering to ml/schemas/incident_output.json.
"""
```

### 4.2 ML $\to$ Backend Response Payload
Matches `ml/schemas/incident_output.json` exactly:
```json
{
  "report_id": "rep-4410",
  "model_version": "all-MiniLM-L6-v2+heuristic-v1",
  "incident_type": {
    "label": "FLOOD_FLASH_FLOOD",
    "confidence": 0.94
  },
  "urgency": {
    "label": "CRITICAL",
    "confidence": 0.88
  },
  "location": {
    "text": "Rasulgarh underpass",
    "latitude": 20.2961,
    "longitude": 85.8245,
    "precision": "approximate",
    "confidence": 0.82
  },
  "people_at_risk": {
    "count": 4,
    "confidence": 0.75
  },
  "required_response": [
    { "type": "SEARCH_AND_RESCUE", "confidence": 0.91 },
    { "type": "MEDICAL_EMS", "confidence": 0.85 }
  ],
  "entities": [
    { "text": "Rasulgarh underpass", "type": "LOCATION", "confidence": 0.88 },
    { "text": "white van", "type": "VEHICLE", "confidence": 0.92 }
  ],
  "embedding_reference": "emb-rep-4410",
  "processing_status": "SUCCESS",
  "warnings": []
}
```

*ML Payload Field Notes:*
* `embedding` (optional, non-nullable): When present, contains exactly 384 normalized numeric floats generated by `all-MiniLM-L6-v2`:
  ```text
  embedding = [f1, f2, ..., f384]  # where fi is a float and ||embedding||_2 == 1.0
  ```
  * Note: In production payloads, `embedding` contains raw numbers strictly matching `minItems: 384, maxItems: 384`. It is omitted from the JSON example above for brevity.
  * Used internally by Daksh's correlation engine for cosine similarity ($S_{\text{sem}} = v_1 \cdot v_2$).
  * If absent, the field is omitted rather than `null`, and backend falls back gracefully to non-vector triangulation dimensions.
  * `embedding` is internal ML $\to$ Backend data and is NOT exposed to frontend API payloads unless explicitly needed later.
* `embedding_reference` (string | null, optional): Key or identifier referencing external vector storage if used.

---

## 5. Frontend $\leftrightarrow$ Backend REST Endpoints

### 5.1 `GET /incidents`
* **Purpose:** Powers Srinivash's Command Center queue and map view.
* **Query Parameters:**
  * `status` (optional string): Comma-separated filter (e.g. `ACTIVE,NEEDS_REVIEW,VERIFIED`).
  * `level` (optional string): Comma-separated filter (e.g. `CRITICAL,HIGH`).
  * `limit` (optional integer): Default `50`, max `200`.
  * `offset` (optional integer): Default `0`.
* **Response (`200 OK`):**
```json
{
  "success": true,
  "data": {
    "incidents": [
      {
        "incident_id": "inc-9831a2",
        "status": "ACTIVE",
        "incident_type": "FLOOD_FLASH_FLOOD",
        "urgency": "CRITICAL",
        "location": {
          "text": "Rasulgarh underpass",
          "latitude": 20.2961,
          "longitude": 85.8245,
          "precision": "approximate"
        },
        "people_at_risk": {
          "count": 4
        },
        "required_response": ["SEARCH_AND_RESCUE", "MEDICAL_EMS"],
        "source_report_ids": ["rep-4410", "rep-4412"],
        "corroboration": {
          "report_count": 2,
          "independent_source_count": 2,
          "score": 0.59,
          "explanation": "Corroborated by 2 distinct field reports."
        },
        "ml_confidence": {
          "overall": 0.86,
          "components": {
            "incident_type": 0.94,
            "urgency": 0.88,
            "location": 0.82
          }
        },
        "priority": {
          "score": 84.5,
          "level": "CRITICAL",
          "explanation": "Elevated to CRITICAL priority due to confirmed trapped persons under flash flood conditions.",
          "factors": [
            { "factor": "Urgency", "value": "CRITICAL", "weight": 0.35, "contribution": 35.0 },
            { "factor": "People at Risk", "value": "4 trapped", "weight": 0.30, "contribution": 26.4 },
            { "factor": "Corroboration", "value": "2 sources", "weight": 0.20, "contribution": 11.8 },
            { "factor": "Hazard Severity", "value": "Flood", "weight": 0.15, "contribution": 12.75 }
          ]
        },
        "human_override": {
          "active": false,
          "updated_by": null,
          "updated_at": null,
          "reason": null
        },
        "is_synthetic": false,
        "created_at": "2026-09-26T14:35:00Z",
        "updated_at": "2026-09-26T14:36:10Z"
      }
    ],
    "total_count": 1,
    "critical_count": 1
  },
  "error": null,
  "request_id": "req-abc-123",
  "timestamp": "2026-09-26T14:36:15Z"
}
```

### 5.2 `GET /incidents/{id}`
* **Purpose:** Opens deep incident inspection drawer in UI.
* **Response (`200 OK`):** Returns `{ "incident": { ... }, "source_reports": [ { ... } ], "audit_trail": [ { ... } ] }`.

### 5.3 `POST /incidents/{id}/review`
* **Purpose:** Transitions incident status (`VERIFIED`, `ESCALATED`, `RESOLVED`, `FALSE_REPORT`).
* **Request Body:**
```json
{
  "operator_id": "srinivash_console",
  "target_status": "VERIFIED",
  "notes": "Verified by fire squad on site."
}
```

### 5.4 `POST /incidents/{id}/override`
* **Purpose:** Overrides specific fields with mandatory audit reason.
* **Request Body:**
```json
{
  "operator_id": "srinivash_console",
  "field": "urgency",
  "new_value": "CRITICAL",
  "reason": "Direct visual CCTV confirmation of trapped civilians."
}
```

### 5.5 `GET /incidents/{id}/timeline`
* **Purpose:** Chronological event audit trail for an incident.

### 5.6 `POST /simulation/start` & `POST /simulation/stop`
* **Purpose:** Simulator control panel for Pankaj and reviewers.
* **Start Request Body:**
```json
{
  "scenario_id": "sim_scenario_flood_01",
  "rate_per_minute": 15,
  "total_reports": 30,
  "duplicate_probability": 0.35
}
```

---

## 6. Real-Time WebSocket Interface (`/ws/events`)

Frontend connects to `wss://<backend-domain>/ws/events`.

### 6.1 Server $\to$ Client Event Envelope
```json
{
  "event": "INCIDENT_UPDATED",
  "payload": {},
  "timestamp": "2026-09-26T14:37:00Z"
}
```

### 6.2 Event Types
1. `INCIDENT_CREATED`: Payload is complete canonical `Incident` object.
2. `INCIDENT_UPDATED`: Payload contains updated `Incident` object or delta (`incident_id`, `new_priority_score`, `new_priority_level`, `corroboration`, `explanation`).
3. `INCIDENT_STATUS_CHANGED`: Payload contains `{ "incident_id": "...", "old_status": "...", "new_status": "..." }`.
4. `SIMULATION_PULSE`: Payload contains `{ "injected_count": 5, "total_simulated": 25, "scenario": "flood_01" }`.
5. `PING`: Server heartbeat every 30s. Client responds with `{ "type": "PONG" }`.
