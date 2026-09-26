"""
Karen's Ear — Information & Entity Extraction Subpackage.

Steps 2C & 2D of the ML pipeline (architecture/ml-pipeline.md Sections 3.4 & 3.5).
Responsible for:
- Named entity extraction (locations, hazards, victims, vehicles)
- Location phrasing extraction with strict No-Hallucination policy (coordinates strictly null if unverified)
- People-at-risk count extraction
"""

__all__: list[str] = []
