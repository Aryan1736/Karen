# Karen's Ear — Real-Time Streaming & Event Architecture

## 1. Document Identity
* **System:** Karen's Ear Emergency Intelligence System
* **Layer:** Layer 1 — Technical Architecture Specification (SOP)
* **Status:** PROPOSED & APPROVED FOR ARCHITECTURE
* **Authority:** Follows `gemini.md` (Project Constitution v1.1)

---

## 2. Real-Time Operational Objectives

In an emergency command center, static dashboards that require manual browser refreshing are hazardous. As floodwaters rise or building collapses occur, incident priority rankings must re-order dynamically on screen in sub-second latency.

```text
[ Report Ingested ] ──► [ NLP Inferred ] ──► [ Priority Updated ]
                                                     │
                                                     ▼
                                        [ Backend Event Broadcaster ]
                                                     │
                             ┌───────────────────────┴───────────────────────┐
                             ▼                                               ▼
                 [ Primary Transport: WebSockets ]              [ Fallback: Polling Loop ]
                             │                                               │
                             └───────────────────────┬───────────────────────┘
                                                     │
                                                     ▼
                                     [ React Command Center UI ]
                                       - Re-sorts priority queue
                                       - Animates updated incident card
                                       - Updates tactical map pin
```

---

## 3. Technology Evaluation for 24-Hour Hackathon

We evaluated three real-time paradigms:

| Mechanism | Pros | Cons | Verdict for Hackathon |
| :--- | :--- | :--- | :--- |
| **A. Native WebSockets (`/ws`)** | Full bi-directional, native FastAPI support (`WebSocket`), sub-50ms latency, zero polling overhead. | Requires connection management & heartbeat handling. | **PRIMARY SELECTION:** Standard in disaster command centers; straightforward in FastAPI. |
| **B. Server-Sent Events (SSE)** | Unidirectional, built-in browser reconnection, standard HTTP. | Unidirectional only; edge proxies/CDNs sometimes buffer chunks. | **BACKUP CANDIDATE:** Simple alternative if WebSockets encounter proxy issues on Render. |
| **C. Periodic HTTP Polling** | Extremely simple, works everywhere through any firewall. | High DB load, sluggish 3-5s latency, poor hackathon wow-factor. | **CLIENT FALLBACK:** Activated automatically if WebSocket fails to connect after 3 retries. |

### Architectural Decision
* **Primary:** FastAPI WebSocket endpoint (`/ws/events`).
* **Fallback:** Client-side React fallback polling `GET /incidents?limit=50` every 5 seconds if WebSocket disconnects and fails to reconnect within 15 seconds.

---

## 4. Real-Time Event Contracts

All real-time messages broadcast over WebSocket use a typed JSON envelope:

```json
{
  "event": "INCIDENT_UPDATED",
  "payload": {},
  "timestamp": "2026-09-26T14:25:00Z"
}
```

### 4.1 Event Catalog

#### 1. `INCIDENT_CREATED`
* **Triggered When:** A new report does not match existing active incidents and spawns a new situation.
* **Payload:** Complete Canonical Incident object.
* **UI Action:** Card prepended to the triage queue with a brief pulsing highlight animation; new marker placed on the Leaflet map.

#### 2. `INCIDENT_UPDATED`
* **Triggered When:** An existing incident absorbs a corroborating/duplicate report, recalculates priority, or is modified by an operator.
* **Payload:**
  ```json
  {
    "incident_id": "inc-9831a2",
    "previous_priority_score": 68.0,
    "new_priority_score": 84.5,
    "new_priority_level": "CRITICAL",
    "corroboration": {
      "report_count": 3,
      "independent_source_count": 2,
      "score": 0.59
    },
    "latest_report_id": "rep-4412",
    "explanation": "Elevated due to new corroborating report indicating trapped victims."
  }
  ```
* **UI Action:** Card smoothly transitions to its new sorted rank in the queue; map marker color updates if level changed.

#### 3. `INCIDENT_STATUS_CHANGED`
* **Triggered When:** Incident is transitioned to `NEEDS_REVIEW`, `VERIFIED`, `RESOLVED`, or `FALSE_REPORT`.
* **Payload:** `{"incident_id": "inc-9831a2", "old_status": "ACTIVE", "new_status": "RESOLVED"}`.
* **UI Action:** Card fades out or moves to the "Resolved" tab; map marker is cleared.

#### 4. `SIMULATION_PULSE`
* **Triggered When:** The synthetic crisis generator injects a batch of reports.
* **Payload:** `{"injected_count": 5, "total_simulated": 42, "scenario": "flood_bhubaneswar_01"}`.
* **UI Action:** Top banner updates simulation counter; status badge shows live stream active.

---

## 5. Connection Lifecycle & Reconnection Policy

1. **Heartbeat / Keepalive:** Server sends `{"type": "PING"}` every 30 seconds. Client responds with `{"type": "PONG"}`.
2. **Reconnection with Exponential Backoff:**
   * If disconnected, the frontend attempts immediate reconnect at $1\text{s}$, $2\text{s}$, $4\text{s}$, up to a max interval of $10\text{s}$.
3. **Queue Resynchronization:**
   * Upon reconnecting, the frontend issues a full `GET /incidents` fetch to heal any events missed during the network drop.
