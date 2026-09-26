# Karen's Ear — Testing & Evaluation Architecture

## 1. Document Identity
* **System:** Karen's Ear Emergency Intelligence System
* **Layer:** Layer 1 — Technical Architecture Specification (SOP)
* **Status:** PROPOSED & APPROVED FOR ARCHITECTURE
* **Authority:** Follows `gemini.md` (Project Constitution v1.1)

---

## 2. Multi-Level Testing Pyramid

Karen's Ear implements a comprehensive verification pyramid to guarantee that life-safety recommendations are deterministic, mathematically verified, and reproducible.

```text
               ┌────────────────────────┐
               │    ML & Heuristic      │
               │      Evaluation        │ (Metrics: F1, Precision/Recall, Latency)
               ├────────────────────────┤
               │   End-to-End (E2E)     │
               │   Crisis Simulation    │ (Bursts of 50+ dispatches, cluster accuracy)
               ├────────────────────────┤
               │   Integration Tests    │
               │  (FastAPI + DB + WS)   │ (Report ingestion → Fusion → DB persistence)
               ├────────────────────────┤
               │ Component & Unit Tests │
               │ (Scorer, Rules, Pyd.)  │ (Priority math, JSON validation, string NER)
               └────────────────────────┘
```

---

## 3. ML & Heuristic Evaluation Architecture
> **CRITICAL INVARIANT: The ML pipeline must NEVER be evaluated solely by whether the frontend "looks nice" or displays mock cards.**

Quantitative evaluation is owned by Pankaj and Aryan, targeting distinct operational dimensions:

### 3.1 Dimension 1: Semantic Embedding & Duplicate Detection
* **Dataset / Evaluation Set:** Paired crisis dispatches from `LanD-FBK/crisitext` and `HumAID`.
* **Metrics:**
  * Area Under the ROC Curve (ROC-AUC) for pairwise duplicate detection.
  * Precision @ Threshold $\tau_{\text{dup}} = 0.85$ (Must minimize false merges: Precision $> 0.90$).
  * Recall @ Threshold $\tau_{\text{corrob}} = 0.70$ (Must capture true corroborations: Recall $> 0.80$).

### 3.2 Dimension 2: Feature-Derived Urgency Calibration
* **Evaluation Target:** Validate that feature extraction rules accurately partition severe crises from low-priority dispatches.
* **Test Fixture:** Curated benchmark of 50 multi-hazard text dispatches with annotated ground truth.
* **Confusion Matrix Evaluation:**
  * Zero tolerance for `CRITICAL` ground-truth incidents being categorized as `LOW` (False Negative Rate for life-safety threats must be $0\%$).

### 3.3 Dimension 3: Information & Location Extraction Precision
* **Metric:** Token-level and entity-level precision/recall for extracted location text and victim counts.
* **Hallucination Rate:** Must be strictly **$0.0\%$**. If location text is absent, extracted coordinates must be `null`.

### 3.4 Dimension 4: Latency & Resource Benchmarks
* Single-item CPU inference latency must remain $< 30\text{ ms}$ (Phase 2 measured **$9.68\text{ ms}$**).
* Peak RAM consumption during batch processing must remain within Render Starter limits ($< 800\text{ MB}$).

---

## 4. Integration & Deterministic Priority Testing

Integration tests verify the contract boundaries without external cloud dependencies:

1. **Ingestion & Persistence Test:**
   * Ingest sample raw report $\to$ Assert written to `raw_reports` with correct timestamp.
2. **Incident Fusion Test:**
   * Ingest Report A (flood at Patia) $\to$ Spawns Incident 1.
   * Ingest Report B (identical wording, different phone) $\to$ Asserts fused into Incident 1 with `relationship_type = "DUPLICATE"`, `independent_source_count = 1`.
   * Ingest Report C (different wording, same coordinates) $\to$ Asserts fused with `relationship_type = "CORROBORATING"`, `independent_source_count = 2`.
3. **Deterministic Priority Math Invariance Test:**
   * Given fixed input vectors:
     $$\text{Urgency: CRITICAL (100)}, \quad \text{Risk: 3 trapped (76)}, \quad \text{Corrob: 2 (59)}, \quad \text{Hazard: Flood (85)}$$
     Assert calculated priority score equals:
     $$(0.35 \times 100) + (0.30 \times 76) + (0.20 \times 59) + (0.15 \times 85) = 35 + 22.8 + 11.8 + 12.75 = 82.35$$
     Assert mapped level is strictly `CRITICAL`.
4. **Human Override Audit Test:**
   * Apply override to incident $\to$ Assert `audit_logs` record created, `incidents.human_override.active == true`, and original `ml_predictions` record remains unchanged.

---

## 5. Automated Verification Tooling Strategy

During Phase 3 and Phase 4, deterministic verification is executed via Python test scripts in `tools/`:
* `tools/check_links.py`: Master connectivity handshake (Phase 2).
* `tools/test_priority_math.py`: Pure unit verification of priority formulas and factor weights.
* `tools/test_fusion_logic.py`: Verification of dynamic thresholding and corroboration logic.
* `tools/evaluate_ml_benchmark.py`: Quantitative metrics across CrisiText evaluation subsets.
