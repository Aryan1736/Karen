"""
Karen's Ear — Data Access Repositories
"""
from .incident_repo import IncidentRepository
from .ingestion_repo import IngestionRepository

__all__ = ["IncidentRepository", "IngestionRepository"]
