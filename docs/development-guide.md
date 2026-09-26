# Karen's Ear — Developer Collaboration & Implementation Guide

> **Target Audience:** Aryan, Daksh, Pankaj, Srinivash  
> **Status:** ACTIVE TEAM GUIDELINE  
> **Authority:** Derived from `gemini.md` (Project Constitution v1.2)

---

## 1. Team Ownership & Git Branches

Each developer operates on a dedicated feature branch. Never commit directly to `main` without cross-review.

| Developer | Primary Role | Feature Branch | Core Domain Ownership |
| :--- | :--- | :--- | :--- |
| **Aryan** | ML & NLP Engineer | `feature/ml-pipeline` | NLP preprocessing, classification, NER, `all-MiniLM-L6-v2` embeddings, feature-derived urgency. Owns `ml/` directory. |
| **Daksh** | Backend & Database | `feature/backend` | FastAPI application, PostgreSQL models, incident fusion engine, priority calculator, WebSocket broadcasting. Owns `backend/` directory. |
| **Pankaj** | Integration & Eval | `feature/evaluation-integration` | Synthetic disaster simulator, CrisiText evaluation benchmarks, end-to-end integration test suites. Owns `simulator/` and integration tests. |
| **Srinivash** | Frontend Engineer | `feature/frontend` | Command Center UI, tactical dark-mode design system, Leaflet map, live priority queue, human review drawer. Owns `frontend/` directory. |

---

## 2. Boundaries & Non-Interference Rules

1. **What You Own:** Full autonomy to implement internal algorithms, components, and helper utilities inside your designated directory.
2. **What You Must NOT Modify Unilaterally:**
   * `gemini.md` (Project Constitution)
   * `docs/api-contract.md` (Shared REST/WS contract)
   * `docs/data-schema.md` (Shared entity models)
   * `ml/schemas/incident_output.json` (Machine-readable ML contract)
   * `frontend/src/types/incident.ts` (Frontend TypeScript types)
   * `tools/` (Verification scripts)

---

## 3. The Shared-Contract Rule

If during development you discover that a shared contract needs an additional field or modified enum:

1. **DISCUSS FIRST:** Raise the proposed change immediately with the affected developers (e.g. Aryan & Daksh for ML output; Daksh & Srinivash for API response).
2. **UPDATE CONTRACT FIRST:** Modify the relevant shared contracts (`docs/api-contract.md`, `docs/data-schema.md`, `ml/schemas/incident_output.json`, `frontend/src/types/incident.ts`) BEFORE changing implementation code.
3. **UPDATE DEPENDENT CODE:** Both sides update their models/types to the new contract simultaneously.
4. **TEST INTERFACE:** Run integration verification to prove both sides serialize and deserialize without schema validation errors.

---

## 4. Role-Specific Implementation Rules

### 4.1 Aryan (ML Pipeline Rule)
* Your pipeline function `analyze_report()` must return a dictionary strictly validating against `ml/schemas/incident_output.json`.
* Do NOT change the 384-dimensional embedding output or field names without coordinating with Daksh.
* Strictly enforce the **No-Hallucination Policy**: If coordinates cannot be verified via the gazetteer, emit `null` for `latitude` and `longitude`.
* Operational urgency must follow the feature-derived rules (life-safety + hazard velocity) documented in `architecture/ml-pipeline.md`.

### 4.2 Daksh (Backend API Rule)
* Your FastAPI endpoints must accept and return payloads matching `docs/api-contract.md`.
* Every response must be wrapped in the canonical envelope:
  `{"success": true, "data": ..., "error": null, "request_id": "...", "timestamp": "..."}`.
* PostgreSQL tables and SQLAlchemy models must reflect `docs/data-schema.md` and `architecture/database.md`.
* Priority calculation must be deterministic; never delegate priority scoring to an LLM.

### 4.3 Srinivash (Frontend Command Center Rule)
* All UI state and components must typecheck against `frontend/src/types/incident.ts`.
* You MAY build and test components using mock incidents, but **all mock fixtures must conform 100% to the canonical `Incident` interface**.
* Do NOT invent private UI fields that conflict with the backend contract.
* If `incident.location.latitude == null`, display an "Unmapped / Approximate" pill on the card and do not place a hallucinated marker on the Leaflet map.

### 4.4 Pankaj (Simulator & Integration Rule)
* The disaster simulator must inject reports using the standard `POST /reports` endpoint matching `RawReport` in `docs/data-schema.md`.
* **Safety Invariant:** All simulated reports must set `"is_synthetic": true`. Never inject synthetic data with `is_synthetic: false`.
* Evaluation metrics must report quantitative F1, ROC-AUC, and latency numbers rather than subjective visual reviews.

---

## 5. Development Verification Commands

Before creating a pull request to `main`, verify that your code does not break local environment links:

```bash
# Run master link check
python tools/check_links.py

# Verify environment & config
python tools/check_environment.py

# Verify PostgreSQL connection
python tools/check_postgres.py
```
