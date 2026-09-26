"""
Karen's Ear — Master Evaluation Harness & Benchmark Runner.

Owner: Pankaj (feature/evaluation-integration)
Authority: gemini.md (v1.2), docs/data-schema.md, docs/api-contract.md, DISASTER_SIMULATOR_ROADMAP.md
Status: Production Hardened Evaluation Runner

Produces the presentation-ready Master Scorecard comparing:
  - Crisis Hazard Categorization (Macro F1, Precision, Recall)
  - Dual-Level Life-Safety Critical Recall (Report vs Incident tier)
  - Urgency Alignment Score (MAE)
  - Pairwise Incident Fusion Accuracy (Pairwise F1, Rand Index)
  - Duplicate Detection Performance (Precision, Recall, F1)
  - Hard Negative Rejection Rate
  - Pipeline Ingestion Latency Profile (P50, P95) — Real measured or truthfully marked NOT MEASURED
  - Location Extraction & Geocoding Evaluation
  - Scenario Choreography Assertions (Tri-State: PASS, FAIL, NOT_EVALUATED)
  - People-at-Risk Casualty Profiling

Usage:
  python -m evaluation.run_all_evals [--ml-predictions path.json] [--backend-results path.json] [--latency-results path.json]
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Sequence

from evaluation.evaluate_correlation import (
    AssertionResult,
    CorrelationEvaluationReport,
    evaluate_correlation_engine,
)
from evaluation.evaluate_ml import (
    EvaluationMode,
    MLEvaluationReport,
    evaluate_ml_predictions,
)
from evaluation.metrics import LatencyProfile, compute_latency_profile
from simulator.models import ScenarioEvent
from simulator.scenarios import get_scenario, list_scenarios


def load_all_golden_events() -> List[ScenarioEvent]:
    """Loads all deterministic golden scenario events."""
    events: List[ScenarioEvent] = []
    for sid in list_scenarios():
        events.extend(get_scenario(sid))
    return events


def generate_markdown_scorecard(
    ml_report: MLEvaluationReport,
    corr_report: CorrelationEvaluationReport,
    latency: LatencyProfile,
    is_real_system_result: bool = False,
) -> str:
    """Renders the clean GitHub-Flavored Markdown scorecard for hackathon judging."""
    md = []
    mode_label = (
        "LIVE SYSTEM BENCHMARK" if is_real_system_result else "HARNESS SELF-TEST (BASELINE FIXTURE)"
    )
    md.append(f"# 🚨 Karen's Ear — Emergency Intelligence System Benchmark Scorecard")
    md.append(f"**Execution Mode:** `{mode_label}` | **is_real_system_result:** `{is_real_system_result}`")
    md.append(f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} | **Lead:** Pankaj (Evaluation & Integration Lead)")
    md.append(f"**Dataset:** Golden Scenarios (`flood_rasulgarh` + `mixed_hard_negatives`) | **Total Dispatches:** {ml_report.total_samples}")
    md.append("")
    md.append("---")
    md.append("")
    md.append("### 1. Dual-Level Life-Safety & Prioritization Metrics")
    md.append("")
    md.append("| Metric | Result | Target | Status | Architectural Defense |")
    md.append("| :--- | :---: | :---: | :---: | :--- |")

    # Coverage rate
    cov = ml_report.coverage.coverage_rate * 100
    cov_status = "PASS" if cov >= 100.0 else "WARN"
    md.append(f"| **Schema Coverage Rate** | **{cov:.1f}%** | 100.0% | `{cov_status}` | Valid JSON schema adherence |")

    # Report critical recall
    if ml_report.report_critical_recall is not None:
        r_crit = ml_report.report_critical_recall * 100
        r_crit_status = "PASS" if r_crit >= 95.0 else "WARN"
        md.append(f"| **Report-Level Critical Recall** | **{r_crit:.1f}%** | $\\ge$ 95.0% | `{r_crit_status}` | Single-report life threat recognition |")
    else:
        md.append("| **Report-Level Critical Recall** | *N/A* | $\\ge$ 95.0% | `NOT EVALUATED` | Zero critical reports in batch |")

    # Incident critical recall
    if corr_report.incident_critical_recall is not None:
        i_crit = corr_report.incident_critical_recall * 100
        i_crit_status = "PASS" if i_crit >= 99.0 else "WARN"
        md.append(f"| **Incident-Level Critical Recall** | **{i_crit:.1f}%** | 100.0% | `{i_crit_status}` | Fused emergency escalation |")
    else:
        md.append("| **Incident-Level Critical Recall** | *N/A* | 100.0% | `NOT EVALUATED` | Zero critical incidents in batch |")

    # Urgency MAE
    if ml_report.urgency_mae is not None:
        mae = ml_report.urgency_mae
        mae_status = "PASS" if mae <= 0.25 else "WARN"
        md.append(f"| **Urgency Alignment (MAE)** | **{mae:.3f}** | $\\le$ 0.25 | `{mae_status}` | Operational tier calibration (1.0 - 4.0) |")
    else:
        md.append("| **Urgency Alignment (MAE)** | *N/A* | $\\le$ 0.25 | `NOT EVALUATED` | Insufficient samples |")

    # Pairwise Fusion F1
    if corr_report.fusion_accuracy.pairwise_f1 is not None:
        fus_f1 = corr_report.fusion_accuracy.pairwise_f1 * 100
        fus_status = "PASS" if fus_f1 >= 90.0 else "WARN"
        md.append(f"| **Incident Fusion (Pairwise F1)** | **{fus_f1:.1f}%** | $\\ge$ 90.0% | `{fus_status}` | Spatiotemporal report clustering |")
    else:
        md.append("| **Incident Fusion (Pairwise F1)** | *N/A* | $\\ge$ 90.0% | `NOT EVALUATED` | Insufficient pairs |")

    # Duplicate Detection F1
    dup_f1 = corr_report.duplicate_f1 * 100
    dup_status = "PASS" if dup_f1 >= 90.0 else "WARN"
    md.append(f"| **Duplicate Detection F1** | **{dup_f1:.1f}%** | $\\ge$ 90.0% | `{dup_status}` | Retweet & echo suppression |")

    # Hard Negative Rejection
    if ml_report.hard_negative_rejection_rate is not None:
        hn_rate = ml_report.hard_negative_rejection_rate * 100
        hn_status = "PASS" if hn_rate >= 90.0 else "WARN"
        md.append(f"| **Hard Negative Discrimination** | **{hn_rate:.1f}%** | $\\ge$ 90.0% | `{hn_status}` | Fire drills, slang & rumor rejection |")
    else:
        md.append("| **Hard Negative Discrimination** | *N/A* | $\\ge$ 90.0% | `NOT EVALUATED` | No hard negative samples tested |")

    # Scenario Rank #1 Assertion
    rank1_status = corr_report.scenario_rank_1_status.value
    md.append(f"| **Scenario Rank #1 Escalation** | **{rank1_status}** | PASS | `{rank1_status}` | Trapped van elevated after eyewitnesses |")

    md.append("")
    md.append("---")
    md.append("")
    md.append("### 2. Operational Ingestion Latency Profile")
    md.append("")
    md.append("| Metric | Measured | Target (SLO) | Status |")
    md.append("| :--- | :---: | :---: | :---: |")

    if latency.is_measured and latency.sample_count > 0:
        if ml_report.warm_latency_profile is not None and ml_report.cold_latency_ms is not None:
            w = ml_report.warm_latency_profile
            c = ml_report.cold_latency_ms
            md.append(f"| **Cold-Start Latency (First Dispatch)** | **{c:.2f} ms** | - | `COLD START` |")
            md.append(f"| **Warm P50 Latency** | **{w.p50_ms:.2f} ms** | $\\le$ 50.0 ms | `{'PASS' if w.p50_ms <= 50.0 else 'WARN'}` |")
            md.append(f"| **Warm P95 Latency** | **{w.p95_ms:.2f} ms** | $\\le$ 150.0 ms | `{'PASS' if w.p95_ms <= 150.0 else 'WARN'}` |")
            md.append(f"| **Warm Mean Latency** | **{w.mean_ms:.2f} ms** | $\\le$ 75.0 ms | `{'PASS' if w.mean_ms <= 75.0 else 'WARN'}` |")
        else:
            md.append(f"| **P50 Latency** | **{latency.p50_ms:.2f} ms** | $\\le$ 50.0 ms | `{'PASS' if latency.p50_ms <= 50.0 else 'WARN'}` |")
            md.append(f"| **P95 Latency** | **{latency.p95_ms:.2f} ms** | $\\le$ 150.0 ms | `{'PASS' if latency.p95_ms <= 150.0 else 'WARN'}` |")
            md.append(f"| **Mean Latency** | **{latency.mean_ms:.2f} ms** | $\\le$ 75.0 ms | `{'PASS' if latency.mean_ms <= 75.0 else 'WARN'}` |")
    else:
        md.append("| **P50 Latency** | *NOT MEASURED* | $\\le$ 50.0 ms | `NOT MEASURED (Offline Self-Test)` |")
        md.append("| **P95 Latency** | *NOT MEASURED* | $\\le$ 150.0 ms | `NOT MEASURED (Offline Self-Test)` |")
        md.append("| **Mean Latency** | *NOT MEASURED* | $\\le$ 75.0 ms | `NOT MEASURED (Offline Self-Test)` |")

    md.append("")
    md.append("---")
    md.append("")
    md.append("### 3. Scenario Choreography Assertions (Tri-State)")
    md.append(f"- **Corroborating Eyewitness Boost**: `{corr_report.corroboration_boost_status.value}` (Priority escalates with corroborating eyewitness reports)")
    md.append(f"- **Duplicate Suppression**: `{corr_report.duplicate_suppression_status.value}` (Echo retweets do not artificially game priority queue)")

    # Dynamic life-safety check
    has_crit_eval = (ml_report.report_critical_recall is not None or corr_report.incident_critical_recall is not None)
    if not has_crit_eval:
        md.append("- **Life-Safety Invariant**: `NOT EVALUATED` — Zero critical emergency events in evaluated batch.")
    else:
        is_safe = (
            (ml_report.report_critical_recall is None or ml_report.report_critical_recall >= 1.0)
            and (corr_report.incident_critical_recall is None or corr_report.incident_critical_recall >= 1.0)
        )
        if is_safe:
            md.append("- **Life-Safety Invariant**: `PASS` — Zero missed life-safety critical emergencies across all evaluated events.")
        else:
            md.append("- **Life-Safety Invariant**: `FAIL` — Detected missed or unescalated life-safety critical emergency!")

    if ml_report.location_report:
        loc = ml_report.location_report
        md.append("")
        md.append("---")
        md.append("")
        md.append("### 4. Location Extraction & Coordinate Integrity")
        md.append(f"- **Text Match Rate**: **{loc.text_match_rate * 100:.1f}%**")
        md.append(f"- **Coordinate Hallucination Rate**: **{loc.coordinate_hallucination_rate * 100:.1f}%** (Must be 0.0% to prevent bogus dispatch)")
        if loc.mean_distance_error_km is not None:
            md.append(f"- **Mean Coordinate Distance Error**: **{loc.mean_distance_error_km:.2f} km**")

    if ml_report.people_report:
        pr = ml_report.people_report
        md.append("")
        md.append("---")
        md.append("")
        md.append("### 5. People-at-Risk Casualty Profiling")
        rec_str = f"{pr.binary_recall * 100:.1f}%" if pr.binary_recall is not None else "N/A"
        md.append(f"- **Life Risk Identification Recall**: **{rec_str}**")
        md.append(f"- **Binary Risk Classification Accuracy**: **{pr.binary_accuracy * 100:.1f}%**")
        if pr.count_mae is not None:
            md.append(f"- **Casualty Count MAE**: **{pr.count_mae:.2f} victims**")

    return "\n".join(md)


def run_full_benchmark(
    output_dir: str = ".tmp",
    quiet: bool = False,
    ml_predictions_file: Optional[str] = None,
    backend_results_file: Optional[str] = None,
    latency_results_file: Optional[str] = None,
    measured_latencies: Optional[Sequence[float]] = None,
    is_real_system_result: bool = False,
    real_ml: bool = False,
    real_correlation: bool = False,
) -> Dict[str, Any]:
    """Runs complete benchmark harness across all scenarios and saves reports."""
    events = load_all_golden_events()

    # Load external ML predictions if provided
    mock_ml = None
    if ml_predictions_file:
        p = Path(ml_predictions_file)
        if not p.exists():
            raise FileNotFoundError(f"Specified ML predictions file not found: {ml_predictions_file}")
        with open(p, "r", encoding="utf-8") as f:
            mock_ml = json.load(f)
        is_real_system_result = True

    # Load external backend correlation results if provided
    mock_corr = None
    if backend_results_file:
        p = Path(backend_results_file)
        if not p.exists():
            raise FileNotFoundError(f"Specified backend correlation results file not found: {backend_results_file}")
        with open(p, "r", encoding="utf-8") as f:
            mock_corr = json.load(f)
        is_real_system_result = True

    # Load measured latencies if provided
    lat_list = list(measured_latencies or [])
    if latency_results_file:
        p = Path(latency_results_file)
        if not p.exists():
            raise FileNotFoundError(f"Specified latency results file not found: {latency_results_file}")
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                lat_list.extend(data)
            elif isinstance(data, dict) and "latencies_ms" in data:
                lat_list.extend(data["latencies_ms"])

    real_predictor = None
    if real_ml:
        from evaluation.evaluate_ml import build_real_ml_predictor
        real_predictor = build_real_ml_predictor(latency_collector=lat_list)
        is_real_system_result = True

    # 1. Run ML Evaluation
    ml_report = evaluate_ml_predictions(
        events=events,
        predict_fn=real_predictor,
        mock_predictions=mock_ml,
        is_real_system_result=is_real_system_result if (mock_ml is not None or real_ml) else None,
    )

    # 2. Run Incident Correlation Evaluation
    corr_stream_fn = None
    corr_latencies: List[float] = []
    corr_embeddings: List[Any] = []
    if real_correlation:
        from evaluation.evaluate_correlation import build_real_correlation_stream_fn
        corr_stream_fn = build_real_correlation_stream_fn(
            latency_collector=corr_latencies,
            embedding_collector=corr_embeddings,
        )
        is_real_system_result = True

    corr_report = evaluate_correlation_engine(
        events=events,
        correlation_stream_fn=corr_stream_fn,
        mock_correlation_outputs=mock_corr,
        is_real_system_result=is_real_system_result if (mock_corr is not None or real_correlation) else None,
    )
    if real_correlation:
        from evaluation.evaluate_correlation import CorrelationEvaluationMode, verify_embedding_contract
        corr_report.evaluation_mode = CorrelationEvaluationMode.REAL_CORRELATION
        corr_report.execution_scope = "IN_PROCESS_ENGINE_REPLAY"
        if corr_embeddings:
            corr_report.embedding_contract = verify_embedding_contract(corr_embeddings)
        if corr_latencies:
            corr_report.latencies_ms = corr_latencies
            corr_report.latency_profile = compute_latency_profile(corr_latencies)
            corr_report.cold_latency_ms = corr_latencies[0]
            if len(corr_latencies) > 1:
                corr_report.warm_latency_profile = compute_latency_profile(corr_latencies[1:])

    # 3. Latency Profile (Truthful: uses real measurements if provided, otherwise NOT MEASURED)
    latency = compute_latency_profile(lat_list)
    if lat_list and ml_report.latency_profile is None:
        ml_report.latency_profile = latency
        ml_report.latencies_ms = lat_list
        ml_report.cold_latency_ms = lat_list[0]
        if len(lat_list) > 1:
            ml_report.warm_latency_profile = compute_latency_profile(lat_list[1:])

    # 4. Generate Markdown Scorecard
    scorecard_md = generate_markdown_scorecard(
        ml_report=ml_report,
        corr_report=corr_report,
        latency=latency,
        is_real_system_result=is_real_system_result,
    )

    # 5. Export JSON & Markdown
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    json_report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "is_real_system_result": is_real_system_result,
        "total_dispatches": len(events),
        "ml_evaluation": ml_report.to_dict(),
        "correlation_evaluation": corr_report.to_dict(),
        "latency_profile": latency.to_dict(),
        "cold_latency_ms": round(lat_list[0], 2) if lat_list else None,
        "warm_latency_profile": compute_latency_profile(lat_list[1:]).to_dict() if len(lat_list) > 1 else None,
    }

    json_file = out_path / "evaluation_scorecard.json"
    md_file = out_path / "evaluation_scorecard.md"

    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(json_report, f, indent=2)

    with open(md_file, "w", encoding="utf-8") as f:
        f.write(scorecard_md)

    if not quiet:
        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
        print(scorecard_md)
        print("\n" + "=" * 80)
        print(f"[OK] Full benchmark completed successfully.")
        print(f"     JSON report: {json_file}")
        print(f"     Markdown:    {md_file}")
        print("=" * 80)

    return json_report


def main(args: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Karen's Ear Master Evaluation Harness Runner")
    parser.add_argument("--output-dir", "-o", default=".tmp", help="Output directory for reports")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress markdown output to stdout")
    parser.add_argument("--ml-predictions", help="Path to external ML predictions JSON file")
    parser.add_argument("--backend-results", help="Path to external correlation outputs JSON file")
    parser.add_argument("--latency-results", help="Path to external latency measurements JSON file")
    parser.add_argument("--real-ml", action="store_true", help="Evaluate live Aryan ML pipeline directly")
    parser.add_argument("--real-correlation", action="store_true", help="Evaluate live Daksh correlation and priority engine directly")
    parsed = parser.parse_args(args)

    run_full_benchmark(
        output_dir=parsed.output_dir,
        quiet=parsed.quiet,
        ml_predictions_file=parsed.ml_predictions,
        backend_results_file=parsed.backend_results,
        latency_results_file=parsed.latency_results,
        real_ml=parsed.real_ml,
        real_correlation=parsed.real_correlation,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
