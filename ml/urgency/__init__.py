"""
Karen's Ear — Operational Urgency Subpackage.

Step 2B of the ML pipeline (architecture/ml-pipeline.md Section 3.3).
Responsible for deriving operational urgency tiers (CRITICAL, HIGH, MEDIUM, LOW)
via explicit, explainable feature rules:
- Life-Safety Indicators (weight: 0.50)
- Hazard Velocity & Physical Threat (weight: 0.30)
- Vulnerability Modifiers (weight: 0.20)
"""

from ml.config import CANONICAL_URGENCY_LEVELS
from ml.urgency.evaluator import (
    TierMetrics,
    UrgencyEvaluationReport,
    UrgencyEvaluator,
)
from ml.urgency.taxonomy import (
    LABEL_CRITICAL,
    LABEL_HIGH,
    LABEL_LOW,
    LABEL_MEDIUM,
    THRESHOLD_CRITICAL,
    THRESHOLD_HIGH,
    THRESHOLD_MEDIUM,
    WEIGHT_HAZARD_VELOCITY,
    WEIGHT_LIFE_SAFETY,
    WEIGHT_VULNERABILITY,
    is_canonical_urgency_label,
)
from ml.urgency.urgency_engine import (
    ComponentScore,
    UrgencyBreakdown,
    UrgencyEngine,
    UrgencyResult,
    extract_urgency,
)

__all__ = [
    "CANONICAL_URGENCY_LEVELS",
    "ComponentScore",
    "LABEL_CRITICAL",
    "LABEL_HIGH",
    "LABEL_LOW",
    "LABEL_MEDIUM",
    "THRESHOLD_CRITICAL",
    "THRESHOLD_HIGH",
    "THRESHOLD_MEDIUM",
    "TierMetrics",
    "UrgencyBreakdown",
    "UrgencyEngine",
    "UrgencyEvaluationReport",
    "UrgencyEvaluator",
    "UrgencyResult",
    "WEIGHT_HAZARD_VELOCITY",
    "WEIGHT_LIFE_SAFETY",
    "WEIGHT_VULNERABILITY",
    "extract_urgency",
    "is_canonical_urgency_label",
]
