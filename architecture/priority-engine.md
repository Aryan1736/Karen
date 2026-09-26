# Karen's Ear — Deterministic Priority Engine Architecture

## 1. Document Identity
* **System:** Karen's Ear Emergency Intelligence System
* **Layer:** Layer 1 — Technical Architecture Specification (SOP)
* **Status:** PROPOSED & APPROVED FOR ARCHITECTURE
* **Authority:** Follows `gemini.md` (Project Constitution v1.1)

---

## 2. Core Architectural Invariant
> **The Priority Engine is strictly deterministic. It is NOT an LLM and does NOT use probabilistic generative models to score emergencies.**

Why this invariant exists:
1. **Explainability:** An incident dispatcher must know *exactly* why an incident ranked #1 versus #4.
2. **Predictability:** Given the exact same set of reports, the system will *always* calculate the exact same score.
3. **Auditability:** In post-incident regulatory reviews, every factor contribution can be legally traced and audited.

---

## 3. Priority Pipeline Architecture

```text
ML Predictions + Incident State + Corroboration Metrics
                        │
                        ▼
           [ Step 1: Input Validation & Bounds Check ]
                        │
                        ▼
           [ Step 2: Factor Extraction & Normalization ]
     (Maps raw data into standardized [0.0, 100.0] factor scores)
                        │
                        ▼
           [ Step 3: Weighted Multi-Factor Calculation ]
   Priority = Σ (Weight_i × Factor_i) + State Modifiers - Penalties
                        │
                        ▼
           [ Step 4: Level Mapping & Threshold Clamping ]
       Score clamped to [0.0, 100.0] → CRITICAL / HIGH / MEDIUM / LOW
                        │
                        ▼
           [ Step 5: Explainability String Generation ]
   (Deconstructs formula into plain-language bullet points for UI)
                        │
                        ▼
           [ Step 6: Human Override Layer Check ]
   (If active human override exists, override takes precedence)
                        │
                        ▼
           Return Canonical Priority Payload
```

---

## 4. Factor Specification & Normalization Rules

Every factor score ($S_i$) is normalized strictly to $[0.0, 100.0]$.

### 4.1 Factor 1: Operational Urgency ($S_{\text{urgency}}$)
Derived from the extracted urgency classification:
* `CRITICAL`: $100.0$
* `HIGH`: $75.0$
* `MEDIUM`: $40.0$
* `LOW`: $15.0$
* `null` / Unknown: $30.0$ (Default neutral with review flag)

### 4.2 Factor 2: People at Risk ($S_{\text{risk}}$)
Derived from extracted victim counts and life-safety markers:
* Specific count verified:
  $$S_{\text{risk}} = \min(100.0, 40.0 + 12.0 \times \text{count})$$
  *(e.g., 1 person $\implies 52$, 3 people $\implies 76$, 5+ people $\implies 100$)*
* Ambiguous trapped/casualty mention without exact count: $70.0$
* No indication of people at risk: $10.0$

### 4.3 Factor 3: Corroboration & Verification ($S_{\text{corrob}}$)
Calculated from independent source saturation:
$$S_{\text{corrob}} = 100.0 \times \left(1.0 - \exp(-0.45 \times N_{\text{independent}})\right)$$
* 1 report: $36.0$
* 2 independent witnesses: $59.0$
* 3 independent witnesses: $74.0$
* 5+ independent witnesses: $90.0 - 100.0$

### 4.4 Factor 4: Hazard Severity & Type ($S_{\text{hazard}}$)
Derived from the incident classification:
* `STRUCTURAL_COLLAPSE`: $100.0$
* `FIRE_WILDFIRE_EXPLOSION`: $90.0$
* `FLOOD_FLASH_FLOOD`: $85.0$
* `CIVIL_UNREST_ACTIVE_THREAT`: $80.0$
* `EARTHQUAKE_LANDSLIDE`: $75.0$
* `MEDICAL_EMERGENCY`: $70.0$
* `UTILITY_INFRASTRUCTURE_FAILURE`: $45.0$
* `OTHER_GENERAL_INCIDENT`: $25.0$

---

## 5. Mathematical Scoring Formulation & Configurable Weights

$$\text{Raw Priority} = w_1 S_{\text{urgency}} + w_2 S_{\text{risk}} + w_3 S_{\text{corrob}} + w_4 S_{\text{hazard}}$$

### 5.1 Baseline Weight Configuration (v1.0 Baseline)
* $w_1 = 0.35$ (Urgency)
* $w_2 = 0.30$ (People at Risk)
* $w_3 = 0.20$ (Corroboration)
* $w_4 = 0.15$ (Hazard Type)
$$\sum w_i = 1.00$$

*Weights are externalized in backend configuration to allow tuning during evaluation:*
```python
PRIORITY_WEIGHT_URGENCY = float(os.getenv("PRIORITY_WEIGHT_URGENCY", "0.35"))
PRIORITY_WEIGHT_RISK = float(os.getenv("PRIORITY_WEIGHT_RISK", "0.30"))
PRIORITY_WEIGHT_CORROB = float(os.getenv("PRIORITY_WEIGHT_CORROB", "0.20"))
PRIORITY_WEIGHT_HAZARD = float(os.getenv("PRIORITY_WEIGHT_HAZARD", "0.15"))
```

### 5.2 Dynamic Modifiers
* **Low Confidence Penalty:** If average ML extraction confidence $< 0.50$, apply a $-10.0$ dampening penalty to prevent false alarms from dominating the top queue, and route incident to `NEEDS_REVIEW`.
* **State Modifiers:**
  * `ESCALATED`: $+15.0$ surge boost.
  * `VERIFIED` by Human Operator: $+10.0$ certainty boost.
  * `RESOLVED`: Forced to $0.0$ (cleared from active dispatch).

---

## 6. Priority Level Thresholds

The resulting clamped score $[0.0, 100.0]$ maps to operator priority tiers:

| Priority Score Range | Level | Color Code (UI) | Expected Dispatch SLA |
| :--- | :--- | :--- | :--- |
| **80.0 – 100.0** | `CRITICAL` | Bright Red (`#EF4444`) | Immediate operator response (< 60s) |
| **60.0 – 79.9** | `HIGH` | Vibrant Orange (`#F97316`) | Fast response (< 5 mins) |
| **35.0 – 59.9** | `MEDIUM` | Amber Gold (`#F59E0B`) | Standard triage queue |
| **0.0 – 34.9** | `LOW` | Slate Blue (`#64748B`) | Informational / backlog |

---

## 7. Explainability & Output Contract

Every calculation produces a human-readable factor breakdown matching the approved `gemini.md` contract:

```json
{
  "incident_id": "inc-9831a2",
  "priority_score": 84.5,
  "priority_level": "CRITICAL",
  "factors": [
    {
      "factor": "Urgency (Life-Safety)",
      "value": "CRITICAL",
      "weight": 0.35,
      "contribution": 35.0
    },
    {
      "factor": "People at Risk",
      "value": "4 trapped persons",
      "weight": 0.30,
      "contribution": 26.4
    },
    {
      "factor": "Corroboration",
      "value": "3 independent reports",
      "weight": 0.20,
      "contribution": 14.8
    },
    {
      "factor": "Hazard Type",
      "value": "FLOOD_FLASH_FLOOD",
      "weight": 0.15,
      "contribution": 12.75
    }
  ],
  "explanation": "Elevated to CRITICAL priority due to confirmed trapped persons (4 reported) under active flash flood conditions corroborated by 3 distinct eyewitness dispatches.",
  "calculation_version": "v1.0-deterministic"
}
```
