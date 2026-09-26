"""
Karen's Ear — ML Evaluation CLI Entry Point.

Usage:
    python -m ml.evaluation [--threshold 0.75] [--output evaluation/results/ml_evaluation.json] [--performance-samples 25]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ml.evaluation.report import DEFAULT_REPORT_FILE, MLEvaluationHarness


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parses command-line arguments for the ML evaluation runner."""
    parser = argparse.ArgumentParser(
        prog="python -m ml.evaluation",
        description="Karen's Ear — Machine Learning Evaluation Harness (Feature 11).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.75,
        help="Similarity threshold for embedding semantic pair evaluation (default: 0.75).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_REPORT_FILE),
        help=f"File path where machine-readable JSON report is saved (default: {DEFAULT_REPORT_FILE}).",
    )
    parser.add_argument(
        "--performance-samples",
        type=int,
        default=25,
        help="Number of warm inference iterations for latency profiling (default: 25).",
    )
    parser.add_argument(
        "--warmup-samples",
        type=int,
        default=2,
        help="Number of untimed warm-up inference iterations before timing (default: 2).",
    )
    parser.add_argument(
        "--skip-performance",
        action="store_true",
        help="Skip performance and memory profiling if running in lightweight test mode.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress human-readable terminal summary and only output the JSON file.",
    )
    return parser.parse_args(args)


def main(argv: list[str] | None = None) -> int:
    """Main execution function for ML evaluation CLI."""
    args = parse_args(argv)

    output_path = Path(args.output)
    if not args.quiet:
        print(f"[INFO] Initializing ML Evaluation Harness (embedding threshold={args.threshold})...")

    harness = MLEvaluationHarness(
        embedding_threshold=args.threshold,
        performance_samples=args.performance_samples,
        warmup_samples=args.warmup_samples,
    )

    if not args.quiet:
        print("[INFO] Running evaluation across classification, extraction, urgency, embeddings, and performance...")

    report = harness.run_evaluation(
        include_performance=not args.skip_performance,
        save_path=output_path,
    )

    if not args.quiet:
        print(f"[SUCCESS] Machine-readable report saved to: {output_path.resolve()}")
        print("\n" + report.format_human_readable_summary() + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
