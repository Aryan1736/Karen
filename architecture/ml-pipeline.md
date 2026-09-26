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
1. **Component-Level Confidence:** Every extracted field carries an individual proxy confidence score strictly bounded in $[0.0, 1.0]$. Unextracted, undetermined, or non-applicable fields emit `null`; the engine strictly prohibits fabricating default or fallback confidence scores.
2. **Overall Model Confidence (Weighted Harmonic Mean):**
   Overall ML confidence is aggregated across active confidence-bearing components $S$ via a weighted harmonic mean:
   $$C_{\text{overall}} = \frac{\sum_{i \in S} w_i}{\sum_{i \in S} \frac{w_i}{c_i}}$$
   where $c_i \in (0.0, 1.0]$ and $w_i > 0$.
3. **Component Weights Specification & Provisional Policy:**
   * **Architectural Gap Notice:** While earlier architecture specified a weighted harmonic mean for overall confidence, the exact component weights were *not* previously defined in repository ADRs, contracts, or schemas.
   * **Provisional Baseline Policy (Feature 9):** To ensure deterministic, operational triage, the pipeline establishes a documented provisional baseline:
     * `incident_type` ($w = 0.30$): Primary hazard category classification.
     * `urgency` ($w = 0.25$): Operational life-safety criticality tier.
     * `location` ($w = 0.20$): Physical spatial grounding.
     * `people_at_risk` ($w = 0.15$): Direct human life-threat count certainty.
     * `required_response` ($w = 0.10$): Tactical capability routing.
   * **Configurability:** All weights are externalized in `MLConfig` and environment variables (`CONFIDENCE_WEIGHT_<COMPONENT>`) and can be overridden programmatically without altering engine logic.
4. **Zero, Null, and Embedding Semantics:**
   * **Zero Confidence ($c_i = 0.0$):** In accordance with the mathematical limit $\lim_{c_i \to 0^+} H = 0.0$, if any active component has confidence 0.0, overall confidence collapses strictly to `0.0` without division-by-zero error, and triggers `NEEDS_REVIEW`.
   * **Null / Missing Components:** If a component is absent or not applicable (e.g. no location mentioned), it is cleanly excluded from $S$; it does not penalize overall confidence to 0.0, nor does it fabricate 1.0.
   * **Embeddings (Feature 8):** Dense semantic vectors have no intrinsic confidence score. They are explicitly excluded from the harmonic mean aggregation.
5. **Deterministic Status Resolution Precedence:**
   * **1. `FAILED`:** All inference components failed or zero meaningful inferences occurred.
   * **2. `NEEDS_REVIEW`:** Overall confidence $< 0.60$ (or explicit critical conflict flag, e.g., hoax tokens). Requires human dispatcher review.
   * **3. `PARTIAL`:** One or more components failed extraction, but remaining evidence achieves overall confidence $\ge 0.60$. Usable intelligence is preserved.
   * **4. `SUCCESS`:** All components executed without failure and overall confidence $\ge 0.60$.
6. **Decoupling Invariants & Calibration Scope:**
   * **ML Confidence $\ne$ Backend Priority:** Overall ML confidence measures evidence reliability, NOT incident importance or priority score (ADR-004).
   * **Urgency Confidence $\ne$ Urgency Score:** Urgency confidence reflects feature extraction certainty, not severity points (Feature 7).
   * **Proxy Confidence $\ne$ Calibrated Probability:** Scores reflect engineering quality aggregation over correlated text evidence; they are not claimed as statistical posterior probabilities.
7. **Resilience Invariant:** The pipeline NEVER throws an uncaught exception that halts execution. If an extraction step fails, it emits `null` for that field, appends descriptive diagnostics to `warnings`, and degrades gracefully according to the deterministic precedence hierarchy.

---

## 5. Model Strategy & Independent Evolution
* The ML architecture decouples the embedding generator from the entity extractor and urgency model.
* **Aryan's Domain:** Aryan can independently swap or upgrade the embedding backbone (e.g., benchmarking `crisistransformers/CT-M1-Complete-SE` against `all-MiniLM-L6-v2`) without touching backend ingestion or database schemas, provided the output conforms to the canonical contract.

---

## 6. Unified Inference Pipeline Orchestration (Feature 10)

### 6.1 Public Entry Point
The unified ML pipeline provides exactly ONE canonical public orchestration entry point:
```python
from ml.pipeline import inference_engine

result = inference_engine.analyze(report, report_id="...", location_hint=...)
```
Or equivalently via instance instantiation:
```python
from ml.pipeline import InferenceEngine

engine = InferenceEngine()
result = engine.analyze(report, report_id="...", location_hint=...)
```

### 6.2 Sequential Stage Order
Execution proceeds in fixed, deterministic order:
1. **Preprocessing (`TextCleaner`):** Unicode normalization, sanitization, length validation.
2. **Incident Classification (`IncidentClassifier`):** Crisis hazard categorization (`predict`).
3. **Entity Extraction (`LocationEntityExtractor` & `PeopleRiskExtractor`):** Verbatim location phrasing, victim counts, and named entity tokens.
4. **Required Response Mapping (`RequiredResponseExtractor`):** Tactical agency capability routing.
5. **Operational Urgency (`UrgencyEngine`):** Life-safety, hazard velocity, and vulnerability scoring.
6. **Dense Semantic Embedding (`SentenceTransformerEmbedder`):** 384-dimensional unit vector generation.
7. **Confidence Calibration & Quality Gating (`ConfidenceEngine`):** Weighted harmonic mean confidence and deterministic operational status resolution.
8. **Final Assembly & Canonical Sorting:** Merges entities and response needs with deterministic ordering; deduplicates warnings.
9. **Final Schema Validation Gate (`SchemaValidator`):** Validates final output against `ml/schemas/incident_output.json`.

### 6.3 Fail-Fast vs. Fail-Soft Policy
* **Fail-Fast Stages:**
  * **Input Validation & Preprocessing:** If input is not a string/dict/context, or contains empty/whitespace-only text, raises `MLInputError` immediately. Downstream components cannot proceed without valid text.
  * **Final Schema Validation:** If the assembled ML output violates `ml/schemas/incident_output.json`, raises `MLSchemaValidationError`. Malformed payloads are never returned to callers.
* **Fail-Soft Stages (Recoverable Component Failures):**
  * Failure in any individual inference component (`classification`, `location`, `people_at_risk`, `required_response`, `urgency`, `embeddings`, or `confidence_engine`) is isolated via exception containment.
  * Recoverable failures set the component's output to null/empty, append diagnostic warnings, and degrade `processing_status` to `PARTIAL` or `NEEDS_REVIEW` according to Feature 9 precedence rules.
  * Complete failure of all inference components degrades strictly to `FAILED`.

### 6.4 Embedding Reference & Coordinate Policies
* **Embedding Reference:** The canonical output provides `"embedding_reference": "emb-{report_id}"` on successful embedding generation. If embedding fails or is absent, `"embedding_reference"` is strictly `null` (never fabricated). The raw 384-dimensional vector is omitted from the canonical contract by default and only included if explicitly requested (`include_embedding=True`).
* **Coordinates (ADR-009):** `latitude` and `longitude` are strictly `null` unless verified via controlled gazetteer lookup. The pipeline never invents or hallucinates coordinates.

