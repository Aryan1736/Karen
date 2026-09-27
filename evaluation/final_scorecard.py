"""
Karen's Ear — Phase 7 Master Real Scorecard Aggregator.

Owner: Pankaj (feature/evaluation-integration)
Authority: gemini.md (v1.2), docs/data-schema.md, docs/api-contract.md, DISASTER_SIMULATOR_ROADMAP.md
Status: Production-Certified Final Benchmark Consolidation

This module consolidates verified metrics across:
1. Phase 2: Direct REAL_ML Inference (commit 91ff2ca)
2. Phase 3: In-Process REAL_CORRELATION & Priority Replay (commit 00426e1)
3. Phase 5: Live REAL_E2E (commit 2455889)
4. Phase 6: Live Surge & System Resilience Fault Injection (commit 312a3f1)

Strict Rules:
- No silent re-execution of models or live services.
- Truthful reporting of provenances (is_real_system_result, execution_scope).
- Complete preservation of NOT_EVALUATED for ranking lacking multi-incident samples.
- Zero invented overall scores or unverified pass/fail thresholds.
- Comprehensive known limitations and empirical scope boundaries.
- Purely descriptive characterization of clustering and duplicate classification.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class DirectMLMetrics:
    """Direct ML inference evaluation metrics (Phase 2: In-Process InferenceEngine)."""
    execution_scope: str = "DIRECT_IN_PROCESS_INFERENCE"
    is_real_system_result: bool = True
    evidence_source: str = "Phase 2 Audited Benchmark (real_ml_evaluation_scorecard.md / commit 91ff2ca)"
    total_samples: int = 27
    coverage_rate: float = 1.0000
    incident_type_accuracy: float = 0.5556
    incident_type_macro_f1: float = 0.6105
    urgency_mae: float = 0.4815
    high_urgency_recall: float = 0.8750
    report_critical_recall: float = 0.2500
    hard_negative_low_rejection_rate: float = 1.0000
    hard_negative_tested: int = 10
    hard_negative_rejected: int = 10
    people_risk_recall: float = 0.7500
    coordinate_hallucination_rate: float = 0.0000
    cold_latency_ms: float = 15211.80
    warm_count: int = 26
    warm_min_ms: float = 20.75
    warm_mean_ms: float = 25.08
    warm_p50_ms: float = 23.42
    warm_p95_ms: float = 39.85
    warm_max_ms: float = 41.21


@dataclass(frozen=True)
class PersistedE2EMLMetrics:
    """PostgreSQL-persisted ML evaluation metrics (Phase 5: Full Ingestion Pipeline)."""
    execution_scope: str = "LIVE_HTTP_POSTGRES_WEBSOCKET"
    is_real_system_result: bool = True
    evidence_source: str = "Phase 5 PostgreSQL karen_e2e run p5e2e-run1 (commit 2455889)"
    total_samples: int = 27
    persisted_predictions_count: int = 27
    hazard_macro_f1: float = 0.5343
    urgency_accuracy: float = 0.5926
    casualty_count_mae: float = 0.0000
    location_precision_accuracy: float = 0.9259
    embedding_dimension: int = 384
    embedding_contract_status: str = "27/27 valid 384-dimensional float embeddings persisted"
    synthetic_partition_violations: int = 0


@dataclass(frozen=True)
class ClusteringEvaluationMetrics:
    """Pairwise incident clustering metrics (Phase 5 Persisted REAL_E2E Primary)."""
    execution_scope: str = "LIVE_HTTP_POSTGRES_WEBSOCKET"
    is_real_system_result: bool = True
    evidence_source: str = "Phase 5 PostgreSQL karen_e2e run p5e2e-run1 (commit 2455889)"
    tp: int = 78
    fp: int = 28
    fn: int = 0
    tn: int = 245
    precision: float = 0.7358
    recall: float = 1.0000
    f1: float = 0.8478
    rand_index: float = 0.9202
    total_over_fused_hard_negatives: int = 3
    focal_absorbed_hard_negative_ids: List[str] = field(
        default_factory=lambda: ["rep-hn-001", "rep-hn-006"]
    )
    distractor_fused_hard_negative_ids: List[str] = field(
        default_factory=lambda: ["rep-hn-004"]
    )
    distractor_paired_report_id: str = "rep-fld-015"
    interpretation: str = (
        "Observed over-fusion under the current correlation and source-identity behavior: "
        "2 hard-negative reports (rep-hn-001, rep-hn-006) were absorbed into the focal flood incident, "
        "and 1 hard-negative report (rep-hn-004) was fused with standalone flood distractor rep-fld-015 "
        "in a separate two-report incident (3 hard-negative reports over-fused in total)."
    )
    diagnostic_in_process_comparison: Dict[str, Any] = field(
        default_factory=lambda: {
            "execution_scope": "IN_PROCESS_ENGINE_REPLAY",
            "pairwise_precision": 1.0000,
            "pairwise_recall": 0.3077,
            "pairwise_f1": 0.4706,
            "rand_index": 0.8462,
        }
    )


@dataclass(frozen=True)
class RelationshipClassificationMetrics:
    """Duplicate and corroborating edge classification metrics (Phase 5 Persisted REAL_E2E)."""
    execution_scope: str = "LIVE_HTTP_POSTGRES_WEBSOCKET"
    is_real_system_result: bool = True
    evidence_source: str = "Phase 5 PostgreSQL karen_e2e run p5e2e-run1 (commit 2455889)"
    duplicate_precision: float = 0.1667
    duplicate_recall: float = 1.0000
    duplicate_f1: float = 0.2858
    duplicate_tp: int = 2
    duplicate_fp: int = 10
    duplicate_fn: int = 0
    duplicate_tn: int = 15
    corroborating_precision: float = 1.0000
    corroborating_recall: float = 0.4286
    corroborating_f1: float = 0.6000
    corroborating_tp: int = 3
    corroborating_fp: int = 0
    corroborating_fn: int = 4
    corroborating_tn: int = 20
    interpretation: str = (
        "Duplicate classification produced substantial false positives on this benchmark "
        "(precision 0.1667, 10 false positives; all 2 expected duplicates detected). "
        "Corroborating predictions were completely precise when emitted (precision 1.0000, 0 false positives), "
        "but recall was conservative (0.4286, 3 of 7 true corroborations detected)."
    )


@dataclass(frozen=True)
class PriorityTriageMetrics:
    """Triage and priority escalation evaluation metrics (Phase 5 Persisted REAL_E2E)."""
    execution_scope: str = "LIVE_HTTP_POSTGRES_WEBSOCKET"
    is_real_system_result: bool = True
    evidence_source: str = "Phase 5 PostgreSQL karen_e2e run p5e2e-run1 (commit 2455889)"
    focal_score: float = 85.35
    focal_level: str = "CRITICAL"
    backend_critical_threshold: float = 80.0
    true_critical_groups: int = 1
    incident_critical_recall: float = 1.0000
    meaningful_ranking_sample: bool = False
    spearman_rank_correlation: Optional[float] = None
    interpretation: str = (
        "1/1 true critical incident group reached CRITICAL in this benchmark: the focal multi-report "
        "disaster successfully escalated to 85.35 (CRITICAL >= 80.0), achieving 100% critical recall for "
        "the life-safety emergency. Multi-incident ranking is NOT EVALUATED because the benchmark contains "
        "only 1 true multi-report emergency."
    )


@dataclass(frozen=True)
class LiveReliabilityMetrics:
    """Live HTTP and WebSocket transport reliability metrics (Phases 5 & 6)."""
    phase5_http_attempted: int = 27
    phase5_http_successful: int = 27
    phase5_transport_errors: int = 0
    phase5_ws_frames_valid: int = 27
    phase5_ws_frames_malformed: int = 0
    phase5_ws_unknown_incident_ids: int = 0
    phase6_surge_attempted: int = 40
    phase6_surge_successful: int = 40
    phase6_surge_dropped: int = 0
    phase6_surge_retries: int = 0
    phase6_surge_circuit_opens: int = 0
    persistence_consistency_status: str = (
        "Observed persistence consistency checks passed for all 27 Phase-5 benchmark reports: "
        "zero missing reports, zero orphan links, and zero synthetic partition violations."
    )


@dataclass(frozen=True)
class ResilienceFaultMetrics:
    """Controlled fault injection and recovery metrics (Phase 6)."""
    http_422_status: str = "Permanent client error -> 0 retries, 0 buffering, 0 DB mutation"
    http_429_status: str = "Retry-After (0.1s) header honored, throttled backoff, retry HTTP 201"
    http_5xx_status: str = (
        "Transient 503 succeeds after retry; persistent 500 cleanly buffers into "
        "EventBuffer upon retry exhaustion"
    )
    circuit_breaker_status: str = (
        "CLOSED -> OPEN (at 5 failures) -> HALF_OPEN (after recovery timeout) -> "
        "CLOSED (after 2 probe successes); failure in HALF_OPEN returns immediately to OPEN"
    )
    fifo_ordering_status: str = "Exact FIFO sequence preserved across buffering and flush"
    buffer_overflow_status: str = "Raises BufferOverflowError at capacity + 1; zero silent dropping"
    backend_outage_attempted: int = 3
    backend_outage_buffered: int = 3
    backend_outage_recovered: int = 3
    backend_outage_lost: int = 0
    backend_outage_duplicate_persistence: int = 0
    database_outage_status: str = "NOT TESTED — SHARED INFRASTRUCTURE SAFETY"


@dataclass(frozen=True)
class LatencyProfileSummary:
    """Latency distribution across system execution scopes."""
    cold_first_inference_s: float = 19.03
    direct_ml_cold_ms: float = 15211.80
    direct_ml_warm_count: int = 26
    direct_ml_warm_min_ms: float = 20.75
    direct_ml_warm_mean_ms: float = 25.08
    direct_ml_warm_p50_ms: float = 23.42
    direct_ml_warm_p95_ms: float = 39.85
    direct_ml_warm_max_ms: float = 41.21
    real_e2e_warm_p50_ms: float = 50.43
    real_e2e_warm_p95_ms: float = 67.25
    real_e2e_warm_max_ms: float = 111.80
    surge_first_request_ms: float = 139.12
    surge_warm_count: int = 39
    surge_warm_min_ms: float = 47.99
    surge_warm_mean_ms: float = 54.06
    surge_warm_p50_ms: float = 51.75
    surge_warm_p95_ms: float = 78.45
    surge_warm_max_ms: float = 82.60
    surge_measured_throughput_rps: float = 19.55


@dataclass
class RealSystemScorecard:
    """Master Real Scorecard for Karen's Ear Emergency Intelligence System."""
    branch: str = "feature/evaluation-integration"
    head_commit: str = "312a3f1"
    evidence_sources: List[str] = field(
        default_factory=lambda: [
            "Phase 2: REAL_ML (commit 91ff2ca)",
            "Phase 3: REAL_CORRELATION (commit 00426e1)",
            "Phase 5: REAL_E2E (commit 2455889)",
            "Phase 6: SURGE_AND_RESILIENCE (commit 312a3f1)",
        ]
    )
    overall_score_formula: str = (
        "NONE_DEFINED (no authoritative formula in project requirements; zero invented overall scores)"
    )
    invented_thresholds: bool = False
    direct_ml: DirectMLMetrics = field(default_factory=DirectMLMetrics)
    persisted_e2e_ml: PersistedE2EMLMetrics = field(default_factory=PersistedE2EMLMetrics)
    clustering: ClusteringEvaluationMetrics = field(default_factory=ClusteringEvaluationMetrics)
    relationships: RelationshipClassificationMetrics = field(default_factory=RelationshipClassificationMetrics)
    priority_triage: PriorityTriageMetrics = field(default_factory=PriorityTriageMetrics)
    live_reliability: LiveReliabilityMetrics = field(default_factory=LiveReliabilityMetrics)
    resilience: ResilienceFaultMetrics = field(default_factory=ResilienceFaultMetrics)
    latency: LatencyProfileSummary = field(default_factory=LatencyProfileSummary)
    known_limitations: List[str] = field(
        default_factory=lambda: [
            "1. Hard-negative over-fusion: 3 non-crisis reports were over-fused under the current correlation and source-identity behavior (2 absorbed into the focal flood incident, 1 fused with standalone distractor rep-fld-015).",
            "2. Duplicate false positives: duplicate classification produced substantial false positives on this benchmark (precision 0.1667).",
            "3. Low corroborating recall: corroborating recall is 0.4286 (3 of 7 true corroborations detected).",
            "4. Only one true multi-report emergency exists in the golden corpus, so multi-incident ranking is not meaningfully evaluated (Spearman rho NOT_EVALUATED).",
            "5. Database outage was not tested to ensure shared-infrastructure PostgreSQL safety.",
            "6. Cold first inference was approximately 19 seconds in the tested environment. Integration clients need timeout headroom above observed cold-start latency; the benchmark harness used a larger timeout.",
            "7. Benchmark datasets are small synthetic golden scenarios (27 reports); results are empirical, not universal guarantees.",
            "8. Source fallback (source='simulator') can influence duplicate classification for anonymous synthetic dispatches.",
        ]
    )
    not_evaluated_items: List[str] = field(
        default_factory=lambda: [
            "Multi-incident priority ranking (only 1 multi-report cluster; Spearman rho uninformative)",
            "Database outage / network partition recovery (omitted to protect shared PostgreSQL daemon)",
            "High-concurrency parallel ingestion (SafeHttpTransport evaluated sequential burst up to 19.55 req/s)",
            "Multi-lingual or audio/image modality reports (text-only English dispatch evaluated)",
            "Long-term historical correlation drift across days/weeks",
        ]
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the scorecard into a standard JSON-compatible dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Serializes the scorecard into a pretty-printed JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def to_markdown(self) -> str:
        """Renders the official Phase 7 Real System Scorecard in GitHub Flavored Markdown."""
        lines: List[str] = []
        lines.append("# Phase 7 — Real System Scorecard")
        lines.append("")
        lines.append("## 1. Provenance")
        lines.append(f"- **branch**: `{self.branch}`")
        lines.append(f"- **HEAD**: `{self.head_commit}`")
        lines.append("- **evidence sources**:")
        for src in self.evidence_sources:
            lines.append(f"  - {src}")
        lines.append(f"- **overall score formula**: {self.overall_score_formula}")
        lines.append(f"- **invented thresholds**: {'YES' if self.invented_thresholds else 'NO'}")
        lines.append("")

        lines.append("## 2. Direct REAL_ML")
        lines.append(f"**Execution Scope:** `{self.direct_ml.execution_scope}` | **Real System Result:** `{self.direct_ml.is_real_system_result}`")
        lines.append(f"**Evidence Source:** {self.direct_ml.evidence_source}")
        lines.append("")
        lines.append("| Metric | Observed Value | Operational Notes |")
        lines.append("| :--- | :---: | :--- |")
        lines.append(f"| Coverage Rate | {self.direct_ml.coverage_rate * 100:.2f}% | Full JSON schema adherence ({self.direct_ml.total_samples}/{self.direct_ml.total_samples}) |")
        lines.append(f"| Incident Type Accuracy | {self.direct_ml.incident_type_accuracy * 100:.2f}% | 15/27 exact disaster category matches |")
        lines.append(f"| Incident Type Macro F1 | {self.direct_ml.incident_type_macro_f1:.4f} | Unweighted macro across 9 categories |")
        lines.append(f"| Urgency MAE | {self.direct_ml.urgency_mae:.4f} | Discrete urgency level distance |")
        lines.append(f"| High Urgency Recall | {self.direct_ml.high_urgency_recall * 100:.2f}% | 7/8 HIGH/CRITICAL urgencies identified |")
        lines.append(f"| Report Critical Recall | {self.direct_ml.report_critical_recall * 100:.2f}% | 1/4 strict CRITICAL reports recognized directly |")
        lines.append(f"| Hard-Negative LOW Rejection | {self.direct_ml.hard_negative_low_rejection_rate * 100:.2f}% | Tested on {self.direct_ml.hard_negative_tested}/{self.direct_ml.hard_negative_tested} non-crisis reports only |")
        lines.append(f"| People-at-Risk Recall | {self.direct_ml.people_risk_recall * 100:.2f}% | 3/4 casualty events flagged |")
        lines.append(f"| Coordinate Hallucination Rate | {self.direct_ml.coordinate_hallucination_rate * 100:.2f}% | Zero spurious coordinates fabricated |")
        lines.append("")

        lines.append("## 3. Persisted REAL_E2E ML")
        lines.append(f"**Execution Scope:** `{self.persisted_e2e_ml.execution_scope}` | **Real System Result:** `{self.persisted_e2e_ml.is_real_system_result}`")
        lines.append(f"**Evidence Source:** {self.persisted_e2e_ml.evidence_source}")
        lines.append("")
        lines.append("| Metric | Observed Value | Scope |")
        lines.append("| :--- | :---: | :--- |")
        lines.append(f"| Persisted Predictions Count | {self.persisted_e2e_ml.persisted_predictions_count}/27 | PostgreSQL `ml_predictions` table |")
        lines.append(f"| Persisted Hazard Macro F1 | {self.persisted_e2e_ml.hazard_macro_f1:.4f} | Full pipeline persisted classifications |")
        lines.append(f"| Persisted Urgency Accuracy | {self.persisted_e2e_ml.urgency_accuracy * 100:.2f}% | 16/27 exact urgency matches |")
        lines.append(f"| Persisted Casualty Count MAE | {self.persisted_e2e_ml.casualty_count_mae:.4f} | Zero error on stored casualty estimates |")
        lines.append(f"| Persisted Location Precision Accuracy | {self.persisted_e2e_ml.location_precision_accuracy * 100:.2f}% | 25/27 stored location precision matches |")
        lines.append(f"| Embedding Contract Compliance | {self.persisted_e2e_ml.embedding_contract_status} | 384-dimensional dense vectors |")
        lines.append(f"| Synthetic Partition Violations | {self.persisted_e2e_ml.synthetic_partition_violations} | Zero leakage into non-synthetic storage |")
        lines.append("")

        lines.append("## 4. Clustering")
        lines.append(f"**Execution Scope:** `{self.clustering.execution_scope}` | **Evidence Source:** {self.clustering.evidence_source}")
        lines.append(f"- **TP**: {self.clustering.tp}")
        lines.append(f"- **FP**: {self.clustering.fp}")
        lines.append(f"- **FN**: {self.clustering.fn}")
        lines.append(f"- **TN**: {self.clustering.tn}")
        lines.append(f"- **precision**: {self.clustering.precision:.4f}")
        lines.append(f"- **recall**: {self.clustering.recall:.4f}")
        lines.append(f"- **F1**: {self.clustering.f1:.4f}")
        lines.append(f"- **Rand**: {self.clustering.rand_index:.4f}")
        lines.append(f"- **interpretation**: {self.clustering.interpretation}")
        lines.append(
            f"*(Diagnostic comparison — Phase 3 In-Process Engine: Precision {self.clustering.diagnostic_in_process_comparison['pairwise_precision']:.4f}, "
            f"Recall {self.clustering.diagnostic_in_process_comparison['pairwise_recall']:.4f}, "
            f"F1 {self.clustering.diagnostic_in_process_comparison['pairwise_f1']:.4f}, "
            f"Rand {self.clustering.diagnostic_in_process_comparison['rand_index']:.4f})*"
        )
        lines.append("")

        lines.append("## 5. Relationship Classification")
        lines.append(f"**Execution Scope:** `{self.relationships.execution_scope}` | **Evidence Source:** {self.relationships.evidence_source}")
        lines.append("### Duplicate")
        lines.append(f"- **precision**: {self.relationships.duplicate_precision:.4f}")
        lines.append(f"- **recall**: {self.relationships.duplicate_recall:.4f}")
        lines.append(f"- **F1**: {self.relationships.duplicate_f1:.4f}")
        lines.append("")
        lines.append("### Corroborating")
        lines.append(f"- **precision**: {self.relationships.corroborating_precision:.4f}")
        lines.append(f"- **recall**: {self.relationships.corroborating_recall:.4f}")
        lines.append(f"- **F1**: {self.relationships.corroborating_f1:.4f}")
        lines.append("")
        lines.append(f"- **interpretation**: {self.relationships.interpretation}")
        lines.append("")

        lines.append("## 6. Priority / Triage")
        lines.append(f"**Execution Scope:** `{self.priority_triage.execution_scope}` | **Evidence Source:** {self.priority_triage.evidence_source}")
        lines.append(f"- **focal score**: {self.priority_triage.focal_score:.2f}")
        lines.append(f"- **level**: {self.priority_triage.focal_level}")
        lines.append(f"- **critical threshold**: >= {self.priority_triage.backend_critical_threshold:.1f}")
        lines.append(f"- **critical recall**: {self.priority_triage.incident_critical_recall:.4f}")
        lines.append(f"- **meaningful ranking**: {'true' if self.priority_triage.meaningful_ranking_sample else 'false'}")
        lines.append(f"- **Spearman**: {'NOT_EVALUATED' if self.priority_triage.spearman_rank_correlation is None else self.priority_triage.spearman_rank_correlation}")
        lines.append(f"- **interpretation**: {self.priority_triage.interpretation}")
        lines.append("")

        lines.append("## 7. Live Reliability")
        lines.append(f"- **Phase 5 HTTP**: {self.live_reliability.phase5_http_successful}/{self.live_reliability.phase5_http_attempted} (201 Created, 0 transport errors)")
        lines.append(f"- **Phase 5 WS**: {self.live_reliability.phase5_ws_frames_valid}/{self.live_reliability.phase5_ws_frames_valid} valid envelopes (0 malformed, 0 unknown IDs)")
        lines.append(f"- **Phase 6 surge**: {self.live_reliability.phase6_surge_successful}/{self.live_reliability.phase6_surge_attempted} (201 Created, 0 retries, 0 dropped, 0 circuit opens)")
        lines.append(f"- **persistence consistency**: {self.live_reliability.persistence_consistency_status}")
        lines.append("")

        lines.append("## 8. Resilience")
        lines.append(f"- **422**: {self.resilience.http_422_status}")
        lines.append(f"- **429**: {self.resilience.http_429_status}")
        lines.append(f"- **5xx**: {self.resilience.http_5xx_status}")
        lines.append(f"- **circuit breaker**: {self.resilience.circuit_breaker_status}")
        lines.append(f"- **FIFO**: {self.resilience.fifo_ordering_status}")
        lines.append(f"- **overflow**: {self.resilience.buffer_overflow_status}")
        lines.append(
            f"- **backend interruption**: {self.resilience.backend_outage_attempted} outage reports attempted, "
            f"{self.resilience.backend_outage_buffered} buffered, {self.resilience.backend_outage_recovered} recovered, "
            f"{self.resilience.backend_outage_lost} lost, {self.resilience.backend_outage_duplicate_persistence} duplicate persistence"
        )
        lines.append(f"- **DB outage**: {self.resilience.database_outage_status}")
        lines.append("")

        lines.append("## 9. Latency")
        lines.append("### Cold")
        lines.append(f"- **First inference initialization (container SentenceTransformer)**: {self.latency.cold_first_inference_s:.2f} s")
        lines.append(f"- **Direct ML cold load (in-process weights load)**: {self.latency.direct_ml_cold_ms:.2f} ms")
        lines.append("")
        lines.append("### Direct ML")
        lines.append(f"- **Warm count**: {self.latency.direct_ml_warm_count}")
        lines.append(f"- **Warm min**: {self.latency.direct_ml_warm_min_ms:.2f} ms")
        lines.append(f"- **Warm mean**: {self.latency.direct_ml_warm_mean_ms:.2f} ms")
        lines.append(f"- **Warm p50**: {self.latency.direct_ml_warm_p50_ms:.2f} ms")
        lines.append(f"- **Warm p95**: {self.latency.direct_ml_warm_p95_ms:.2f} ms")
        lines.append(f"- **Warm max**: {self.latency.direct_ml_warm_max_ms:.2f} ms")
        lines.append("")
        lines.append("### REAL_E2E")
        lines.append(f"- **Warm p50**: {self.latency.real_e2e_warm_p50_ms:.2f} ms")
        lines.append(f"- **Warm p95**: {self.latency.real_e2e_warm_p95_ms:.2f} ms")
        lines.append(f"- **Warm max**: {self.latency.real_e2e_warm_max_ms:.2f} ms")
        lines.append("")
        lines.append("### Surge")
        lines.append(f"- **First surge request**: {self.latency.surge_first_request_ms:.2f} ms")
        lines.append(f"- **Warm count**: {self.latency.surge_warm_count}")
        lines.append(f"- **Warm min**: {self.latency.surge_warm_min_ms:.2f} ms")
        lines.append(f"- **Warm mean**: {self.latency.surge_warm_mean_ms:.2f} ms")
        lines.append(f"- **Warm p50**: {self.latency.surge_warm_p50_ms:.2f} ms")
        lines.append(f"- **Warm p95**: {self.latency.surge_warm_p95_ms:.2f} ms")
        lines.append(f"- **Warm max**: {self.latency.surge_warm_max_ms:.2f} ms")
        lines.append(f"- **Measured throughput**: {self.latency.surge_measured_throughput_rps:.2f} reports/sec")
        lines.append("")

        lines.append("## 10. Known Limitations")
        for lim in self.known_limitations:
            lines.append(f"- {lim}")
        lines.append("")

        lines.append("## 11. NOT_EVALUATED")
        for item in self.not_evaluated_items:
            lines.append(f"- {item}")

        return "\n".join(lines)


def build_final_scorecard() -> RealSystemScorecard:
    """Builds the canonical RealSystemScorecard containing verified benchmark metrics."""
    return RealSystemScorecard()


if __name__ == "__main__":
    scorecard = build_final_scorecard()
    print(scorecard.to_markdown())
