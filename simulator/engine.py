"""
Karen's Ear — Disaster Simulator Playback Engine.

Owner: Pankaj (feature/evaluation-integration)
Authority: gemini.md (v1.2), docs/data-schema.md (v1.0), DISASTER_SIMULATOR_ROADMAP.md
Status: Production Hardened Playback Engine

This module provides:
1. Orchestration of timeline playback in synchronous and asynchronous modes.
2. Unified interface with BaseTransport (DryRunTransport, SafeHttpTransport).
3. Configurable speed multipliers, burst emission, and step-by-step playback.
4. Pause, resume, and stop controls.
5. Multi-line ground truth firewall: asserts public payload invariants before every dispatch.
6. Structured PlaybackSummary with verified audit metrics.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional, Union

from simulator.models import (
    GroundTruthLeakageError,
    ScenarioEvent,
    verify_no_ground_truth_leakage,
)
from simulator.timeline import Timeline
from simulator.transport import BaseTransport, DryRunTransport, prepare_payload

logger = logging.getLogger("simulator.engine")


# =============================================================================
# 1. Engine State and Summary
# =============================================================================

class EngineState(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"


@dataclass
class PlaybackSummary:
    """Summary metrics produced upon simulation run completion."""
    scenario_id: Optional[str]
    total_events: int
    dispatched_events: int
    skipped_events: int
    start_time: datetime
    end_time: datetime
    elapsed_wall_seconds: float
    speed_mode: str
    speed_multiplier: float
    is_synthetic_verified: bool
    dry_run: bool
    errors: List[str] = field(default_factory=list)

    @property
    def events_dispatched(self) -> int:
        return self.dispatched_events

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "total_events": self.total_events,
            "dispatched_events": self.dispatched_events,
            "skipped_events": self.skipped_events,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "elapsed_wall_seconds": round(self.elapsed_wall_seconds, 4),
            "speed_mode": self.speed_mode,
            "speed_multiplier": (
                "inf" if self.speed_multiplier == float("inf") else self.speed_multiplier
            ),
            "is_synthetic_verified": self.is_synthetic_verified,
            "dry_run": self.dry_run,
            "errors": self.errors,
        }


# =============================================================================
# 2. Simulation Playback Engine
# =============================================================================

class SimulationEngine:
    """
    Coordinates execution and streaming of disaster simulation events.

    Invariants Enforced:
      - 100% of outgoing dispatches have `is_synthetic: true` and `source: 'simulator'`.
      - Evaluator ground truth is completely isolated and never emitted.
      - Playback can be paused, resumed, stepped, or aborted cleanly.
    """

    def __init__(
        self,
        timeline: Timeline,
        transport: Optional[BaseTransport] = None,
        dry_run: bool = True,
        on_event: Optional[Callable[[ScenarioEvent, int, int], Any]] = None,
        dispatch_fn: Optional[Callable[[Any], Any]] = None,
    ) -> None:
        """
        Initializes the simulation engine.

        Args:
            timeline: Configured Timeline instance.
            transport: Unified BaseTransport instance (defaults to DryRunTransport if dry_run=True).
            dry_run: If True, operates in dry-run mode.
            on_event: Optional callback invoked for each event (event, current_index, total_events).
            dispatch_fn: Optional fallback dispatch callable for custom integrations.
        """
        self.timeline = timeline
        self.dry_run = dry_run
        self.on_event = on_event
        self.dispatch_fn = dispatch_fn

        if transport is not None:
            self.transport: Optional[BaseTransport] = transport
        elif dry_run:
            self.transport = DryRunTransport()
        else:
            self.transport = None

        self._state = EngineState.IDLE
        self._dispatched_count = 0
        self._errors: List[str] = []
        self._synthetic_verified_all = True
        self._dispatched_events: List[ScenarioEvent] = []

    # -------------------------------------------------------------------------
    # Properties & Status
    # -------------------------------------------------------------------------

    @property
    def state(self) -> EngineState:
        return self._state

    @property
    def dispatched_count(self) -> int:
        return self._dispatched_count

    @property
    def dispatched_events(self) -> List[ScenarioEvent]:
        return list(self._dispatched_events)

    def reset(self) -> None:
        """Resets engine counters, errors, and timeline cursor for a clean re-run."""
        self.timeline.reset()
        self._state = EngineState.IDLE
        self._dispatched_count = 0
        self._errors.clear()
        self._synthetic_verified_all = True
        self._dispatched_events.clear()
        if hasattr(self.transport, "clear_buffer"):
            self.transport.clear_buffer()
        if hasattr(self.transport, "circuit_breaker"):
            self.transport.circuit_breaker.reset()

    # -------------------------------------------------------------------------
    # Control Methods (Pause, Resume, Stop)
    # -------------------------------------------------------------------------

    def pause(self) -> None:
        """Pauses running or pending playback."""
        if self._state in (EngineState.RUNNING, EngineState.IDLE):
            self._previous_state = self._state
            self._state = EngineState.PAUSED
            logger.info("Simulation playback paused.")

    def resume(self) -> None:
        """Resumes paused playback."""
        if self._state == EngineState.PAUSED:
            self._state = getattr(self, "_previous_state", EngineState.RUNNING)
            logger.info("Simulation playback resumed.")

    def stop(self) -> None:
        """Stops playback permanently."""
        self._state = EngineState.STOPPED
        logger.info("Simulation playback stopped.")

    # -------------------------------------------------------------------------
    # Safety Firewall
    # -------------------------------------------------------------------------

    def _verify_and_extract_payload(self, event: ScenarioEvent) -> Dict[str, Any]:
        """
        Strict safety firewall:
        Verifies contract invariants before ANY payload is dispatched or emitted.
        Uses centralized recursive ground-truth firewall.
        """
        try:
            payload = prepare_payload(event)
            return payload
        except Exception as exc:
            self._synthetic_verified_all = False
            raise ValueError(f"SAFETY VIOLATION in event '{event.event_id}': {exc}") from exc

    def _dispatch_single_event(self, event: ScenarioEvent, index: int, total: int) -> None:
        """Validates, fires callbacks, and dispatches a single event."""
        payload = self._verify_and_extract_payload(event)

        # Fire on_event observer callback if registered
        if self.on_event is not None:
            try:
                self.on_event(event, index, total)
            except Exception as exc:
                logger.error(f"Error in on_event callback for '{event.event_id}': {exc}")
                self._errors.append(f"Callback error on {event.event_id}: {str(exc)}")

        # Execute dispatch via unified BaseTransport
        if self.transport is not None:
            try:
                res = self.transport.send_event(event)
                if not res.success:
                    self._errors.append(f"Transport error on {event.event_id}: {res.error}")
            except Exception as exc:
                logger.error(f"Error in transport.send_event for '{event.event_id}': {exc}")
                self._errors.append(f"Transport exception on {event.event_id}: {str(exc)}")
        elif not self.dry_run and self.dispatch_fn is not None:
            try:
                self.dispatch_fn(payload)
            except Exception as exc:
                logger.error(f"Error in dispatch_fn for '{event.event_id}': {exc}")
                self._errors.append(f"Dispatch error on {event.event_id}: {str(exc)}")

        self._dispatched_count += 1
        self._dispatched_events.append(event)

    # -------------------------------------------------------------------------
    # Step-by-Step Execution
    # -------------------------------------------------------------------------

    def step(self) -> Optional[ScenarioEvent]:
        """
        Executes exactly one event from the timeline without waiting.
        Useful for interactive debuggers, step-by-step demos, and manual control.
        """
        if self._state == EngineState.STOPPED:
            return None

        if not self.timeline.has_next():
            self._state = EngineState.COMPLETED
            return None

        entry = self.timeline.next_entry()
        if entry is None:
            self._state = EngineState.COMPLETED
            return None

        self._dispatch_single_event(entry.event, entry.index, self.timeline.total_events)

        if not self.timeline.has_next():
            self._state = EngineState.COMPLETED
        else:
            self._state = EngineState.PAUSED

        return entry.event

    # -------------------------------------------------------------------------
    # Synchronous Execution
    # -------------------------------------------------------------------------

    def run_sync(
        self,
        sleep_fn: Callable[[float], None] = time.sleep,
        max_events: Optional[int] = None,
    ) -> PlaybackSummary:
        """
        Executes the timeline synchronously until completion or stop.

        Args:
            sleep_fn: Sleep function for delay between events (default: time.sleep).
            max_events: Optional cap on number of events to dispatch.

        Returns:
            PlaybackSummary: Comprehensive execution audit report.
        """
        if self._state == EngineState.RUNNING:
            raise RuntimeError("SimulationEngine is already RUNNING.")
        if self._state == EngineState.COMPLETED and not self.timeline.has_next():
            raise RuntimeError("SimulationEngine has already COMPLETED. Call engine.reset() before running again.")

        start_time = datetime.now(timezone.utc)
        start_perf = time.perf_counter()
        if self._state != EngineState.PAUSED:
            self._state = EngineState.RUNNING

        total_scheduled = self.timeline.total_events
        limit = total_scheduled if max_events is None else min(max_events, total_scheduled)

        # Detect scenario ID from metadata if present
        scenario_id = None
        first_entry = self.timeline.peek_next()
        if first_entry and getattr(first_entry.event, "dispatch", None) is not None:
            meta = getattr(first_entry.event.dispatch, "metadata", None)
            if meta:
                scenario_id = getattr(meta, "scenario_id", None)

        while self.timeline.has_next() and self._dispatched_count < limit:
            if self._state == EngineState.STOPPED:
                break

            # Handle pause state
            while self._state == EngineState.PAUSED:
                sleep_fn(0.05)

            entry = self.timeline.next_entry()
            if entry is None:
                break

            # Wait scheduled delay unless in burst mode or delay is 0
            if not self.timeline.is_burst and entry.effective_delay_seconds > 0.0:
                sleep_fn(entry.effective_delay_seconds)

            self._dispatch_single_event(entry.event, entry.index, total_scheduled)

        end_time = datetime.now(timezone.utc)
        elapsed_wall = time.perf_counter() - start_perf

        if self._state != EngineState.STOPPED:
            self._state = EngineState.COMPLETED

        return PlaybackSummary(
            scenario_id=scenario_id,
            total_events=total_scheduled,
            dispatched_events=self._dispatched_count,
            skipped_events=total_scheduled - self._dispatched_count,
            start_time=start_time,
            end_time=end_time,
            elapsed_wall_seconds=elapsed_wall,
            speed_mode=(
                "burst"
                if self.timeline.is_burst
                else (f"{self.timeline.speed_multiplier}x")
            ),
            speed_multiplier=self.timeline.speed_multiplier,
            is_synthetic_verified=self._synthetic_verified_all,
            dry_run=self.dry_run,
            errors=list(self._errors),
        )

    # Alias run to run_sync for convenience
    run = run_sync

    # -------------------------------------------------------------------------
    # Asynchronous Execution
    # -------------------------------------------------------------------------

    async def run_async(
        self,
        async_dispatch_fn: Optional[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = None,
        max_events: Optional[int] = None,
    ) -> PlaybackSummary:
        """
        Executes the timeline asynchronously using asyncio.sleep and optional async dispatch.
        """
        if self._state == EngineState.RUNNING:
            raise RuntimeError("SimulationEngine is already RUNNING.")
        if self._state == EngineState.COMPLETED and not self.timeline.has_next():
            raise RuntimeError("SimulationEngine has already COMPLETED. Call engine.reset() before running again.")

        start_time = datetime.now(timezone.utc)
        start_perf = time.perf_counter()
        if self._state != EngineState.PAUSED:
            self._state = EngineState.RUNNING

        total_scheduled = self.timeline.total_events
        limit = total_scheduled if max_events is None else min(max_events, total_scheduled)

        scenario_id = None
        first_entry = self.timeline.peek_next()
        if first_entry and getattr(first_entry.event, "dispatch", None) is not None:
            meta = getattr(first_entry.event.dispatch, "metadata", None)
            if meta:
                scenario_id = getattr(meta, "scenario_id", None)

        while self.timeline.has_next() and self._dispatched_count < limit:
            if self._state == EngineState.STOPPED:
                break

            # Handle pause state
            while self._state == EngineState.PAUSED:
                await asyncio.sleep(0.05)

            entry = self.timeline.next_entry()
            if entry is None:
                break

            # Wait scheduled delay
            if not self.timeline.is_burst and entry.effective_delay_seconds > 0.0:
                await asyncio.sleep(entry.effective_delay_seconds)

            payload = self._verify_and_extract_payload(entry.event)

            # Fire sync observer callback if present
            if self.on_event is not None:
                try:
                    self.on_event(entry.event, entry.index, total_scheduled)
                except Exception as exc:
                    self._errors.append(f"Callback error on {entry.event.event_id}: {str(exc)}")

            # Execute async dispatch if provided
            if not self.dry_run and async_dispatch_fn is not None:
                try:
                    await async_dispatch_fn(payload)
                except Exception as exc:
                    self._errors.append(f"Async dispatch error on {entry.event.event_id}: {str(exc)}")
            elif not self.dry_run and self.dispatch_fn is not None:
                try:
                    await asyncio.to_thread(self.dispatch_fn, payload)
                except Exception as exc:
                    self._errors.append(f"Dispatch error on {entry.event.event_id}: {str(exc)}")
            elif self.transport is not None:
                try:
                    res = await asyncio.to_thread(self.transport.send_event, entry.event)
                    if not res.success:
                        self._errors.append(f"Transport error on {entry.event.event_id}: {res.error}")
                except Exception as exc:
                    self._errors.append(f"Transport error on {entry.event.event_id}: {str(exc)}")

            self._dispatched_count += 1
            self._dispatched_events.append(entry.event)

        end_time = datetime.now(timezone.utc)
        elapsed_wall = time.perf_counter() - start_perf

        if self._state != EngineState.STOPPED:
            self._state = EngineState.COMPLETED

        return PlaybackSummary(
            scenario_id=scenario_id,
            total_events=total_scheduled,
            dispatched_events=self._dispatched_count,
            skipped_events=total_scheduled - self._dispatched_count,
            start_time=start_time,
            end_time=end_time,
            elapsed_wall_seconds=elapsed_wall,
            speed_mode=(
                "burst"
                if self.timeline.is_burst
                else (f"{self.timeline.speed_multiplier}x")
            ),
            speed_multiplier=self.timeline.speed_multiplier,
            is_synthetic_verified=self._synthetic_verified_all,
            dry_run=self.dry_run,
            errors=list(self._errors),
        )
