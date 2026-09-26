# Karen's Ear — Database Architecture Specification

## 1. Document Identity
* **System:** Karen's Ear Emergency Intelligence System
* **Layer:** Layer 1 — Technical Architecture Specification (SOP)
* **Status:** PROPOSED & APPROVED FOR ARCHITECTURE
* **Authority:** Follows `gemini.md` (Project Constitution v1.1)

---

## 2. Core Database Invariant
> **PostgreSQL is the runtime source of truth. All application state, incident linkages, ML predictions, and audit logs persist in PostgreSQL.**

The database model is designed for:
1. **Append-Only Immutability for Ingested Reports:** Raw emergency messages are never overwritten or deleted.
2. **Relational Traceability:** Every incident can trace back to the exact individual dispatches that corroborated it.
3. **Audit Trail Preservation:** Overrides and state transitions are stored in an append-only audit ledger.

---

## 3. Entity-Relationship Diagram

```text
       ┌────────────────────────┐
       │      raw_reports       │
       │────────────────────────│
       │ PK  report_id          │
       │     text (immutable)   │
       │     source             │
       │     is_synthetic       │
       │     reported_at        │
       │     location_hint      │
       └───────────┬────────────┘
                   │ 1
                   │
         ┌─────────┴─────────┐
         │ 1                 │ 1
         ▼                   ▼
┌──────────────────┐  ┌─────────────────────────┐
│  ml_predictions  │  │    incident_reports     │
│──────────────────│  │─────────────────────────│
│ PK  prediction_id│  │ PK  id                  │
│ FK  report_id    │  │ FK  report_id           │
│     incident_type│  │ FK  incident_id         │
│     urgency      │  │     relationship_type   │
│     entities     │  │     similarity_score    │
│     embedding    │  │     fused_at            │
│     confidence   │  └───────────┬─────────────┘
└──────────────────┘              │ N
                                  │
                                  ▼ 1
                      ┌─────────────────────────┐
                      │        incidents        │
                      │─────────────────────────│
                      │ PK  incident_id         │
                      │     status              │
                      │     incident_type       │
                      │     urgency             │
                      │     latitude / longitude│
                      │     people_at_risk_count│
                      │     priority_score      │
                      │     priority_level      │
                      │     corroboration_score │
                      │     human_override_json │
                      │     created_at          │
                      │     updated_at          │
                      └───────────┬─────────────┘
                                  │ 1
                   ┌──────────────┴──────────────┐
                   │ 1                           │ 1
                   ▼ N                           ▼ N
       ┌─────────────────────────┐   ┌─────────────────────────┐
       │  priority_calculations  │   │       audit_logs        │
       │─────────────────────────│   │─────────────────────────│
       │ PK  calc_id             │   │ PK  override_id         │
       │ FK  incident_id         │   │ FK  incident_id         │
       │     priority_score      │   │     operator_id         │
       │     priority_level      │   │     field               │
       │     factors_json        │   │     previous_value      │
       │     explanation         │   │     new_value           │
       │     calc_version        │   │     reason              │
       │     calculated_at       │   │     created_at          │
       └─────────────────────────┘   └─────────────────────────┘
```

---

## 4. Entity Specifications

### 4.1 Table: `raw_reports`
* **Purpose:** Stores the untampered, incoming dispatch from any source.
* **Fields:**
  * `report_id` (`VARCHAR(64)`, Primary Key, UUID or deterministic hash).
  * `text` (`TEXT`, NOT NULL): Original raw dispatch content.
  * `source` (`VARCHAR(32)`, NOT NULL): e.g. `'manual'`, `'simulator'`, `'crisitext'`.
  * `is_synthetic` (`BOOLEAN`, NOT NULL, default `FALSE`).
  * `reported_at` (`TIMESTAMPTZ`, NOT NULL): Event timestamp reported by source.
  * `location_hint` (`JSONB`, NULL): Raw location text or initial GPS coordinates.
  * `metadata` (`JSONB`, NULL): Technical metadata (caller ID, client IP, channel).
  * `ingested_at` (`TIMESTAMPTZ`, NOT NULL, default `NOW()`).

### 4.2 Table: `ml_predictions`
* **Purpose:** Stores the advisory NLP output generated for a specific report.
* **Fields:**
  * `prediction_id` (`VARCHAR(64)`, Primary Key).
  * `report_id` (`VARCHAR(64)`, Foreign Key $\to$ `raw_reports.report_id`, UNIQUE).
  * `model_version` (`VARCHAR(64)`, NOT NULL): e.g. `'all-MiniLM-L6-v2+heuristic-v1'`.
  * `incident_type` (`JSONB`): `{"label": "FLOOD", "confidence": 0.94}`.
  * `urgency` (`JSONB`): `{"label": "CRITICAL", "confidence": 0.88}`.
  * `location` (`JSONB`): Extracted location text, coords, and confidence.
  * `people_at_risk` (`JSONB`): Extracted count and confidence.
  * `required_response` (`JSONB`): Array of response types.
  * `entities` (`JSONB`): NER token entities.
  * `embedding` (`REAL[]` or `VECTOR(384)`): 384-dimensional dense representation.
  * `overall_confidence` (`NUMERIC(4,3)`): Aggregated confidence $[0.0, 1.0]$.
  * `processing_status` (`VARCHAR(32)`): `'SUCCESS'`, `'PARTIAL'`, `'FAILED'`, `'NEEDS_REVIEW'`.
  * `warnings` (`TEXT[]`): Diagnostics or fallback notes.
  * `created_at` (`TIMESTAMPTZ`, NOT NULL, default `NOW()`).

### 4.3 Table: `incidents`
* **Purpose:** Represents the unified, actionable emergency situation presented to dispatchers.
* **Fields:**
  * `incident_id` (`VARCHAR(64)`, Primary Key).
  * `status` (`VARCHAR(32)`, NOT NULL): `'NEW'`, `'ANALYZING'`, `'ACTIVE'`, `'NEEDS_REVIEW'`, `'VERIFIED'`, `'ESCALATED'`, `'RESOLVED'`, `'FALSE_REPORT'`.
  * `incident_type` (`VARCHAR(64)`, NULL): Dominant hazard classification.
  * `urgency` (`VARCHAR(32)`, NULL): Current operational urgency.
  * `location_text` (`TEXT`, NULL): Primary location phrasing.
  * `latitude` (`DOUBLE PRECISION`, NULL): Geocoded latitude.
  * `longitude` (`DOUBLE PRECISION`, NULL): Geocoded longitude.
  * `location_precision` (`VARCHAR(32)`, default `'unknown'`): `'exact'`, `'approximate'`, `'unknown'`.
  * `people_at_risk_count` (`INTEGER`, default 0).
  * `priority_score` (`NUMERIC(5,2)`, default 0.00): Current ranking score $[0.0, 100.0]$.
  * `priority_level` (`VARCHAR(16)`, default `'LOW'`): `'CRITICAL'`, `'HIGH'`, `'MEDIUM'`, `'LOW'`.
  * `corroboration_score` (`NUMERIC(4,3)`, default 0.000).
  * `report_count` (`INTEGER`, default 1).
  * `independent_source_count` (`INTEGER`, default 1).
  * `human_override` (`JSONB`, default `{"active": false}`): Active operator override snapshot.
  * `created_at` (`TIMESTAMPTZ`, NOT NULL, default `NOW()`).
  * `updated_at` (`TIMESTAMPTZ`, NOT NULL, default `NOW()`).

### 4.4 Table: `incident_reports`
* **Purpose:** Join table linking dispatches to incidents, tracking deduplication vs corroboration.
* **Fields:**
  * `id` (`VARCHAR(64)`, Primary Key).
  * `incident_id` (`VARCHAR(64)`, Foreign Key $\to$ `incidents.incident_id`, NOT NULL).
  * `report_id` (`VARCHAR(64)`, Foreign Key $\to$ `raw_reports.report_id`, NOT NULL).
  * `relationship_type` (`VARCHAR(32)`, NOT NULL): `'INITIAL'`, `'CORROBORATING'`, `'DUPLICATE'`, `'RELATED'`, `'UNCERTAIN'`.
  * `similarity_score` (`NUMERIC(4,3)`, NULL): Cosine similarity at time of fusion.
  * `fused_at` (`TIMESTAMPTZ`, NOT NULL, default `NOW()`).

### 4.5 Table: `priority_calculations`
* **Purpose:** Historical log of every priority score adjustment for full explainability and replay.
* **Fields:**
  * `calc_id` (`VARCHAR(64)`, Primary Key).
  * `incident_id` (`VARCHAR(64)`, Foreign Key $\to$ `incidents.incident_id`, NOT NULL).
  * `priority_score` (`NUMERIC(5,2)`, NOT NULL).
  * `priority_level` (`VARCHAR(16)`, NOT NULL).
  * `factors` (`JSONB`, NOT NULL): Array of factor objects (factor, value, weight, contribution).
  * `explanation` (`TEXT`, NOT NULL): Plain-language justification string.
  * `calc_version` (`VARCHAR(32)`, NOT NULL): e.g. `'v1.0-deterministic'`.
  * `calculated_at` (`TIMESTAMPTZ`, NOT NULL, default `NOW()`).

### 4.6 Table: `audit_logs`
* **Purpose:** Immutable audit ledger for every human override and administrative modification.
* **Fields:**
  * `override_id` (`VARCHAR(64)`, Primary Key).
  * `incident_id` (`VARCHAR(64)`, Foreign Key $\to$ `incidents.incident_id`, NOT NULL).
  * `operator_id` (`VARCHAR(64)`, NOT NULL).
  * `field` (`VARCHAR(64)`, NOT NULL): e.g. `'urgency'`, `'priority_score'`, `'location'`.
  * `previous_value` (`JSONB`, NOT NULL).
  * `new_value` (`JSONB`, NOT NULL).
  * `reason` (`TEXT`, NOT NULL).
  * `created_at` (`TIMESTAMPTZ`, NOT NULL, default `NOW()`).

### 4.7 Table: `simulation_runs`
* **Purpose:** Metadata tracking for simulated disaster scenarios.
* **Fields:**
  * `simulation_id` (`VARCHAR(64)`, Primary Key).
  * `scenario_id` (`VARCHAR(64)`, NOT NULL).
  * `status` (`VARCHAR(32)`, NOT NULL): `'RUNNING'`, `'STOPPED'`, `'COMPLETED'`.
  * `reports_injected` (`INTEGER`, default 0).
  * `started_at` (`TIMESTAMPTZ`, NOT NULL, default `NOW()`).
  * `ended_at` (`TIMESTAMPTZ`, NULL).

---

## 5. Indexing & Query Optimization Strategy

1. **Active Triage Queue Index:**
   ```sql
   CREATE INDEX idx_incidents_active_priority 
   ON incidents (priority_score DESC, status) 
   WHERE status IN ('ACTIVE', 'NEEDS_REVIEW', 'VERIFIED', 'ESCALATED');
   ```
2. **Recent Active Incidents for Correlation:**
   ```sql
   CREATE INDEX idx_incidents_recent_active 
   ON incidents (updated_at DESC) 
   WHERE status IN ('ACTIVE', 'NEEDS_REVIEW');
   ```
3. **Relationship Lookup Indexes:**
   ```sql
   CREATE INDEX idx_incident_reports_incident ON incident_reports (incident_id);
   CREATE INDEX idx_incident_reports_report ON incident_reports (report_id);
   ```
4. **Audit Search Index:**
   ```sql
   CREATE INDEX idx_audit_logs_incident ON audit_logs (incident_id, created_at DESC);
   ```
