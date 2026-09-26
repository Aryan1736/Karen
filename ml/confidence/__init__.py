"""
Karen's Ear — Confidence Calibration Subpackage.

Step 4 of the ML pipeline (architecture/ml-pipeline.md Section 4).
Responsible for:
- Computing overall model confidence from component scores
- Evaluating quality thresholds (confidence < 0.60 flag)
- Routing uncertain or contradictory extractions to NEEDS_REVIEW
"""

__all__: list[str] = []
