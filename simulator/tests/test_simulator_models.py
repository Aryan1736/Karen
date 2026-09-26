"""
Karen's Ear — Phase 1 Test Suite: Simulator Models & Ground-Truth Schema.

Owner: Pankaj (feature/evaluation-integration)
Authority: gemini.md, docs/data-schema.md, docs/api-contract.md
Status: Phase 1 — Models & Ground-Truth Foundation

Tests:
  TEST 1: Valid RawReportPayload construction
  TEST 2: Synthetic invariant enforcement (is_synthetic=False must fail)
  TEST 3: Source invariant enforcement (source != 'simulator' must fail)
  TEST 4: Missing required fields and text length bounds (< 3 or > 4000)
  TEST 5: Location with approximate text and null coordinates (ADR-009)
  TEST 6: Location with unknown precision and null coordinates
  TEST 7: Scenario delay validation (delay_seconds < 0 fails, >= 0 passes)
  TEST 8: GroundTruth standalone existence & partial/ambiguous field support
  TEST 9: Ground-truth isolation (public payload has ZERO private evaluator fields)
  TEST 10: Serialization round trip (Model -> JSON dict -> Model)
  TEST 11: Metadata preservation (scenario_id and event_id survive serialization)
  TEST 12: Simulator safety immutability (cannot construct with is_synthetic=False)
  TEST 13: Timezone-awareness requirement (naive datetime fails, UTC serialized with 'Z')
"""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

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


# =============================================================================
# Helper Fixtures
# =============================================================================

def sample_utc_datetime() -> datetime:
    """Returns a deterministic timezone-aware UTC datetime."""
    return datetime(2026, 9, 26, 18, 15, 0, tzinfo=timezone.utc)


def valid_dispatch_dict() -> dict:
    """Returns a valid dictionary representation of a simulator dispatch."""
    return {
        "report_id": "rep-sim-001",
        "text": "Flash flooding near Rasulgarh underpass. 4 people trapped in white van.",
        "source": "simulator",
        "is_synthetic": True,
        "reported_at": "2026-09-26T18:15:00Z",
        "location_hint": {
            "raw_text": "Rasulgarh underpass",
            "latitude": 20.2961,
            "longitude": 85.8245,
            "precision": "approximate",
        },
        "metadata": {
            "scenario_id": "flood_rasulgarh",
            "event_id": "evt-001",
        },
    }


# =============================================================================
# TEST 1 — Valid Report
# =============================================================================

def test_valid_simulator_raw_report():
    """A correct simulator RawReport validates successfully and matches canonical fields."""
    payload = RawReportPayload(**valid_dispatch_dict())

    assert payload.report_id == "rep-sim-001"
    assert "Rasulgarh" in payload.text
    assert payload.source == "simulator"
    assert payload.is_synthetic is True
    assert payload.reported_at == sample_utc_datetime()
    assert payload.location_hint is not None
    assert payload.location_hint.precision == LocationPrecision.APPROXIMATE
    assert payload.location_hint.latitude == 20.2961
    assert payload.metadata is not None
    assert payload.metadata.scenario_id == "flood_rasulgarh"
    assert payload.metadata.event_id == "evt-001"


# =============================================================================
# TEST 2 — Synthetic Invariant
# =============================================================================

def test_synthetic_invariant_cannot_be_false():
    """Attempting is_synthetic = False must strictly fail validation without silent coercion."""
    data = valid_dispatch_dict()
    data["is_synthetic"] = False

    with pytest.raises(ValidationError) as exc_info:
        RawReportPayload(**data)

    errors = exc_info.value.errors()
    assert any("is_synthetic" in str(err["loc"]) for err in errors)


# =============================================================================
# TEST 3 — Source Invariant
# =============================================================================

def test_source_invariant_must_be_simulator():
    """Simulator dispatches must strictly carry source='simulator'."""
    data = valid_dispatch_dict()
    data["source"] = "manual"

    with pytest.raises(ValidationError) as exc_info:
        RawReportPayload(**data)

    errors = exc_info.value.errors()
    assert any("source" in str(err["loc"]) for err in errors)


# =============================================================================
# TEST 4 — Missing Required Fields & Text Length Constraints
# =============================================================================

def test_missing_required_fields_fails():
    """Missing mandatory canonical fields (report_id, text, reported_at) must fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        RawReportPayload(
            text="Valid length dispatch text.",
            reported_at=sample_utc_datetime(),
            # Missing report_id
        )
    assert any("report_id" in str(err["loc"]) for err in exc_info.value.errors())

    with pytest.raises(ValidationError) as exc_info:
        RawReportPayload(
            report_id="rep-sim-002",
            reported_at=sample_utc_datetime(),
            # Missing text
        )
    assert any("text" in str(err["loc"]) for err in exc_info.value.errors())


def test_text_length_bounds():
    """Text must be between 3 and 4,000 characters per docs/data-schema.md Section 2.1."""
    data = valid_dispatch_dict()

    # Too short (< 3 chars)
    data["text"] = "No"
    with pytest.raises(ValidationError):
        RawReportPayload(**data)

    # Valid minimum (3 chars)
    data["text"] = "SOS"
    valid_payload = RawReportPayload(**data)
    assert valid_payload.text == "SOS"

    # Too long (> 4000 chars)
    data["text"] = "A" * 4001
    with pytest.raises(ValidationError):
        RawReportPayload(**data)

    # Valid maximum (4000 chars)
    data["text"] = "B" * 4000
    valid_max = RawReportPayload(**data)
    assert len(valid_max.text) == 4000


# =============================================================================
# TEST 5 — Approximate Location with Null Coordinates
# =============================================================================

def test_approximate_location_with_null_coordinates():
    """Approximate location text without coordinates must validate without error (ADR-009)."""
    loc = LocationHint(
        raw_text="somewhere near Rasulgarh underpass",
        latitude=None,
        longitude=None,
        precision=LocationPrecision.APPROXIMATE,
    )
    assert loc.raw_text == "somewhere near Rasulgarh underpass"
    assert loc.latitude is None
    assert loc.longitude is None
    assert loc.precision == LocationPrecision.APPROXIMATE

    # In a full report
    data = valid_dispatch_dict()
    data["location_hint"] = loc.model_dump()
    report = RawReportPayload(**data)
    assert report.location_hint.latitude is None
    assert report.location_hint.precision == LocationPrecision.APPROXIMATE


# =============================================================================
# TEST 6 — Unknown Location Handling
# =============================================================================

def test_unknown_location_with_null_fields():
    """Unknown location with null coordinates and unknown precision must validate."""
    loc = LocationHint(
        raw_text=None,
        latitude=None,
        longitude=None,
        precision=LocationPrecision.UNKNOWN,
    )
    assert loc.raw_text is None
    assert loc.latitude is None
    assert loc.longitude is None
    assert loc.precision == LocationPrecision.UNKNOWN

    # location_hint itself can also be None on RawReportPayload
    data = valid_dispatch_dict()
    data["location_hint"] = None
    report = RawReportPayload(**data)
    assert report.location_hint is None


# =============================================================================
# TEST 7 — Scenario Delay Validation
# =============================================================================

def test_scenario_delay_validation():
    """ScenarioEvent delay_seconds must be >= 0.0; negative delays must fail."""
    dispatch = RawReportPayload(**valid_dispatch_dict())
    gt = GroundTruth(incident_group="bbsr-flood-01")

    # Zero delay is valid
    event_zero = ScenarioEvent(
        event_id="evt-001",
        delay_seconds=0.0,
        dispatch=dispatch,
        ground_truth=gt,
    )
    assert event_zero.delay_seconds == 0.0

    # Positive delay is valid
    d_pos = valid_dispatch_dict()
    d_pos["metadata"]["event_id"] = "evt-002"
    dispatch_pos = RawReportPayload(**d_pos)
    event_pos = ScenarioEvent(
        event_id="evt-002",
        delay_seconds=15.5,
        dispatch=dispatch_pos,
        ground_truth=gt,
    )
    assert event_pos.delay_seconds == 15.5

    # Negative delay must fail
    d_neg = valid_dispatch_dict()
    d_neg["metadata"]["event_id"] = "evt-003"
    dispatch_neg = RawReportPayload(**d_neg)
    with pytest.raises(ValidationError) as exc_info:
        ScenarioEvent(
            event_id="evt-003",
            delay_seconds=-5.0,
            dispatch=dispatch_neg,
            ground_truth=gt,
        )
    assert any("delay_seconds" in str(err["loc"]) for err in exc_info.value.errors())


def test_scenario_event_empty_id_fails():
    """Empty event_id must fail validation."""
    dispatch = RawReportPayload(**valid_dispatch_dict())
    gt = GroundTruth(incident_group="bbsr-flood-01")

    with pytest.raises(ValidationError):
        ScenarioEvent(
            event_id="",
            delay_seconds=1.0,
            dispatch=dispatch,
            ground_truth=gt,
        )


# =============================================================================
# TEST 8 — GroundTruth Standalone Existence & Ambiguity Support
# =============================================================================

def test_ground_truth_standalone_and_ambiguous_cases():
    """GroundTruth must exist independently and support ambiguous/partial cases."""
    # Fully specified ground truth
    gt_full = GroundTruth(
        incident_group="bbsr-flood-01",
        expected_incident_type=GroundTruthIncidentType.FLOOD_FLASH_FLOOD,
        expected_urgency=GroundTruthUrgency.CRITICAL,
        expected_people_at_risk=True,
        expected_people_count=4,
        relation_type=GroundTruthRelationType.CORROBORATING,
        expected_direction="ESCALATE_TO_TOP",
        expected_needs_review=False,
        notes="Confirmed trapped passengers by 2nd eyewitness.",
    )
    assert gt_full.incident_group == "bbsr-flood-01"
    assert gt_full.expected_urgency == GroundTruthUrgency.CRITICAL
    assert gt_full.expected_people_count == 4

    # Ambiguous / rumor test case (hard negative)
    gt_ambiguous = GroundTruth(
        incident_group=None,
        expected_incident_type=None,
        expected_urgency=GroundTruthUrgency.LOW,
        expected_people_at_risk=False,
        expected_people_count=None,
        relation_type=GroundTruthRelationType.NOISE,
        expected_direction="LOW_PRIORITY",
        expected_needs_review=True,
        notes="Unverified blast rumor, citizen admits didn't see anything.",
    )
    assert gt_ambiguous.expected_needs_review is True
    assert gt_ambiguous.relation_type == GroundTruthRelationType.NOISE
    assert gt_ambiguous.expected_incident_type is None


# =============================================================================
# TEST 9 — No GroundTruth Leakage (Public vs Private Isolation)
# =============================================================================

def test_no_ground_truth_leakage():
    """
    Architectural Leak Prevention:
    Given a ScenarioEvent, the public payload obtained from event.dispatch.model_dump()
    or event.public_payload() must NEVER contain any GroundTruth fields.
    """
    d_dict = valid_dispatch_dict()
    d_dict["metadata"]["event_id"] = "evt-007"
    d_dict["report_id"] = "rep-sim-007"
    dispatch = RawReportPayload(**d_dict)
    gt = GroundTruth(
        incident_group="bbsr-flood-01",
        expected_incident_type=GroundTruthIncidentType.FLOOD_FLASH_FLOOD,
        expected_urgency=GroundTruthUrgency.CRITICAL,
        expected_people_at_risk=True,
        expected_people_count=4,
        relation_type=GroundTruthRelationType.CORROBORATING,
        expected_direction=ExpectedQueueDirection.ESCALATE_TO_TOP,
        expected_needs_review=False,
        notes="Top secret evaluation label",
    )

    event = ScenarioEvent(
        event_id="evt-007",
        delay_seconds=10.0,
        dispatch=dispatch,
        ground_truth=gt,
    )

    # Retrieve public transmission payload
    public_dump = event.public_payload()

    # Assert standard public fields are present
    assert public_dump["report_id"] == "rep-sim-007"
    assert public_dump["source"] == "simulator"
    assert public_dump["is_synthetic"] is True
    assert "reported_at" in public_dump
    assert "text" in public_dump

    # ASSERT STRICT ABSENCE OF PRIVATE GROUND TRUTH
    private_keys = [
        "ground_truth",
        "incident_group",
        "expected_incident_type",
        "expected_urgency",
        "expected_people_at_risk",
        "expected_people_count",
        "relation_type",
        "expected_direction",
        "expected_needs_review",
        "notes",
    ]
    for key in private_keys:
        assert key not in public_dump, f"Leakage detected: '{key}' found in public dispatch dump!"

    # Assert extra fields cannot be smuggled into RawReportPayload
    with pytest.raises(ValidationError):
        RawReportPayload(
            report_id="rep-leak-01",
            text="Testing leakage",
            source="simulator",
            is_synthetic=True,
            reported_at=sample_utc_datetime(),
            ground_truth={"expected_urgency": "CRITICAL"},  # extra field forbidden
        )


# =============================================================================
# TEST 10 — Serialization Round Trip
# =============================================================================

def test_serialization_round_trip():
    """RawReportPayload -> model_dump(mode='json') -> RawReportPayload round trip succeeds."""
    original = RawReportPayload(**valid_dispatch_dict())

    # Serialize to JSON dictionary
    dumped = original.model_dump(mode="json")
    assert isinstance(dumped["reported_at"], str)
    assert dumped["reported_at"].endswith("Z")

    # Re-instantiate from dumped data
    recreated = RawReportPayload(**dumped)
    assert recreated.report_id == original.report_id
    assert recreated.text == original.text
    assert recreated.source == original.source
    assert recreated.is_synthetic == original.is_synthetic
    assert recreated.reported_at == original.reported_at
    assert recreated.location_hint.precision == original.location_hint.precision
    assert recreated.metadata == original.metadata


# =============================================================================
# TEST 11 — Metadata Preservation
# =============================================================================

def test_metadata_preservation():
    """scenario_id, event_id, and custom metadata survive serialization cleanly."""
    data = valid_dispatch_dict()
    data["metadata"] = {
        "scenario_id": "flood_rasulgarh",
        "event_id": "evt-042",
        "batch_index": 3,
        "caller_channel": "mock_radio",
    }
    payload = RawReportPayload(**data)
    dumped = payload.model_dump(mode="json")

    assert dumped["metadata"]["scenario_id"] == "flood_rasulgarh"
    assert dumped["metadata"]["event_id"] == "evt-042"
    assert dumped["metadata"]["batch_index"] == 3
    assert dumped["metadata"]["caller_channel"] == "mock_radio"


# =============================================================================
# TEST 12 — Simulator Safety Immutability
# =============================================================================

def test_safety_invariants_cannot_be_overridden():
    """Simulator dispatches cannot accidentally be constructed with is_synthetic=False or source='manual'."""
    with pytest.raises(ValidationError):
        RawReportPayload(
            report_id="rep-safe-01",
            text="Legitimate emergency text",
            source="manual",
            is_synthetic=False,
            reported_at=sample_utc_datetime(),
        )


# =============================================================================
# TEST 13 — Timezone-Awareness & ISO-8601 UTC Formatting
# =============================================================================

def test_timezone_aware_datetime_required():
    """Naive datetimes without tzinfo must be rejected; UTC datetimes serialize with 'Z'."""
    naive_dt = datetime(2026, 9, 26, 18, 15, 0)  # No tzinfo

    with pytest.raises(ValidationError) as exc_info:
        RawReportPayload(
            report_id="rep-tz-01",
            text="Valid text description",
            source="simulator",
            is_synthetic=True,
            reported_at=naive_dt,
        )
    assert any("timezone-aware" in str(err["msg"]) for err in exc_info.value.errors())

    # Timezone aware UTC datetime serializes to string ending with 'Z'
    aware_dt = datetime(2026, 9, 26, 18, 15, 0, tzinfo=timezone.utc)
    report = RawReportPayload(
        report_id="rep-tz-02",
        text="Valid text description",
        source="simulator",
        is_synthetic=True,
        reported_at=aware_dt,
    )
    dumped = report.model_dump(mode="json")
    assert dumped["reported_at"] == "2026-09-26T18:15:00Z"


# =============================================================================
# TEST 14 — Microsecond Precision Timestamp Formatting (Phase 1.1)
# =============================================================================

def test_microsecond_precision_timestamp_serialization():
    """Timestamps with microsecond components serialize strictly to ISO-8601 UTC with .%fZ."""
    dt_with_micros = datetime(2026, 9, 26, 18, 15, 0, 123456, tzinfo=timezone.utc)
    report = RawReportPayload(
        report_id="rep-micro-01",
        text="Valid text description",
        source="simulator",
        is_synthetic=True,
        reported_at=dt_with_micros,
    )
    dumped = report.model_dump(mode="json")
    assert dumped["reported_at"] == "2026-09-26T18:15:00.123456Z"


# =============================================================================
# TEST 15 — Typed ReportMetadata Validation (Phase 1.1)
# =============================================================================

def test_typed_report_metadata_validation():
    """ReportMetadata validates structured attributes without loose unvalidated dicts."""
    from simulator.models import ReportMetadata

    # Direct model construction
    meta = ReportMetadata(
        scenario_id="flood_rasulgarh",
        event_id="evt-001",
        phase="T+2m",
        caller_id="+91-99999-11111",
        channel="phone_911",
        batch_index=0,
    )
    assert meta.scenario_id == "flood_rasulgarh"
    assert meta.phase == "T+2m"
    assert meta.batch_index == 0

    # Embedded in RawReportPayload
    report = RawReportPayload(
        report_id="rep-meta-01",
        text="Valid text description",
        source="simulator",
        is_synthetic=True,
        reported_at=sample_utc_datetime(),
        metadata=meta,
    )
    assert isinstance(report.metadata, ReportMetadata)
    assert report.metadata.scenario_id == "flood_rasulgarh"

    # Raw dictionary coerced into ReportMetadata
    report_from_dict = RawReportPayload(
        report_id="rep-meta-02",
        text="Valid text description",
        source="simulator",
        is_synthetic=True,
        reported_at=sample_utc_datetime(),
        metadata={"scenario_id": "collapse_market", "event_id": "evt-010"},
    )
    assert isinstance(report_from_dict.metadata, ReportMetadata)
    assert report_from_dict.metadata.scenario_id == "collapse_market"


# =============================================================================
# TEST 16 — Coordinate Bounds Validation on LocationHint (Phase 1.1)
# =============================================================================

def test_location_coordinate_bounds():
    """Latitude must be [-90, 90] and Longitude [-180, 180]. Out of bounds must fail."""
    # Valid extreme bounds
    valid_loc = LocationHint(latitude=90.0, longitude=-180.0, precision=LocationPrecision.EXACT)
    assert valid_loc.latitude == 90.0

    # Out of bounds latitude
    with pytest.raises(ValidationError):
        LocationHint(latitude=90.1, longitude=85.0, precision=LocationPrecision.EXACT)

    # Out of bounds longitude
    with pytest.raises(ValidationError):
        LocationHint(latitude=20.0, longitude=180.1, precision=LocationPrecision.EXACT)


# =============================================================================
# TEST 17 — Recursive Firewall String Value Smuggling Defense (R4.3)
# =============================================================================

def test_metadata_string_value_smuggling_firewall():
    """
    R4.3: verify_no_ground_truth_leakage recursively audits string values within allowed
    metadata fields ('channel', 'caller_id', 'reporter_id', 'phase') to prevent smuggling
    evaluator ground-truth tokens (expected_*, ground_truth, etc.), raising GroundTruthLeakageError.
    Also ensures zero false positives on legitimate scenario metadata values.
    """
    # 1. Smuggling in 'channel'
    channel_attacks = [
        "expected_urgency",
        "expected_hazard=FLOOD",
        "emergency_hotline;ground_truth=true",
        "E_X_P_E_C_T_E_D_U_R_G_E_N_C_Y",
    ]
    for attack in channel_attacks:
        with pytest.raises(GroundTruthLeakageError, match="private ground-truth"):
            ReportMetadata(channel=attack)
        with pytest.raises(GroundTruthLeakageError, match="private ground-truth"):
            verify_no_ground_truth_leakage({"metadata": {"channel": attack}})

    # 2. Smuggling in 'caller_id'
    caller_attacks = [
        "sim-caller?expected_people_at_risk=True",
        "trueurgency:CRITICAL",
        "incident_group=bbsr-flood-01",
        "g_r_o_u_n_d_t_r_u_t_h",
    ]
    for attack in caller_attacks:
        with pytest.raises(GroundTruthLeakageError, match="private ground-truth"):
            ReportMetadata(caller_id=attack)
        with pytest.raises(GroundTruthLeakageError, match="private ground-truth"):
            verify_no_ground_truth_leakage({"caller_id": attack})

    # 3. Smuggling in 'reporter_id'
    reporter_attacks = [
        "source-01|relation_type=DUPLICATE",
        "expected_actionable:false",
        "TrueHazard",
    ]
    for attack in reporter_attacks:
        with pytest.raises(GroundTruthLeakageError, match="private ground-truth"):
            ReportMetadata(reporter_id=attack)
        with pytest.raises(GroundTruthLeakageError, match="private ground-truth"):
            verify_no_ground_truth_leakage({"reporter_id": attack})

    # 4. Smuggling in 'phase'
    phase_attacks = [
        "T0_expected_direction_ESCALATING",
        "phase1?expected_latitude=20.2961",
        "expectedneedsreview",
    ]
    for attack in phase_attacks:
        with pytest.raises(GroundTruthLeakageError, match="private ground-truth"):
            ReportMetadata(phase=attack)
        with pytest.raises(GroundTruthLeakageError, match="private ground-truth"):
            verify_no_ground_truth_leakage({"phase": attack})

    # 5. Nested container smuggling inside allowed metadata fields
    nested_list_attack = {"metadata": {"channel": ["phone", "expected_urgency=HIGH"]}}
    with pytest.raises(GroundTruthLeakageError, match="private ground-truth"):
        verify_no_ground_truth_leakage(nested_list_attack)

    nested_dict_attack = {"metadata": {"phase": {"nested_tag": "expected_actionable"}}}
    with pytest.raises(GroundTruthLeakageError, match="private ground-truth"):
        verify_no_ground_truth_leakage(nested_dict_attack)

    # 6. Egress integration: RawReportPayload validation catches smuggled string
    with pytest.raises(GroundTruthLeakageError, match="private ground-truth"):
        RawReportPayload(
            report_id="rep-smuggle-01",
            text="Legitimate dispatch text",
            source="simulator",
            is_synthetic=True,
            reported_at=sample_utc_datetime(),
            metadata={"channel": "radio;expected_incident_type=FLOOD"},
        )

    # 7. ScenarioEvent public_payload egress integration
    valid_dispatch = RawReportPayload(
        report_id="rep-smuggle-02",
        text="Normal emergency dispatch text",
        source="simulator",
        is_synthetic=True,
        reported_at=sample_utc_datetime(),
        metadata=ReportMetadata(
            scenario_id="flood_rasulgarh",
            event_id="evt-smuggle-02",
            channel="citizen_call",
        ),
    )
    # Manually modify dict to bypass model construction and verify public_payload firewall catches it
    event = ScenarioEvent(
        event_id="evt-smuggle-02",
        delay_seconds=1.0,
        dispatch=valid_dispatch,
        ground_truth=GroundTruth(incident_group="bbsr-flood-01"),
    )
    # Tamper with dispatch metadata dict
    event.dispatch.metadata.channel = "emergency_hotline;expected_urgency=CRITICAL"
    with pytest.raises(GroundTruthLeakageError, match="private ground-truth"):
        event.public_payload()

    # 8. Positive controls: legitimate metadata values must pass with zero false positives
    clean_meta = ReportMetadata(
        scenario_id="flood_rasulgarh",
        event_id="evt-001",
        caller_id="sim-caller-001",
        reporter_id="sim-source-001",
        channel="emergency_hotline",
        phase="minor_fire",
        batch_index=0,
    )
    assert clean_meta.channel == "emergency_hotline"
    assert clean_meta.phase == "minor_fire"

    # 9. Legitimate freeform dispatch text containing "ground" must NOT be blocked
    clean_payload = {
        "report_id": "rep-001",
        "text": "Water 3 feet on the ground near Rasulgarh market",
        "source": "simulator",
        "is_synthetic": True,
        "metadata": {
            "channel": "citizen_call",
            "phase": "T+20s",
        },
    }
    verify_no_ground_truth_leakage(clean_payload)  # Must not raise

    # 10. Non-audited metadata fields such as event_id containing 'expected' substring must NOT be blocked
    clean_meta_event = ReportMetadata(
        scenario_id="flood_rasulgarh",
        event_id="evt-expected-001",
        channel="police_radio",
    )
    assert clean_meta_event.event_id == "evt-expected-001"


