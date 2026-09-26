"""
Karen's Ear — ML Evaluation Report Generation & Formatting.

Feature 11 — Quantitative Evaluation Layer.
Provides:
- Machine-readable JSON evaluation report compilation & serialization
  (schema matching evaluation/results/ml_evaluation.json)
- Human-readable Markdown and CLI summary generator
- Comprehensive evaluation orchestration harness (MLEvaluationHarness)
"""

from __future__ import annotations

import json
import os
import platform
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ml.evaluation.classification_evaluator import (
    ClassificationEvaluationResult,
    ClassificationEvaluator,
)
from ml.evaluation.embedding_evaluator import (
    EmbeddingEvaluationResult,
    EmbeddingEvaluator,
)
from ml.evaluation.entity_evaluator import (
    EntityEvaluationResult,
    EntityEvaluator,
)
from ml.evaluation.performance_evaluator import (
    PerformanceEvaluationResult,
    PerformanceEvaluator,
)
from ml.evaluation.urgency_evaluator import (
    UrgencyEvaluationResult,
    UrgencyEvaluator,
)
from ml.pipeline import inference_engine
from ml.pipeline.inference_engine import InferenceEngine

DEFAULT_REPORT_DIR = Path("evaluation/results")
DEFAULT_REPORT_FILE = DEFAULT_REPORT_DIR / "ml_evaluation.json"


def validate_report_path(
    filepath: Path | str,
    allowed_root: Path | str | None = None,
) -> Path:
    """
    Validates and resolves a report output filepath, ensuring it does not escape
    the allowed root directory via path traversal or outside absolute paths.

    Args:
        filepath: Target destination filepath (relative or absolute).
        allowed_root: Allowed root directory (defaults to DEFAULT_REPORT_DIR, cwd, or tempdir).

    Returns:
        Resolved Path guaranteed to be inside an allowed root.

    Raises:
        ValueError: If filepath traverses or points outside allowed roots.
    """
    raw_str = str(filepath).strip()
    if not raw_str:
        raise ValueError("Report output filepath cannot be empty")

    raw_path = Path(filepath)
    resolved = raw_path.resolve()

    if allowed_root is not None:
        root = Path(allowed_root).resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            raise ValueError(
                f"Unsafe output path detected: '{filepath}' escapes allowed root '{root}'"
            ) from None
        return resolved

    # Default allowed roots: DEFAULT_REPORT_DIR or system temp dir (for isolated test execution)
    allowed_roots = [
        DEFAULT_REPORT_DIR.resolve(),
        Path(tempfile.gettempdir()).resolve(),
    ]

    is_allowed = False
    for candidate_root in allowed_roots:
        try:
            resolved.relative_to(candidate_root)
            is_allowed = True
            break
        except ValueError:
            continue

    if not is_allowed:
        raise ValueError(
            f"Unsafe output path detected: '{filepath}' escapes allowed root directories"
        )

    return resolved


@dataclass
class Finding:
    """An individual evaluation finding, limitation, or engineering observation."""

    category: str  # "measured_results", "limitations", "engineering_observations"
    title: str
    details: str


def _fmt_num(val: Any, prec: int = 4) -> str:
    """Safely formats a numerical value or returns 'N/A' if None."""
    if val is None:
        return "N/A"
    try:
        return f"{float(val):.{prec}f}"
    except (ValueError, TypeError):
        return str(val)


@dataclass
class EvaluationReport:
    """Complete consolidated machine-readable evaluation report."""

    evaluation_version: str
    timestamp_utc: str
    environment: dict[str, Any]
    classification: dict[str, Any]
    entity_extraction: dict[str, Any]
    urgency: dict[str, Any]
    embeddings: dict[str, Any]
    performance: dict[str, Any]
    findings: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Converts to a dictionary suitable for JSON serialization."""
        return {
            "evaluation_version": self.evaluation_version,
            "timestamp_utc": self.timestamp_utc,
            "environment": self.environment,
            "classification": self.classification,
            "entity_extraction": self.entity_extraction,
            "urgency": self.urgency,
            "embeddings": self.embeddings,
            "performance": self.performance,
            "findings": self.findings,
        }

    def save(
        self,
        filepath: Path | str = DEFAULT_REPORT_FILE,
        allowed_root: Path | str | None = None,
    ) -> Path:
        """
        Saves the report to a formatted JSON file after strictly validating that
        the target path does not escape the allowed root directory.
        """
        path = validate_report_path(filepath, allowed_root=allowed_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        return path

    def format_human_readable_summary(self) -> str:
        """
        Formats a clean, human-readable terminal / markdown evaluation summary.
        """
        lines = [
            "# Karen's Ear — Machine Learning Evaluation Report",
            f"**Evaluation Version:** {self.evaluation_version} | **Timestamp:** {self.timestamp_utc}",
            "",
        ]
        lines.extend(self._format_environment_section())
        lines.extend(self._format_classification_section())
        lines.extend(self._format_entity_section())
        lines.extend(self._format_urgency_section())
        lines.extend(self._format_embedding_section())
        lines.extend(self._format_performance_section())
        lines.extend(self._format_findings_section())
        return "\n".join(lines)

    def _format_environment_section(self) -> list[str]:
        return [
            "## 1. System Environment",
            f"- **Python:** {self.environment.get('python_version')} on {self.environment.get('platform')}",
            f"- **Architecture:** {self.environment.get('architecture')} ({self.environment.get('processor')})",
            f"- **Model Version:** {self.environment.get('model_version')}",
            "",
        ]

    def _format_classification_section(self) -> list[str]:
        lines = [
            "## 2. Incident Classification Evaluation",
            f"- **Fixture:** {self.classification.get('fixture_name')} ({self.classification.get('sample_count')} samples across 9 canonical classes)",
            f"- **Accuracy:** {_fmt_num(self.classification.get('accuracy'))}",
            f"- **Macro Precision:** {_fmt_num(self.classification.get('macro_precision'))} | **Macro Recall:** {_fmt_num(self.classification.get('macro_recall'))} | **Macro F1:** {_fmt_num(self.classification.get('macro_f1'))}",
            "",
            "| Incident Class | TP | FP | FN | Precision | Recall | F1 | Support |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]
        per_class = self.classification.get("per_class", {})
        for label, m in per_class.items():
            lines.append(
                f"| `{label}` | {m.get('tp', 0)} | {m.get('fp', 0)} | {m.get('fn', 0)} | "
                f"{_fmt_num(m.get('precision'))} | {_fmt_num(m.get('recall'))} | {_fmt_num(m.get('f1'))} | {m.get('support', 0)} |"
            )
        lines.append("")
        return lines

    def _format_entity_section(self) -> list[str]:
        return [
            "## 3. Entity & Location Extraction Evaluation",
            f"- **Fixture:** {self.entity_extraction.get('fixture_name')} ({self.entity_extraction.get('sample_count')} samples: {self.entity_extraction.get('positive_samples')} pos, {self.entity_extraction.get('negative_samples')} neg)",
            "",
            "### A. Location Span Matching",
            "#### 1. Normalized Sub-Span Containment (Operational Baseline)",
            f"- **Rule:** {self.entity_extraction.get('location_subspan_metrics', self.entity_extraction.get('location_span_metrics', {})).get('matching_rule')}",
            f"- **Precision:** {_fmt_num(self.entity_extraction.get('location_subspan_metrics', self.entity_extraction.get('location_span_metrics', {})).get('precision'))} | "
            f"**Recall:** {_fmt_num(self.entity_extraction.get('location_subspan_metrics', self.entity_extraction.get('location_span_metrics', {})).get('recall'))} | "
            f"**F1:** {_fmt_num(self.entity_extraction.get('location_subspan_metrics', self.entity_extraction.get('location_span_metrics', {})).get('f1'))}",
            f"- **Counts:** TP={self.entity_extraction.get('location_subspan_metrics', {}).get('tp')}, "
            f"FP={self.entity_extraction.get('location_subspan_metrics', {}).get('fp')}, "
            f"FN={self.entity_extraction.get('location_subspan_metrics', {}).get('fn')}, "
            f"TN={self.entity_extraction.get('location_subspan_metrics', {}).get('tn')}",
            "",
            "#### 2. Exact Normalized Span Match (Strict Equality)",
            f"- **Rule:** {self.entity_extraction.get('location_exact_metrics', {}).get('matching_rule', 'exact_normalized')}",
            f"- **Precision:** {_fmt_num(self.entity_extraction.get('location_exact_metrics', {}).get('precision'))} | "
            f"**Recall:** {_fmt_num(self.entity_extraction.get('location_exact_metrics', {}).get('recall'))} | "
            f"**F1:** {_fmt_num(self.entity_extraction.get('location_exact_metrics', {}).get('f1'))}",
            f"- **Counts:** TP={self.entity_extraction.get('location_exact_metrics', {}).get('tp')}, "
            f"FP={self.entity_extraction.get('location_exact_metrics', {}).get('fp')}, "
            f"FN={self.entity_extraction.get('location_exact_metrics', {}).get('fn')}, "
            f"TN={self.entity_extraction.get('location_exact_metrics', {}).get('tn')}",
            "",
            "### B. Entity Type + Span Jointly",
            f"- **Rule:** {self.entity_extraction.get('joint_entity_metrics', {}).get('matching_rule')}",
            f"- **Precision:** {_fmt_num(self.entity_extraction.get('joint_entity_metrics', {}).get('precision'))} | "
            f"**Recall:** {_fmt_num(self.entity_extraction.get('joint_entity_metrics', {}).get('recall'))} | "
            f"**F1:** {_fmt_num(self.entity_extraction.get('joint_entity_metrics', {}).get('f1'))}",
            "",
        ]

    def _format_urgency_section(self) -> list[str]:
        lines = [
            "## 4. Urgency Engine Evaluation",
            f"- **Fixture:** {self.urgency.get('fixture_name')} ({self.urgency.get('sample_count')} samples)",
            f"- **Notice:** {self.urgency.get('notice')}",
            f"- **Accuracy:** {_fmt_num(self.urgency.get('accuracy'))}",
            f"- **Critical Recall:** {_fmt_num(self.urgency.get('critical_recall'))}",
            f"- **Critical False-Negative Rate:** {_fmt_num(self.urgency.get('critical_false_negative_rate'))} *(FN / (TP + FN))*",
            f"- **Macro Precision:** {_fmt_num(self.urgency.get('macro_precision'))} | "
            f"**Macro Recall:** {_fmt_num(self.urgency.get('macro_recall'))} | "
            f"**Macro F1:** {_fmt_num(self.urgency.get('macro_f1'))}",
            "",
            "| Urgency Tier | TP | FP | FN | Precision | Recall | F1 | Support |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]
        per_tier = self.urgency.get("per_tier", {})
        for tier, m in per_tier.items():
            lines.append(
                f"| `{tier}` | {m.get('tp', 0)} | {m.get('fp', 0)} | {m.get('fn', 0)} | "
                f"{_fmt_num(m.get('precision'))} | {_fmt_num(m.get('recall'))} | {_fmt_num(m.get('f1'))} | {m.get('support', 0)} |"
            )
        lines.append("")
        return lines

    def _format_embedding_section(self) -> list[str]:
        return [
            "## 5. Dense Semantic Embedding Evaluation",
            f"- **Model:** {self.embeddings.get('model_name')} (dim={self.embeddings.get('embedding_dimension')})",
            f"- **Fixture:** {self.embeddings.get('fixture_name')} ({self.embeddings.get('total_pairs_evaluated')} pairs: {self.embeddings.get('positive_pair_count')} pos, {self.embeddings.get('negative_pair_count')} neg)",
            f"- **ROC-AUC:** {_fmt_num(self.embeddings.get('roc_auc'))}",
            f"- **Configured Threshold:** {self.embeddings.get('configured_threshold')}",
            f"- **Precision @ Threshold:** {_fmt_num(self.embeddings.get('metrics_at_threshold', {}).get('precision'))}",
            f"- **Recall @ Threshold:** {_fmt_num(self.embeddings.get('metrics_at_threshold', {}).get('recall'))}",
            f"- **F1 @ Threshold:** {_fmt_num(self.embeddings.get('metrics_at_threshold', {}).get('f1'))}",
            f"- **Confusion @ Threshold:** TP={self.embeddings.get('metrics_at_threshold', {}).get('tp')}, "
            f"FP={self.embeddings.get('metrics_at_threshold', {}).get('fp')}, "
            f"FN={self.embeddings.get('metrics_at_threshold', {}).get('fn')}, "
            f"TN={self.embeddings.get('metrics_at_threshold', {}).get('tn')}",
            f"- **Mean Positive Similarity:** {_fmt_num(self.embeddings.get('mean_positive_similarity'))} | "
            f"**Mean Negative Similarity:** {_fmt_num(self.embeddings.get('mean_negative_similarity'))} | "
            f"**Margin:** {_fmt_num(self.embeddings.get('semantic_margin'))}",
            "",
        ]

    def _format_performance_section(self) -> list[str]:
        return [
            "## 6. Performance & Resource Profiling",
            f"- **Cold-Start Methodology:** {self.performance.get('cold_start', {}).get('methodology', 'fresh subprocess first full inference')}",
            f"- **Cold-Start Latency:** {_fmt_num(self.performance.get('cold_start', {}).get('latency_ms', self.performance.get('cold_start_latency_ms')), 2)} ms",
            f"- **Cold-Start Memory:** initial RSS={_fmt_num(self.performance.get('cold_start', {}).get('memory', {}).get('initial_rss_mb'), 1)} MB | "
            f"post-inference RSS={_fmt_num(self.performance.get('cold_start', {}).get('memory', {}).get('post_inference_rss_mb'), 1)} MB (delta={_fmt_num(self.performance.get('cold_start', {}).get('memory', {}).get('rss_delta_mb'), 1)} MB) | "
            f"peak working set={_fmt_num(self.performance.get('cold_start', {}).get('memory', {}).get('peak_working_set_mb'), 1)} MB",
            f"- **Memory Note:** {self.performance.get('cold_start', {}).get('memory', {}).get('limitation_notice', self.performance.get('memory', {}).get('limitation_notice'))}",
            f"- **Warm-Up Samples:** {self.performance.get('warm_latency', {}).get('warmup_samples', 0)} (untimed, excluded from warm latency distribution)",
            f"- **Timed Samples:** {self.performance.get('warm_latency', {}).get('timed_samples', self.performance.get('warm_latency', {}).get('sample_count', 0))}",
            f"- **Warm Latency Distribution:** p50={_fmt_num(self.performance.get('warm_latency', {}).get('p50_ms'), 2)} ms | "
            f"p90={_fmt_num(self.performance.get('warm_latency', {}).get('p90_ms'), 2)} ms | "
            f"p95={_fmt_num(self.performance.get('warm_latency', {}).get('p95_ms'), 2)} ms | "
            f"p99={_fmt_num(self.performance.get('warm_latency', {}).get('p99_ms'), 2)} ms | "
            f"mean={_fmt_num(self.performance.get('warm_latency', {}).get('mean_ms'), 2)} ms | "
            f"min={_fmt_num(self.performance.get('warm_latency', {}).get('min_ms'), 2)} ms | "
            f"max={_fmt_num(self.performance.get('warm_latency', {}).get('max_ms'), 2)} ms",
            f"- **Warm Throughput:** {_fmt_num(self.performance.get('warm_latency', {}).get('throughput_items_per_sec'), 1)} reports/sec",
            "",
        ]

    def _format_findings_section(self) -> list[str]:
        lines = ["## 7. Findings & Observations"]
        categories = {
            "measured_results": "Measured Results",
            "limitations": "Limitations",
            "engineering_observations": "Engineering Observations",
        }
        for cat_key, cat_title in categories.items():
            cat_findings = [f for f in self.findings if f.get("category") == cat_key]
            if cat_findings:
                lines.append(f"### {cat_title}")
                for f in cat_findings:
                    lines.append(f"- **{f.get('title')}:** {f.get('details')}")
                lines.append("")
        return lines


class MLEvaluationHarness:
    """
    Unified evaluation harness that coordinates all sub-evaluators and compiles
    the final machine-readable and human-readable reports.
    """

    def __init__(
        self,
        engine: InferenceEngine | None = None,
        embedding_threshold: float = 0.75,
        performance_samples: int = 25,
        warmup_samples: int = 2,
    ) -> None:
        self.engine = engine or inference_engine
        self.embedding_threshold = embedding_threshold
        self.performance_samples = performance_samples
        self.warmup_samples = warmup_samples

        self.classification_evaluator = ClassificationEvaluator(engine=self.engine)
        self.entity_evaluator = EntityEvaluator(engine=self.engine)
        self.urgency_evaluator = UrgencyEvaluator(engine=self.engine)
        self.embedding_evaluator = EmbeddingEvaluator(engine=self.engine, default_threshold=embedding_threshold)
        self.performance_evaluator = PerformanceEvaluator(engine=self.engine)

    def run_evaluation(
        self,
        include_performance: bool = True,
        save_path: Path | str | None = DEFAULT_REPORT_FILE,
        allowed_root: Path | str | None = None,
    ) -> EvaluationReport:
        """
        Executes complete end-to-end ML evaluation across all components.
        """
        timestamp_now = datetime.now(timezone.utc).isoformat()

        # ----------------------------------------------------------------------
        # 1. Performance Evaluation (Isolated Cold-Start Subprocess FIRST, then Warm)
        # ----------------------------------------------------------------------
        if include_performance:
            perf_res = self.performance_evaluator.evaluate(
                warm_trials=self.performance_samples,
                warmup_trials=self.warmup_samples,
            )
            perf_dict = perf_res.to_dict()
            env_dict = asdict(perf_res.environment)
        else:
            perf_dict = {"status": "SKIPPED"}
            env_dict = {
                "python_version": sys.version.split()[0],
                "platform": platform.platform(),
                "operating_system": platform.system(),
                "architecture": platform.machine(),
                "processor": platform.processor() or "Unknown",
                "process_pid": os.getpid(),
                "model_version": self.engine.config.model_version,
            }

        # ----------------------------------------------------------------------
        # 2. Incident Classification Evaluation
        # ----------------------------------------------------------------------
        class_res = self.classification_evaluator.evaluate()

        # ----------------------------------------------------------------------
        # 3. Entity & Location Extraction Evaluation
        # ----------------------------------------------------------------------
        ent_res = self.entity_evaluator.evaluate()

        # ----------------------------------------------------------------------
        # 4. Urgency Engine Evaluation
        # ----------------------------------------------------------------------
        urg_res = self.urgency_evaluator.evaluate()

        # ----------------------------------------------------------------------
        # 5. Dense Semantic Embedding Evaluation
        # ----------------------------------------------------------------------
        emb_res = self.embedding_evaluator.evaluate(threshold=self.embedding_threshold)

        # ----------------------------------------------------------------------
        # 6. Synthesize Honest Findings
        # ----------------------------------------------------------------------
        findings: list[dict[str, Any]] = [
            {
                "category": "measured_results",
                "title": "Incident Classification Accuracy & Macro F1",
                "details": f"Measured accuracy of {class_res.accuracy:.4f} and macro F1 of {class_res.macro_f1:.4f} across 63 curated benchmark samples.",
            },
            {
                "category": "measured_results",
                "title": "Urgency Critical Recall & Safety",
                "details": f"Critical recall measured at {urg_res.critical_recall:.4f} with Critical false-negative rate of {urg_res.critical_false_negative_rate:.4f}.",
            },
            {
                "category": "measured_results",
                "title": "Semantic Embedding Separation",
                "details": f"ROC-AUC measured at {emb_res.roc_auc:.4f} with a semantic separation margin of {emb_res.semantic_margin:.4f} between positive and negative pairs.",
            },
            {
                "category": "limitations",
                "title": "Reference Benchmark vs Real-World Distribution",
                "details": "Evaluation is conducted against curated engineering benchmarks designed for determinism, boundary checking, and regression testing. It is NOT evidence of real-world 100% field accuracy under noisy, unconstrained disaster distributions.",
            },
            {
                "category": "limitations",
                "title": "CrisiText Ground Truth Clarification",
                "details": "CrisiText does NOT provide operational urgency labels or fine-grained token NER spans. Urgency labels in the benchmark are engineering reference labels derived from domain feature extraction rules.",
            },
            {
                "category": "engineering_observations",
                "title": "Cold-Start Subprocess Isolation",
                "details": (
                    f"Cold-start latency measured at {perf_dict.get('cold_start', {}).get('latency_ms', 'N/A')} ms in a dedicated fresh Python subprocess immediately before ML initialization, "
                    f"observing a process RSS delta of {perf_dict.get('cold_start', {}).get('memory', {}).get('rss_delta_mb', 'N/A')} MB without in-process model cache contamination."
                ),
            },
            {
                "category": "engineering_observations",
                "title": "Fail-Soft Pipeline Degradation",
                "details": "The inference pipeline gracefully degrades to PARTIAL or NEEDS_REVIEW status upon individual component failures while preserving surviving component outputs and schema validity.",
            },
            {
                "category": "engineering_observations",
                "title": "Process Memory Interpretation",
                "details": "Reported memory usage reflects OS process RSS and peak working set via psutil, which includes runtime overhead and memory pools rather than isolated tensor weights.",
            },
            {
                "category": "engineering_observations",
                "title": "Warm Latency & Untimed Warm-Up",
                "details": (
                    f"Warm latency distribution measured across {perf_dict.get('warm_latency', {}).get('timed_samples', 'N/A')} timed inference iterations "
                    f"following {perf_dict.get('warm_latency', {}).get('warmup_samples', 'N/A')} untimed warm-up calls, "
                    f"isolating model and runtime initialization from warm execution metrics."
                ),
            },
        ]

        report = EvaluationReport(
            evaluation_version="1.0.0",
            timestamp_utc=timestamp_now,
            environment=env_dict,
            classification=class_res.to_dict(),
            entity_extraction=ent_res.to_dict(),
            urgency=urg_res.to_dict(),
            embeddings=emb_res.to_dict(),
            performance=perf_dict,
            findings=findings,
        )

        if save_path:
            report.save(save_path, allowed_root=allowed_root)

        return report
