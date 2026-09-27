"""
Karen's Ear — Simulation Orchestration Service
Coordinates execution of scenario playbacks, step pulses, and real-time WebSocket telemetry.
Integrates simulator scenarios (Pankaj) directly with the live ingestion pipeline (Daksh & Aryan).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from backend.app.models.simulation import SimulationRun
from backend.app.schemas.common import SimulationStatus
from backend.app.schemas.report import RawReportCreate
from backend.app.schemas.simulation import SimulationRunResponse
from backend.app.services.incident_service import IncidentService
from backend.app.services.ingestion import IngestionService
from backend.app.services.ml_adapter import get_ml_adapter
from backend.app.services.websocket_manager import broadcast_event, broadcast_simulation_pulse
from simulator.scenarios import SCENARIO_REGISTRY, get_scenario, list_scenarios

logger = logging.getLogger("karen.backend.simulation")


class SimulationManager:
    """
    In-memory and persistent manager for disaster simulation scenario streaming.
    Ensures safe, non-leaking simulation execution and broadcast across Karen's Ear.
    """

    def __init__(self) -> None:
        self.active_simulation_id: Optional[str] = None
        self.active_scenario_id: Optional[str] = None
        self.status: SimulationStatus = SimulationStatus.STOPPED
        self.reports_injected: int = 0
        self.total_events: int = 0
        self.started_at: Optional[datetime] = None
        self.ended_at: Optional[datetime] = None
        self._playback_task: Optional[asyncio.Task] = None
        self._current_step_index: Dict[str, int] = {}

    def get_available_scenarios(self) -> List[Dict[str, Any]]:
        """Lists registered golden disaster scenarios with metadata and event counts."""
        scenarios = []
        for sid in list_scenarios():
            meta = SCENARIO_REGISTRY.get(sid, {})
            try:
                events = get_scenario(sid)
                event_count = len(events)
            except Exception:
                event_count = 0

            scenarios.append({
                "id": sid,
                "name": meta.get("name", sid.replace("_", " ").title()),
                "description": meta.get("description", "Disaster scenario template"),
                "total_events": event_count,
                "default_rate_per_minute": 15,
            })
        return scenarios

    def get_status(self) -> Dict[str, Any]:
        """Returns the current simulation playback telemetry state."""
        return {
            "status": self.status.value,
            "is_running": self.status == SimulationStatus.RUNNING,
            "simulation_id": self.active_simulation_id,
            "scenario_id": self.active_scenario_id,
            "reports_injected": self.reports_injected,
            "total_events": self.total_events,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
        }

    async def start_simulation(
        self,
        scenario_id: str,
        speed: str = "burst",
        rate_per_minute: int = 15,
    ) -> SimulationRunResponse:
        """
        Initiates an asynchronous simulation run. Cancels any currently active playback.
        """
        if scenario_id not in SCENARIO_REGISTRY:
            raise ValueError(f"Unknown scenario ID '{scenario_id}'. Available: {list_scenarios()}")

        # Stop any active task
        await self.stop_simulation()

        events = get_scenario(scenario_id)
        if not events:
            raise ValueError(f"Scenario '{scenario_id}' contains 0 events.")

        simulation_id = f"sim-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)

        self.active_simulation_id = simulation_id
        self.active_scenario_id = scenario_id
        self.status = SimulationStatus.RUNNING
        self.reports_injected = 0
        self.total_events = len(events)
        self.started_at = now
        self.ended_at = None

        # Persist simulation run record
        db = SessionLocal()
        try:
            run_orm = SimulationRun(
                simulation_id=simulation_id,
                scenario_id=scenario_id,
                status="RUNNING",
                reports_injected=0,
                started_at=now,
            )
            db.add(run_orm)
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.error("Failed to commit SimulationRun record: %s", exc)
        finally:
            db.close()

        # Calculate pacing interval
        if speed == "burst" or rate_per_minute >= 600:
            interval = 0.05
        elif speed == "10x":
            interval = 0.25
        elif speed == "5x":
            interval = 0.5
        elif speed == "2x":
            interval = 1.0
        elif speed == "1x":
            interval = 2.0
        else:
            interval = max(0.1, 60.0 / float(rate_per_minute))

        # Launch playback loop in background
        self._playback_task = asyncio.create_task(
            self._execute_playback(simulation_id, scenario_id, events, interval)
        )

        return SimulationRunResponse(
            simulation_id=simulation_id,
            scenario_id=scenario_id,
            status=SimulationStatus.RUNNING,
            reports_injected=0,
            started_at=now,
        )

    async def _execute_playback(
        self,
        simulation_id: str,
        scenario_id: str,
        events: list,
        interval: float,
    ) -> None:
        """Background asynchronous playback loop feeding reports to IngestionService."""
        logger.info(
            "Starting simulation playback [%s] for scenario '%s' (%d events, interval %.2fs)",
            simulation_id,
            scenario_id,
            len(events),
            interval,
        )

        try:
            for idx, event in enumerate(events):
                if self.status != SimulationStatus.RUNNING or self.active_simulation_id != simulation_id:
                    logger.info("Simulation playback [%s] aborted early.", simulation_id)
                    break

                # Extract validated public payload (guarantees zero ground-truth leakage)
                payload_dict = event.public_payload()
                report_create = RawReportCreate(**payload_dict)

                # Ingest into system with fresh DB session
                db = SessionLocal()
                try:
                    ingestion_service = IngestionService(db=db, ml_adapter=get_ml_adapter())
                    result = ingestion_service.ingest_report(report_create)

                    # Post-commit real-time event broadcast
                    inc_service = IncidentService(db=db)
                    incident_orm = inc_service.repo.get_incident(db, result.incident_id)
                    if incident_orm is not None:
                        incident_dto = inc_service.assemble_single_incident(incident_orm)
                        event_name = "INCIDENT_CREATED" if result.is_new_incident else "INCIDENT_UPDATED"
                        broadcast_event(event_name, incident_dto.model_dump(mode="json"))
                except Exception as ingest_exc:
                    logger.error("Simulation error ingesting report %d: %s", idx, ingest_exc)
                finally:
                    db.close()

                self.reports_injected += 1

                # Update DB run record
                db = SessionLocal()
                try:
                    run_record = db.query(SimulationRun).filter_by(simulation_id=simulation_id).first()
                    if run_record:
                        run_record.reports_injected = self.reports_injected
                        db.commit()
                except Exception as db_exc:
                    logger.warning("Failed to update simulation_runs progress: %s", db_exc)
                finally:
                    db.close()

                # Broadcast pulse to WebSocket clients
                broadcast_simulation_pulse(
                    injected_count=1,
                    total_simulated=self.reports_injected,
                    scenario=scenario_id,
                )

                # Wait before next event
                if idx < len(events) - 1:
                    await asyncio.sleep(interval)

            # Mark completed if reached the end naturally
            if self.status == SimulationStatus.RUNNING and self.active_simulation_id == simulation_id:
                self.status = SimulationStatus.COMPLETED
                self.ended_at = datetime.now(timezone.utc)
                db = SessionLocal()
                try:
                    run_record = db.query(SimulationRun).filter_by(simulation_id=simulation_id).first()
                    if run_record:
                        run_record.status = "COMPLETED"
                        run_record.ended_at = self.ended_at
                        db.commit()
                finally:
                    db.close()
                logger.info(
                    "Simulation playback [%s] COMPLETED (%d/%d reports dispatched).",
                    simulation_id,
                    self.reports_injected,
                    len(events),
                )

        except asyncio.CancelledError:
            logger.info("Simulation playback [%s] cancelled.", simulation_id)
        except Exception as exc:
            logger.error("Simulation playback [%s] encountered error: %s", simulation_id, exc)

    async def inject_pulse(
        self,
        scenario_id: str = "flood_rasulgarh",
        event_index: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Immediately injects a single scenario dispatch step on demand.
        Enables interactive manual stepping and instant testing in the UI.
        """
        if scenario_id not in SCENARIO_REGISTRY:
            raise ValueError(f"Unknown scenario ID '{scenario_id}'. Available: {list_scenarios()}")

        events = get_scenario(scenario_id)
        if not events:
            raise ValueError(f"Scenario '{scenario_id}' has no events.")

        if event_index is None:
            curr_idx = self._current_step_index.get(scenario_id, 0)
            event_index = curr_idx % len(events)
            self._current_step_index[scenario_id] = (curr_idx + 1) % len(events)

        target_event = events[event_index]
        payload_dict = target_event.public_payload()
        # Ensure fresh unique report ID if stepping through repeatedly
        payload_dict["report_id"] = f"rep-sim-{uuid.uuid4().hex[:8]}"
        payload_dict["reported_at"] = datetime.now(timezone.utc).isoformat()

        report_create = RawReportCreate(**payload_dict)

        db = SessionLocal()
        try:
            ingestion_service = IngestionService(db=db, ml_adapter=get_ml_adapter())
            result = ingestion_service.ingest_report(report_create)

            # Post-commit real-time event broadcast
            inc_service = IncidentService(db=db)
            incident_orm = inc_service.repo.get_incident(db, result.incident_id)
            incident_data = None
            if incident_orm is not None:
                incident_dto = inc_service.assemble_single_incident(incident_orm)
                event_name = "INCIDENT_CREATED" if result.is_new_incident else "INCIDENT_UPDATED"
                broadcast_event(event_name, incident_dto.model_dump(mode="json"))
                incident_data = incident_dto.model_dump(mode="json")
        finally:
            db.close()

        # Update manager telemetry
        self.reports_injected += 1
        broadcast_simulation_pulse(
            injected_count=1,
            total_simulated=self.reports_injected,
            scenario=scenario_id,
        )

        return {
            "success": True,
            "scenario_id": scenario_id,
            "event_index": event_index,
            "total_events": len(events),
            "report_id": result.report_id,
            "incident_id": result.incident_id,
            "is_new_incident": result.is_new_incident,
            "relationship": result.relationship.value if result.relationship else None,
            "processing_status": result.processing_status.value if result.processing_status else None,
            "incident": incident_data,
        }

    async def stop_simulation(self) -> Dict[str, Any]:
        """Cancels and halts any active simulation background loop."""
        if self._playback_task and not self._playback_task.done():
            self._playback_task.cancel()
            try:
                await self._playback_task
            except asyncio.CancelledError:
                pass

        if self.status == SimulationStatus.RUNNING:
            self.status = SimulationStatus.STOPPED
            self.ended_at = datetime.now(timezone.utc)
            if self.active_simulation_id:
                db = SessionLocal()
                try:
                    run_record = db.query(SimulationRun).filter_by(simulation_id=self.active_simulation_id).first()
                    if run_record and run_record.status == "RUNNING":
                        run_record.status = "STOPPED"
                        run_record.ended_at = self.ended_at
                        db.commit()
                finally:
                    db.close()

        return self.get_status()


# Global singleton instance
simulation_manager = SimulationManager()
