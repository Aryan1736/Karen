"""
Karen's Ear — API Routes Package
"""
from .incidents import router as incidents_router
from .reports import router as reports_router
from .simulation import router as simulation_router

__all__ = ["incidents_router", "reports_router", "simulation_router"]
