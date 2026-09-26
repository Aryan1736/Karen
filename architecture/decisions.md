# Karen's Ear — Architectural Decision Records (ADRs)

## 1. Document Identity
* **System:** Karen's Ear Emergency Intelligence System
* **Layer:** Layer 1 — Architectural Decision Ledger
* **Status:** APPROVED & BINDING
* **Authority:** Follows `gemini.md` (Project Constitution v1.1)

---

## Index of Architectural Decision Records

* **ADR-001:** Hybrid ML + Deterministic Business Logic Architecture
* **ADR-002:** PostgreSQL as Runtime Source of Truth
* **ADR-003:** Feature-Derived Urgency Methodology (CrisiText Independence)
* **ADR-004:** Strict Separation of ML Confidence from Operational Priority
* **ADR-005:** Spatiotemporal Evidence Triangulation & Dynamic Thresholding
* **ADR-006:** Immutable Human Override Audit Trail & Raw ML Preservation
* **ADR-007:** Dual-Platform Deployment (Vercel Frontend + Render Backend/DB)
* **ADR-008:** Absolute Prohibition of Automated Real-World Emergency Contact
* **ADR-009:** Strict No-Hallucination Policy for Geographic Coordinates
* **ADR-010:** WebSockets as Primary Real-Time Transport with Polling Fallback

---

### ADR-001: Hybrid ML + Deterministic Business Logic Architecture
* **Context:** Modern AI applications often attempt to use large language models (LLMs) to make end-to-end decisions, including scoring priorities and triggering database updates. In high-stakes emergency triage, LLM non-determinism, hallucinations, and latency introduce unacceptable risks.
* **Decision:** Split the system strictly into probabilistic AI/ML signals (NLP feature extraction, embeddings, similarity) and deterministic application logic (schema validation, incident fusion, priority scoring formula, database state transitions).
* **Alternatives Considered:** Pure LLM agent orchestration; hardcoded rule-based regex system without ML.
* **Rationale:** Combines the semantic understanding of NLP with the mathematical reproducibility, auditability, and speed of deterministic code.
* **Consequences:** Every priority calculation is fully explainable; tests can deterministically verify score outputs.

---

### ADR-002: PostgreSQL as Runtime Source of Truth
* **Context:** The system handles unstructured reports, intermediate embeddings, fused incidents, and operator audits.
* **Decision:** PostgreSQL is the sole runtime source of truth. All entities (`raw_reports`, `incidents`, `ml_predictions`, `audit_logs`) reside in relational tables.
* **Alternatives Considered:** MongoDB / Document DB; in-memory Redis state; local SQLite files.
* **Rationale:** ACID compliance, relational integrity between reports and incidents, rich JSONB support for variable entities, and managed availability on Render.
* **Consequences:** Backend services remain completely stateless and can scale or restart without risk of state corruption.

---

### ADR-003: Feature-Derived Urgency Methodology (CrisiText Independence)
* **Context:** CrisiText (`LanD-FBK/crisitext`) is our primary crisis research dataset. However, CrisiText consists of crisis scenario event chains and NLG warning variants; it does *not* provide categorical operational urgency labels (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
* **Decision:** Do NOT claim or attempt to train an end-to-end urgency classifier directly on CrisiText. Instead, derive operational urgency via an explicit, documented feature-extraction heuristic (life-safety markers, trapped victims, hazard dynamics, infrastructure vulnerability) and evaluate it separately against a curated test benchmark.
* **Alternatives Considered:** Forcing artificial pseudo-labels on CrisiText text; training a classifier on an unrelated sentiment dataset.
* **Rationale:** Academic integrity and operational safety. Transparent feature extraction avoids hallucinated urgency labels.
* **Consequences:** Urgency logic is inspectable, configurable, and evaluated independently without corrupting dataset fidelity.

---

### ADR-004: Strict Separation of ML Confidence from Operational Priority
* **Context:** A high-confidence prediction does not mean an incident is urgent (e.g. 99% confident a cat is in a tree $\implies$ low priority). Conversely, a low-confidence report might describe a fatal building collapse $\implies$ critical priority.
* **Decision:** Model prediction confidence and operational incident priority are modeled and computed as completely distinct dimensions.
* **Alternatives Considered:** Multiplying priority by confidence (which dangerously suppresses critical, noisy reports).
* **Rationale:** Ensures operators are immediately alerted to high-risk situations while being transparently warned if the AI extraction confidence is low.
* **Consequences:** UI displays both the Priority Badge (`CRITICAL`) and the Confidence Metric (`54% - Needs Review`).

---

### ADR-005: Spatiotemporal Evidence Triangulation & Dynamic Thresholding
* **Context:** Incoming dispatches during a disaster are repetitive. Naive duplicate detection either fails to merge related reports or mistakenly merges distinct emergencies across town.
* **Decision:** Implement three-dimensional correlation (dense semantic cosine similarity + exponential temporal decay + spatial proximity). Set initial experimental baseline $\tau_{\text{dup}} \approx 0.85$, but externalize all thresholds in environment configuration without hard-coding.
* **Alternatives Considered:** Fixed hardcoded cosine threshold of 0.85; exact text string matching; purely geographic bounding box clustering.
* **Rationale:** Allows empirical calibration on real crisis data during development and prevents false incident merges.
* **Consequences:** Thresholds can be tuned without modifying codebase; distinct emergencies are preserved.

---

### ADR-006: Immutable Human Override Audit Trail & Raw ML Preservation
* **Context:** Dispatchers must be able to correct AI errors. However, overwriting original ML predictions destroys diagnostic and training data.
* **Decision:** Human overrides update the active incident presentation, but never mutate or delete the underlying `ml_predictions` record. Every override requires an operator ID and an explanation reason, recorded in an append-only `audit_logs` table.
* **Alternatives Considered:** In-place column overwriting without audit; read-only AI output with no operator override capability.
* **Rationale:** Full legal and regulatory accountability; enables retrospective analysis of human-AI agreement rates.
* **Consequences:** Storage overhead is negligible; compliance and safety guarantees are absolute.

---

### ADR-007: Dual-Platform Deployment (Vercel Frontend + Render Backend/DB)
* **Context:** Karen's Ear is built under a 24-hour hackathon constraint.
* **Decision:** Deploy static React/Vite command center to Vercel; deploy FastAPI backend, ML runtime, and PostgreSQL to Render.
* **Alternatives Considered:** Monolithic container on AWS ECS; full self-hosted VPS; serverless lambdas for ML.
* **Rationale:** Vercel provides instant global edge hosting for SPAs with zero configuration; Render supports native Python 3.13 web services and managed PostgreSQL within a unified dashboard.
* **Consequences:** Clear division of team responsibilities; avoids complex cloud infrastructure setup during the 24-hour sprint.

---

### ADR-008: Absolute Prohibition of Automated Real-World Emergency Contact
* **Context:** Hackathon prototypes handling disaster dispatches must avoid triggering actual emergency response infrastructure.
* **Decision:** The system strictly operates as an operator decision-support console. Automated outbound integration with real 911/112 PSAPs, SMS dispatchers, or siren sirens is permanently prohibited.
* **Alternatives Considered:** Mocking external webhooks; real SMS alerts.
* **Rationale:** Safety, ethical compliance, and legal liability.
* **Consequences:** The system remains safely self-contained for evaluation and demonstration.

---

### ADR-009: Strict No-Hallucination Policy for Geographic Coordinates
* **Context:** Reports often mention vague locations ("near Patia market", "under the overpass"). Geocoding services or LLMs might hallucinate exact lat/long coordinates.
* **Decision:** If verifiable coordinates cannot be confirmed via controlled gazetteer lookup, `latitude` and `longitude` remain `null`, `precision` is set to `"approximate"` or `"unknown"`, and raw location text is preserved verbatim.
* **Alternatives Considered:** Defaulting to city center coordinates (0,0 or municipal hall); letting an LLM guess coordinates.
* **Rationale:** Placing a pin in the wrong neighborhood directs rescue teams to the wrong location, costing lives.
* **Consequences:** UI cleanly displays an "Unmapped / Approximate" tag without false pins on the map.

---

### ADR-010: WebSockets as Primary Real-Time Transport with Polling Fallback
* **Context:** Incident queue re-ordering requires sub-second push updates to the operator browser.
* **Decision:** Use native FastAPI WebSockets (`/ws/events`) as primary transport. Implement automated client-side fallback to periodic HTTP polling if WebSockets fail to connect.
* **Alternatives Considered:** Pure HTTP polling; Server-Sent Events (SSE) only.
* **Rationale:** WebSockets deliver minimal latency and bidirectional heartbeat support; HTTP fallback guarantees resilience under restrictive proxy or firewall conditions.
* **Consequences:** Robust real-time connectivity across all deployment environments.
