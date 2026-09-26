"""
Karen's Ear — Incident Classification Subpackage.

Step 2A of the ML pipeline (architecture/ml-pipeline.md Section 3.2).
Responsible for classifying emergency reports into the 9 canonical crisis hazard
categories (FLOOD_FLASH_FLOOD, FIRE_WILDFIRE_EXPLOSION, STRUCTURAL_COLLAPSE, etc.)
with calibrated confidence metrics.
"""

from ml.classification.incident_classifier import (
    ClassificationResult,
    IncidentClassifier,
    classify_incident,
)
from ml.classification.taxonomy import (
    CRISITEXT_SCENARIO_MAPPING,
    HAZARD_PRECEDENCE_ORDER,
    INCIDENT_TAXONOMY_CATALOG,
    IncidentClassDefinition,
)

__all__ = [
    "ClassificationResult",
    "IncidentClassifier",
    "classify_incident",
    "INCIDENT_TAXONOMY_CATALOG",
    "IncidentClassDefinition",
    "CRISITEXT_SCENARIO_MAPPING",
    "HAZARD_PRECEDENCE_ORDER",
]
