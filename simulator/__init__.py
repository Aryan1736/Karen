"""
Karen's Ear — Disaster Simulation Package.

Owner: Pankaj (feature/evaluation-integration)
Authority: gemini.md, docs/data-schema.md, docs/api-contract.md
Status: Production Hardened Models, Transport, and Simulation Engine
"""

from simulator.engine import (
    EngineState,
    PlaybackSummary,
    SimulationEngine,
)
from simulator.models import (
    ExpectedQueueDirection,
    GroundTruth,
    GroundTruthIncidentType,
    GroundTruthLeakageError,
    GroundTruthRelationType,
    GroundTruthUrgency,
    LocationHint,
    LocationPrecision,
    RawReportPayload,
    ReportMetadata,
    ReportSource,
    ScenarioEvent,
    verify_no_ground_truth_leakage,
)
from simulator.timeline import (
    SpeedMode,
    Timeline,
    TimelineEntry,
)
from simulator.transport import (
    CircuitBreaker,
    CircuitState,
    RateLimiter,
    SafeTransport,
    TransportConfig,
    TransportResult,
    prepare_payload,
)

__all__ = [
    # Core Models & Firewall
    "ExpectedQueueDirection",
    "GroundTruth",
    "GroundTruthIncidentType",
    "GroundTruthLeakageError",
    "GroundTruthRelationType",
    "GroundTruthUrgency",
    "LocationHint",
    "LocationPrecision",
    "RawReportPayload",
    "ReportMetadata",
    "ReportSource",
    "ScenarioEvent",
    "verify_no_ground_truth_leakage",
    # Timeline & Playback
    "Timeline",
    "TimelineEntry",
    "SpeedMode",
    "SimulationEngine",
    "EngineState",
    "PlaybackSummary",
    # Transport
    "CircuitBreaker",
    "CircuitState",
    "RateLimiter",
    "SafeTransport",
    "TransportConfig",
    "TransportResult",
    "prepare_payload",
]
