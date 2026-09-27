# Phase 7 — Real System Scorecard

## 1. Provenance
- **branch**: `feature/evaluation-integration`
- **HEAD**: `312a3f1`
- **evidence sources**:
  - Phase 2: REAL_ML (commit 91ff2ca)
  - Phase 3: REAL_CORRELATION (commit 00426e1)
  - Phase 5: REAL_E2E (commit 2455889)
  - Phase 6: SURGE_AND_RESILIENCE (commit 312a3f1)
- **overall score formula**: NONE_DEFINED (no authoritative formula in project requirements; zero invented overall scores)
- **invented thresholds**: NO

## 2. Direct REAL_ML
**Execution Scope:** `DIRECT_IN_PROCESS_INFERENCE` | **Real System Result:** `True`
**Evidence Source:** Phase 2 Audited Benchmark (real_ml_evaluation_scorecard.md / commit 91ff2ca)

| Metric | Observed Value | Operational Notes |
| :--- | :---: | :--- |
| Coverage Rate | 100.00% | Full JSON schema adherence (27/27) |
| Incident Type Accuracy | 55.56% | 15/27 exact disaster category matches |
| Incident Type Macro F1 | 0.6105 | Unweighted macro across 9 categories |
| Urgency MAE | 0.4815 | Discrete urgency level distance |
| High Urgency Recall | 87.50% | 7/8 HIGH/CRITICAL urgencies identified |
| Report Critical Recall | 25.00% | 1/4 strict CRITICAL reports recognized directly |
| Hard-Negative LOW Rejection | 100.00% | Tested on 10/10 non-crisis reports only |
| People-at-Risk Recall | 75.00% | 3/4 casualty events flagged |
| Coordinate Hallucination Rate | 0.00% | Zero spurious coordinates fabricated |

## 3. Persisted REAL_E2E ML
**Execution Scope:** `LIVE_HTTP_POSTGRES_WEBSOCKET` | **Real System Result:** `True`
**Evidence Source:** Phase 5 PostgreSQL karen_e2e run p5e2e-run1 (commit 2455889)

| Metric | Observed Value | Scope |
| :--- | :---: | :--- |
| Persisted Predictions Count | 27/27 | PostgreSQL `ml_predictions` table |
| Persisted Hazard Macro F1 | 0.5343 | Full pipeline persisted classifications |
| Persisted Urgency Accuracy | 59.26% | 16/27 exact urgency matches |
| Persisted Casualty Count MAE | 0.0000 | Zero error on stored casualty estimates |
| Persisted Location Precision Accuracy | 92.59% | 25/27 stored location precision matches |
| Embedding Contract Compliance | 27/27 valid 384-dimensional float embeddings persisted | 384-dimensional dense vectors |
| Synthetic Partition Violations | 0 | Zero leakage into non-synthetic storage |

## 4. Clustering
**Execution Scope:** `LIVE_HTTP_POSTGRES_WEBSOCKET` | **Evidence Source:** Phase 5 PostgreSQL karen_e2e run p5e2e-run1 (commit 2455889)
- **TP**: 78
- **FP**: 28
- **FN**: 0
- **TN**: 245
- **precision**: 0.7358
- **recall**: 1.0000
- **F1**: 0.8478
- **Rand**: 0.9202
- **interpretation**: Observed over-fusion under the current correlation and source-identity behavior: 2 hard-negative reports (rep-hn-001, rep-hn-006) were absorbed into the focal flood incident, and 1 hard-negative report (rep-hn-004) was fused with standalone flood distractor rep-fld-015 in a separate two-report incident (3 hard-negative reports over-fused in total).
*(Diagnostic comparison — Phase 3 In-Process Engine: Precision 1.0000, Recall 0.3077, F1 0.4706, Rand 0.8462)*

## 5. Relationship Classification
**Execution Scope:** `LIVE_HTTP_POSTGRES_WEBSOCKET` | **Evidence Source:** Phase 5 PostgreSQL karen_e2e run p5e2e-run1 (commit 2455889)
### Duplicate
- **precision**: 0.1667
- **recall**: 1.0000
- **F1**: 0.2858

### Corroborating
- **precision**: 1.0000
- **recall**: 0.4286
- **F1**: 0.6000

- **interpretation**: Duplicate classification produced substantial false positives on this benchmark (precision 0.1667, 10 false positives; all 2 expected duplicates detected). Corroborating predictions were completely precise when emitted (precision 1.0000, 0 false positives), but recall was conservative (0.4286, 3 of 7 true corroborations detected).

## 6. Priority / Triage
**Execution Scope:** `LIVE_HTTP_POSTGRES_WEBSOCKET` | **Evidence Source:** Phase 5 PostgreSQL karen_e2e run p5e2e-run1 (commit 2455889)
- **focal score**: 85.35
- **level**: CRITICAL
- **critical threshold**: >= 80.0
- **critical recall**: 1.0000
- **meaningful ranking**: false
- **Spearman**: NOT_EVALUATED
- **interpretation**: 1/1 true critical incident group reached CRITICAL in this benchmark: the focal multi-report disaster successfully escalated to 85.35 (CRITICAL >= 80.0), achieving 100% critical recall for the life-safety emergency. Multi-incident ranking is NOT EVALUATED because the benchmark contains only 1 true multi-report emergency.

## 7. Live Reliability
- **Phase 5 HTTP**: 27/27 (201 Created, 0 transport errors)
- **Phase 5 WS**: 27/27 valid envelopes (0 malformed, 0 unknown IDs)
- **Phase 6 surge**: 40/40 (201 Created, 0 retries, 0 dropped, 0 circuit opens)
- **persistence consistency**: Observed persistence consistency checks passed for all 27 Phase-5 benchmark reports: zero missing reports, zero orphan links, and zero synthetic partition violations.

## 8. Resilience
- **422**: Permanent client error -> 0 retries, 0 buffering, 0 DB mutation
- **429**: Retry-After (0.1s) header honored, throttled backoff, retry HTTP 201
- **5xx**: Transient 503 succeeds after retry; persistent 500 cleanly buffers into EventBuffer upon retry exhaustion
- **circuit breaker**: CLOSED -> OPEN (at 5 failures) -> HALF_OPEN (after recovery timeout) -> CLOSED (after 2 probe successes); failure in HALF_OPEN returns immediately to OPEN
- **FIFO**: Exact FIFO sequence preserved across buffering and flush
- **overflow**: Raises BufferOverflowError at capacity + 1; zero silent dropping
- **backend interruption**: 3 outage reports attempted, 3 buffered, 3 recovered, 0 lost, 0 duplicate persistence
- **DB outage**: NOT TESTED — SHARED INFRASTRUCTURE SAFETY

## 9. Latency
### Cold
- **First inference initialization (container SentenceTransformer)**: 19.03 s
- **Direct ML cold load (in-process weights load)**: 15211.80 ms

### Direct ML
- **Warm count**: 26
- **Warm min**: 20.75 ms
- **Warm mean**: 25.08 ms
- **Warm p50**: 23.42 ms
- **Warm p95**: 39.85 ms
- **Warm max**: 41.21 ms

### REAL_E2E
- **Warm p50**: 50.43 ms
- **Warm p95**: 67.25 ms
- **Warm max**: 111.80 ms

### Surge
- **First surge request**: 139.12 ms
- **Warm count**: 39
- **Warm min**: 47.99 ms
- **Warm mean**: 54.06 ms
- **Warm p50**: 51.75 ms
- **Warm p95**: 78.45 ms
- **Warm max**: 82.60 ms
- **Measured throughput**: 19.55 reports/sec

## 10. Known Limitations
- 1. Hard-negative over-fusion: 3 non-crisis reports were over-fused under the current correlation and source-identity behavior (2 absorbed into the focal flood incident, 1 fused with standalone distractor rep-fld-015).
- 2. Duplicate false positives: duplicate classification produced substantial false positives on this benchmark (precision 0.1667).
- 3. Low corroborating recall: corroborating recall is 0.4286 (3 of 7 true corroborations detected).
- 4. Only one true multi-report emergency exists in the golden corpus, so multi-incident ranking is not meaningfully evaluated (Spearman rho NOT_EVALUATED).
- 5. Database outage was not tested to ensure shared-infrastructure PostgreSQL safety.
- 6. Cold first inference was approximately 19 seconds in the tested environment. Integration clients need timeout headroom above observed cold-start latency; the benchmark harness used a larger timeout.
- 7. Benchmark datasets are small synthetic golden scenarios (27 reports); results are empirical, not universal guarantees.
- 8. Source fallback (source='simulator') can influence duplicate classification for anonymous synthetic dispatches.

## 11. NOT_EVALUATED
- Multi-incident priority ranking (only 1 multi-report cluster; Spearman rho uninformative)
- Database outage / network partition recovery (omitted to protect shared PostgreSQL daemon)
- High-concurrency parallel ingestion (SafeHttpTransport evaluated sequential burst up to 19.55 req/s)
- Multi-lingual or audio/image modality reports (text-only English dispatch evaluated)
- Long-term historical correlation drift across days/weeks
