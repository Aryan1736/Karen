"""
Karen's Ear — Scenario 1: Bhubaneswar Flash Flood & Underpass Submersion.

Scenario ID: flood_rasulgarh
Hazard Category: FLOOD_FLASH_FLOOD
Focus: Urban flash flooding, trapped vehicle life-safety surge, duplicate echo suppression,
       multi-source eyewitness corroboration, cascading electrical hazard, and ambient noise.
Authority: gemini.md, docs/data-schema.md, architecture/simulation.md
"""

from datetime import datetime, timezone
from typing import List

from simulator.models import (
    ExpectedQueueDirection,
    GroundTruth,
    GroundTruthIncidentType,
    GroundTruthRelationType,
    GroundTruthUrgency,
    LocationHint,
    LocationPrecision,
    RawReportPayload,
    ReportMetadata,
    ScenarioEvent,
)

SCENARIO_ID = "flood_rasulgarh"
SCENARIO_NAME = "Bhubaneswar Flash Flood & Underpass Submersion"
SCENARIO_DESCRIPTION = (
    "Monsoon cloudburst triggers rapid urban flooding at Rasulgarh railway underpass. "
    "Demonstrates progression from low-level street waterlogging to a critical trapped-vehicle "
    "emergency with 4 passengers, followed by independent corroboration, echo duplicates, "
    "cascading electrical hazards, and ambient distractor noise."
)

BASE_TIMESTAMP = datetime(2026, 9, 26, 18, 0, 0, tzinfo=timezone.utc)


def get_flood_rasulgarh_events() -> List[ScenarioEvent]:
    """Generates the 15 deterministic scenario events for flood_rasulgarh."""
    return [
        # Phase 1: Early Ambient & Municipal Advisory (T0 - T+45s)
        ScenarioEvent(
            event_id="evt-flood-001",
            delay_seconds=0.0,
            dispatch=RawReportPayload(
                report_id="rep-fld-001",
                text="Heavy rain causing water logging starting near Rasulgarh square. Drainage appears blocked.",
                source="simulator",
                is_synthetic=True,
                reported_at=BASE_TIMESTAMP,
                location_hint=LocationHint(
                    raw_text="Rasulgarh square",
                    latitude=20.2961,
                    longitude=85.8245,
                    precision=LocationPrecision.APPROXIMATE,
                ),
                metadata=ReportMetadata(
                    scenario_id=SCENARIO_ID,
                    event_id="evt-flood-001",
                    phase="T0",
                    channel="twitter_public",
                    batch_index=0,
                ),
            ),
            ground_truth=GroundTruth(
                incident_group="bbsr-flood-rasulgarh-01",
                expected_incident_type=GroundTruthIncidentType.FLOOD_FLASH_FLOOD,
                expected_urgency=GroundTruthUrgency.LOW,
                expected_people_at_risk=False,
                expected_people_count=0,
                relation_type=GroundTruthRelationType.INITIAL,
                expected_direction=ExpectedQueueDirection.LOW_PRIORITY,
                expected_needs_review=False,
                notes="Early waterlogging advisory without life threat.",
            ),
        ),
        ScenarioEvent(
            event_id="evt-flood-002",
            delay_seconds=20.0,
            dispatch=RawReportPayload(
                report_id="rep-fld-002",
                text="Vehicles moving very slowly near Rasulgarh flyover, rain getting heavier by the minute.",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 18, 0, 20, tzinfo=timezone.utc),
                location_hint=LocationHint(
                    raw_text="Rasulgarh flyover",
                    latitude=20.2965,
                    longitude=85.8240,
                    precision=LocationPrecision.APPROXIMATE,
                ),
                metadata=ReportMetadata(
                    scenario_id=SCENARIO_ID,
                    event_id="evt-flood-002",
                    phase="T+20s",
                    channel="citizen_sms",
                    batch_index=1,
                ),
            ),
            ground_truth=GroundTruth(
                incident_group="bbsr-flood-rasulgarh-01",
                expected_incident_type=GroundTruthIncidentType.FLOOD_FLASH_FLOOD,
                expected_urgency=GroundTruthUrgency.LOW,
                expected_people_at_risk=False,
                expected_people_count=0,
                relation_type=GroundTruthRelationType.CORROBORATING,
                expected_direction=ExpectedQueueDirection.LOW_PRIORITY,
                notes="Traffic slowdown confirmation.",
            ),
        ),
        ScenarioEvent(
            event_id="evt-flood-003",
            delay_seconds=25.0,
            dispatch=RawReportPayload(
                report_id="rep-fld-003",
                text="Water level rising rapidly on service road under railway bridge near Rasulgarh, 2 feet water.",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 18, 0, 45, tzinfo=timezone.utc),
                location_hint=LocationHint(
                    raw_text="service road under railway bridge Rasulgarh",
                    latitude=20.2958,
                    longitude=85.8248,
                    precision=LocationPrecision.APPROXIMATE,
                ),
                metadata=ReportMetadata(
                    scenario_id=SCENARIO_ID,
                    event_id="evt-flood-003",
                    phase="T+45s",
                    channel="police_radio",
                    batch_index=2,
                ),
            ),
            ground_truth=GroundTruth(
                incident_group="bbsr-flood-rasulgarh-01",
                expected_incident_type=GroundTruthIncidentType.FLOOD_FLASH_FLOOD,
                expected_urgency=GroundTruthUrgency.MEDIUM,
                expected_people_at_risk=False,
                expected_people_count=0,
                relation_type=GroundTruthRelationType.CORROBORATING,
                expected_direction=ExpectedQueueDirection.ESCALATE,
                notes="Rapid water accumulation, approaching hazard threshold.",
            ),
        ),

        # Phase 2: The Critical Trigger (T+75s)
        ScenarioEvent(
            event_id="evt-flood-004",
            delay_seconds=30.0,
            dispatch=RawReportPayload(
                report_id="rep-fld-004",
                text="URGENT: White Maruti van stuck under Rasulgarh underpass! Water reaching window level, 4 people trapped inside screaming for help!",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 18, 1, 15, tzinfo=timezone.utc),
                location_hint=LocationHint(
                    raw_text="Rasulgarh underpass",
                    latitude=20.2960,
                    longitude=85.8245,
                    precision=LocationPrecision.APPROXIMATE,
                ),
                metadata=ReportMetadata(
                    scenario_id=SCENARIO_ID,
                    event_id="evt-flood-004",
                    phase="T+75s",
                    channel="emergency_hotline",
                    caller_id="sim-caller-001",
                    batch_index=3,
                ),
            ),
            ground_truth=GroundTruth(
                incident_group="bbsr-flood-rasulgarh-01",
                expected_incident_type=GroundTruthIncidentType.FLOOD_FLASH_FLOOD,
                expected_urgency=GroundTruthUrgency.CRITICAL,
                expected_people_at_risk=True,
                expected_people_count=4,
                relation_type=GroundTruthRelationType.CORROBORATING,
                expected_direction=ExpectedQueueDirection.ESCALATE_TO_TOP,
                expected_needs_review=False,
                notes="Critical life-safety trigger: 4 passengers trapped in submerged vehicle.",
            ),
        ),

        # Phase 3: Multi-Source Independent Eyewitness Corroboration (T+95s - T+140s)
        ScenarioEvent(
            event_id="evt-flood-005",
            delay_seconds=20.0,
            dispatch=RawReportPayload(
                report_id="rep-fld-005",
                text="4 passengers trapped in submerged white van at Rasulgarh railway bridge, water rising fast please send rescue boats!",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 18, 1, 35, tzinfo=timezone.utc),
                location_hint=LocationHint(
                    raw_text="Rasulgarh railway bridge",
                    latitude=20.2959,
                    longitude=85.8246,
                    precision=LocationPrecision.APPROXIMATE,
                ),
                metadata=ReportMetadata(
                    scenario_id=SCENARIO_ID,
                    event_id="evt-flood-005",
                    phase="T+95s",
                    channel="citizen_call",
                    caller_id="sim-caller-002",
                    batch_index=4,
                ),
            ),
            ground_truth=GroundTruth(
                incident_group="bbsr-flood-rasulgarh-01",
                expected_incident_type=GroundTruthIncidentType.FLOOD_FLASH_FLOOD,
                expected_urgency=GroundTruthUrgency.CRITICAL,
                expected_people_at_risk=True,
                expected_people_count=4,
                relation_type=GroundTruthRelationType.CORROBORATING,
                expected_direction=ExpectedQueueDirection.ESCALATE_TO_TOP,
                notes="Independent witness #1 corroborating trapped passengers.",
            ),
        ),
        ScenarioEvent(
            event_id="evt-flood-006",
            delay_seconds=15.0,
            dispatch=RawReportPayload(
                report_id="rep-fld-006",
                text="Eyewitness at Rasulgarh: Van completely underwater, people banging on glass from inside! Rescue needed immediately!",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 18, 1, 50, tzinfo=timezone.utc),
                location_hint=LocationHint(
                    raw_text="Rasulgarh",
                    latitude=20.2961,
                    longitude=85.8245,
                    precision=LocationPrecision.APPROXIMATE,
                ),
                metadata=ReportMetadata(
                    scenario_id=SCENARIO_ID,
                    event_id="evt-flood-006",
                    phase="T+110s",
                    channel="twitter_public",
                    reporter_id="sim-source-001",
                    batch_index=5,
                ),
            ),
            ground_truth=GroundTruth(
                incident_group="bbsr-flood-rasulgarh-01",
                expected_incident_type=GroundTruthIncidentType.FLOOD_FLASH_FLOOD,
                expected_urgency=GroundTruthUrgency.CRITICAL,
                expected_people_at_risk=True,
                expected_people_count=4,
                relation_type=GroundTruthRelationType.CORROBORATING,
                expected_direction=ExpectedQueueDirection.ESCALATE_TO_TOP,
                notes="Independent witness #2 confirming active distress.",
            ),
        ),
        ScenarioEvent(
            event_id="evt-flood-007",
            delay_seconds=15.0,
            dispatch=RawReportPayload(
                report_id="rep-fld-007",
                text="Rasulgarh underpass is a deathtrap right now, family of 4 stuck in drowning vehicle, need emergency response!",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 18, 2, 5, tzinfo=timezone.utc),
                location_hint=LocationHint(
                    raw_text="Rasulgarh underpass",
                    latitude=20.2960,
                    longitude=85.8245,
                    precision=LocationPrecision.APPROXIMATE,
                ),
                metadata=ReportMetadata(
                    scenario_id=SCENARIO_ID,
                    event_id="evt-flood-007",
                    phase="T+125s",
                    channel="citizen_call",
                    caller_id="sim-caller-003",
                    batch_index=6,
                ),
            ),
            ground_truth=GroundTruth(
                incident_group="bbsr-flood-rasulgarh-01",
                expected_incident_type=GroundTruthIncidentType.FLOOD_FLASH_FLOOD,
                expected_urgency=GroundTruthUrgency.CRITICAL,
                expected_people_at_risk=True,
                expected_people_count=4,
                relation_type=GroundTruthRelationType.CORROBORATING,
                expected_direction=ExpectedQueueDirection.ESCALATE_TO_TOP,
                notes="Independent witness #3 confirming family trapped.",
            ),
        ),

        # Phase 4: Viral Duplicate Amplification & Echo Suppression (T+140s - T+165s)
        ScenarioEvent(
            event_id="evt-flood-008",
            delay_seconds=15.0,
            dispatch=RawReportPayload(
                report_id="rep-fld-008",
                text="RT @sim_eyewitness_bbsr: URGENT: White Maruti van stuck under Rasulgarh underpass! Water reaching window level, 4 people trapped inside screaming for help!",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 18, 2, 20, tzinfo=timezone.utc),
                location_hint=LocationHint(
                    raw_text="Rasulgarh underpass",
                    latitude=20.2960,
                    longitude=85.8245,
                    precision=LocationPrecision.APPROXIMATE,
                ),
                metadata=ReportMetadata(
                    scenario_id=SCENARIO_ID,
                    event_id="evt-flood-008",
                    phase="T+140s",
                    channel="twitter_retweet",
                    batch_index=7,
                ),
            ),
            ground_truth=GroundTruth(
                incident_group="bbsr-flood-rasulgarh-01",
                expected_incident_type=GroundTruthIncidentType.FLOOD_FLASH_FLOOD,
                expected_urgency=GroundTruthUrgency.CRITICAL,
                expected_people_at_risk=True,
                expected_people_count=4,
                relation_type=GroundTruthRelationType.DUPLICATE,
                expected_direction=ExpectedQueueDirection.STABLE,
                notes="Near-verbatim retweet; must NOT increment independent source count.",
            ),
        ),
        ScenarioEvent(
            event_id="evt-flood-009",
            delay_seconds=10.0,
            dispatch=RawReportPayload(
                report_id="rep-fld-009",
                text="White Maruti van stuck under Rasulgarh underpass! Water reaching window level, 4 people trapped inside screaming for help!",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 18, 2, 30, tzinfo=timezone.utc),
                location_hint=LocationHint(
                    raw_text="Rasulgarh underpass",
                    latitude=20.2960,
                    longitude=85.8245,
                    precision=LocationPrecision.APPROXIMATE,
                ),
                metadata=ReportMetadata(
                    scenario_id=SCENARIO_ID,
                    event_id="evt-flood-009",
                    phase="T+150s",
                    channel="whatsapp_forward",
                    batch_index=8,
                ),
            ),
            ground_truth=GroundTruth(
                incident_group="bbsr-flood-rasulgarh-01",
                expected_incident_type=GroundTruthIncidentType.FLOOD_FLASH_FLOOD,
                expected_urgency=GroundTruthUrgency.CRITICAL,
                expected_people_at_risk=True,
                expected_people_count=4,
                relation_type=GroundTruthRelationType.DUPLICATE,
                expected_direction=ExpectedQueueDirection.STABLE,
                notes="Exact duplicate forward; deduplication engine must fuse without score surge.",
            ),
        ),

        # Phase 5: Conflicting Bystander Rumor (T+165s)
        ScenarioEvent(
            event_id="evt-flood-010",
            delay_seconds=15.0,
            dispatch=RawReportPayload(
                report_id="rep-fld-010",
                text="I heard someone say 10 people drowned at Rasulgarh underpass already!",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 18, 2, 45, tzinfo=timezone.utc),
                location_hint=LocationHint(
                    raw_text="Rasulgarh underpass",
                    latitude=20.2960,
                    longitude=85.8245,
                    precision=LocationPrecision.APPROXIMATE,
                ),
                metadata=ReportMetadata(
                    scenario_id=SCENARIO_ID,
                    event_id="evt-flood-010",
                    phase="T+165s",
                    channel="twitter_public",
                    batch_index=9,
                ),
            ),
            ground_truth=GroundTruth(
                incident_group="bbsr-flood-rasulgarh-01",
                expected_incident_type=GroundTruthIncidentType.FLOOD_FLASH_FLOOD,
                expected_urgency=GroundTruthUrgency.CRITICAL,
                expected_people_at_risk=True,
                expected_people_count=None,
                relation_type=GroundTruthRelationType.UNCERTAIN,
                expected_direction=ExpectedQueueDirection.STABLE,
                expected_needs_review=True,
                notes="Conflicting casualty rumor; requires operator review flag without corrupting ground truth.",
            ),
        ),

        # Phase 6: Secondary Ripple Effects & Infrastructure Cascading (T+180s - T+220s)
        ScenarioEvent(
            event_id="evt-flood-011",
            delay_seconds=15.0,
            dispatch=RawReportPayload(
                report_id="rep-fld-011",
                text="Massive traffic gridlock stretching 2 km from Vani Vihar toward Rasulgarh due to underpass flooding.",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 18, 3, 0, tzinfo=timezone.utc),
                location_hint=LocationHint(
                    raw_text="Vani Vihar toward Rasulgarh",
                    latitude=20.3015,
                    longitude=85.8310,
                    precision=LocationPrecision.APPROXIMATE,
                ),
                metadata=ReportMetadata(
                    scenario_id=SCENARIO_ID,
                    event_id="evt-flood-011",
                    phase="T+180s",
                    channel="traffic_police",
                    batch_index=10,
                ),
            ),
            ground_truth=GroundTruth(
                incident_group="bbsr-flood-rasulgarh-01",
                expected_incident_type=GroundTruthIncidentType.FLOOD_FLASH_FLOOD,
                expected_urgency=GroundTruthUrgency.MEDIUM,
                expected_people_at_risk=False,
                expected_people_count=0,
                relation_type=GroundTruthRelationType.RELATED,
                expected_direction=ExpectedQueueDirection.STABLE,
                notes="Secondary traffic consequence linked to flood.",
            ),
        ),
        ScenarioEvent(
            event_id="evt-flood-012",
            delay_seconds=20.0,
            dispatch=RawReportPayload(
                report_id="rep-fld-012",
                text="Electric transformer sparking near floodwater at Rasulgarh market junction, power cut across block.",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 18, 3, 20, tzinfo=timezone.utc),
                location_hint=LocationHint(
                    raw_text="Rasulgarh market junction",
                    latitude=20.2970,
                    longitude=85.8250,
                    precision=LocationPrecision.APPROXIMATE,
                ),
                metadata=ReportMetadata(
                    scenario_id=SCENARIO_ID,
                    event_id="evt-flood-012",
                    phase="T+200s",
                    channel="citizen_call",
                    batch_index=11,
                ),
            ),
            ground_truth=GroundTruth(
                incident_group="bbsr-flood-rasulgarh-01",
                expected_incident_type=GroundTruthIncidentType.UTILITY_INFRASTRUCTURE_FAILURE,
                expected_urgency=GroundTruthUrgency.MEDIUM,
                expected_people_at_risk=False,
                expected_people_count=0,
                relation_type=GroundTruthRelationType.RELATED,
                expected_direction=ExpectedQueueDirection.STABLE,
                notes="Related utility hazard in flood zone.",
            ),
        ),
        ScenarioEvent(
            event_id="evt-flood-013",
            delay_seconds=20.0,
            dispatch=RawReportPayload(
                report_id="rep-fld-013",
                text="Electrical pole collapsed into rising flood water near trapped van, rescue team needs electricity shutdown immediately!",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 18, 3, 40, tzinfo=timezone.utc),
                location_hint=LocationHint(
                    raw_text="near trapped van Rasulgarh underpass",
                    latitude=20.2960,
                    longitude=85.8245,
                    precision=LocationPrecision.APPROXIMATE,
                ),
                metadata=ReportMetadata(
                    scenario_id=SCENARIO_ID,
                    event_id="evt-flood-013",
                    phase="T+220s",
                    channel="fire_dispatch",
                    batch_index=12,
                ),
            ),
            ground_truth=GroundTruth(
                incident_group="bbsr-flood-rasulgarh-01",
                expected_incident_type=GroundTruthIncidentType.FLOOD_FLASH_FLOOD,
                expected_urgency=GroundTruthUrgency.CRITICAL,
                expected_people_at_risk=True,
                expected_people_count=4,
                relation_type=GroundTruthRelationType.CORROBORATING,
                expected_direction=ExpectedQueueDirection.ESCALATE_TO_TOP,
                notes="Cascading electrical threat to trapped victims.",
            ),
        ),

        # Phase 7: Ambient Noise & Unrelated Distractors (T+240s - T+260s)
        ScenarioEvent(
            event_id="evt-flood-014",
            delay_seconds=20.0,
            dispatch=RawReportPayload(
                report_id="rep-fld-014",
                text="Best monsoon pakoras available at Master Canteen stall today, enjoy the rain everyone!",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 18, 4, 0, tzinfo=timezone.utc),
                location_hint=LocationHint(
                    raw_text="Master Canteen stall",
                    latitude=20.2660,
                    longitude=85.8430,
                    precision=LocationPrecision.APPROXIMATE,
                ),
                metadata=ReportMetadata(
                    scenario_id=SCENARIO_ID,
                    event_id="evt-flood-014",
                    phase="T+240s",
                    channel="twitter_public",
                    batch_index=13,
                ),
            ),
            ground_truth=GroundTruth(
                incident_group=None,
                expected_incident_type=None,
                expected_urgency=GroundTruthUrgency.LOW,
                expected_people_at_risk=False,
                expected_people_count=0,
                relation_type=GroundTruthRelationType.NOISE,
                expected_direction=ExpectedQueueDirection.LOW_PRIORITY,
                expected_needs_review=False,
                notes="Irrelevant social media noise.",
            ),
        ),
        ScenarioEvent(
            event_id="evt-flood-015",
            delay_seconds=20.0,
            dispatch=RawReportPayload(
                report_id="rep-fld-015",
                text="Anyone know if colleges in Patia are closed tomorrow because of rain?",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 18, 4, 20, tzinfo=timezone.utc),
                location_hint=LocationHint(
                    raw_text="Patia",
                    latitude=20.3540,
                    longitude=85.8180,
                    precision=LocationPrecision.APPROXIMATE,
                ),
                metadata=ReportMetadata(
                    scenario_id=SCENARIO_ID,
                    event_id="evt-flood-015",
                    phase="T+260s",
                    channel="student_query",
                    batch_index=14,
                ),
            ),
            ground_truth=GroundTruth(
                incident_group=None,
                expected_incident_type=None,
                expected_urgency=GroundTruthUrgency.LOW,
                expected_people_at_risk=False,
                expected_people_count=0,
                relation_type=GroundTruthRelationType.NOISE,
                expected_direction=ExpectedQueueDirection.LOW_PRIORITY,
                expected_needs_review=False,
                notes="General weather query noise.",
            ),
        ),
    ]
