"""
Karen's Ear — Scenario 2: Adversarial Hard Negatives & Ambient Discrimination.

Scenario ID: mixed_hard_negatives
Hazard Category: MIXED / BENCHMARK
Focus: Adversarial keyword traps, false alarms, drills, slang, ambiguous rumors,
       genuine minor incidents, and unlocated distress calls.
Authority: gemini.md, docs/data-schema.md, architecture/testing.md
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

SCENARIO_ID = "mixed_hard_negatives"
SCENARIO_NAME = "Adversarial Hard Negatives & Ambient Discrimination"
SCENARIO_DESCRIPTION = (
    "A rigorous benchmark suite of 12 challenging adversarial reports designed to test "
    "whether Aryan's NLP and Daksh's correlation rely on naive keyword matching or genuine "
    "semantic understanding. Includes scheduled fire drills, hyperbole, slang, stage pyrotechnics, "
    "unverified rumors, and genuine minor utilities."
)

BASE_TIMESTAMP = datetime(2026, 9, 26, 19, 0, 0, tzinfo=timezone.utc)


def get_mixed_hard_negatives_events() -> List[ScenarioEvent]:
    """Generates the 12 deterministic adversarial scenario events."""
    return [
        # 1. Scheduled Fire Drill (Must NOT trigger Critical Fire alert)
        ScenarioEvent(
            event_id="evt-hn-001",
            delay_seconds=0.0,
            dispatch=RawReportPayload(
                report_id="rep-hn-001",
                text="Annual scheduled fire alarm drill happening at Block C commercial tower at 3 PM, no emergency, do not panic.",
                source="simulator",
                is_synthetic=True,
                reported_at=BASE_TIMESTAMP,
                location_hint=LocationHint(
                    raw_text="Block C commercial tower",
                    latitude=20.3010,
                    longitude=85.8200,
                    precision=LocationPrecision.APPROXIMATE,
                ),
                metadata=ReportMetadata(
                    scenario_id=SCENARIO_ID,
                    event_id="evt-hn-001",
                    phase="drill_notice",
                    batch_index=0,
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
                expected_needs_review=True,
                notes="Hard negative: Scheduled fire drill; must not trigger real fire dispatch.",
            ),
        ),

        # 2. Colloquial Slang & Hyperbole (Must NOT infer casualties)
        ScenarioEvent(
            event_id="evt-hn-002",
            delay_seconds=15.0,
            dispatch=RawReportPayload(
                report_id="rep-hn-002",
                text="This traffic on Cuttack road is absolute murder, I am literally dying laughing at this bus driver cutting across three lanes!",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 19, 0, 15, tzinfo=timezone.utc),
                location_hint=LocationHint(
                    raw_text="Cuttack road",
                    latitude=20.2700,
                    longitude=85.8500,
                    precision=LocationPrecision.APPROXIMATE,
                ),
                metadata=ReportMetadata(
                    scenario_id=SCENARIO_ID,
                    event_id="evt-hn-002",
                    phase="slang_test",
                    batch_index=1,
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
                notes="Hard negative: 'murder' and 'dying' used colloquially; zero casualties.",
            ),
        ),

        # 3. Stage Effect / Event Testing (Must NOT trigger structural/fire response)
        ScenarioEvent(
            event_id="evt-hn-003",
            delay_seconds=20.0,
            dispatch=RawReportPayload(
                report_id="rep-hn-003",
                text="Testing high-power fog and smoke machines at the open-air auditorium for tonight's cultural festival.",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 19, 0, 35, tzinfo=timezone.utc),
                location_hint=LocationHint(
                    raw_text="open-air auditorium",
                    latitude=20.3150,
                    longitude=85.8300,
                    precision=LocationPrecision.APPROXIMATE,
                ),
                metadata=ReportMetadata(
                    scenario_id=SCENARIO_ID,
                    event_id="evt-hn-003",
                    phase="stage_effects",
                    batch_index=2,
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
                notes="Hard negative: Artificial fog/smoke test; zero fire hazard.",
            ),
        ),

        # 4. Unverified Third-Hand Blast Rumor (Must flag for operator review)
        ScenarioEvent(
            event_id="evt-hn-004",
            delay_seconds=25.0,
            dispatch=RawReportPayload(
                report_id="rep-hn-004",
                text="Someone in WhatsApp group said there might have been a cylinder blast near Patia, but I looked outside and saw nothing at all.",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 19, 1, 0, tzinfo=timezone.utc),
                location_hint=LocationHint(
                    raw_text="near Patia",
                    latitude=20.3540,
                    longitude=85.8180,
                    precision=LocationPrecision.APPROXIMATE,
                ),
                metadata=ReportMetadata(
                    scenario_id=SCENARIO_ID,
                    event_id="evt-hn-004",
                    phase="unverified_rumor",
                    batch_index=3,
                ),
            ),
            ground_truth=GroundTruth(
                incident_group=None,
                expected_incident_type=None,
                expected_urgency=GroundTruthUrgency.LOW,
                expected_people_at_risk=False,
                expected_people_count=None,
                relation_type=GroundTruthRelationType.UNCERTAIN,
                expected_direction=ExpectedQueueDirection.LOW_PRIORITY,
                expected_needs_review=True,
                notes="Hard negative: Hearsay rumor without eyewitness corroboration; requires operator review.",
            ),
        ),

        # 5. Sports Metaphorical Speech (Must NOT trigger explosion/threat)
        ScenarioEvent(
            event_id="evt-hn-005",
            delay_seconds=20.0,
            dispatch=RawReportPayload(
                report_id="rep-hn-005",
                text="Our cricket team just exploded on the scoreboard, killing the competition in today's tournament match!",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 19, 1, 20, tzinfo=timezone.utc),
                location_hint=None,
                metadata=ReportMetadata(
                    scenario_id=SCENARIO_ID,
                    event_id="evt-hn-005",
                    phase="metaphor_test",
                    batch_index=4,
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
                notes="Hard negative: Sports metaphor ('exploded', 'killing'); zero crisis relevance.",
            ),
        ),

        # 6. Harmless Weather Query (Must stay LOW)
        ScenarioEvent(
            event_id="evt-hn-006",
            delay_seconds=15.0,
            dispatch=RawReportPayload(
                report_id="rep-hn-006",
                text="Is it raining heavily in Bhubaneswar right now? Planning to drive down from Puri this evening.",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 19, 1, 35, tzinfo=timezone.utc),
                location_hint=LocationHint(
                    raw_text="Bhubaneswar",
                    latitude=20.2960,
                    longitude=85.8245,
                    precision=LocationPrecision.APPROXIMATE,
                ),
                metadata=ReportMetadata(
                    scenario_id=SCENARIO_ID,
                    event_id="evt-hn-006",
                    phase="weather_query",
                    batch_index=5,
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
                notes="Hard negative: Weather inquiry; zero hazard.",
            ),
        ),

        # 7. Genuine Domestic Minor Fire (Must classify correctly as FIRE but LOW urgency)
        ScenarioEvent(
            event_id="evt-hn-007",
            delay_seconds=25.0,
            dispatch=RawReportPayload(
                report_id="rep-hn-007",
                text="Small grease fire on stovetop in Unit 4 kitchen, extinguished with wet blanket, minor smoke in corridor.",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 19, 2, 0, tzinfo=timezone.utc),
                location_hint=LocationHint(
                    raw_text="Unit 4 kitchen",
                    latitude=20.2850,
                    longitude=85.8150,
                    precision=LocationPrecision.APPROXIMATE,
                ),
                metadata=ReportMetadata(
                    scenario_id=SCENARIO_ID,
                    event_id="evt-hn-007",
                    phase="minor_fire",
                    batch_index=6,
                ),
            ),
            ground_truth=GroundTruth(
                incident_group="bbsr-minor-fire-01",
                expected_incident_type=GroundTruthIncidentType.FIRE_WILDFIRE_EXPLOSION,
                expected_urgency=GroundTruthUrgency.LOW,
                expected_people_at_risk=False,
                expected_people_count=0,
                relation_type=GroundTruthRelationType.INITIAL,
                expected_direction=ExpectedQueueDirection.LOW_PRIORITY,
                notes="Genuine fire hazard, but already contained; correctly classified as LOW urgency.",
            ),
        ),

        # 8. Genuine Utility Hazard (Must classify as UTILITY with MEDIUM urgency)
        ScenarioEvent(
            event_id="evt-hn-008",
            delay_seconds=20.0,
            dispatch=RawReportPayload(
                report_id="rep-hn-008",
                text="Downed live electric wire sparking across street after tree branch fell near Forest Park road, vehicles turning around.",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 19, 2, 20, tzinfo=timezone.utc),
                location_hint=LocationHint(
                    raw_text="Forest Park road",
                    latitude=20.2550,
                    longitude=85.8280,
                    precision=LocationPrecision.APPROXIMATE,
                ),
                metadata=ReportMetadata(
                    scenario_id=SCENARIO_ID,
                    event_id="evt-hn-008",
                    phase="utility_wire",
                    batch_index=7,
                ),
            ),
            ground_truth=GroundTruth(
                incident_group="bbsr-utility-wire-01",
                expected_incident_type=GroundTruthIncidentType.UTILITY_INFRASTRUCTURE_FAILURE,
                expected_urgency=GroundTruthUrgency.MEDIUM,
                expected_people_at_risk=False,
                expected_people_count=0,
                relation_type=GroundTruthRelationType.INITIAL,
                expected_direction=ExpectedQueueDirection.ESCALATE,
                notes="Live electrical wire hazard; requires public works/utility response.",
            ),
        ),

        # 9. Shallow Water Puddle (Must NOT escalate to flash flood emergency)
        ScenarioEvent(
            event_id="evt-hn-009",
            delay_seconds=15.0,
            dispatch=RawReportPayload(
                report_id="rep-hn-009",
                text="Minor water puddle about 6 inches deep near Baramunda bus stand, buses passing through normally.",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 19, 2, 35, tzinfo=timezone.utc),
                location_hint=LocationHint(
                    raw_text="Baramunda bus stand",
                    latitude=20.2780,
                    longitude=85.7950,
                    precision=LocationPrecision.APPROXIMATE,
                ),
                metadata=ReportMetadata(
                    scenario_id=SCENARIO_ID,
                    event_id="evt-hn-009",
                    phase="minor_water",
                    batch_index=8,
                ),
            ),
            ground_truth=GroundTruth(
                incident_group=None,
                expected_incident_type=GroundTruthIncidentType.FLOOD_FLASH_FLOOD,
                expected_urgency=GroundTruthUrgency.LOW,
                expected_people_at_risk=False,
                expected_people_count=0,
                relation_type=GroundTruthRelationType.INITIAL,
                expected_direction=ExpectedQueueDirection.LOW_PRIORITY,
                notes="Minor water logging without life risk; must stay in LOW tier.",
            ),
        ),

        # 10. Spam Prank / Hoax Dispatch (Must flag for review)
        ScenarioEvent(
            event_id="evt-hn-010",
            delay_seconds=20.0,
            dispatch=RawReportPayload(
                report_id="rep-hn-010",
                text="Zombie apocalypse spotted near Big Bazaar square, send the military lol!",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 19, 2, 55, tzinfo=timezone.utc),
                location_hint=LocationHint(
                    raw_text="Big Bazaar square",
                    latitude=20.2880,
                    longitude=85.8350,
                    precision=LocationPrecision.APPROXIMATE,
                ),
                metadata=ReportMetadata(
                    scenario_id=SCENARIO_ID,
                    event_id="evt-hn-010",
                    phase="hoax_test",
                    batch_index=9,
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
                expected_needs_review=True,
                notes="Spam/hoax text; must be flagged for review or marked FALSE_REPORT.",
            ),
        ),

        # 11. Past Recovery Status Update (Must NOT trigger active response)
        ScenarioEvent(
            event_id="evt-hn-011",
            delay_seconds=20.0,
            dispatch=RawReportPayload(
                report_id="rep-hn-011",
                text="Road has been cleared and debris removed from yesterday's storm near Airport road, traffic restored.",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 19, 3, 15, tzinfo=timezone.utc),
                location_hint=LocationHint(
                    raw_text="Airport road",
                    latitude=20.2520,
                    longitude=85.8180,
                    precision=LocationPrecision.APPROXIMATE,
                ),
                metadata=ReportMetadata(
                    scenario_id=SCENARIO_ID,
                    event_id="evt-hn-011",
                    phase="past_recovery",
                    batch_index=10,
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
                notes="Historical recovery notice; no active response needed.",
            ),
        ),

        # 12. Vague Unlocated Chemical Distress (Must preserve null coordinates)
        ScenarioEvent(
            event_id="evt-hn-012",
            delay_seconds=25.0,
            dispatch=RawReportPayload(
                report_id="rep-hn-012",
                text="Strong smell of ammonia or toxic chemical in the air somewhere in industrial area, eyes stinging slightly.",
                source="simulator",
                is_synthetic=True,
                reported_at=datetime(2026, 9, 26, 19, 3, 40, tzinfo=timezone.utc),
                location_hint=LocationHint(
                    raw_text="somewhere in industrial area",
                    latitude=None,
                    longitude=None,
                    precision=LocationPrecision.UNKNOWN,
                ),
                metadata=ReportMetadata(
                    scenario_id=SCENARIO_ID,
                    event_id="evt-hn-012",
                    phase="unlocated_hazard",
                    batch_index=11,
                ),
            ),
            ground_truth=GroundTruth(
                incident_group="bbsr-chem-unlocated-01",
                expected_incident_type=GroundTruthIncidentType.FIRE_WILDFIRE_EXPLOSION,
                expected_urgency=GroundTruthUrgency.MEDIUM,
                expected_people_at_risk=False,
                expected_people_count=None,
                relation_type=GroundTruthRelationType.INITIAL,
                expected_direction=ExpectedQueueDirection.ESCALATE,
                expected_needs_review=True,
                notes="Unlocated chemical hazard; coordinates must remain null without hallucination.",
            ),
        ),
    ]
