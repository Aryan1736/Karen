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

---

## 9. Integration & Evaluation Findings (Pankaj)

### 9.1 [CONTRACT CLARIFICATION REQUIRED] LocationHint Coordinates vs. Precision Invariant
- **Exact Conflict:**
  - `docs/data-schema.md` Section 1, Rule 4 states:
    > *"If an exact location cannot be verified, latitude and longitude MUST be null. Never guess GPS coordinates. Raw text is preserved verbatim with precision = 'approximate' or 'unknown'."*
  - Conversely, `docs/api-contract.md` Section 3 (`POST /reports` example body) specifies:
    ```json
    "location_hint": {
      "raw_text": "Rasulgarh underpass",
      "latitude": 20.2961,
      "longitude": 85.8245,
      "precision": "approximate"
    }
    ```
- **File & Section References:**
  - `docs/data-schema.md#L24-L26`
  - `docs/api-contract.md#L79-L84`
- **Current Simulator Implementation (Conservative Dual-Contract Resolution):**
  - Cross-field validation in `LocationHint` enforces:
    1. Coordinate pair completeness: `latitude` and `longitude` must either BOTH be present or BOTH be null.
    2. Precision `"unknown"` strictly requires `latitude=None` and `longitude=None`.
    3. Precision `"exact"` strictly requires non-null coordinates for both latitude and longitude.
    4. Precision `"approximate"` permits either both coordinates present (conforming to `docs/api-contract.md` centroid hints) or both null (conforming to `docs/data-schema.md` unverified raw text).
    5. Geodetic bounds: Latitude $[-90.0, 90.0]$, Longitude $[-180.0, 180.0]$.
  - Zero coordinate fabrication: Simulator never invents coordinates for unlocated reports.
- **Recommended Team Resolution:**
  - The team should formally ratify whether approximate geocoding allows centroid coordinates (with precision `"approximate"`) or if non-null coordinates are strictly reserved for `"exact"`.

### 9.2 Deep Repair, Hardening & Truthful Evaluation Audit (Pass 2)
1. **Recursive Ground-Truth Firewall:**
   - Centralized `verify_no_ground_truth_leakage()` in `simulator/models.py` recursively audits any arbitrary payload depth, list elements, and extra metadata keys.
   - Forbids all private ground-truth fields (`expected_urgency`, `incident_group`, `relation_type`, `expected_direction`, `expected_people_count`, and all `expected_*` keys).
   - Applied at model instantiation (`ScenarioEvent.public_payload()`), before transport dispatch (`prepare_payload()`), and during engine playback.

2. **Scenario Synthetic Hygiene:**
   - Scanned all scenarios (`flood_rasulgarh.py`, `mixed_hard_negatives.py`) and eliminated all real telephone numbers (`+91-94370-...`, `+91-98610-...`, `+91-70081-...`).
   - Replaced with strictly synthetic caller handles: `sim-caller-001`, `sim-caller-002`, `sim-caller-003`, `sim-source-001`.
   - Converted all string direction labels (`MODERATE_INCREASE`, `LOW_PRIORITY`) to the typed `ExpectedQueueDirection` enum.

3. **Transport Resilience & Zero Data Loss:**
   - Unified engine-transport interface around `BaseTransport.send_event(event: ScenarioEvent)`.
   - `EventBuffer`: Implemented explicit `BufferOverflowError` when exceeding `max_capacity` (refusing to silently drop emergency reports).
   - `flush_buffer()`: Partial dispatch failure at index $i$ preserves all unsent events from $i$ onward in strict FIFO order.

4. **Canonical ML Output Parsing (`ml/schemas/incident_output.json`):**
   - Implemented `MLPredictionAdapter` in `evaluation/evaluate_ml.py` to parse Aryan's nested schema (`incident_type.label`, `urgency.label`, `location.text`, `people_at_risk.count`, `required_response`).
   - Handles both canonical nested format and legacy test fixtures.
   - Enforces coverage auditing: malformed or unparseable predictions increment `invalid_predictions` and penalize `coverage_rate`.

5. **Spearman's Rho Rank Tie Calibration:**
   - Naive $1 - \frac{6 \sum d^2}{n(n^2 - 1)}$ formula produces distorted values when ties occur (common in discrete disaster urgency queues).
   - Replaced with standard average-rank assignment (`rankdata`) and Pearson rank correlation in `evaluation/metrics.py`.

6. **Tri-State Assertions & Strict Rank #1 Tie-Breaking:**
   - Replaced naive booleans with `AssertionResult` (`PASS`, `FAIL`, `NOT_EVALUATED`).
   - If a scenario does not test an assertion (e.g. trapped van corroboration in hard negatives), it evaluates to `NOT_EVALUATED` rather than falsely passing.
   - Strict Rank #1 tie semantics: When multiple incidents tie for highest priority, `strict_rank_1_no_ties=True` requires a strictly higher score to earn `PASS`.

7. **Zero Fabricated Metrics Policy:**
### 9.3 Extreme Adversarial Audit & Release Certification Pass (Pass 3)
1. **Python 3.14 PEP 649 Deferred Annotation Reflection Fix:**
   - `simulator/cli.py` used `Optional[List[str]]` without importing `Optional`. Under standard runtime in Python 3.14, PEP 649 deferred annotation evaluation masked the missing import. However, runtime reflection (`typing.get_type_hints(simulator.cli.main)`) or pytest collection in Python <= 3.13 immediately raised `NameError: name 'Optional' is not defined`.
   - *Resolution:* Added `from __future__ import annotations` and explicit imports `from typing import Optional, List, Dict, Any` across all simulator and evaluation modules.

2. **Rankdata NaN Infinite Loop Resolution:**
   - In `evaluation/metrics.py`, `rankdata()` tested ties via `a[sorted_indices[j]] == a[sorted_indices[i]]`. When `a[i]` was `float('nan')`, `nan == nan` evaluated to `False`. Thus `j` never advanced, causing `i = j` to deadlock the `while i < n` loop indefinitely.
   - *Resolution:* Implemented safe tie-checking `_is_rank_equal()` handling `math.isnan()` symmetrically and sorting NaNs cleanly to the end of the ranking vector.

3. **HTTP 422 Poison Pill Buffer Lockup Prevention:**
   - `SafeHttpTransport` previously treated 422 Unprocessable Entity as a retry exhaustion failure, tripping the circuit breaker and buffering the unprocessable payload. This permanently deadlocked `flush_buffer()` on every retry.
   - *Resolution:* Classified 400, 401, 403, 404, and 422 as permanent client errors that immediately fail without tripping the circuit breaker and without entering the FIFO buffer.

4. **Haversine Floating-Point Domain Clamping:**
   - Floating-point imprecision when calculating great-circle distance between antipodal coordinates could yield `a > 1.0` (e.g. `1.0000000000000002`), causing `math.sqrt(1.0 - a)` to crash with `ValueError: math domain error`.
   - *Resolution:* Clamped `a = max(0.0, min(1.0, a))` and `c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))`.

5. **Monotonic Maximum Urgency Incident Aggregation:**
   - In `evaluate_correlation_engine()`, earlier implementations allowed subsequent lower-urgency reports for the same incident group to overwrite a previous `HIGH` urgency with `LOW`.
   - *Resolution:* Enforced monotonic maximum severity tracking (`LOW < MEDIUM < HIGH < CRITICAL`).

6. **Strict Directionality for Corroboration Assertions:**
   - Changed corroboration boost assertion from `>=` to strictly greater `>` (`max(corrob_scores) > max(initial_scores)`). Corroborating independent eyewitnesses must actively escalate priority.
   - Enforced duplicate suppression invariant: duplicate retweets must not escalate priority above corroboration (`max(dup_scores) <= max(corrob_scores)`).

7. **Social Media Handle Hygiene:**
   - Replaced remaining `@citizen` handle in `simulator/scenarios/flood_rasulgarh.py:298` with synthetic handle `@sim_eyewitness_bbsr`.

8. **Casualty & People-at-Risk Profiling:**
   - Added `PeopleAtRiskEvaluationReport` and `compute_people_at_risk_metrics()` to `evaluation/metrics.py`, evaluating life-safety binary accuracy, risk recall, and casualty count MAE.

9. **Release Packaging & Cold-Import Verification Gate:**
   - Packaged source into clean `simulator.zip` (SHA256: `2dbb5d2fc2ffdc5fcb8791e95770dfb557129e14357b9d171083210aa98190ad`).
   - Verified in clean isolated extraction `.tmp/clean_package_test/` with fresh subprocess cold imports and pytest (105/105 passed in 2.11s).

### 9.4 Forensic Autonomous Repair & Self-Correcting Quality Loop Pass (Pass 4)
1. **Allowlist Egress Projection (`ScenarioEvent.public_payload`):**
   - *Reviewer Alpha Finding:* `ReportMetadata`'s `extra="allow"` permitted arbitrary un-blocklisted evaluator keys to pass across the public wire if not explicitly starting with `expected_`.
   - *Resolution:* Added `ALLOWED_PUBLIC_METADATA_KEYS` filtering at egress projection in `ScenarioEvent.public_payload()`. Only approved operational keys (`scenario_id`, `event_id`, `reporter_id`, `caller_id`, `channel`, `phase`, `batch_index`) survive projection. Verified with adversarial fuzzing.
2. **Handle Hygiene in Stored Fixtures:**
   - *Reviewer Alpha Finding:* Stored fixture `evaluation/fixtures/golden_scenarios.json` still contained `@citizen` from an earlier export pass.
   - *Resolution:* Regenerated `golden_scenarios.json` directly from hardened scenario loaders, ensuring zero non-synthetic handles across the entire codebase and all fixtures.
3. **Async Event Loop Offloading:**
   - *Reviewer Beta Finding:* `send_event_async` had a redundant second definition that called synchronous `send_event` directly on the event loop, potentially blocking async loops during rate-limit sleeps.
   - *Resolution:* Removed the duplicate definition, ensuring `await asyncio.to_thread(self.send_event, event)` is the active implementation.
4. **Statistical Rigor & Hand-Calculated Confusion Matrix:**
   - *Reviewer Gamma Finding:* Baseline tests relied on symmetric mock predictions rather than an explicit hand-calculated confusion matrix asserting exact known precision, recall, and macro F1 formulas.
   - *Resolution:* Added `test_hand_calculated_3x3_confusion_matrix_and_metrics()` in `simulator/tests/test_evaluation.py` asserting an exact 3x3 table with hand-calculated values (Macro Precision = 0.5000, Macro Recall = 0.5000, Macro F1 = 0.4905).
5. **Anti-Leakage Attack Vector Verification:**
   - Added `test_anti_leakage_adversarial_vectors()` in `simulator/tests/test_adversarial_hardening.py` covering all 6 leakage vectors from Section 9 (string conversion, JSON serialization, egress allowlisting, metadata injection, recursive structure nesting, and obfuscated/normalized tokens).
6. **External Dependency Blocker Truthfulness:**
   - Documented that real live end-to-end integration is currently `BLOCKED / UNAVAILABLE` because Daksh's backend directory (`backend/`) does not yet exist on this branch. Pankaj's transport layer and evaluation harness are fully verified against mock HTTP servers and ready for immediate deployment when the backend service is delivered.




