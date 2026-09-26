"""
Karen's Ear — Disaster Simulator Timeline & Playback Sequencer.

Owner: Pankaj (feature/evaluation-integration)
Authority: gemini.md (v1.2), docs/data-schema.md (v1.0), DISASTER_SIMULATOR_ROADMAP.md
Status: Phase 3 — Timeline & Playback Engine

This module provides:
1. Deterministic event scheduling and chronological sequence management.
2. Configurable playback speeds (1x, 2x, 5x, 10x, burst, step).
3. Deterministic seed-based jitter/replay without mutating ground-truth integrity.
4. Schedule export for evaluation planning and inspection.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import random
from typing import Any, Dict, Iterator, List, Optional, Union

from simulator.models import ScenarioEvent
from simulator.scenarios import get_scenario


# =============================================================================
# 1. Playback Speed Representation
# =============================================================================

class SpeedMode:
    """Standard playback speed definitions and string parser."""
    SPEED_1X = 1.0
    SPEED_2X = 2.0
    SPEED_5X = 5.0
    SPEED_10X = 10.0
    BURST = float("inf")
    STEP = 0.0

    @classmethod
    def parse(cls, speed: Union[str, float, int]) -> float:
        """
        Parses speed string (e.g. '1x', '5x', 'burst', 'step', '10.0') to float multiplier.
        Returns:
            float: Multiplier (e.g. 1.0, 5.0, float('inf') for burst, 0.0 for step).
        """
        if isinstance(speed, (int, float)):
            if speed < 0:
                raise ValueError(f"Playback speed multiplier must be strictly positive (got '{speed}').")
            if speed == 0:
                return cls.BURST
            return float(speed)

        norm = str(speed).strip().lower()
        if norm in ("burst", "inf", "+inf"):
            return cls.BURST
        if norm == "step":
            return cls.STEP
        if norm.endswith("x"):
            norm = norm[:-1].strip()

        try:
            val = float(norm)
        except ValueError as exc:
            raise ValueError(
                f"Invalid playback speed '{speed}'. Expected e.g. '1x', '5x', 'burst', 'step'."
            ) from exc

        if val < 0:
            raise ValueError(f"Playback speed multiplier must be strictly positive (got '{speed}').")
        if val == 0.0:
            return cls.BURST
        return val


# =============================================================================
# 2. Timeline Schedule Entry
# =============================================================================

@dataclass(frozen=True)
class TimelineEntry:
    """
    An immutable scheduled point in the simulation timeline.
    """
    index: int
    event: ScenarioEvent
    scheduled_delay_seconds: float
    effective_delay_seconds: float
    cumulative_simulated_seconds: float
    cumulative_effective_seconds: float

    def to_dict(self) -> Dict[str, Any]:
        """Exports entry schedule metadata for inspection."""
        return {
            "index": self.index,
            "event_id": self.event.event_id,
            "report_id": self.event.dispatch.report_id,
            "scheduled_delay_seconds": self.scheduled_delay_seconds,
            "effective_delay_seconds": self.effective_delay_seconds,
            "cumulative_simulated_seconds": self.cumulative_simulated_seconds,
            "cumulative_effective_seconds": self.cumulative_effective_seconds,
            "text_preview": (
                self.event.dispatch.text[:60] + "..."
                if len(self.event.dispatch.text) > 60
                else self.event.dispatch.text
            ),
        }


# =============================================================================
# 3. Timeline Sequencer
# =============================================================================

class Timeline:
    """
    Chronological sequencer and deterministic schedule controller.

    Guarantees:
      - Deterministic ordering of scenario events.
      - Bit-for-bit identical schedules when given the same seed.
      - Exact delay scaling based on configured speed multiplier.
      - Burst mode sets all effective delays to 0.0s.
    """

    def __init__(
        self,
        events: List[ScenarioEvent],
        speed: Union[str, float, int] = 1.0,
        seed: Optional[int] = None,
        jitter_stddev: float = 0.0,
    ) -> None:
        """
        Initializes a timeline schedule with events.

        Args:
            events: Ordered sequence of ScenarioEvents.
            speed: Speed multiplier ('1x', '5x', 'burst', 'step', or float).
            seed: Deterministic integer seed for replay / optional jitter.
            jitter_stddev: Optional standard deviation (seconds) for Gaussian delay jitter.
        """
        if not events:
            raise ValueError("Timeline requires at least one ScenarioEvent.")

        self._raw_events = list(events)
        self._speed_str = str(speed)
        self._speed_multiplier = SpeedMode.parse(speed)
        self._seed = seed
        self._jitter_stddev = max(0.0, float(jitter_stddev))

        self._entries: List[TimelineEntry] = []
        self._cursor: int = 0
        self._build_schedule()

    @classmethod
    def from_scenario(
        cls,
        scenario_id: str,
        speed: Union[str, float, int] = 1.0,
        seed: Optional[int] = None,
        jitter_stddev: float = 0.0,
    ) -> "Timeline":
        """
        Convenience factory to build a Timeline directly from registered scenario ID.
        """
        events = get_scenario(scenario_id)
        return cls(events=events, speed=speed, seed=seed, jitter_stddev=jitter_stddev)

    def _build_schedule(self) -> None:
        """Builds the deterministic TimelineEntry list according to speed and jitter."""
        rng = random.Random(self._seed) if self._seed is not None else random.Random()

        self._entries = []
        cumulative_sim = 0.0
        cumulative_eff = 0.0

        for idx, event in enumerate(self._raw_events):
            base_delay = float(event.delay_seconds)

            # Apply deterministic jitter if configured
            if rng is not None and self._jitter_stddev > 0.0:
                jitter = rng.gauss(0.0, self._jitter_stddev)
                scheduled_delay = max(0.0, round(base_delay + jitter, 3))
            else:
                scheduled_delay = base_delay

            # Calculate effective delay given speed multiplier
            if math.isinf(self._speed_multiplier):
                effective_delay = 0.0
            elif self._speed_multiplier == 0.0:
                # Step mode: delay is manual
                effective_delay = 0.0
            else:
                effective_delay = round(scheduled_delay / self._speed_multiplier, 4)

            cumulative_sim = round(cumulative_sim + scheduled_delay, 3)
            cumulative_eff = round(cumulative_eff + effective_delay, 4)

            entry = TimelineEntry(
                index=idx,
                event=event,
                scheduled_delay_seconds=scheduled_delay,
                effective_delay_seconds=effective_delay,
                cumulative_simulated_seconds=cumulative_sim,
                cumulative_effective_seconds=cumulative_eff,
            )
            self._entries.append(entry)

    # -------------------------------------------------------------------------
    # Properties & Inspection
    # -------------------------------------------------------------------------

    @property
    def speed_multiplier(self) -> float:
        """Returns the active speed multiplier."""
        return self._speed_multiplier

    @property
    def is_burst(self) -> bool:
        """True if running in zero-delay burst mode."""
        return math.isinf(self._speed_multiplier)

    @property
    def is_step(self) -> bool:
        """True if running in step-by-step mode."""
        return self._speed_multiplier == 0.0

    @property
    def total_events(self) -> int:
        """Total number of events scheduled."""
        return len(self._entries)

    @property
    def events_remaining(self) -> int:
        """Number of unconsumed events remaining in the cursor queue."""
        return max(0, len(self._entries) - self._cursor)

    @property
    def current_index(self) -> int:
        """Current playback cursor index (0-indexed)."""
        return self._cursor

    @property
    def total_simulated_duration(self) -> float:
        """Total duration of scenario in real-world simulated seconds."""
        if not self._entries:
            return 0.0
        return self._entries[-1].cumulative_simulated_seconds

    @property
    def total_effective_duration(self) -> float:
        """Total expected wall-clock duration in seconds given current speed multiplier."""
        if not self._entries:
            return 0.0
        return self._entries[-1].cumulative_effective_seconds

    # -------------------------------------------------------------------------
    # Cursor Movement & Iteration
    # -------------------------------------------------------------------------

    def reset(self) -> None:
        """Resets the playback cursor back to start."""
        self._cursor = 0

    def has_next(self) -> bool:
        """Returns True if there are remaining events to consume."""
        return self._cursor < len(self._entries)

    def peek_next(self) -> Optional[TimelineEntry]:
        """Peeks at the next entry without advancing the cursor."""
        if not self.has_next():
            return None
        return self._entries[self._cursor]

    def next_entry(self) -> Optional[TimelineEntry]:
        """Consumes and returns the next entry, advancing the cursor."""
        if not self.has_next():
            return None
        entry = self._entries[self._cursor]
        self._cursor += 1
        return entry

    def __iter__(self) -> Iterator[TimelineEntry]:
        """Iterates through all entries in schedule order."""
        return iter(self._entries)

    def get_entries(self) -> List[TimelineEntry]:
        """Returns a copy of all scheduled entries."""
        return list(self._entries)

    def export_schedule(self) -> List[Dict[str, Any]]:
        """Exports full schedule summary as serializable list of dicts."""
        return [entry.to_dict() for entry in self._entries]
