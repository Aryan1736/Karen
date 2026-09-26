# Karen's Ear — Incident Correlation & Deduplication Architecture

## 1. Document Identity
* **System:** Karen's Ear Emergency Intelligence System
* **Layer:** Layer 1 — Technical Architecture Specification (SOP)
* **Status:** PROPOSED & APPROVED FOR ARCHITECTURE
* **Authority:** Follows `gemini.md` (Project Constitution v1.1)

---

## 2. Conceptual Overview & Objectives

In crisis scenarios, hundreds of incoming reports may refer to the same physical event. Some are duplicate retweets, some are updates from the same caller, while others are independent eyewitness reports that corroborate the severity of the disaster.

The Incident Correlation Engine must:
1. **Cluster Related Reports:** Group dispatches describing the same physical crisis into a single living **Incident**.
2. **Distinguish Duplicates from Corroborations:** Avoid gaming where identical spammed messages falsely inflate incident credibility.
3. **Preserve Dynamic Thresholding:** Maintain configurable similarity thresholds that can be calibrated empirically against real crisis data.

---

## 3. The Triangulation Pipeline

Incident correlation uses **three-dimensional evidence triangulation**:

```text
Incoming Report (Vector v_new, Time t_new, Location L_new, Source S_new)
                          │
                          ▼
            [ Filter Active Candidate Incidents ]
      (Incidents in state ACTIVE / NEEDS_REVIEW within time window Δt)
                          │
                          ▼
             [ Triangulation Scoring Engine ]
      ┌───────────────────┼───────────────────┐
      ▼                   ▼                   ▼
1. Semantic Text      2. Temporal         3. Spatial
   Similarity            Proximity           Proximity
   (Cosine dot prod)     (Time decay)        (Gazetteer / Geo)
      │                   │                   │
      └───────────────────┼───────────────────┘
                          │
                          ▼
        Composite Correlation Score (C_score)
                          │
            ┌─────────────┴─────────────┐
            ▼                           ▼
  C_score >= Threshold?       C_score < Threshold?
            │                           │
           YES                          NO
            │                           │
            ▼                           ▼
[ Fuse into Existing Incident ]  [ Spawn New Incident ]
  - Classify relationship:          - Set status = "ACTIVE"
    DUPLICATE vs CORROBORATING      - Initialize source_report_ids
  - Update corroboration metrics    - Set base priority
  - Trigger priority re-calculation
```

---

## 4. Evidence Dimensions & Mathematical Formulation

### 4.1 Dimension 1: Dense Semantic Similarity ($S_{\text{sem}}$)
Calculated using the normalized 384-dimensional embeddings:
$$S_{\text{sem}} = \frac{v_{\text{report}} \cdot v_{\text{incident}}}{\|v_{\text{report}}\|_2 \|v_{\text{incident}}\|_2} = v_{\text{report}} \cdot v_{\text{incident}} \quad (\in [-1.0, 1.0])$$

### 4.2 Dimension 2: Temporal Proximity ($S_{\text{temp}}$)
Emergency events have a finite duration. Reports hours apart for the same location may represent distinct events or aftermath:
$$\Delta t = |t_{\text{report}} - t_{\text{incident\_last\_active}}|$$
$$S_{\text{temp}} = \exp\left(-\frac{\Delta t}{\tau_{\text{decay}}}\right)$$
* Where $\tau_{\text{decay}}$ is the half-life window (configurable baseline: 3 hours).
* If $\Delta t > 6$ hours, $S_{\text{temp}} \to 0$.

### 4.3 Dimension 3: Spatial Proximity ($S_{\text{spatial}}$)
* **Case A: Both entities have coordinates:**
  $$d = \text{HaversineDistance}(L_{\text{report}}, L_{\text{incident}})$$
  $$S_{\text{spatial}} = \max\left(0, 1.0 - \frac{d}{d_{\text{max}}}\right)$$
  Where $d_{\text{max}}$ is the geographic cluster radius (e.g., 2.5 km for urban flooding, 10 km for regional storm).
* **Case B: Textual locations only:**
  * Exact landmark match (e.g., *"Patia square"* = *"Patia square"*): $S_{\text{spatial}} = 0.90$.
  * Partial substring match: $S_{\text{spatial}} = 0.60$.
  * Both unknown: $S_{\text{spatial}} = 0.50$ (neutral, relies strictly on semantics).
  * Explicitly conflicting locations (e.g. *"Bhubaneswar"* vs *"Cuttack"*): $S_{\text{spatial}} = 0.0$ (hard veto against fusion).

### 4.4 Composite Score ($C_{\text{score}}$)
$$C_{\text{score}} = w_1 S_{\text{sem}} + w_2 S_{\text{temp}} + w_3 S_{\text{spatial}}$$
* Baseline weights: $w_1 = 0.55$, $w_2 = 0.20$, $w_3 = 0.25$.

---

## 5. Dynamic Thresholding Invariant

* **Experimental Baseline:** $\tau_{\text{dup}} \approx 0.85$ is the starting candidate.
* **Prohibition Against Hard-Coding:** Code MUST NOT hard-code `0.85`.
* **Configurable Parameter:**
  ```python
  DUPLICATE_SIMILARITY_THRESHOLD = float(os.getenv("DUPLICATE_SIMILARITY_THRESHOLD", "0.85"))
  CORROBORATION_SIMILARITY_THRESHOLD = float(os.getenv("CORROBORATION_SIMILARITY_THRESHOLD", "0.70"))
  ```
* **Separation of Tiers:**
  * $C_{\text{score}} \ge \tau_{\text{dup}}$: Candidate for **Duplicate / Amplification**.
  * $\tau_{\text{corrob}} \le C_{\text{score}} < \tau_{\text{dup}}$: Candidate for **Corroboration / Related Incident Report**.
  * $C_{\text{score}} < \tau_{\text{corrob}}$: **Distinct Incident**.

---

## 6. Duplicate vs. Independent Corroboration

A critical vulnerability of naive incident aggregators is treating bot amplification or repeated retweets as independent confirmation.

### 6.1 Definitions & Relationship Classification
Every fused report-to-incident link (`incident_reports`) is assigned an explicit `relationship_type`:

| Relationship Type | Definition | Impact on Corroboration |
| :--- | :--- | :--- |
| `DUPLICATE` | Identical or near-verbatim text from same or indeterminate sender; echo/re-transmission. | Adds to `report_count`, **0** increase to `independent_source_count`. |
| `CORROBORATING` | Distinct source reporting consistent facts from the scene (different vantage point, new detail). | Adds to `report_count`, **+1** to `independent_source_count`. |
| `RELATED` | Mentions the incident or secondary effect (e.g., traffic jam caused by flood), but not direct hazard confirmation. | Stored in incident history; minimal corroboration weight. |
| `UNCERTAIN` | High semantic match but contradictory location/time. | Fused with warning flag; sends incident to `NEEDS_REVIEW`. |

### 6.2 Independence Rules
To qualify as `CORROBORATING`, the report must satisfy:
1. Distinct `source_id` / telephone / IP / author handle from previous reports.
2. Formatted variation indicating human re-phrasing rather than programmatic retweets.
3. Reasonable temporal sequence.

### 6.3 Corroboration Score Formulation
To prevent endless score inflation during high-volume events, the corroboration score is bounded using an asymptotic saturating curve:
$$\text{Corroboration Score} = 1.0 - \exp(-\lambda \cdot N_{\text{independent}})$$
* With $\lambda = 0.45$:
  * $N = 1$ source $\implies Score = 0.36$
  * $N = 2$ sources $\implies Score = 0.59$
  * $N = 3$ sources $\implies Score = 0.74$
  * $N = 5$ sources $\implies Score = 0.89$
  * $N \ge 7$ sources $\implies Score \approx 0.96 \to 1.0$ (Saturated)
* This guarantees that a single viral incident cannot monopolize 100% of the triage queue simply because 500 people tweeted about it.
