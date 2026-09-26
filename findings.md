# Karen's Ear — Findings

## 1. CrisiText Dataset Deep Inspection
- **Source:** Hugging Face [`LanD-FBK/crisitext`](https://huggingface.co/datasets/LanD-FBK/crisitext)
- **Origin & Creators:** Language and Data (LanD) research unit, Fondazione Bruno Kessler (FBK), Italy. Published in *Findings of EACL 2026*.
- **License:** Creative Commons Attribution 4.0 International (`CC-BY-4.0`).
- **Scale:** ~400,000 warning messages across ~18,000 crisis situations.
- **Underlying Sources:** FEMA IPAWS (Integrated Public Alert and Warning System) Archived Alerts and Global Terrorism Database (GTD).
- **Exact Schema & Fields (from Croissant metadata):**
  - `scenario_id` (`string`): Unique scenario identifier.
  - `source` (`string`): Originating alert system (FEMA IPAWS / GTD).
  - `original_description` (`string`): Narrative of the crisis event.
  - `events` (`string`): Chronological chain of emergency events.
  - `messages` (`string`): 1 expert-aligned optimal warning + 3 suboptimal variants.
  - `original_eventid` (`float64`), `set`, `guidelines`, `split` (`train`/`validation`/`test`).
- **13 Crisis Scenarios Covered:**
  - *Natural Hazards:* Flood, hurricane, wildfire, earthquake, thunderstorm, landslide, tsunami.
  - *Human-induced Hazards:* Terrorism, armed attack, explosion, arson, active hazard.
- **Critical Architectural Finding & Urgency Methodology:**
  > **CrisiText is fundamentally an NLG warning message & crisis scenario dataset, NOT a token-level NER or categorical urgency classification dataset.**
  > - CrisiText does **NOT** provide ground-truth operational urgency labels (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
  > - **Methodology:** We will **not** claim to train an end-to-end urgency classifier directly on CrisiText. Instead, operational urgency will be derived through documented feature extraction rules:
  >   1. *Life-Safety Indicators:* Trapped persons, casualties, active distress tokens ("suffocating", "help", "under rubble").
  >   2. *Hazard Velocity & Destruction:* Nature of incident (active flash flood / structural collapse vs minor waterlogging / road blockage).
  >   3. *Vulnerability Indicators:* Impact on hospitals, schools, elder care centers.
  >   4. *Evaluation:* The mapping from features to urgency tiers will be benchmarked and evaluated separately on a curated validation set.
  > - CrisiText will be used for realistic crisis scenario modeling, synthetic simulation streaming, and clustering evaluation.

---

## 2. Crisis Classification & Domain NLP Resources
- **Resource:** [`QCRI/HumAID-all`](https://huggingface.co/datasets/QCRI/HumAID-all)
  - *Relevance:* Largest human-annotated crisis informatics benchmark (tens of thousands of disaster messages).
  - *Categories:* Infrastructure damage, injured or dead people, rescue volunteering, caution and advice, sympathy/emotional support.
  - *Role:* Reference taxonomy for humanitarian category classification.
- **Resource:** [`QCRI/CrisisBench-all-lang`](https://huggingface.co/datasets/QCRI/CrisisBench-all-lang)
  - *Relevance:* Consolidates CrisisLex (CrisisLexT6, CrisisLexT26) and CrisisNLP.
  - *Role:* Provides benchmark classification vocabularies and evaluation criteria.
- **Resource:** [`crisistransformers`](https://huggingface.co/crisistransformers)
  - *Relevance:* Specialized pre-trained language models and sentence encoders trained on 15+ billion tokens of crisis text.
  - *Models:* `crisistransformers/CT-M1-Complete-SE` and `crisistransformers/CT-M1-Mini`.
  - *Role:* Candidate embedding backbone for semantic similarity and duplicate detection.

---

## 3. Incident Correlation & Duplicate Detection Research
- **Dynamic Threshold Calibration Invariant:**
  - The cosine similarity threshold $\tau_{\text{dup}} \approx 0.85$ is strictly an **initial experimental baseline**, not a universal constant.
  - Locking a rigid threshold prematurely risks falsely merging separate, proximate incidents.
  - The deduplication and fusion engine must support configurable thresholds and be empirically tuned on real and simulated data during development.
- **Spatiotemporal Triangulation:**
  - Deduplication and fusion combine:
    1. **Semantic Textual Similarity:** Dense vector cosine similarity of message embeddings.
    2. **Temporal Window ($\Delta t$):** Time decay threshold (e.g. 2-4 hours).
    3. **Spatial Proximity:** Extracted location string matching or coordinate proximity.
- **Corroboration vs. Duplicate Suppression:**
  - Multiple identical tweets/reports from the same source or retweets represent *amplification/duplicates*, not *independent corroboration*.
  - True corroboration requires distinct sources/senders reporting consistent facts from proximate viewpoints.
  - *Mathematical Formula Target:*
    $$\text{Corroboration Score} = 1 - e^{-\lambda \cdot N_{\text{independent}}}$$
    where $N_{\text{independent}}$ saturates around 5-7 reports to prevent duplicate gaming.

---

## 4. Emergency Command Center Dashboard Patterns
- **Open-Source References Examined:**
  - **Aegis Incident Management System** ([GitHub](https://github.com/Panos1221/AegisIncidentManagement)): Map-centric incident logging and tactical responder coordination.
  - **CrisisKit Lite** ([GitHub](https://github.com/vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFLLR8VkRNWbZIKxkF3-R2XOXY9B_KQte2ub5oinA_xYCIOyaP9BY6UIB3Z7TM-ItOgRPuFZQrfshb5BRq6SjRRx1eXRHg_hqNS-xMlNJRPITN7YxLidb6Pyw==)): React/TypeScript crisis triage and geographic distribution.
  - **disaster-mgmt** ([GitHub](https://github.com/Gautam-2604/disaster-mgmt)): AI classification combined with Leaflet interactive mapping.
- **Key UX/UI Patterns Adopted for Karen's Ear:**
  - High-contrast, dark-mode command center optimized for high cognitive load environments.
  - Split-pane layout: Left pane = Live prioritized incident queue; Right pane = Interactive Leaflet map; Drawer modal = Deep incident inspection, raw reports, and human override controls.
  - Real-time reactivity via WebSockets/SSE with color-coded severity badges (`CRITICAL` in vivid amber-red, `HIGH` in orange, `MEDIUM` in gold, `LOW` in slate).
  - Clear visual indicator for `"is_synthetic": true` on simulated feeds.

---

## 5. Research Inventory & Attribution Table

| Resource Name | URL / Source | Relevance | What We Learn / Use | Classification |
|---|---|---|---|---|
| **LanD-FBK/crisitext** | [HuggingFace](https://huggingface.co/datasets/LanD-FBK/crisitext) | Primary crisis dataset | 13 crisis scenarios, event chains, warning message patterns | Evaluation & Simulation Resource |
| **QCRI HumAID** | [HuggingFace](https://huggingface.co/datasets/QCRI/HumAID-all) | Crisis tweet annotations | Humanitarian label taxonomy (injured, infrastructure, rescue) | Reference Taxonomy |
| **CrisisTransformers** | [HuggingFace](https://huggingface.co/crisistransformers) | Pre-trained crisis encoders | Dense sentence embeddings for crisis domain | Reference / Candidate Model |
| **Sentence-Transformers** | `all-MiniLM-L6-v2` | General lightweight embedder | Small memory footprint candidate for CPU inference | Candidate Embedding Model |
| **Aegis Incident Mgmt** | [GitHub](https://github.com/Panos1221/AegisIncidentManagement) | Disaster command center UI | Map-based incident tracking, operator workflow | Reference Architecture |
| **Leaflet & OSM** | [Leafletjs.com](https://leafletjs.com/) | Client-side map engine | Zero-cost, keyless tile mapping for disaster points | Core Frontend Dependency |

---

## 6. Runtime Resource Profiling & Technical Trade-offs
1. **Model Memory Footprint & Inference Latency on Render:**
   - Resource claims such as $<500$MB RAM and low CPU latency are **targets to benchmark and profile**, not guaranteed constants.
   - Render's actual performance will depend on the instance type and concurrent workload.
   - Aryan and Pankaj will profile memory usage and inference latency during Phase 2 (Link) to confirm viability.
2. **Geocoding Without External Paid APIs:**
   - How to geocode location strings without external API costs or hallucination?
   - *Mitigation:* Implement a curated gazetteer / dictionary of relevant disaster hotspots (or bounding-box centroid matching) and default to `latitude: null, longitude: null, precision: "approximate"` when unverified.

---

## 7. Phase 2: Link Verification & Connectivity Findings

1. **Environment & Runtime Verification:**
   - **Python:** `3.13.5` (64-bit Windows), with `pip` and active virtual environment capabilities.
   - **Node.js:** `v22.19.0`, **npm:** `10.9.3`. Ready for modern React/Vite frontend tooling.
   - **Git Remote:** `origin -> https://github.com/Aryan1736/Karen.git` reachable and synchronized on branch `main`.
   - **Project Memory:** All 4 core documents (`gemini.md`, `task_plan.md`, `findings.md`, `progress.md`) verified and preserved.
   - **Secrets Discipline:** Created `.env.example` with safe placeholder tokens and added `.env`, `node_modules`, and `.tmp/` to root `.gitignore`.

2. **CrisiText Dataset Access (`LanD-FBK/crisitext`):**
   - Verified unauthenticated public access via Hugging Face Hub using the `datasets` streaming API (`load_dataset("LanD-FBK/crisitext", split="train", streaming=True)`).
   - Zero API key required for exploration and inference testing.
   - Verified available splits: `['train', 'validation', 'test']`.
   - Verified 8 record attributes: `['set', 'guidelines', 'scenario_id', 'source', 'original_description', 'events', 'messages', 'original_eventid']`.
   - Sample `train-0` originates from FEMA IPAWS alert archives (`source: FEMA`).

3. **ML Runtime & Performance Benchmarking:**
   - **Model Tested:** `sentence-transformers/all-MiniLM-L6-v2`.
   - **Dependency Delivery Discovery:** Standard PyPI wheel download for PyTorch on this network was severely throttled (~15-30 kB/s). Resolved by fetching CPU wheels directly via Cloudflare R2 mirror index (`https://download.pytorch.org/whl/cpu`), completing the 124 MB download in ~45 seconds (~2.7 MB/s).
   - **Cold Load Time:** Model loaded and initialized in **8,564 ms** (first-run CPU cold start).
   - **Measured Local CPU Inference Latency:** **9.68 ms** per text report (verified on sample emergency text: *"Heavy flash flooding near Rasulgarh square, multiple vehicles trapped in underpass"*).
   - **Output Dimensionality:** Verified **384-dimensional dense vector**, with unit L2 norm ($1.0$).
   - **Takeaway:** Low-latency CPU inference is completely viable locally for real-time deduplication and similarity scoring.

4. **PostgreSQL Connectivity:**
   - Local service `postgresql-x64-18` active on `localhost:5432`.
   - Connection string configured securely in `.env` as `postgresql://postgres:****@localhost:5432/postgres`.
   - Discovered that an external system environment variable `DATABASE_URL` was initially pointing to an inactive local port; resolved by enforcing `load_dotenv(override=True)` in Python tooling.
   - Minimal query handshake (`SELECT 1`) executed successfully. PostgreSQL Server Version verified: **18.3**.

5. **OpenStreetMap Connectivity:**
   - Verified network accessibility:
     - `https://www.openstreetmap.org` returned HTTP 200.
     - `https://tile.openstreetmap.org/0/0/0.png` returned HTTP 200 with standard image/png payload.
   - Zero API key required for client-side Leaflet tile rendering under Standard Tile Usage Policy.

6. **Deployment Platform Compatibility (Vercel & Render):**
   - **Vercel (Frontend Target):** Node.js `v22.19.0` and npm `10.9.3` verified locally. The planned React/Vite/Tailwind client architecture adheres strictly to Vercel's zero-config static/SPA deployment model.
   - **Render (Backend, ML, PostgreSQL Target):** Python 3.13 is fully supported by Render's native Python runtime for Web Services and Background Workers. Application state will be persisted in Render PostgreSQL via `DATABASE_URL` without local filesystem coupling.

---

## 8. Phase 3: Architectural Discoveries & Structural Formulations

1. **3-Layer Architecture Boundary Enforcement:**
   - **Layer 1 (Architecture SOPs):** 17 dedicated specifications established in `architecture/`. All mathematical formulas, database schemas, API envelopes, and fallback policies are codified in documentation before any implementation code.
   - **Layer 2 (Navigation):** Explicit state machine defined in `architecture/navigation.md` routing data from `REPORT_RECEIVED` through ML analysis, fusion, prioritization, and WebSocket dispatch.
   - **Layer 3 (Tools):** Reusable deterministic tools in `tools/` with scratch/ephemeral storage in `.tmp/` (gitignored).

2. **Decoupled Urgency & Probabilistic-Deterministic Split:**
   - Verified that separating probabilistic NLP predictions (`ml_predictions`) from deterministic operational state (`incidents`) solves the critical explainability requirement of disaster triage.
   - Documented that CrisiText serves scenario modeling and simulation, while operational urgency is derived via life-safety feature heuristics.

3. **Dynamic Thresholding & Corroboration Math:**
   - Triangulation combines dense semantic cosine similarity ($w_1=0.55$), temporal half-life decay ($w_2=0.20$), and spatial proximity ($w_3=0.25$).
   - Saturated corroboration formulation ($1 - e^{-0.45 \cdot N}$) prevents viral re-tweets or bot amplification from gaming emergency priority queues.
   - Similarity thresholds ($\tau_{\text{dup}} \approx 0.85$, $\tau_{\text{corrob}} \approx 0.70$) remain fully configurable via environment variables.

4. **Real-Time Transport Decision:**
   - Native FastAPI WebSockets (`/ws/events`) selected as the primary event stream for sub-50ms reactive queue reordering.
   - Implemented automatic client-side fallback to periodic HTTP polling (`GET /incidents` every 5s) if WebSocket transport drops.

5. **Human-in-the-Loop Audit Invariant:**
   - Every human modification writes an append-only audit record to `audit_logs` requiring operator identity and non-empty justification.
   - The underlying raw ML prediction remains completely untouched for retrospective evaluation.
