"""
Karen's Ear — Timeline & Simulation Engine Unit Tests.

Owner: Pankaj (feature/evaluation-integration)
Authority: gemini.md (v1.2), DISASTER_SIMULATOR_ROADMAP.md
Status: Phase 3 — Timeline & Playback Engine Test Suite
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from unittest.mock import MagicMock

from simulator.cli import export_ground_truth_events, export_public_dispatches, main as cli_main
from simulator.engine import EngineState, PlaybackSummary, SimulationEngine
from simulator.models import (
    GroundTruth,
    GroundTruthIncidentType,
    GroundTruthRelationType,
    GroundTruthUrgency,
    RawReportPayload,
    ScenarioEvent,
)
from simulator.scenarios import get_scenario, list_scenarios
from simulator.timeline import SpeedMode, Timeline, TimelineEntry


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def flood_events():
    return get_scenario("flood_rasulgarh")


@pytest.fixture
def adversarial_events():
    return get_scenario("mixed_hard_negatives")


# =============================================================================
# 1. Timeline Speed & Scheduling Tests
# =============================================================================

def test_speed_mode_parsing():
    assert SpeedMode.parse("1x") == 1.0
    assert SpeedMode.parse("2.5x") == 2.5
    assert SpeedMode.parse("5") == 5.0
    assert SpeedMode.parse(10) == 10.0
    assert SpeedMode.parse("burst") == float("inf")
    assert SpeedMode.parse("BURST") == float("inf")
    assert SpeedMode.parse("step") == 0.0
    assert SpeedMode.parse("STEP") == 0.0

    with pytest.raises(ValueError, match="Invalid playback speed"):
        SpeedMode.parse("invalid_speed")

    with pytest.raises(ValueError, match="strictly positive"):
        SpeedMode.parse("-2x")


def test_speed_mode_parse_zero_and_burst_mappings():
    """R5.2: SpeedMode.parse allows 0 and 0.0 (numeric and string), mapping to BURST."""
    import math

    # String representations of zero
    assert SpeedMode.parse("0") == SpeedMode.BURST
    assert SpeedMode.parse("0.0") == SpeedMode.BURST
    assert SpeedMode.parse("0x") == SpeedMode.BURST
    assert SpeedMode.parse("0.0x") == SpeedMode.BURST
    assert math.isinf(SpeedMode.parse("0"))

    # Numeric representations of zero
    assert SpeedMode.parse(0) == SpeedMode.BURST
    assert SpeedMode.parse(0.0) == SpeedMode.BURST
    assert math.isinf(SpeedMode.parse(0))

    # Preserves explicit step mode
    assert SpeedMode.parse("step") == 0.0
    assert SpeedMode.parse("STEP") == 0.0

    # Negative values still strictly raise ValueError
    with pytest.raises(ValueError, match="strictly positive"):
        SpeedMode.parse("-1")
    with pytest.raises(ValueError, match="strictly positive"):
        SpeedMode.parse("-0.5x")
    with pytest.raises(ValueError, match="strictly positive"):
        SpeedMode.parse(-2)


def test_timeline_with_zero_speed(flood_events):
    """R5.2: Timeline initialized with speed '0' or 0 behaves as burst mode."""
    t_str = Timeline(events=flood_events, speed="0")
    assert t_str.is_burst is True
    assert t_str.total_effective_duration == 0.0

    t_num = Timeline(events=flood_events, speed=0)
    assert t_num.is_burst is True
    assert t_num.total_effective_duration == 0.0


def test_timeline_initialization(flood_events):
    timeline = Timeline(events=flood_events, speed="1x")
    assert timeline.total_events == 15
    assert timeline.events_remaining == 15
    assert timeline.current_index == 0
    assert timeline.has_next() is True
    assert timeline.total_simulated_duration > 0
    assert timeline.total_effective_duration == timeline.total_simulated_duration


def test_timeline_empty_events_raises_error():
    with pytest.raises(ValueError, match="requires at least one ScenarioEvent"):
        Timeline(events=[])


def test_timeline_speed_scaling(flood_events):
    timeline_1x = Timeline(events=flood_events, speed="1x")
    timeline_5x = Timeline(events=flood_events, speed="5x")
    timeline_burst = Timeline(events=flood_events, speed="burst")

    # In 1x, simulated duration equals effective duration
    assert timeline_1x.total_effective_duration == pytest.approx(timeline_1x.total_simulated_duration)

    # In 5x, effective duration is ~ 1/5th
    assert timeline_5x.total_effective_duration == pytest.approx(timeline_1x.total_simulated_duration / 5.0, abs=0.1)

    # In burst, effective duration is exactly 0.0s
    assert timeline_burst.is_burst is True
    assert timeline_burst.total_effective_duration == 0.0
    for entry in timeline_burst.get_entries():
        assert entry.effective_delay_seconds == 0.0


def test_timeline_deterministic_seed_and_jitter(flood_events):
    # Two timelines with identical seed and jitter must have bit-for-bit identical schedules
    t1 = Timeline(events=flood_events, seed=42, jitter_stddev=1.5)
    t2 = Timeline(events=flood_events, seed=42, jitter_stddev=1.5)
    t3 = Timeline(events=flood_events, seed=999, jitter_stddev=1.5)

    entries1 = [e.scheduled_delay_seconds for e in t1.get_entries()]
    entries2 = [e.scheduled_delay_seconds for e in t2.get_entries()]
    entries3 = [e.scheduled_delay_seconds for e in t3.get_entries()]

    assert entries1 == entries2
    assert entries1 != entries3


def test_timeline_cursor_navigation(flood_events):
    timeline = Timeline(events=flood_events[:3], speed="burst")
    assert timeline.total_events == 3

    # Peek should not advance cursor
    first_peek = timeline.peek_next()
    assert first_peek is not None
    assert first_peek.event.event_id == flood_events[0].event_id
    assert timeline.current_index == 0

    # Next advances cursor
    e0 = timeline.next_entry()
    assert e0.event.event_id == flood_events[0].event_id
    assert timeline.current_index == 1

    e1 = timeline.next_entry()
    assert e1.event.event_id == flood_events[1].event_id
    assert timeline.current_index == 2

    e2 = timeline.next_entry()
    assert e2.event.event_id == flood_events[2].event_id
    assert timeline.current_index == 3

    assert timeline.has_next() is False
    assert timeline.peek_next() is None
    assert timeline.next_entry() is None

    # Reset
    timeline.reset()
    assert timeline.current_index == 0
    assert timeline.has_next() is True


def test_timeline_from_scenario_factory():
    timeline = Timeline.from_scenario("flood_rasulgarh", speed="10x")
    assert timeline.total_events == 15

    timeline_hn = Timeline.from_scenario("mixed_hard_negatives", speed="burst")
    assert timeline_hn.total_events == 12


def test_timeline_export_schedule(flood_events):
    timeline = Timeline(events=flood_events[:3], speed="5x")
    sched = timeline.export_schedule()
    assert len(sched) == 3
    assert sched[0]["event_id"] == flood_events[0].event_id
    assert "effective_delay_seconds" in sched[0]
    assert "cumulative_effective_seconds" in sched[0]


# =============================================================================
# 2. Simulation Engine Execution & Control Tests
# =============================================================================

def test_engine_dry_run_sync_execution(flood_events):
    timeline = Timeline(events=flood_events, speed="burst")

    dispatched = []
    def on_event(evt, idx, total):
        dispatched.append(evt.event_id)

    engine = SimulationEngine(
        timeline=timeline,
        dry_run=True,
        on_event=on_event,
    )

    summary = engine.run_sync()

    assert summary.dispatched_events == 15
    assert summary.total_events == 15
    assert summary.skipped_events == 0
    assert summary.is_synthetic_verified is True
    assert summary.dry_run is True
    assert len(summary.errors) == 0
    assert engine.state == EngineState.COMPLETED
    assert len(dispatched) == 15


def test_engine_max_events_cap(flood_events):
    timeline = Timeline(events=flood_events, speed="burst")
    engine = SimulationEngine(timeline=timeline, dry_run=True)

    summary = engine.run_sync(max_events=5)
    assert summary.dispatched_events == 5
    assert summary.skipped_events == 10
    assert len(engine.dispatched_events) == 5


def test_engine_step_by_step_mode(flood_events):
    timeline = Timeline(events=flood_events[:3], speed="step")
    engine = SimulationEngine(timeline=timeline, dry_run=True)

    assert engine.state == EngineState.IDLE

    # Step 1
    evt1 = engine.step()
    assert evt1 is not None
    assert evt1.event_id == flood_events[0].event_id
    assert engine.state == EngineState.PAUSED
    assert engine.dispatched_count == 1

    # Step 2
    evt2 = engine.step()
    assert evt2 is not None
    assert evt2.event_id == flood_events[1].event_id
    assert engine.dispatched_count == 2

    # Step 3 (final)
    evt3 = engine.step()
    assert evt3 is not None
    assert evt3.event_id == flood_events[2].event_id
    assert engine.state == EngineState.COMPLETED

    # Step 4 (exhausted)
    evt4 = engine.step()
    assert evt4 is None


def test_engine_stop_control(flood_events):
    timeline = Timeline(events=flood_events, speed="burst")
    engine = SimulationEngine(timeline=timeline, dry_run=True)

    # Dispatch first event, then stop
    def on_event(evt, idx, total):
        if idx == 2:
            engine.stop()

    engine.on_event = on_event
    summary = engine.run_sync()

    assert engine.state == EngineState.STOPPED
    assert summary.dispatched_events == 3
    assert summary.skipped_events == 12


def test_engine_pause_and_resume(flood_events):
    timeline = Timeline(events=flood_events[:4], speed="burst")
    engine = SimulationEngine(timeline=timeline, dry_run=True)

    engine.pause()
    assert engine.state == EngineState.PAUSED
    engine.resume()
    assert engine.state == EngineState.RUNNING or engine.state == EngineState.IDLE


# =============================================================================
# 3. Async Engine Execution Tests
# =============================================================================

@pytest.mark.asyncio
async def test_engine_async_execution(flood_events):
    timeline = Timeline(events=flood_events[:5], speed="burst")

    dispatched_payloads = []
    async def mock_async_dispatch(payload):
        dispatched_payloads.append(payload)

    engine = SimulationEngine(
        timeline=timeline,
        dry_run=False,
    )

    summary = await engine.run_async(async_dispatch_fn=mock_async_dispatch)

    assert summary.dispatched_events == 5
    assert len(dispatched_payloads) == 5
    for p in dispatched_payloads:
        assert p["is_synthetic"] is True
        assert p["source"] == "simulator"
        assert "ground_truth" not in p


# =============================================================================
# 4. Engine Ground-Truth Firewall Tests
# =============================================================================

def test_engine_safety_firewall_catches_leakage():
    fake_event = MagicMock(spec=ScenarioEvent)
    fake_event.event_id = "evt-bad-001"
    fake_event.delay_seconds = 0.0
    fake_event.dispatch = None
    fake_event.public_payload.return_value = {
        "report_id": "rep-bad-001",
        "text": "Water rising fast",
        "source": "simulator",
        "is_synthetic": True,
        "reported_at": "2026-09-26T18:00:00Z",
        "ground_truth": {"urgency": "CRITICAL"},
    }

    timeline = Timeline(events=[fake_event], speed="burst")
    engine = SimulationEngine(timeline=timeline, dry_run=True)

    with pytest.raises(ValueError, match="LEAKAGE VIOLATION"):
        engine.run_sync()
    assert engine._synthetic_verified_all is False


def test_engine_safety_firewall_catches_non_synthetic():
    fake_event = MagicMock(spec=ScenarioEvent)
    fake_event.event_id = "evt-bad-002"
    fake_event.delay_seconds = 0.0
    fake_event.dispatch = None
    fake_event.public_payload.return_value = {
        "report_id": "rep-bad-002",
        "text": "Water rising fast",
        "source": "simulator",
        "is_synthetic": False,
        "reported_at": "2026-09-26T18:00:00Z",
    }

    timeline = Timeline(events=[fake_event], speed="burst")
    engine = SimulationEngine(timeline=timeline, dry_run=True)

    with pytest.raises(ValueError, match="SAFETY VIOLATION.*is_synthetic"):
        engine.run_sync()


# =============================================================================
# 5. CLI Execution & Export Tests
# =============================================================================

def test_cli_dry_run_flood():
    ret = cli_main(["--scenario", "flood_rasulgarh", "--speed", "burst", "--quiet"])
    assert ret == 0


def test_cli_dry_run_all():
    ret = cli_main(["--scenario", "all", "--speed", "burst", "--quiet"])
    assert ret == 0


def test_cli_export_public_dispatches(tmp_path):
    export_file = tmp_path / "flood_public.json"
    ret = cli_main([
        "--scenario", "flood_rasulgarh",
        "--speed", "burst",
        "--export", str(export_file),
        "--quiet",
    ])
    assert ret == 0
    assert export_file.exists()

    with open(export_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) == 15
    for item in data:
        assert item["is_synthetic"] is True
        assert item["source"] == "simulator"
        assert "ground_truth" not in item
        assert "incident_group" not in item
        assert "expected_urgency" not in item


def test_cli_export_ground_truth_events(tmp_path):
    export_file = tmp_path / "all_golden_gt.json"
    ret = cli_main([
        "--scenario", "all",
        "--speed", "burst",
        "--export-ground-truth", str(export_file),
        "--quiet",
    ])
    assert ret == 0
    assert export_file.exists()

    with open(export_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 15 flood + 12 adversarial = 27 total events
    assert len(data) == 27
    for item in data:
        assert "event_id" in item
        assert "dispatch" in item
        assert "ground_truth" in item
        assert item["dispatch"]["is_synthetic"] is True


def test_cli_dry_run_speed_zero():
    """R5.2: CLI execution with --speed 0 runs successfully without error."""
    ret = cli_main(["--scenario", "flood_rasulgarh", "--speed", "0", "--dry-run", "--quiet"])
    assert ret == 0


def test_cli_list_scenarios(capsys):
    """R5.3: --list-scenarios prints sorted registered scenario IDs and exits with status 0."""
    ret = cli_main(["--list-scenarios"])
    assert ret == 0

    captured = capsys.readouterr()
    lines = [line.strip() for line in captured.out.strip().splitlines() if line.strip()]
    expected = sorted(list_scenarios())

    assert lines == expected
    assert "flood_rasulgarh" in lines
    assert "mixed_hard_negatives" in lines


def test_cli_list_scenarios_ignores_other_args(capsys):
    """R5.3: --list-scenarios exits 0 even if an unknown scenario is specified."""
    ret = cli_main(["--scenario", "non_existent_scenario", "--list-scenarios"])
    assert ret == 0

    captured = capsys.readouterr()
    lines = [line.strip() for line in captured.out.strip().splitlines() if line.strip()]
    assert lines == sorted(list_scenarios())


def test_cli_export_public_alias(tmp_path):
    """R5.3: --export-public acts as an alias for --export producing identical public payloads."""
    export_file = tmp_path / "flood_export_public.json"
    ret = cli_main([
        "--scenario", "flood_rasulgarh",
        "--speed", "burst",
        "--export-public", str(export_file),
        "--quiet",
    ])
    assert ret == 0
    assert export_file.exists()

    with open(export_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) == 15
    for item in data:
        assert item["is_synthetic"] is True
        assert item["source"] == "simulator"
        assert "ground_truth" not in item
        assert "incident_group" not in item
        assert "expected_urgency" not in item


def test_cli_subprocess_speed_zero_dry_run():
    """R5.2: CLI execution via subprocess python -m simulator.cli --scenario flood_rasulgarh --speed 0 --dry-run."""
    from pathlib import Path
    karen_dir = str(Path(__file__).resolve().parent.parent.parent)
    env = dict(os.environ)
    env["PYTHONPATH"] = karen_dir + (os.pathsep + env["PYTHONPATH"] if "PYTHONPATH" in env else "")
    proc = subprocess.run(
        [sys.executable, "-m", "simulator.cli", "--scenario", "flood_rasulgarh", "--speed", "0", "--dry-run"],
        capture_output=True,
        text=True,
        cwd=karen_dir,
        env=env,
    )
    assert proc.returncode == 0
    assert "SIMULATION PLAYBACK COMPLETED" in proc.stdout
    assert "Dispatched Events:       15 / 15" in proc.stdout

