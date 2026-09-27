"""
Adversarial and Empirical Stress Test Suite for Milestone 1.
Challenger 1 Verification Suite:
- R5.1: RateLimiter boundary capacities, refills, multi-threaded stress, deadlock prevention
- R5.2: SpeedMode exhaustive edge cases (0, 0.0, '0', '0.0', '0x', '0.0x', 'burst', 'step', negatives, malformed)
- R5.3: CLI flags and scenarios execution
- R4.3: Recursive Firewall string-value audit & false-positive resistance
"""

import concurrent.futures
import json
import os
import subprocess
import sys
import time
import pytest

from simulator.transport import RateLimiter
from simulator.timeline import SpeedMode
from simulator.models import (
    verify_no_ground_truth_leakage,
    GroundTruthLeakageError,
    ReportMetadata,
    RawReportPayload,
    LocationHint,
    LocationPrecision,
    ScenarioEvent,
    GroundTruth,
)
from simulator.scenarios import list_scenarios, get_scenario


# =============================================================================
# 1. R5.1 RateLimiter Boundary Capacities & Deadlock Verification
# =============================================================================

@pytest.mark.parametrize("capacity,expected_cap", [
    (0.01, 1.0),
    (0.5, 1.0),
    (0.99, 1.0),
    (1.0, 1.0),
    (5.0, 5.0),
])
def test_rate_limiter_boundary_capacities_initialization(capacity: float, expected_cap: float):
    """Verify that capacity < 1.0 is clamped to 1.0, while >= 1.0 is preserved."""
    limiter = RateLimiter(rate_per_second=0.5, capacity=capacity)
    assert limiter.capacity == expected_cap, f"Capacity {capacity} should be clamped/set to {expected_cap}"
    assert limiter.tokens == expected_cap
    assert limiter.rate == 0.5


@pytest.mark.parametrize("cap", [0.01, 0.5, 0.99, 1.0, 5.0])
def test_rate_limiter_blocking_acquire_does_not_deadlock(cap: float):
    """
    Verify blocking acquire does NOT deadlock or hang on boundary capacities.
    Runs with high refill rate (100.0 tokens/sec) so acquire(block=True) succeeds in < 20ms.
    """
    limiter = RateLimiter(rate_per_second=100.0, capacity=cap)

    # Initial acquire should succeed immediately (tokens >= 1.0)
    t0 = time.monotonic()
    assert limiter.acquire(block=False) is True
    t1 = time.monotonic()
    assert (t1 - t0) < 0.05

    # If capacity was 1.0, tokens are now 0.0. Blocking acquire should sleep and succeed in ~10ms
    t2 = time.monotonic()
    assert limiter.acquire(block=True) is True
    t3 = time.monotonic()
    assert (t3 - t2) < 0.2, f"Blocking acquire took too long: {t3 - t2}s"


def test_rate_limiter_multiple_consecutive_blocking_acquires():
    """Verify multiple consecutive blocking acquires cleanly refill tokens and do not freeze."""
    rate = 50.0  # 50 tokens/sec -> 0.02s per token
    limiter = RateLimiter(rate_per_second=rate, capacity=0.01)  # clamped to 1.0
    assert limiter.capacity == 1.0

    t_start = time.monotonic()
    for _ in range(10):
        acquired = limiter.acquire(block=True)
        assert acquired is True
    t_end = time.monotonic()
    elapsed = t_end - t_start
    # 1st token was free, remaining 9 tokens at 50/s should take ~0.18s
    assert 0.10 <= elapsed <= 0.60, f"Expected ~0.18s, got {elapsed}s"


def test_rate_limiter_concurrent_threads_no_deadlock():
    """
    Stress-test RateLimiter under concurrent multi-threaded contention.
    Ensures no thread permanently hangs or deadlocks.
    """
    limiter = RateLimiter(rate_per_second=200.0, capacity=0.5)  # capacity clamped to 1.0
    num_threads = 10
    acquires_per_thread = 5

    def worker():
        for _ in range(acquires_per_thread):
            ok = limiter.acquire(block=True)
            assert ok is True
        return True

    t0 = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker) for _ in range(num_threads)]
        for f in concurrent.futures.as_completed(futures, timeout=5.0):
            assert f.result() is True
    elapsed = time.monotonic() - t0
    assert elapsed < 3.0, f"Concurrent acquires took {elapsed}s"


def test_rate_limiter_rate_clamping():
    """Ensure sub-0.1 rate_per_second is clamped to 0.1 and does not divide by zero."""
    limiter = RateLimiter(rate_per_second=0.0001, capacity=0.01)
    assert limiter.rate == 0.1
    assert limiter.capacity == 1.0


# =============================================================================
# 2. R5.2 SpeedMode Parsing Exhaustive Edge Cases
# =============================================================================

@pytest.mark.parametrize("input_val", [
    0,
    0.0,
    "0",
    "0.0",
    "0x",
    "0.0x",
    "0X",
    "0.0X",
    " 0 ",
    " 0.0 ",
    " 0x ",
    " 0.0x ",
    "00",
    "0.000",
    "burst",
    "BURST",
    "Burst",
    " burst ",
])
def test_speed_mode_burst_and_zero_mappings(input_val):
    """Verify that all numeric and string variations of zero and burst map to float('inf')."""
    parsed = SpeedMode.parse(input_val)
    assert parsed == float("inf"), f"Expected float('inf') for {repr(input_val)}, got {parsed}"
    assert parsed == SpeedMode.BURST


@pytest.mark.parametrize("input_val", [
    "step",
    "STEP",
    "Step",
    " step ",
])
def test_speed_mode_step_mappings(input_val):
    """Verify that 'step' mappings return 0.0 (SpeedMode.STEP)."""
    parsed = SpeedMode.parse(input_val)
    assert parsed == 0.0
    assert parsed == SpeedMode.STEP


@pytest.mark.parametrize("input_val,expected", [
    (1, 1.0),
    (1.0, 1.0),
    ("1", 1.0),
    ("1x", 1.0),
    ("1X", 1.0),
    ("5", 5.0),
    ("5x", 5.0),
    (10.0, 10.0),
    ("10x", 10.0),
    ("0.5x", 0.5),
    (" 2.5X ", 2.5),
])
def test_speed_mode_positive_multipliers(input_val, expected):
    """Verify valid positive speeds parse to correct float values."""
    assert SpeedMode.parse(input_val) == expected


@pytest.mark.parametrize("invalid_val", [
    -1,
    -0.01,
    -100,
    "-1",
    "-1x",
    "-0.5",
    "-0.01x",
    "-5X",
])
def test_speed_mode_negative_values_raise_value_error(invalid_val):
    """Verify negative speeds raise ValueError with strictly positive message."""
    with pytest.raises(ValueError, match="strictly positive"):
        SpeedMode.parse(invalid_val)


@pytest.mark.parametrize("malformed_val", [
    "invalid",
    "abc",
    "1xx",
    "x",
    "",
    "   ",
    "none",
])
def test_speed_mode_malformed_strings_raise_value_error(malformed_val):
    """Verify malformed non-numeric strings raise ValueError."""
    with pytest.raises(ValueError):
        SpeedMode.parse(malformed_val)


def test_speed_mode_inf_parses_to_burst():
    """Verify 'inf' string parses to float('inf') which equals SpeedMode.BURST."""
    parsed = SpeedMode.parse("inf")
    assert parsed == SpeedMode.BURST
    assert parsed == float("inf")


def test_speed_mode_nan_edge_case():
    """
    Adversarial observation: 'nan' float and string are parsed by float() without ValueError,
    returning math.nan. Documenting this empirical behavior.
    """
    import math
    parsed = SpeedMode.parse("nan")
    assert math.isnan(parsed)



# =============================================================================
# 3. R4.3 Recursive Firewall String-Value Audit Stress & False Positive Testing
# =============================================================================

@pytest.mark.parametrize("field_name,smuggled_val", [
    ("channel", "expected_urgency"),
    ("channel", "ground_truth"),
    ("caller_id", "incident_group"),
    ("reporter_id", "relation_type"),
    ("phase", "true_hazard"),
    ("channel", "expected_location_text"),
    ("channel", "expected_latitude"),
    ("caller_id", "expected_people_at_risk"),
    ("reporter_id", "expected_required_response"),
    ("channel", "radio;expected_urgency=HIGH"),
    ("caller_id", "caller-expected-incident-type-01"),
    ("phase", "expected:phase1"),
    ("phase", "expected=mitigation"),
    ("phase", "expected.test"),
    ("channel", "EXPECTED_URGENCY"),
    ("caller_id", "GROUNDTRUTH_911"),
    ("reporter_id", "expected_people_count=10"),
])
def test_firewall_blocks_smuggled_metadata_string_values(field_name: str, smuggled_val: str):
    """Verify verify_no_ground_truth_leakage catches all smuggled ground-truth tokens in metadata."""
    payload = {
        "report_id": "rep-test-001",
        "text": "Normal report text about heavy rain",
        "metadata": {
            field_name: smuggled_val,
        },
    }
    with pytest.raises(GroundTruthLeakageError) as exc_info:
        verify_no_ground_truth_leakage(payload)
    assert "LEAKAGE VIOLATION" in str(exc_info.value)


@pytest.mark.parametrize("legitimate_val", [
    "vhf_channel_16",
    "police_dispatch_radio",
    "citizen_hotline_911",
    "reporter_alpha_01",
    "caller_user_58291",
    "phase_initial_response",
    "mitigation_stage",
    "emergency_call_center",
])
def test_firewall_permits_legitimate_metadata_strings(legitimate_val: str):
    """Ensure legitimate operational metadata strings pass without false positives."""
    payload = {
        "report_id": "rep-test-002",
        "text": "Normal report text",
        "metadata": {
            "channel": legitimate_val,
            "caller_id": legitimate_val,
            "reporter_id": legitimate_val,
            "phase": legitimate_val,
        },
    }
    # Should not raise GroundTruthLeakageError
    verify_no_ground_truth_leakage(payload)


def test_firewall_permits_report_text_with_word_expected():
    """
    Ensure natural language text in report body containing the common English word
    'expected' (e.g. 'water level is expected to rise') is NOT falsely blocked,
    as report body is not an audited metadata field.
    """
    payload = {
        "report_id": "rep-test-003",
        "text": "Water levels are expected to rise significantly near Rasulgarh flyover by evening.",
        "metadata": {
            "channel": "civic_hotline",
        },
    }
    verify_no_ground_truth_leakage(payload)


def test_all_registered_scenarios_public_payloads_pass_firewall():
    """Verify that every single scenario event in all registered scenarios passes firewall."""
    for s_id in list_scenarios():
        events = get_scenario(s_id)
        assert len(events) > 0
        for ev in events:
            pub = ev.public_payload()
            verify_no_ground_truth_leakage(pub)


# =============================================================================
# 4. R5.3 CLI Invocations and Subprocess Verification
# =============================================================================

def _get_subprocess_kwargs():
    from pathlib import Path
    karen_dir = str(Path(__file__).resolve().parent.parent.parent)
    env = dict(os.environ)
    env["PYTHONPATH"] = karen_dir + (os.pathsep + env["PYTHONPATH"] if "PYTHONPATH" in env else "")
    return {"cwd": karen_dir, "env": env}


def test_cli_list_scenarios_subprocess():
    """Verify `python -m simulator.cli --list-scenarios` exits 0 and prints scenario IDs."""
    cmd = [sys.executable, "-m", "simulator.cli", "--list-scenarios"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, **_get_subprocess_kwargs())
    assert result.returncode == 0
    lines = [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
    assert "flood_rasulgarh" in lines
    assert "mixed_hard_negatives" in lines


def test_cli_dry_run_speed_zero_subprocess():
    """Verify `python -m simulator.cli --scenario flood_rasulgarh --speed 0 --dry-run` succeeds."""
    cmd = [sys.executable, "-m", "simulator.cli", "--scenario", "flood_rasulgarh", "--speed", "0", "--dry-run"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, **_get_subprocess_kwargs())
    assert result.returncode == 0
    assert "SIMULATION PLAYBACK COMPLETED" in result.stdout
    assert "Dispatched Events:       15 / 15" in result.stdout
    assert "Ground-Truth Firewall:   PASSED" in result.stdout


def test_cli_export_public_subprocess(tmp_path):
    """Verify `python -m simulator.cli --scenario flood_rasulgarh --export-public <path>` works."""
    export_path = str(tmp_path / "export_test.json")
    cmd = [sys.executable, "-m", "simulator.cli", "--scenario", "flood_rasulgarh", "--export-public", export_path]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, **_get_subprocess_kwargs())
    assert result.returncode == 0
    assert os.path.exists(export_path)

    with open(export_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert isinstance(data, list)
    assert len(data) == 15
    # Strict firewall audit on the exported data
    verify_no_ground_truth_leakage(data)
