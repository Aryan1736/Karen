"""
Karen's Ear — Information & Entity Extraction Subpackage.

Steps 2C & 2D of the ML pipeline (architecture/ml-pipeline.md Sections 3.4 & 3.5).
Responsible for:
- Named entity extraction (locations, hazards, victims, vehicles)
- Location phrasing extraction with strict No-Hallucination policy (coordinates strictly null if unverified)
- People-at-risk count extraction
"""

from ml.extraction.location_entity_extractor import (
    EntityMention,
    GazetteerConfig,
    LocationEntityExtractor,
    LocationEntityResult,
    LocationPrediction,
    extract_location_and_entities,
)
from ml.extraction.people_risk_extractor import (
    PeopleRiskExtractor,
    PeopleRiskResult,
    RiskEvidence,
    extract_people_at_risk,
)

__all__: list[str] = [
    "EntityMention",
    "GazetteerConfig",
    "LocationEntityExtractor",
    "LocationEntityResult",
    "LocationPrediction",
    "extract_location_and_entities",
    "PeopleRiskExtractor",
    "PeopleRiskResult",
    "RiskEvidence",
    "extract_people_at_risk",
]

