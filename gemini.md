# Karen's Ear — Project Constitution
Version: 1.1 (Phase 1 — Blueprint Approved with Revisions)
Status: BLUEPRINT_PENDING_APPROVAL
Authority: Project Source of Truth

---

# 1. Project Identity & North Star
**Project:** Karen's Ear Emergency Intelligence System  
**Event:** Bit n Build Hackathon (24-hour sprint)  
**Repository:** [https://github.com/Aryan1736/Karen.git](https://github.com/Aryan1736/Karen.git)

### The North Star
> **Karen's Ear transforms incoming emergency reports into structured, explainable and continuously prioritized incidents, helping an operator identify the most urgent situations quickly.**

The system is an **operator decision-support tool**, not an autonomous emergency dispatch system. It processes incoming emergency reports and answers:
1. **What happened?** (Incident type and classification)
2. **Where did it happen?** (Extracted location text, geocoded coordinates if verifiable, without hallucination)
3. **How urgent is it?** (Urgency and severity assessment)
4. **Who may be at risk?** (People at risk and vulnerability detection)
5. **What response may be required?** (Service needs: medical, fire, search & rescue, police)
6. **What reports belong together?** (Semantic duplicate/related report detection and incident fusion)
7. **Which incident deserves attention first?** (Continuous, explainable, deterministic operational priority ranking)

---

# 2. Core Architectural Principles
1. **AI is Probabilistic; Business Logic is Deterministic:**
   - ML components classify, extract entities, compute semantic embeddings, detect similarity, and output confidence.
   - Deterministic backend logic validates schemas, calculates final priority scores, executes incident fusion, transitions incident states, enforces safety bounds, and manages persistence.
2. **The ML Model is NOT the Source of Truth:**
   - ML generates advisory signals with explicit confidence metrics.
   - Operational truth resides strictly in the validated PostgreSQL database.
3. **No Hallucination Rule:**
   - Unknown information must strictly remain unknown (`null` / `"unknown"`).
   - Never fabricate precise locations. If a report only says "near Patia", preserve the raw phrasing with precision `"approximate"` rather than inventing an exact street address or coordinate.
4. **Resilience & Graceful Degradation:**
   - Model failure or schema validation errors must never crash the service; unparseable or failed reports are safely routed to `NEEDS_REVIEW` with warning diagnostics.
5. **Explainability Invariant:**
   - Every incident priority score must include human-readable component reasons (`priority.factors`), explaining why it was elevated or de-escalated.

---

# 3. System Architecture & Tech Stack

```text
GitHub (Aryan1736/Karen)
   │
   ├── Vercel
   │     └── Frontend / Command Center (React/Vite + Leaflet/OSM + Tailwind)
   │
   └── Render
         ├── Backend API (Python FastAPI + WebSockets)
         ├── ML/NLP Service (Hugging Face Transformers / Sentence-Transformers)
         └── PostgreSQL Database (Managed on Render)
```

- **Layer 1 (Architecture SOPs):** Technical SOPs in `architecture/`.
- **Layer 2 (Navigation / Decision Logic):** Deterministic routing between ML inference, deduplication, and database.
- **Layer 3 (Deterministic Tools):** Reusable atomic scripts in `tools/` with intermediate files in `.tmp/`.

---

# 4. Source of Truth Boundaries
- **Historical / Research / Evaluation Source:** `LanD-FBK/crisitext` (Hugging Face) supplemented by `QCRI/HumAID-all` and `crisistransformers`.
- **Runtime Application Source of Truth:** PostgreSQL (Stores raw reports, derived incidents, report-incident fusion links, ML predictions, confidence scores, corroboration metrics, priority logs, human overrides, and audit trails).

---

# 5. ML Pipeline & Urgency Methodology

### 5.1 Urgency Classification Methodology
- **CrisiText Dataset Limitation:** CrisiText provides 13 crisis hazard categories, scenario narratives, and warning messages. It does **not** provide ground-truth operational urgency labels (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
- **Methodology:** We will **not** pretend to train an end-to-end urgency classifier directly on CrisiText labels. Instead, urgency will be derived through an explicit, documented feature-based methodology:
  1. **Life-Safety Indicators:** Presence of trapped victims, confirmed casualties, distress markers ("help", "screaming", "suffocating").
  2. **Hazard Severity & Speed:** Hazard category dynamics (e.g., active flash flood / chemical explosion vs. slow rising water / downed tree).
  3. **Vulnerability Modifiers:** Impact on critical infrastructure (hospitals, shelters, schools).
  4. **Urgency Mapping:**
     - `CRITICAL`: Active imminent threat to human life or mass casualty event.
     - `HIGH`: Major destruction, severe hazard requiring immediate response.
     - `MEDIUM`: Secondary hazards, localized damage without trapped persons.
     - `LOW`: Advisory information, historical status updates, recovery requests.
  5. **Independent Evaluation:** This heuristic/feature model will be validated and benchmarked separately against a curated evaluation subset.

### 5.2 Performance & Resource Targets
- Resource limits on Render (free/starter tiers) and local machines depend on the specific hardware allocation and workload.
- Memory usage (target: $<500$MB) and CPU latency (target: $<25$ms) are **benchmarking targets to be measured and validated**, not pre-assumed constants. The pipeline will profile these metrics during Phase 2 (Link).

---

# 6. Canonical JSON Schema Contracts

## 6.1 Raw Report Input (`raw_reports`)
```json
{
  "report_id": "string",
  "text": "string",
  "source": "manual | simulator | dataset | other",
  "is_synthetic": true,
  "reported_at": "ISO-8601 datetime",
  "location_hint": {
    "raw_text": "string | null",
    "latitude": "number | null",
    "longitude": "number | null",
    "precision": "exact | approximate | unknown"
  },
  "metadata": {}
}
```

## 6.2 ML Analysis Output Contract
```json
{
  "report_id": "string",
  "model_version": "string",
  "incident_type": {
    "label": "string | null",
    "confidence": "number | null"
  },
  "urgency": {
    "label": "string | null",
    "confidence": "number | null"
  },
  "location": {
    "text": "string | null",
    "latitude": "number | null",
    "longitude": "number | null",
    "precision": "exact | approximate | unknown",
    "confidence": "number | null"
  },
  "people_at_risk": {
    "count": "number | null",
    "confidence": "number | null"
  },
  "required_response": [
    {
      "type": "string",
      "confidence": "number | null"
    }
  ],
  "entities": [
    {
      "text": "string",
      "type": "string",
      "confidence": "number | null"
    }
  ],
  "embedding_reference": "string | null",
  "processing_status": "SUCCESS | PARTIAL | FAILED | NEEDS_REVIEW",
  "warnings": []
}
```

## 6.3 Incident Representation (`incidents`)
```json
{
  "incident_id": "string",
  "status": "string",
  "incident_type": "string | null",
  "urgency": "string | null",
  "location": {
    "text": "string | null",
    "latitude": "number | null",
    "longitude": "number | null",
    "precision": "exact | approximate | unknown"
  },
  "people_at_risk": {
    "count": "number | null"
  },
  "required_response": [
    "string"
  ],
  "source_report_ids": [
    "string"
  ],
  "corroboration": {
    "report_count": "number",
    "independent_source_count": "number",
    "score": "number",
    "explanation": "string"
  },
  "ml_confidence": {
    "overall": "number | null",
    "components": {}
  },
  "priority": {
    "score": "number",
    "level": "string",
    "explanation": "string",
    "factors": []
  },
  "human_override": {
    "active": false,
    "updated_by": "string | null",
    "updated_at": "ISO-8601 datetime | null",
    "reason": "string | null"
  },
  "created_at": "ISO-8601 datetime",
  "updated_at": "ISO-8601 datetime"
}
```

## 6.4 Priority Output
```json
{
  "incident_id": "string",
  "priority_score": "number",
  "priority_level": "string",
  "factors": [
    {
      "factor": "string",
      "value": "number | string",
      "weight": "number",
      "contribution": "number"
    }
  ],
  "explanation": "string",
  "calculation_version": "string"
}
```

## 6.5 Human Override Schema (`audit_logs`)
```json
{
  "override_id": "string",
  "incident_id": "string",
  "operator_id": "string",
  "field": "string",
  "previous_value": "any",
  "new_value": "any",
  "reason": "string",
  "created_at": "ISO-8601 datetime"
}
```

## 6.6 API Response Envelope
```json
{
  "success": true,
  "data": {},
  "error": null,
  "request_id": "string",
  "timestamp": "ISO-8601 datetime"
}
```

---

# 7. Schema Rules & Invariants
- **IDs:** Generated by the application layer (UUIDv4 strings).
- **Timestamps:** Must strictly use ISO-8601 UTC format (`YYYY-MM-DDTHH:MM:SSZ`).
- **Confidence Values:** Normalized strictly to `[0.0, 1.0]`.
- **Raw Report Text:** Immutable once ingested into PostgreSQL.
- **Synthetic Data:** Must be explicitly tagged with `"is_synthetic": true`.
- **Unknown Values:** Use `null`, never fabricated placeholders or hallucinatory defaults.
- **Separation of Concerns:** ML outputs and deterministic outputs remain strictly distinct fields.
- **Human Overrides:** Stored and represented separately from ML predictions with full audit traceability.
- **Preservation of Lineage:** Every incident record must preserve its `source_report_ids`.
- **Constitutional Change Control:** Any schema modification requires updating `gemini.md` before implementation code.

---

# 8. Incident State Machine
- `NEW`: Raw report ingested, awaiting ML enrichment.
- `ANALYZING`: ML inference in flight.
- `ACTIVE`: Prioritized and active in operator queue.
- `NEEDS_REVIEW`: Confidence < 0.60, contradictory information, or extraction failure.
- `VERIFIED`: Confirmed by human operator or corroborated by independent sources.
- `ESCALATED`: Surged priority due to life-safety hazard or multi-source confirmation.
- `RESOLVED`: Incident handled and closed by operator.
- `FALSE_REPORT`: Spam, hoax, or out-of-scope; preserved for audit, excluded from active queue.

---

# 9. Incident Fusion & Dynamic Thresholding
- **Threshold Calibration Requirement:**
  - $\tau_{\text{dup}} \approx 0.85$ is established strictly as an **initial experimental baseline**.
  - It is **not** locked as a universal constant. The fusion threshold will be empirically tuned on real and simulated crisis data during development to prevent the serious failure mode of falsely merging separate, proximate incidents.
  - The fusion engine will support an environment-configurable threshold (`DUPLICATE_SIMILARITY_THRESHOLD`).
- **Corroboration Mechanics:**
  - Semantic similarity alone does not equal independent corroboration.
  - Reports from identical senders, identical IPs, or verbatim retweets are marked duplicates without incrementing the independent source count.

---

# 10. Deterministic Priority Engine (Blueprint Target)
Priority is bounded strictly between `0.0` and `100.0`:
$$\text{Priority Score} = w_{\text{urgency}} \cdot S_{\text{urgency}} + w_{\text{risk}} \cdot S_{\text{risk}} + w_{\text{corroboration}} \cdot S_{\text{corroboration}} + w_{\text{type}} \cdot S_{\text{type}} + \text{Modifiers}$$

Proposed baseline weights:
- $w_{\text{urgency}} = 35\%$ ($S_{\text{urgency}} \in [0, 100]$: CRITICAL=100, HIGH=75, MEDIUM=40, LOW=15)
- $w_{\text{risk}} = 30\%$ (People at risk: detected count or life-safety mention $\implies 100$, suspected $\implies 50$, none $\implies 0$)
- $w_{\text{corroboration}} = 20\%$ (Independent source reports: scaled log-sigmoid up to saturation at 5+ distinct witnesses)
- $w_{\text{type}} = 15\%$ (Hazard severity: structural collapse/active fire/flash flood $\implies 100$, medical/utility $\implies 60$)
- Modifiers: Explicit human priority override overrides formula value.

---

# 11. Real-Time Modes
- **Mode A (Manual Injection):** Operator enters report $\rightarrow$ ingested $\rightarrow$ ML inference $\rightarrow$ deduplication/fusion $\rightarrow$ priority calculated $\rightarrow$ WebSocket push to UI.
- **Mode B (Streaming Simulation):** Playback engine streams synthetic crisis scenarios (batch or interval), testing concurrency, clustering, and live priority re-ordering.

---

# 12. Team Ownership & Feature Branches
- Aryan: `feature/ml-pipeline` — ML inference, classification, NER, sentence embeddings.
- Daksh: `feature/backend` — FastAPI, PostgreSQL models, incident fusion engine, priority calculator, WebSockets.
- Pankaj: `feature/evaluation-integration` — End-to-end integration tests, simulation streaming engine, CrisiText evaluation.
- Srinivash: `feature/frontend` — Vercel dashboard, Leaflet map, live priority queue, human review UI, report injection.

---

# 13. Unresolved Architectural Decisions (Blueprint Sign-Off Items)
1. **Embedding Model Choice:**
   - Option A: `crisistransformers/CT-M1-Complete-SE` (tailored specifically for crisis texts).
   - Option B: `sentence-transformers/all-MiniLM-L6-v2` (lightweight baseline model).
   - Validation: Profile both models for memory usage and inference latency on actual target runtime instances.
2. **NER / Location Strategy:**
   - SpaCy `en_core_web_sm` vs Hugging Face `dslim/bert-base-NER` for zero-cost local entity extraction without API keys.
3. **Database Migration Strategy:**
   - Alembic vs direct SQLAlchemy/SQL init script for 24h hackathon speed.
