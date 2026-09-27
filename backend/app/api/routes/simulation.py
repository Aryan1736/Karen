"""
Karen's Ear — Disaster Simulation Control Route
Implements POST /simulation/start, POST /simulation/stop, GET /simulation/status,
GET /simulation/scenarios, and POST /simulation/pulse matching docs/api-contract.md Section 5.6.
"""
from __future__ import annotations

import logging
from typing import Optional
from fastapi import APIRouter, Body, Request, Response, status
from pydantic import BaseModel, Field

from backend.app.core.envelope import error_response, get_request_id, success_response
from backend.app.schemas.simulation import SimulationRunResponse, SimulationStartRequest
from backend.app.services.simulation_service import simulation_manager

logger = logging.getLogger("karen.backend.api.simulation")

router = APIRouter(prefix="/simulation", tags=["Simulation"])


class SimulationPulseRequest(BaseModel):
    """Configuration to inject a single simulated event."""
    scenario_id: str = Field(default="flood_rasulgarh", description="Scenario template ID")
    event_index: Optional[int] = Field(default=None, ge=0, description="Optional specific event index")


@router.get(
    "/scenarios",
    status_code=status.HTTP_200_OK,
    summary="List Registered Disaster Scenarios",
    description="Returns metadata and event counts for all available crisis simulation templates.",
)
def list_simulation_scenarios(request: Request) -> Response:
    """Lists registered golden disaster scenarios."""
    req_id = getattr(request.state, "request_id", None) or get_request_id()
    scenarios = simulation_manager.get_available_scenarios()
    return success_response(
        data=scenarios,
        status_code=status.HTTP_200_OK,
        request_id=req_id,
    )


@router.get(
    "/status",
    status_code=status.HTTP_200_OK,
    summary="Get Simulation Telemetry Status",
    description="Returns current run state, reports injected, active scenario, and start/end times.",
)
def get_simulation_status(request: Request) -> Response:
    """Returns current active simulation state."""
    req_id = getattr(request.state, "request_id", None) or get_request_id()
    state = simulation_manager.get_status()
    return success_response(
        data=state,
        status_code=status.HTTP_200_OK,
        request_id=req_id,
    )


@router.post(
    "/start",
    status_code=status.HTTP_200_OK,
    summary="Start Disaster Simulation Playback",
    description="Starts streaming simulated dispatches through the live ML and correlation pipeline.",
)
async def start_simulation_playback(
    payload: SimulationStartRequest,
    request: Request,
) -> Response:
    """Initiates an asynchronous simulation playback run."""
    req_id = getattr(request.state, "request_id", None) or get_request_id()
    try:
        run_res = await simulation_manager.start_simulation(
            scenario_id=payload.scenario_id,
            speed=payload.speed or "burst",
            rate_per_minute=payload.rate_per_minute,
        )
        return success_response(
            data=run_res.model_dump(mode="json"),
            status_code=status.HTTP_200_OK,
            request_id=req_id,
        )
    except ValueError as val_err:
        return error_response(
            code="SCENARIO_NOT_FOUND",
            message=str(val_err),
            status_code=status.HTTP_404_NOT_FOUND,
            request_id=req_id,
        )
    except Exception as exc:
        logger.error("Failed to start simulation: %s", exc)
        return error_response(
            code="SIMULATION_START_FAILED",
            message=f"Failed to start simulation: {exc}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            request_id=req_id,
        )


@router.post(
    "/stop",
    status_code=status.HTTP_200_OK,
    summary="Halt Active Simulation Playback",
    description="Cancels and stops any currently active simulation playback loop.",
)
async def stop_simulation_playback(request: Request) -> Response:
    """Halts active playback."""
    req_id = getattr(request.state, "request_id", None) or get_request_id()
    state = await simulation_manager.stop_simulation()
    return success_response(
        data=state,
        status_code=status.HTTP_200_OK,
        request_id=req_id,
    )


@router.post(
    "/pulse",
    status_code=status.HTTP_201_CREATED,
    summary="Inject Single Step Simulation Event",
    description="Immediately feeds a single scenario report through ingestion, ML analysis, and WebSocket broadcast.",
)
async def inject_simulation_pulse(
    request: Request,
    payload: SimulationPulseRequest = Body(default_factory=SimulationPulseRequest),
) -> Response:
    """Injects a single dispatch event for interactive testing and stepping."""
    req_id = getattr(request.state, "request_id", None) or get_request_id()
    try:
        pulse_result = await simulation_manager.inject_pulse(
            scenario_id=payload.scenario_id,
            event_index=payload.event_index,
        )
        return success_response(
            data=pulse_result,
            status_code=status.HTTP_201_CREATED,
            request_id=req_id,
        )
    except ValueError as val_err:
        return error_response(
            code="SCENARIO_NOT_FOUND",
            message=str(val_err),
            status_code=status.HTTP_404_NOT_FOUND,
            request_id=req_id,
        )
    except Exception as exc:
        logger.error("Simulation pulse injection failed: %s", exc)
        return error_response(
            code="SIMULATION_PULSE_FAILED",
            message=f"Failed to inject simulation pulse: {exc}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            request_id=req_id,
        )
