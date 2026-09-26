# 🎙️ Karen's Ear — AI/ML Emergency Intelligence & Prioritization System

> **Transforming noisy, fragmented emergency dispatches into structured, explainable, and continuously prioritized incidents.**

Developed for the **Bit n Build Hackathon** (24-Hour Sprint).

---

## 🧭 North Star
In a disaster, emergency call centers and social media feeds are inundated with duplicate, chaotic, and urgent messages. **Karen's Ear** serves as an intelligent decision-support console for emergency operators by answering:
1. **What happened?** (Multi-hazard crisis classification)
2. **Where did it happen?** (Conservative location extraction without GPS hallucination)
3. **How urgent is it?** (Feature-derived life-safety and hazard velocity scoring)
4. **Who is at risk?** (Victim and trapped persons detection)
5. **What response is needed?** (Automated service mapping: Search & Rescue, Medical, Fire)
6. **Which reports belong together?** (Dense semantic embedding + spatiotemporal triangulation to distinguish duplicates from true corroborations)
7. **Which incident deserves attention first?** (Deterministic, multi-factor priority ranking with human-in-the-loop auditability)

---

## 🏛️ The 3-Layer Architecture (B.L.A.S.T. Protocol)

```text
┌────────────────────────────────────────────────────────┐
│ LAYER 1 — ARCHITECTURE (SOPs & Contracts)               │
│ Standard Operating Procedures in architecture/         │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ LAYER 2 — NAVIGATION (State Orchestration)             │
│ Decision flow & state machine in architecture/navigation.md
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ LAYER 3 — TOOLS (Deterministic Executables)            │
│ Atomic verification and operational tools in tools/    │
└────────────────────────────────────────────────────────┘
```

---

## 📚 Technical Architecture Documentation (`architecture/`)

All system logic, invariants, and interface contracts are formally specified in [`architecture/`](architecture/):

1. **[System Overview](architecture/system-overview.md):** Purpose, data flow, trust boundaries, and component roles.
2. **[ML & NLP Pipeline](architecture/ml-pipeline.md):** Open-source inference, embeddings (`all-MiniLM-L6-v2`), and feature-derived urgency.
3. **[Incident Correlation & Deduplication](architecture/incident-correlation.md):** Dense cosine similarity, time decay, and corroboration saturation.
4. **[Deterministic Priority Engine](architecture/priority-engine.md):** Mathematical formula, factor normalization, and explainability breakdown.
5. **[Human Review & Override](architecture/human-review.md):** Operator workflow, immutable audit ledger, and raw ML preservation.
6. **[Failure Handling & Fallbacks](architecture/failure-handling.md):** Graceful degradation matrix (`AI failure ≠ system failure`).
7. **[API Contracts](architecture/api-contracts.md):** Standardized JSON envelopes, REST endpoints, and error handling.
8. **[Database Architecture](architecture/database.md):** PostgreSQL runtime source of truth, schema models, and indexes.
9. **[Real-Time Streaming](architecture/realtime.md):** Native WebSocket event catalog and reconnection policies.
10. **[Synthetic Simulation Engine](architecture/simulation.md):** Scenario presets (`CrisiText`), rate throttling, and safety tagging.
11. **[Command Center Frontend](architecture/frontend.md):** Tactical dark-mode UI, Leaflet map integration, and design system tokens.
12. **[Deployment & Infrastructure](architecture/deployment.md):** Vercel (Edge SPA) + Render (FastAPI + ML + Managed PostgreSQL).
13. **[Security Architecture](architecture/security.md):** Secrets isolation, input sanitization, and automated dispatch prohibition.
14. **[Testing & Evaluation](architecture/testing.md):** Multi-level verification pyramid and quantitative ML benchmark criteria.
15. **[Observability & Telemetry](architecture/observability.md):** Structured JSON logging, end-to-end tracing, and health checks.
16. **[Navigation Layer](architecture/navigation.md):** Layer 2 state machine transitions and orchestration flow.
17. **[Architectural Decision Records (ADRs)](architecture/decisions.md):** Binding design decisions (ADR-001 through ADR-010).

---

## 🤝 Shared Developer Contracts & Implementation Tooling

Shared contracts ensuring zero interface drift across the four feature branches:
* **[API Contract](docs/api-contract.md):** Complete REST endpoints, WebSocket envelopes, status codes, and request tracing.
* **[Canonical Data Schema](docs/data-schema.md):** Required/optional fields, enums, timestamps, and validation invariants.
* **[Developer Collaboration Guide](docs/development-guide.md):** Feature branch ownership, shared-contract change protocol, and mocking rules.
* **[ML Output JSON Schema](ml/schemas/incident_output.json):** Machine-readable JSON Schema for Aryan's NLP inference output.
* **[Frontend TypeScript Types](frontend/src/types/incident.ts):** Strict TypeScript types for Srinivash's command center components.

---

## 🛠️ Verification & Connectivity Tools (`tools/`)

Deterministic verification scripts created during Phase 2 (Link):
* `tools/check_environment.py`: Verifies Python 3.13, Node.js v22, git remote, and core files.
* `tools/check_osm.py`: Verifies OpenStreetMap tile and web server connectivity.
* `tools/check_postgres.py`: Verifies live local PostgreSQL connection and `SELECT 1`.
* `tools/check_crisitext.py`: Verifies public streaming access to `LanD-FBK/crisitext` on Hugging Face.
* `tools/check_ml_runtime.py`: Verifies `all-MiniLM-L6-v2` loading and measures CPU inference latency (**9.68 ms**).
* `tools/check_links.py`: Master deterministic runner executing all connectivity checks.

Run master link check:
```bash
python tools/check_links.py
```

---

## 👥 Team Ownership
* **Aryan:** ML Architecture, NLP Pipeline, Embeddings, Feature-derived Urgency (`feature/ml-pipeline`).
* **Daksh:** Backend API, PostgreSQL Models, Incident Fusion Engine, Priority Calculator (`feature/backend`).
* **Pankaj:** System Integration, Simulation Streaming Engine, CrisiText Evaluation (`feature/evaluation-integration`).
* **Srinivash:** Command Center UX, Leaflet Map, Queue Re-ordering, Operator Review UI (`feature/frontend`).

---

## 📜 Project Memory & Constitution
* [`gemini.md`](gemini.md): Project Constitution & canonical JSON contracts.
* [`task_plan.md`](task_plan.md): B.L.A.S.T. roadmap and active checklist.
* [`findings.md`](findings.md): Research discoveries, dataset schemas, and empirical benchmarks.
* [`progress.md`](progress.md): Chronological execution log and test scorecard.
