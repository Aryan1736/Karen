# Karen's Ear — Security Architecture Specification

## 1. Document Identity
* **System:** Karen's Ear Emergency Intelligence System
* **Layer:** Layer 1 — Technical Architecture Specification (SOP)
* **Status:** PROPOSED & APPROVED FOR ARCHITECTURE
* **Authority:** Follows `gemini.md` (Project Constitution v1.1)

---

## 2. Security Principles & Threat Model

Karen's Ear processes crisis intelligence. Malicious or compromised inputs must not crash the service, falsify incident records, or inject unauthorized emergency dispatches.

### Core Security Invariants
1. **Secrets Isolation:** No credentials, tokens, or connection strings are ever committed to version control, stored in client-side bundles, or printed to application logs.
2. **Input Sanitization by Default:** All external dispatches are untrusted input.
3. **Audit Immutability:** Human actions cannot be executed anonymously; every modification requires operator attribution.
4. **No Autonomous External Action:** The system strictly forbids automated outbound integration with real-world public safety answering points (PSAPs, 911, 112).

---

## 3. Secrets Management & Environment Isolation

* **Local Environment:** Stored in `.env` (enforced as untracked in `.gitignore`).
* **Safe Repository Template:** `.env.example` provides keys and safe placeholder values only.
* **Credential Masking:** Any diagnostic tool (such as `tools/check_postgres.py`) must dynamically mask sensitive fields (e.g., `postgresql://postgres:****@localhost:5432`).
* **Client-Side Restrictions:** The Vercel frontend only receives public configuration prefixed with `VITE_`. No database or private API tokens are exposed to the browser.

---

## 4. Input Validation & Defensive Boundaries

### 4.1 Schema Enforcement (FastAPI & Pydantic)
* Every endpoint validates incoming payloads against strict Pydantic schemas.
* **String Constraints:**
  * Report `text`: Minimum 3 characters, maximum 4,000 characters (guards against DoS via giant payloads).
  * `location_hint`: Maximum 255 characters.
  * `source`: Validated against allowed enum (`'manual'`, `'simulator'`, `'dataset'`, `'other'`).
* **HTML & Script Sanitization:** Text inputs undergo basic escaping/stripping to neutralize potential stored Cross-Site Scripting (XSS) when rendered in the command center.

### 4.2 SQL Injection Prevention
* All queries interact with PostgreSQL via **parameterized queries** through SQLAlchemy Core/ORM.
* String concatenation of raw user inputs into SQL statements is strictly prohibited.

---

## 5. Operational Safety & Synthetic Data Isolation

1. **Synthetic Data Guardrails:**
   * In a disaster scenario, confusing drill data with real human distress calls can lead to fatal misallocation of emergency assets.
   * Every synthetic report injected by the simulator or evaluation engine is stamped with:
     ```json
     "is_synthetic": true
     ```
   * The database enforces this boolean flag, and the UI visually styles synthetic incidents with distinct purple badges.
2. **Absolute Prohibition of Automated Real-World Dispatch:**
   * The system does not possess any outbound SMS, telephony, or webhook integrations to real police, fire, or ambulance dispatchers.
   * The system is strictly a decision-support and prioritization console for human operators.

---

## 6. Operator Authentication Architecture (Hackathon vs Production)

* **Hackathon Scope (24-Hour Sprint):**
  * Console operators identify themselves via a custom header (`X-Operator-Id: dispatcher_name`) or local storage session.
  * All overrides record this operator identity in `audit_logs`.
* **Production Roadmap:**
  * OAuth2 / OIDC authentication with Role-Based Access Control (RBAC):
    * `Viewer`: Can observe live queue and map.
    * `Dispatcher`: Can perform human review and overrides.
    * `Admin`: Can trigger simulation runs and alter system weights.
