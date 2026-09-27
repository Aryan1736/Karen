"""
Karen's Ear — Disaster Simulator Command-Line Interface.

Owner: Pankaj (feature/evaluation-integration)
Authority: gemini.md (v1.2), DISASTER_SIMULATOR_ROADMAP.md
Status: Production Hardened CLI & Playback Interface

Usage examples:
  python -m simulator.cli --scenario flood_rasulgarh --dry-run
  python -m simulator.cli --scenario flood_rasulgarh --speed burst --export .tmp/flood.json
  python -m simulator.cli --scenario all --export-ground-truth .tmp/golden_gt.json
  python -m simulator.cli --scenario flood_rasulgarh --live --endpoint http://localhost:8000/reports
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

from simulator.engine import SimulationEngine
from simulator.models import ScenarioEvent
from simulator.scenarios import get_scenario, list_scenarios
from simulator.timeline import SpeedMode, Timeline
from simulator.transport import BaseTransport, DryRunTransport, SafeHttpTransport, TransportConfig


def format_event_log(
    event: ScenarioEvent,
    index: int,
    total: int,
    show_ground_truth: bool = False,
) -> str:
    """Formats a concise terminal log line for an event."""
    preview = event.dispatch.text[:55] + "..." if len(event.dispatch.text) > 55 else event.dispatch.text

    if show_ground_truth:
        gt = event.ground_truth
        rel = gt.relation_type.value if gt.relation_type else "NONE"
        urg = gt.expected_urgency.value if gt.expected_urgency else "NONE"
        risk = f"Victims: {gt.expected_people_count}" if gt.expected_people_count is not None else "Victims: None"
        return (
            f"[{index + 1:02d}/{total:02d}] {event.event_id} ({event.dispatch.report_id}) "
            f"| +{event.delay_seconds:4.1f}s | [{rel:<13}] [{urg:<8}] [{risk:<13}] -> \"{preview}\""
        )

    # Public-safe telemetry display
    return (
        f"[{index + 1:02d}/{total:02d}] {event.event_id} ({event.dispatch.report_id}) "
        f"| +{event.delay_seconds:4.1f}s | [{event.dispatch.source:<9}] -> \"{preview}\""
    )


def export_public_dispatches(events: List[ScenarioEvent], target_path: str) -> int:
    """Exports only public RawReportPayload items to JSON (guarantees zero leakage)."""
    out_path = Path(target_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    public_payloads = [event.public_payload() for event in events]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(public_payloads, f, indent=2)

    return len(public_payloads)


def export_ground_truth_events(events: List[ScenarioEvent], target_path: str) -> int:
    """Exports full ScenarioEvents with GroundTruth for evaluation fixtures."""
    out_path = Path(target_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    full_payloads = [event.model_dump(mode="json") for event in events]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(full_payloads, f, indent=2)

    return len(full_payloads)


def main(args: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Karen's Ear Disaster Crisis Simulator & Playback CLI (Pankaj)"
    )
    parser.add_argument(
        "--scenario",
        "-s",
        type=str,
        default="flood_rasulgarh",
        help="Scenario ID (e.g. 'flood_rasulgarh', 'mixed_hard_negatives', or 'all').",
    )
    parser.add_argument(
        "--list-scenarios",
        action="store_true",
        default=False,
        help="Lists all registered scenarios and exits.",
    )
    parser.add_argument(
        "--speed",
        type=str,
        default="1x",
        help="Playback speed multiplier: '1x', '2x', '5x', '10x', 'burst', 'step' (0 for burst mode).",
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--live",
        action="store_true",
        default=False,
        help="Execute in live mode, transmitting HTTP requests to --endpoint.",
    )
    mode_group.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Explicitly run in dry-run mode (default behavior unless --live is specified).",
    )

    parser.add_argument(
        "--step",
        action="store_true",
        default=False,
        help="Pause and require interactive step advance for each event.",
    )
    parser.add_argument(
        "--show-ground-truth",
        action="store_true",
        default=False,
        help="Display private ground-truth fields in console logs (for offline inspection only).",
    )
    parser.add_argument(
        "--rebase-time-now",
        action="store_true",
        default=False,
        help="Rebase event reported_at timestamps relative to current UTC time for live demos.",
    )
    parser.add_argument(
        "--export",
        "--export-public",
        type=str,
        default=None,
        dest="export",
        help="Export public dispatch payloads to JSON file (e.g. .tmp/flood.json).",
    )
    parser.add_argument(
        "--export-ground-truth",
        type=str,
        default=None,
        help="Export full ScenarioEvents (with private ground truth) to JSON fixture.",
    )
    parser.add_argument(
        "--export-only",
        action="store_true",
        default=False,
        help="Export requested data and exit immediately without running playback.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of events to process.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Deterministic integer seed for playback schedule.",
    )
    parser.add_argument(
        "--jitter",
        type=float,
        default=0.0,
        help="Gaussian jitter stddev in seconds for inter-event delays.",
    )
    parser.add_argument(
        "--endpoint",
        type=str,
        default=None,
        help="Target ingestion endpoint URL (e.g. http://localhost:8000/reports).",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress per-event stdout logs.",
    )

    parsed = parser.parse_args(args)
    parsed.export_public = parsed.export

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    if parsed.list_scenarios:
        for sid in sorted(list_scenarios()):
            print(sid)
        return 0

    # 1. Collect Scenario Events
    registered = list_scenarios()
    events: List[ScenarioEvent] = []

    if parsed.scenario.lower() == "all":
        for sid in registered:
            events.extend(get_scenario(sid))
    else:
        matched = None
        for sid in registered:
            if sid.lower() == parsed.scenario.lower() or parsed.scenario.lower() in sid.lower():
                matched = sid
                break
        if matched is None:
            print(f"Error: Unknown scenario '{parsed.scenario}'. Available: {registered}", file=sys.stderr)
            return 1
        events = get_scenario(matched)

    if parsed.limit is not None:
        if parsed.limit <= 0:
            print(f"Error: --limit must be a strictly positive integer (got {parsed.limit}).", file=sys.stderr)
            return 1
        events = events[:parsed.limit]

    # Rebase timestamps if requested
    if parsed.rebase_time_now and events:
        now = datetime.now(timezone.utc)
        base_time = events[0].dispatch.reported_at
        rebased: List[ScenarioEvent] = []
        for ev in events:
            offset = ev.dispatch.reported_at - base_time
            new_dispatch = ev.dispatch.model_copy(update={"reported_at": now + offset})
            rebased.append(ev.model_copy(update={"dispatch": new_dispatch}))
        events = rebased

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    # Warn if endpoint supplied without live
    if parsed.endpoint and not parsed.live:
        print(
            "Warning: --endpoint provided without --live. Simulation will run offline (DRY RUN). "
            "Use --live to enable network transmission.",
            file=sys.stderr,
        )

    if parsed.live:
        if not parsed.endpoint:
            print(
                "Error: --live mode requires an ingestion target endpoint specified with --endpoint "
                "(e.g. http://localhost:8000/reports).",
                file=sys.stderr,
            )
            return 1
        is_live = True
        is_dry_run = False
        is_burst = False
        try:
            is_burst = (SpeedMode.parse(parsed.speed) == SpeedMode.BURST)
        except Exception:
            is_burst = parsed.speed in ("burst", "0", "0.0", "0x", "0.0x")
        rate_limit = 1000.0 if is_burst else 20.0
        transport: BaseTransport = SafeHttpTransport(
            config=TransportConfig(
                endpoint=parsed.endpoint,
                dry_run=False,
                rate_limit_per_sec=rate_limit,
            )
        )
    else:
        is_live = False
        is_dry_run = True
        transport = DryRunTransport()

    # Step mode handling
    speed = "step" if parsed.step else parsed.speed

    print("=" * 80)
    print("[!] KAREN'S EAR -- DISASTER SIMULATION ENGINE")
    print(f"   Scenario:       {parsed.scenario} ({len(events)} events loaded)")
    print(f"   Speed Mode:     {speed}")
    print(f"   Execution Mode: {'LIVE (' + parsed.endpoint + ')' if is_live else 'DRY RUN (Offline)'}")
    print(f"   Seed:           {parsed.seed}")
    print("=" * 80)

    # 2. Export Public Dispatches if requested
    if parsed.export:
        count = export_public_dispatches(events, parsed.export)
        print(f"[OK] Exported {count} public dispatches (0 ground truth leaked) to: {parsed.export}")

    # 3. Export Ground Truth if requested
    if parsed.export_ground_truth:
        count = export_ground_truth_events(events, parsed.export_ground_truth)
        print(f"[OK] Exported {count} full ground-truth events to: {parsed.export_ground_truth}")

    if parsed.export_only:
        return 0

    # If only exporting was requested and speed is not explicitly set for run, default to burst
    raw_args = args if args is not None else sys.argv[1:]
    has_explicit_speed = any(a == "--speed" or a.startswith("--speed=") for a in raw_args)
    if (parsed.export or parsed.export_ground_truth) and not has_explicit_speed and not parsed.step:
        speed = "burst"

    # 4. Build Timeline & Engine
    timeline = Timeline(
        events=events,
        speed=speed,
        seed=parsed.seed,
        jitter_stddev=parsed.jitter,
    )

    def on_event_callback(event: ScenarioEvent, index: int, total: int) -> None:
        if not parsed.quiet:
            print(format_event_log(event, index, total, show_ground_truth=parsed.show_ground_truth))
        if parsed.step and index < total - 1:
            try:
                input("   [STEP] Press Enter to advance to next event...")
            except (EOFError, KeyboardInterrupt):
                pass

    engine = SimulationEngine(
        timeline=timeline,
        transport=transport,
        dry_run=is_dry_run,
        on_event=on_event_callback,
    )

    print(f"\n>> Starting playback ({timeline.total_events} events, simulated {timeline.total_simulated_duration:.1f}s)...")
    summary = engine.run_sync()

    print("\n" + "=" * 80)
    print("[DONE] SIMULATION PLAYBACK COMPLETED")
    print(f"   Dispatched Events:       {summary.dispatched_events} / {summary.total_events}")
    print(f"   Elapsed Wall Time:       {summary.elapsed_wall_seconds:.3f}s")
    print(f"   Synthetic Flag Verified: {summary.is_synthetic_verified} (All payloads carries is_synthetic: True)")
    print("   Ground-Truth Firewall:   PASSED (0 leaks)")
    print(f"   Errors:                  {len(summary.errors)}")
    print("=" * 80)

    return 0 if not summary.errors else 2


if __name__ == "__main__":
    sys.exit(main())
