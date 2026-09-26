# Karen's Ear — Deployment & Infrastructure Architecture

## 1. Document Identity
* **System:** Karen's Ear Emergency Intelligence System
* **Layer:** Layer 1 — Technical Architecture Specification (SOP)
* **Status:** PROPOSED & APPROVED FOR ARCHITECTURE
* **Authority:** Follows `gemini.md` (Project Constitution v1.1)

---

## 2. Deployment Topology

```text
                                GitHub (Aryan1736/Karen)
                                           │
                       ┌───────────────────┴───────────────────┐
                       ▼                                       ▼
            [ VERCEL (Frontend) ]                    [ RENDER (Backend) ]
         Static React / Vite Edge SPA            FastAPI + PyTorch ML Service
                       │                                       │
                       │ HTTPS / WSS API Requests              │ Private Network
                       │                                       ▼
                       └─────────────────────────────► [ RENDER PostgreSQL ]
                                                        Managed Database
```

---

## 3. Platform Breakdown & Service Roles

### 3.1 Frontend: Vercel
* **Platform:** Vercel Global Edge Network.
* **Build Command:** `npm run build` (produces optimized `dist/`).
* **Output Directory:** `dist/`.
* **Runtime:** Edge CDN Static Hosting with client-side SPA routing (`rewrites: [{"source": "/(.*)", "destination": "/index.html"}]`).
* **Environment Variables:**
  * `VITE_API_URL`: Base HTTPS URL of Render backend (e.g. `https://karen-backend.onrender.com`).
  * `VITE_WS_URL`: WebSocket URL of Render backend (e.g. `wss://karen-backend.onrender.com/ws/events`).

### 3.2 Backend & ML Service: Render
* **Platform:** Render Web Service (Native Python 3.13 environment).
* **Build Command:**
  ```bash
  pip install --upgrade pip && pip install -r requirements.txt
  ```
* **Start Command:**
  ```bash
  uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
  ```
* **Single Worker Deployment Invariant:**
  The backend **MUST** run with exactly one worker (`--workers 1`). The real-time WebSocket `ConnectionManager` maintains connected clients in an in-memory process registry. Multiple Uvicorn workers would partition connected clients across isolated memory spaces, preventing cross-worker event broadcasting without an external message broker (such as Redis pub/sub).
* **Hardware Tier Target:** Render Starter / Free tier (512MB - 2GB RAM).
* **Statelessness Invariant:** The service has **zero** dependency on the local ephemeral disk for persistence. All incident data, predictions, and audit logs reside in PostgreSQL.

### 3.3 Database: Render Managed PostgreSQL
* **Version:** PostgreSQL 16+ (Local dev tested on 18.3).
* **Access Mode:** Internal secure connection string over Render private network (`postgresql://...`).
* **External Access:** SSL-enforced for developer tools and migration scripts.

---

## 4. Environment Variables Matrix

| Variable Name | Required Service | Example (Safe Placeholder) | Secret? | Purpose |
| :--- | :--- | :--- | :---: | :--- |
| `DATABASE_URL` | Backend | `postgresql://user:pass@render-db:5432/karen` | **YES** | Primary relational datastore connection string |
| `ML_MODEL_NAME` | Backend | `sentence-transformers/all-MiniLM-L6-v2` | No | Model identifier for Hugging Face weights |
| `HF_DATASET` | Backend / Eval | `LanD-FBK/crisitext` | No | Public dataset identifier |
| `DUPLICATE_SIMILARITY_THRESHOLD` | Backend | `0.85` | No | Baseline cosine threshold for incident deduplication |
| `CORROBORATION_SIMILARITY_THRESHOLD` | Backend | `0.70` | No | Minimum similarity threshold for related incident fusion |
| `CORS_ORIGINS` | Backend | `https://karen-ear.vercel.app,http://localhost:5173` | No | Allowed frontend origins |
| `VITE_API_URL` | Frontend | `https://karen-backend.onrender.com` | No | REST API endpoint |
| `VITE_WS_URL` | Frontend | `wss://karen-backend.onrender.com/ws/events` | No | Real-time event streaming endpoint |

---

## 5. Network Security & CORS Policy

1. **Cross-Origin Resource Sharing (CORS):**
   * Configured via FastAPI `CORSMiddleware`.
   * Restricts origins to trusted Vercel production domains and local development ports (`http://localhost:5173`, `http://localhost:3000`).
   * Wildcards (`*`) are strictly prohibited in production.
2. **Transport Security:**
   * HTTPS enforced on all REST endpoints.
   * WSS (WebSocket Secure over TLS) enforced for event streams.
3. **Database Security:**
   * Database credentials are injected solely via environment variables; never logged or serialized in error messages.
