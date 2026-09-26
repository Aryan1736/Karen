"""
Karen's Ear — Operational Urgency Subpackage.

Step 2B of the ML pipeline (architecture/ml-pipeline.md Section 3.3).
Responsible for deriving operational urgency tiers (CRITICAL, HIGH, MEDIUM, LOW)
via explicit, explainable feature rules:
- Life-Safety Indicators (weight: 0.50)
- Hazard Velocity & Physical Threat (weight: 0.30)
- Vulnerability Modifiers (weight: 0.20)
"""

__all__: list[str] = []
