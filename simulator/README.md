# Karen's Ear — Crisis Simulator & Evaluation Engine

**Lead Engineer:** Pankaj (Integration, Simulation & Evaluation Lead)  
**Branch:** `feature/evaluation-integration`  
**Authorities:** `gemini.md` (v1.2), `docs/data-schema.md` (v1.0), `docs/api-contract.md` (v1.0), `DISASTER_SIMULATOR_ROADMAP.md`  

---

## 1. Overview & Architectural Role

The Disaster Simulator and Evaluation Engine serves two non-negotiable architectural mandates within Karen's Ear:

```
        ┌────────────────────────────────────────────────────────┐
        │                 Pankaj Test Harness                    │
        │  [Private Ground Truth]       [Evaluation Engine]      │
        └──────────────┬────────────────────────▲────────────────┘
                       │ Safe Public Projection │ Scores & Metrics
                       │ (GroundTruth Stripped) │ (Predictions vs GT)
                       ▼                        │
        ┌────────────────────────────────────────────────────────┐
        │                 Karen's Ear System                     │
        │   POST /reports ──► Aryan (ML) ──► Daksh (Correlation) │
        └────────────────────────────────────────────────────────┘
```

1. **Controlled Crisis Ingestion (Simulator):**
   - Feeds safe, synthetic, timestamped dispatches into Karen's Ear (`POST /reports`).
   - Replays deterministic multi-phase disaster scenarios with configurable speeds, seeds, and jitter.
   - Enforces the **Zero-Leakage Invariant**: Private evaluator ground truth is hermetically isolated and can never cross the network boundary.

2. **Truthful Quantitative Verification (Evaluation):**
   - Benchmarks Aryan's ML model against ground-truth labels (incident type classification, urgency tier, victim count, location extraction).
   - Benchmarks Daksh's correlation engine against ground-truth clustering (pairwise Rand Index, duplicate vs. corroborating detection, priority queue rank #1 escalation).
   - Generates reproducible Markdown and JSON benchmark scorecards with clear provenance tracking (`HARNESS_SELF_TEST`, `MOCK_FIXTURE`, or `REAL_ML`).

---

## 2. Directory Structure

```
simulator/
├── __init__.py               # Simulator package root
├── models.py                 # Pydantic v2 core models, ground-truth schema & recursive firewall
├── timeline.py               # Deterministic event timeline sequencer & time compression
├── transport.py              # Circuit breaker, token bucket rate limiter, FIFO buffer
├── engine.py                 # Multi-state playback engine (IDLE, RUNNING, PAUSED, COMPLETED, STOPPED)
├── cli.py                    # Production CLI interface (--scenario, --speed, --live, --endpoint, etc.)
├── scenarios/                # Golden crisis scenarios
│   ├── __init__.py           # Scenario registry and loader
│   ├── flood_rasulgarh.py    # Flagship 15-event Bhubaneswar flash flood scenario
│   └── mixed_hard_negatives.py # 12-event hard negative and multi-hazard distractor scenario
└── tests/                    # 107 hermetic unit, integration, and adversarial tests
    ├── test_adversarial_hardening.py
    ├── test_evaluation.py
    ├── test_hardened_eval_and_transport.py
    ├── test_live_http_integration.py
    ├── test_scenarios.py
    ├── test_simulator_models.py
    ├── test_timeline_engine.py
    └── test_transport.py

evaluation/
├── __init__.py               # Evaluation package root (PEP 562 lazy exports)
├── metrics.py                # Mathematical scoring metrics (Classification, Recall, Correlation, Latency)
├── evaluate_ml.py            # ML prediction adapter & evaluation runner
├── evaluate_correlation.py   # Incident correlation & clustering evaluation runner
├── run_all_evals.py          # Unified CLI benchmark runner & scorecard generator
└── fixtures/                 # Golden evaluation fixtures (golden_scenarios.json)
```

---

## 3. Ground-Truth Firewall Guarantees

Private evaluator ground truth contains situation cluster IDs, expected urgency tiers, true victim counts, and expected queue movements. To prevent data contamination:

- **Structural Isolation:** `ScenarioEvent` pairs a public `RawReportPayload` with a private `GroundTruth` object.
- **Allowlist Projection:** `ScenarioEvent.public_payload()` projects only explicitly allowlisted metadata fields (`scenario_id`, `event_id`, `reporter_id`, `caller_id`, `channel`, `phase`, `batch_index`). Arbitrary extra fields are dropped.
- **Recursive Audit:** `verify_no_ground_truth_leakage()` traverses all nested dictionaries, lists, sets, and primitives. Any key matching forbidden terms, normalized tokens, or starting with `expected_` immediately raises `GroundTruthLeakageError`.
- **Pre-Flight Invariants:** Prior to wire transmission, `prepare_payload()` asserts:
  - `is_synthetic == True`
  - `source == 'simulator'`
  - Full recursive firewall validation passes.

---

## 4. CLI Reference & Execution Modes

The simulator CLI is executed via `python -m simulator.cli`.

```bash
# General Syntax
python -m simulator.cli [OPTIONS]
```

### Options:

| Flag | Type | Default | Description |
|---|---|---|---|
| `--scenario` | string | `flood_rasulgarh` | Scenario ID to execute (`flood_rasulgarh`, `mixed_hard_negatives`). |
| `--list-scenarios` | flag | `False` | Lists all registered scenarios and exits. |
| `--speed` | float | `1.0` | Playback speed multiplier (e.g. `10.0` = 10x real-time; `0` = burst mode). |
| `--step` | flag | `False` | Interactive step mode: prompts operator on enter before injecting each dispatch. |
| `--live` | flag | `False` | Enables live HTTP transmission over the network. Default is dry-run mode. |
| `--dry-run` | flag | `True` | Hermetic dry-run mode: dispatches to local in-memory sink without network calls. |
| `--endpoint` | string | `http://localhost:8000/reports` | Target ingestion URL for `POST /reports`. |
| `--seed` | int | `None` | Deterministic random seed for reproducible timeline jitter. |
| `--jitter` | float | `0.0` | Maximum relative timing jitter fraction (e.g. `0.1` = ±10%). |
| `--export-public` | path | `None` | Path to export public `RawReportPayload` JSON dispatches. |
| `--export-ground-truth`| path | `None` | Path to export complete scenario events with private ground truth. |
| `--quiet` | flag | `False` | Suppresses verbose console logs during simulation. |

---

## 5. Evaluation Harness & Metrics

The evaluation harness evaluates both components independently or together via `python -m evaluation.run_all_evals`.

```bash
# Run hermetic self-test benchmark
python -m evaluation.run_all_evals --output-dir .tmp/benchmark_results

# Run benchmark with external ML and Backend results
python -m evaluation.run_all_evals \
  --output-dir .tmp/benchmark_results \
  --ml-predictions path/to/aryan_predictions.json \
  --backend-results path/to/daksh_incidents.json \
  --latency-results path/to/latencies.json
```

### Metric Definitions & Life-Safety Truthfulness:

1. **Dual Critical Recall:**
   - `report_critical_recall`: Recall of individual critical reports.
   - `incident_critical_recall`: Recall of fused situations containing critical reports.
   - *Truthful Zero-Denominator Policy:* If zero critical reports exist in test data, critical recall returns `None` (`NOT_EVALUATED`), **never** a misleading 1.0 (100%).
2. **Spearman's Rank Correlation ($\rho$):**
   - Measures monotonic alignment between predicted priority scores and ground-truth urgency tiers.
   - Handled with average-rank tie resolution; NaN and Inf safe (prevents infinite ranking loops).
3. **Pairwise Clustering Accuracy:**
   - Pairwise Precision, Recall, and F1 over $\binom{N}{2}$ event pairs to evaluate cluster purity without label assignment bias.
4. **People at Risk Evaluation:**
   - Evaluates binary life-safety danger detection accuracy alongside Mean Absolute Error (MAE) on casualty counts.
5. **Latency Profiling:**
   - Computes P50, P95, and mean round-trip latency in milliseconds. Marked `is_measured: false` when running offline to prevent fake performance claims.

---

## 6. Deterministic Demo Walkthrough

Follow these verified steps for a live or dry-run presentation:

### Step 1: Pre-Flight Verification & Dry Run
Execute the flagship Bhubaneswar flood scenario at 10x speed locally:
```powershell
python -m simulator.cli --scenario flood_rasulgarh --speed 10 --dry-run
```
*Expected Output:* 15 dispatches processed cleanly with zero network errors.

### Step 2: Ground-Truth Isolation Verification
Verify programmatically that ground truth cannot leak to public egress:
```powershell
python -c "from simulator.scenarios.flood_rasulgarh import get_flood_rasulgarh_events; ev = get_flood_rasulgarh_events()[2]; print('Public payload keys:', list(ev.public_payload().keys()))"
```
*Expected Output:* `['report_id', 'text', 'source', 'is_synthetic', 'reported_at', 'location_hint', 'metadata']` (Zero evaluator keys).

### Step 3: Run Full Benchmark Suite
Generate the standardized evaluation scorecard:
```powershell
python -m evaluation.run_all_evals --output-dir .tmp/demo_eval
```
*Outputs Created:*
- `.tmp/demo_eval/evaluation_scorecard.json`
- `.tmp/demo_eval/evaluation_scorecard.md`

### Step 4: Live Ingestion (When Backend is Running)
When Daksh's backend service is deployed and listening at `http://localhost:8000`:
```powershell
python -m simulator.cli --scenario flood_rasulgarh --speed 1.0 --live --endpoint http://localhost:8000/reports
```

---

## 7. Known External Dependencies & Limitations

1. **Backend Integration Status:**
   - Real end-to-end HTTP integration is currently **BLOCKED / UNAVAILABLE** because the backend service directory (`backend/`) does not yet exist in the repository on this branch.
   - All HTTP transport resilience features (circuit breaking, 422 bypass, 429 backoff, rate limiting, FIFO buffer recovery) are fully verified and passing against local mock HTTP servers in `simulator/tests/test_live_http_integration.py`.
2. **ML Schema Alignment:**
   - `MLPredictionAdapter` supports Aryan's nested schema (`ml/schemas/incident_output.json`). Real ML evaluations will execute once inference endpoints or prediction files are generated.
