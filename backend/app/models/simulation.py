"""
Karen's Ear — Simulation Run Metadata ORM Model
Table: simulation_runs
Tracks scenario execution, status, and injection volume for simulated disaster streams.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class SimulationRun(Base):
    """
    Metadata record for disaster simulation scenarios.
    """
    __tablename__ = "simulation_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('RUNNING', 'STOPPED', 'COMPLETED')",
            name="check_simulation_runs_status",
        ),
        CheckConstraint(
            "reports_injected >= 0",
            name="check_simulation_runs_reports_injected",
        ),
    )

    simulation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reports_injected: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
