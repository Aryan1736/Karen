# Karen's Ear — ML & NLP Pipeline Architecture

## 1. Document Identity
* **System:** Karen's Ear Emergency Intelligence System
* **Layer:** Layer 1 — Technical Architecture Specification (SOP)
* **Status:** PROPOSED & APPROVED FOR ARCHITECTURE
* **Authority:** Follows `gemini.md` (Project Constitution v1.1)

---

## 2. Pipeline Overview & Processing Flow

The ML/NLP pipeline transforms unstructured emergency dispatch text into a validated, typed, and normalized intelligence contract. It is designed to run entirely with open-source models on commodity CPU hardware without paid external APIs.

```text
Raw Text Input
      │
      ▼
[ Step 1: Preprocessing & Normalization ]
      │ (Whitespace normalization, casing preservation, noise reduction)
      ▼
[ Step 2: Multi-Task Feature & Entity Extraction ]
      ├── A. Incident Type Classification (Crisis category & hazard identification)
      ├── B. Urgency Inference (Life-safety heuristic + hazard velocity rules)
      ├── C. Information & NER Extraction (Locations, critical facilities, infrastructure)
      ├── D. People-at-Risk Extraction (Victim counts, trapped markers, casualty flags)
      └── E. Response Service Mapping (Medical, Fire, Search & Rescue, Police, Utility)
      │
      ▼
[ Step 3: Dense Semantic Embedding Generation ]
      │ (sentence-transformers/all-MiniLM-L6-v2 → 384-dimensional unit vector)
      ▼
[ Step 4: Confidence Calibration & Quality Checks ]
      │ (Check threshold < 0.60, validate field constraints, flag anomalies)
      ▼
[ Step 5: Canonical ML Output Packaging ]
      │ (Pydantic validation against canonical contract)
      ▼
Return ML Output Payload
```

---

## 3. Modular ML Component Specifications

### 3.1 Step 1: Text Preprocessing
* **Input:** Raw string (max 4,000 characters).
* **Operations:**
  * Unicode normalization (NFKC).
  * Stripping dangerous HTML/script tags or null bytes.
  * Preserving casing, punctuation, and exclamation marks (crucial signals for urgency and distress).
  * Handling multi-line formatting from SMS, transcripts, or radio dispatches.
* **Output:** Cleaned text string.

### 3.2 Step 2A: Incident Type Classification
* **Taxonomy:** Derived from humanitarian crisis informatics (`QCRI/HumAID` and `CrisiText` hazards):
  * `FLOOD_FLASH_FLOOD`
  * `FIRE_WILDFIRE_EXPLOSION`
  * `STRUCTURAL_COLLAPSE`
  * `EARTHQUAKE_LANDSLIDE`
  * `SEVERE_WEATHER_STORM`
  * `MEDICAL_EMERGENCY`
  * `CIVIL_UNREST_ACTIVE_THREAT`
  * `UTILITY_INFRASTRUCTURE_FAILURE`
  * `OTHER_GENERAL_INCIDENT`
* **Architecture:** Zero-shot or fine-tuned lightweight classifier (e.g. `DeBERTa-v3-small` / fast keyword-embedding hybrid).
* **Output Contract:**
  ```json
  "incident_type": {
    "label": "FLOOD_FLASH_FLOOD",
    "confidence": 0.94
  }
  ```

### 3.3 Step 2B: Operational Urgency Methodology
* **Core Constraint:** CrisiText does **NOT** provide categorical ground-truth urgency labels. Urgency is derived via a documented, deterministic feature-extraction rule system:
  1. **Life-Safety Indicators (Weight 50%):**
     * Presence of trapped persons, suffocating, drowning, bleeding, active screaming for help.
     * Detected distress phrases: *"under rubble"*, *"water rising fast"*, *"trapped on roof"*, *"people inside"*.
  2. **Hazard Velocity & Physical Threat (Weight 30%):**
     * Dynamic nature of hazard: active electrical wires in water, gas leak spreading, active structural cracking.
  3. **Vulnerability Modifiers (Weight 20%):**
     * Mention of sensitive sites: hospitals, nursing homes, schools, daycare centers, critical bridges.
* **Tier Mapping:**
  * `CRITICAL`: Active, imminent mortal threat or mass casualties ($Score \ge 80$).
  * `HIGH`: Major ongoing destruction, severe injury, high escalation potential ($60 \le Score < 80$).
  * `MEDIUM`: Localized damage, blocked roads, utility failures, no immediate life threat ($35 \le Score < 60$).
  * `LOW`: Informational advisories, minor weather updates, past recovery requests ($Score < 35$).
* **Output Contract:**
  ```json
  "urgency": {
    "label": "CRITICAL",
    "confidence": 0.88
  }
  ```

### 3.4 Step 2C: Information & Location Extraction
* **Location Extraction:**
  * Uses token classification (NER model or SpaCy `en_core_web_sm` / regex gazetteer matching).
  * Extracts exact location text snippet from dispatch (e.g., *"Rasulgarh flyover underpass"*).
  * **Strict No-Hallucination Policy:** If no exact coordinates are verified via controlled gazetteer lookup, `latitude` and `longitude` MUST remain `null`, and `precision` is tagged `"approximate"` or `"unknown"`.
* **Output Contract:**
  ```json
  "location": {
    "text": "Rasulgarh underpass",
    "latitude": 20.2961,
    "longitude": 85.8245,
    "precision": "approximate",
    "confidence": 0.82
  }
  ```

### 3.5 Step 2D: People-at-Risk Extraction
* **Logic:** Pattern extraction for cardinal numbers and victim entity references (e.g., *"3 children"*, *"family of 5"*, *"at least 20 passengers"*).
* **Strict No-Hallucination Policy:** Qualitative quantities (e.g., *"multiple people trapped"*, *"several injured"*) MUST NEVER be converted to an estimated numeric baseline (such as 2). Count strictly remains `null` with `confidence = null`, preserving qualitative risk signals (e.g., `MULTIPLE_PEOPLE`, `TRAPPED`) separately.
* Qualitative quantity != numeric quantity. Only explicit or contextually verified numeric counts are extracted into `count`.
* **Output Contract:**
  ```json
  "people_at_risk": {
    "count": 5,
    "confidence": 0.75
  }
  ```

### 3.6 Step 2E: Required Response Mapping
* **Services Extracted:** Multi-label identification of needed responder units:
  * `SEARCH_AND_RESCUE`
  * `MEDICAL_EMS`
  * `FIRE_HAZMAT`
  * `POLICE_SECURITY`
  * `PUBLIC_WORKS_UTILITY`
* **Output Contract:**
  ```json
  "required_response": [
    { "type": "SEARCH_AND_RESCUE", "confidence": 0.91 },
    { "type": "MEDICAL_EMS", "confidence": 0.85 }
  ]
  ```

### 3.7 Step 3: Dense Semantic Embedding Generation
* **Model:** `sentence-transformers/all-MiniLM-L6-v2`.
* **Dimension:** 384 floats.
* **Normalization:** Unit L2 norm ($\|v\|_2 = 1.0$), enabling cosine similarity computation via fast dot product:
  $$\text{Cosine Similarity}(u, v) = u \cdot v \quad (\in [-1.0, 1.0])$$
* **Model Loading:** Lazy loading on first inference; thread-safe process-level cache reuses loaded weights across calls and instances without reload latency.
* **Batch Support:** Native vectorized batch encoding with strict input order preservation and output shape $(N, 384)$.
* **Architectural Boundary & Responsibility:**
  * **ML Responsibility (Aryan):** Produces normalized 384-d vector embeddings and scalar semantic similarity signals. Provides representation and similarity only.
  * **Backend Responsibility (Daksh):** Fuses semantic similarity signals with spatial proximity (Haversine/gazetteer), temporal decay, and incident metadata to perform actual clustering, deduplication, and corroboration decisions.
  * **Strict Negative Invariants:** The embedding engine MUST NOT decide duplicate status, create incident IDs, merge reports, or assign backend priority/urgency.
* **Benchmark Baseline:** Phase 2 measured **9.68 ms** per text inference on local CPU.
* **Storage:** Embedding vectors are stored in memory or PostgreSQL array for fast incident correlation.

---

## 4. Confidence & Quality Calibration
1. **Component-Level Confidence:** Every extracted field carries an individual confidence score in $[0.0, 1.0]$.
2. **Overall Model Confidence:** Calculated as the weighted harmonic mean of component confidences.
3. **Threshold for Review (`NEEDS_REVIEW`):** If overall confidence $< 0.60$ or if critical conflicts are detected (e.g., urgency reported `CRITICAL` but text contains joke tokens), `processing_status` is set to `NEEDS_REVIEW`.
4. **Resilience Invariant:** The pipeline NEVER throws an uncaught exception that halts execution. If an extraction step fails, it emits `null` for that field, appends a descriptive item to `warnings`, and sets `processing_status = "PARTIAL"`.

---

## 5. Model Strategy & Independent Evolution
* The ML architecture decouples the embedding generator from the entity extractor and urgency model.
* **Aryan's Domain:** Aryan can independently swap or upgrade the embedding backbone (e.g., benchmarking `crisistransformers/CT-M1-Complete-SE` against `all-MiniLM-L6-v2`) without touching backend ingestion or database schemas, provided the output conforms to the canonical contract.
