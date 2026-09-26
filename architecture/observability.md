# Karen's Ear — Observability & Telemetry Architecture

## 1. Document Identity
* **System:** Karen's Ear Emergency Intelligence System
* **Layer:** Layer 1 — Technical Architecture Specification (SOP)
* **Status:** PROPOSED & APPROVED FOR ARCHITECTURE
* **Authority:** Follows `gemini.md` (Project Constitution v1.1)

---

## 2. Telemetry Principles & Requirements

In an emergency intelligence platform, operators and engineers must have immediate visibility into system health, ingestion throughput, inference latency, and algorithm explainability.

Key metrics tracked:
1. **End-to-End Tracing:** Every report ingestion carries a `request_id` passed through ML inference, database writes, and WebSocket broadcasts.
2. **ML Pipeline Profiling:** Tracking inference latency (ms), confidence scores, and fallback activation.
3. **Operational Metrics:** Tracking incident volume, critical queue size, and operator override frequencies.

---

## 3. Structured Logging Specification

Application logs are emitted in JSON format to stdout, adhering to 12-factor cloud standards for ingestion by Render and developer consoles:

```json
{
  "timestamp": "2026-09-26T14:30:15.120Z",
  "level": "INFO",
  "request_id": "req-18a7b93c",
  "event": "REPORT_PROCESSED",
  "report_id": "rep-4410",
  "incident_id": "inc-9831a2",
  "is_synthetic": false,
  "ml_latency_ms": 11.4,
  "total_latency_ms": 28.6,
  "similarity_score": 0.88,
  "relationship": "CORROBORATING",
  "priority_score": 84.5,
  "priority_level": "CRITICAL"
}
```

### Log Levels
* `DEBUG`: Raw token details, embedding dimensions, pairwise distance matrices.
* `INFO`: Standard business events (`REPORT_INGESTED`, `INCIDENT_FUSED`, `PRIORITY_CALCULATED`).
* `WARN`: Fallbacks triggered, low model confidence ($< 0.60$), unrecognized location formats, operator overrides.
* `ERROR`: Database connection retries, unhandled exceptions, WebSocket disconnect surges.

---

## 4. Key Performance Indicators (KPIs) & Monitoring Catalog

| KPI Name | Target SLA | Alert Condition | Diagnostic Action |
| :--- | :--- | :--- | :--- |
| **Ingestion Latency** | $< 100\text{ ms}$ | $> 500\text{ ms}$ | Check DB connection pool exhaustion. |
| **ML Inference Latency** | $< 30\text{ ms}$ (CPU) | $> 150\text{ ms}$ | Check CPU throttling or long string length. |
| **Confidence Ratio** | $> 80\%$ with $Conf \ge 0.60$ | $> 30\%$ falling to `NEEDS_REVIEW` | Potential data drift or noisy input channel. |
| **Deduplication Rate** | $25\% - 50\%$ in bursts | $0\%$ or $> 90\%$ | Verify `DUPLICATE_SIMILARITY_THRESHOLD`. |
| **WebSocket Connectivity** | Continuous stream | $> 5$ disconnects/min | Network instability between client and Render. |
| **Fallback Rate** | $< 1\%$ | $> 5\%$ fallback activation | Model process crash or memory pressure. |

---

## 5. Health Check & Diagnostics Endpoint

The backend provides a `/health` endpoint delivering real-time subsystem readiness:

```json
{
  "status": "HEALTHY",
  "timestamp": "2026-09-26T14:30:00Z",
  "uptime_seconds": 3600,
  "subsystems": {
    "database": {
      "status": "UP",
      "latency_ms": 2.1,
      "pool_available": 8
    },
    "ml_engine": {
      "status": "UP",
      "model": "sentence-transformers/all-MiniLM-L6-v2",
      "device": "cpu",
      "avg_latency_ms": 10.2
    },
    "websockets": {
      "active_connections": 2
    },
    "simulator": {
      "status": "IDLE"
    }
  }
}
```
