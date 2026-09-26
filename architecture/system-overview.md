# Karen's Ear — System Overview & Architecture Specification

## 1. Document Identity
* **System:** Karen's Ear Emergency Intelligence System
* **Layer:** Layer 1 — Technical Architecture Specification (SOP)
* **Status:** PROPOSED & APPROVED FOR ARCHITECTURE
* **Authority:** Follows `gemini.md` (Project Constitution v1.1)

---

## 2. North Star & Purpose
> **Karen's Ear transforms incoming emergency reports into structured, explainable, and continuously prioritized incidents, helping an operator identify the most urgent situations quickly.**

Karen's Ear is an **operator decision-support system** for disaster response and emergency triage. In a disaster event, emergency hotlines, social media feeds, and field dispatches are flooded with fragmented, duplicate, unstructured, and urgent messages. Human dispatchers face extreme cognitive overload.

Karen's Ear solves this by:
1. Ingesting raw, unstructured emergency dispatches from heterogeneous sources (manual operator entry, streaming simulation, crisis datasets).
2. Extracting key intelligence: *What happened? Where did it happen? How urgent is it? Who is at risk? What response is required?*
3. Projecting semantic embeddings and running spatiotemporal correlation to detect duplicates vs. independent corroborations.
4. Fusing related reports into single, living **Incidents**.
5. Computing a transparent, deterministic, factor-by-factor priority score.
6. Presenting the intelligence in a real-time reactive command center with an interactive map and full human-in-the-loop auditability.

---

## 3. High-Level Data Flow Architecture

```text
Emergency Report (Unstructured Text, Source, Timestamp)
       │
       ▼
[ Ingestion & Validation ] (FastAPI / Pydantic schema validation)
       │
       ▼
[ ML/NLP Analysis Pipeline ] (Open-source Transformers, Zero-cost inference)
       ├── Incident Type Classification
       ├── Urgency Inference (Feature-derived rules & heuristics)
       ├── Information & Entity Extraction (Location, People at Risk, Response)
       └── Dense Semantic Embedding (384d MiniLM vector)
       │
       ▼
[ Structured Report Contract ] (Immutable record in PostgreSQL)
       │
       ▼
[ Semantic Correlation & Deduplication ] (Dense cosine similarity + Time decay + Proximity)
       ├── Duplicate Detection (Suppressed amplification, no corroboration boost)
       └── Corroboration Detection (Independent source evidence accumulation)
       │
       ▼
[ Incident Fusion Engine ] (Create new incident OR fuse into existing incident)
       │
       ▼
[ Deterministic Priority Engine ] (Urgency 35% + Risk 30% + Corroboration 20% + Type 15%)
       │
       ▼
[ Human-in-the-Loop Review ] (Operator verification, modification, or override)
       │
       ▼
[ Real-Time Dispatch ] (WebSockets / SSE state sync)
       │
       ▼
[ Command Center Dashboard ] (Vite / React + Leaflet / OpenStreetMap)
```

---

## 4. System Boundaries & Core Components

### 4.1 Frontend Component (Command Center)
* **Target:** Vercel (Static/SPA Edge Hosting)
* **Responsibilities:**
  * Real-time Prioritized Incident Queue (sorted by descending priority score).
  * Interactive Tactical Map (Leaflet.js + OpenStreetMap tiles, color-coded severity markers).
  * Incident Detail Drawer (Root causes, factor breakdown, corroboration audit trail, raw source reports).
  * Human Override Controls (Edit urgency, location, people at risk, notes with mandatory operator audit log).
  * Manual Report Injection Form (Direct field entry for testing and operator input).
  * Crisis Simulator Control Panel (Start/stop synthetic crisis streams, monitor ingestion velocity).
* **Boundaries:** Zero application business logic. Renders state delivered from Backend API; sends explicit operator commands.

### 4.2 Backend & Orchestration API Component
* **Target:** Render (Python Web Service)
* **Responsibilities:**
  * Ingestion endpoint handling and request validation against canonical contracts.
  * Layer 2 Navigation orchestration: triggers ML analysis, invokes fusion, calls priority scorer.
  * Incident State Machine management (`NEW` $\to$ `ANALYZING` $\to$ `ACTIVE` $\to$ `NEEDS_REVIEW` $\to$ `VERIFIED` $\to$ `RESOLVED`).
  * Real-time pub/sub delivery via WebSockets or SSE to connected frontend clients.
  * Audit logging for all state mutations and human overrides.
* **Boundaries:** Does not perform heavy ML model fine-tuning; acts as the deterministic coordinator and validation gate.

### 4.3 ML/NLP Service Component
* **Target:** Render (Colocated or dedicated Python worker service)
* **Responsibilities:**
  * Zero-cost CPU inference for dense embeddings (`sentence-transformers/all-MiniLM-L6-v2`).
  * Hybrid classification for crisis category and entity extraction.
  * Feature-derived operational urgency scoring based on life-safety tokens, hazard dynamics, and vulnerability context.
  * Producing normalized confidence scores $[0.0, 1.0]$.
* **Boundaries:** Advisory only. Does NOT write directly to the database or decide final priority. Emits strictly validated `ml_predictions` payload.

### 4.4 PostgreSQL Database Component
* **Target:** Render Managed PostgreSQL
* **Responsibilities:**
  * Runtime Source of Truth for all entities: `raw_reports`, `incidents`, `incident_reports`, `ml_predictions`, `priority_logs`, `audit_logs`.
  * Preserving immutable history of raw ingested messages.
  * Relational consistency and transactional safety.
* **Boundaries:** No business logic stored in stored procedures. Raw SQL / SQLAlchemy schema managed by Backend.

---

## 5. Trust Boundaries & Security Enclaves

```text
[ UNTRUSTED / EXTERNAL ]
  │  Public Internet / Simulated Feeds / Manual Dispatches
  ▼
──┼─────────────────────────────────────────────────────────────
  │  HTTPS / WSS Transport Security (TLS 1.3)
  ▼
[ CLIENT BOUNDARY: Vercel Frontend ]
  │  Stateless React Application
  │  Operator session / JWT or API Secret Header
  ▼
──┼─────────────────────────────────────────────────────────────
  │  Backend CORS Policy (Restricted to Vercel origin)
  ▼
[ INTERNAL BOUNDARY: Render Services Enclave ]
  ├── FastAPI Application (Pydantic Input Sanitization & Validation)
  ├── Local ML Runtime (Isolated in-memory process, read-only weights)
  └── PostgreSQL Database (Private internal network, password auth, SSL)
```

1. **Input Untrusted by Default:** All text dispatches are treated as raw untrusted strings. HTML/script tags are sanitized.
2. **AI Segregation:** The ML inference engine operates with read-only access to model weights. It cannot trigger database writes or system commands.
3. **No External Emergency Service Contact:** The system has an absolute invariant preventing automated calls, SMS, or automated webhooks to real 911/112/police dispatchers. It is an operator triage display only.
4. **Synthetic Data Labeling:** All synthetic or simulated reports carry `"is_synthetic": true`, visible on UI badges to prevent operator confusion.

---

## 6. Stakeholders & Users
1. **Emergency Command Center Operator:** Monitors the live priority feed, inspects highest-risk incidents, verifies AI explanations, and dispatches field assets.
2. **Tactical Supervisor:** Reviews `NEEDS_REVIEW` queues, overrides priority when external intelligence dictates, and inspects system audit logs.
3. **Field Dispatcher / Reporter:** Submits manual emergency reports from citizens or radios.
4. **Hackathon Evaluator:** Injects synthetic disaster bursts via the Simulator panel to assess system latency, deduplication accuracy, and live priority reordering.
