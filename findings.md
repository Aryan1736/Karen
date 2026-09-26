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
