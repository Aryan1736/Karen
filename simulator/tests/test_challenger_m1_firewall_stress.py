"""
Adversarial and Empirical Stress Test Suite for Milestone 1 Security Firewall.
Challenger 2 Verification Suite (teamwork_preview_challenger_m1_2):
- Comprehensive adversarial stress-testing of verify_no_ground_truth_leakage() in simulator/models.py
- Smuggling attack vectors inside allowed metadata fields (channel, caller_id, reporter_id, phase):
  * Case variations ('EXPECTED_URGENCY', 'Expected_Type', mixed case)
  * Punctuation / delimiters ('expected:CRITICAL', 'expected=HIGH', 'expected-phase', ;, ., /, |, etc.)
  * Obfuscated / normalized variants (fullwidth, combining accents, zero-width, non-breaking spaces)
  * Nested containers (lists, dicts, tuples, sets, frozensets, arbitrary depth)
- False positive resistance:
  * Innocent strings ('underground water pipe', 'playground flooding', 'background noise', 'foreground')
  * Report body containing 'expected'
  * Allowed metadata fields with legitimate values
- Golden scenario event validation across all 27 events (flood_rasulgarh and mixed_hard_negatives)
- Empirical investigation of snake_case underscore delimiter edge cases
"""

import unicodedata
import pytest

from simulator.models import (
    AUDITED_METADATA_FIELDS,
    GroundTruth,
    GroundTruthLeakageError,
    RawReportPayload,
    ReportMetadata,
    ScenarioEvent,
    verify_no_ground_truth_leakage,
)
from simulator.scenarios import (
    FLOOD_ID,
    HARD_NEG_ID,
    get_scenario,
    list_scenarios,
)


# =============================================================================
# 1. Smuggling Attacks: Case Variations
# =============================================================================

@pytest.mark.parametrize("field", ["channel", "caller_id", "reporter_id", "phase"])
@pytest.mark.parametrize("case_attack", [
    "EXPECTED_URGENCY",
    "Expected_Type",
    "ExPeCtEd_UrGeNcY",
    "eXpEcTeD_pEoPlE_aT_rIsK",
    "GROUND_TRUTH",
    "GrOuNdTrUtH",
    "TRUEURGENCY",
    "tRuE_hAzArD",
    "INCIDENT_GROUP",
    "InCiDeNtGrOuP",
    "RELATION_TYPE",
    "ReLaTiOnTyPe",
    "EXPECTED_PEOPLE_COUNT",
    "EXPECTED_DIRECTION",
    "EXPECTED_NEEDS_REVIEW",
    "EXPECTED_LOCATION_TEXT",
    "EXPECTED_LATITUDE",
    "EXPECTED_LONGITUDE",
    "EXPECTED_REQUIRED_RESPONSE",
    "EXPECTED_ACTIONABLE",
])
def test_firewall_blocks_case_variations(field: str, case_attack: str):
    """
    Ensure all case variations of forbidden ground truth tokens are blocked
    across all audited metadata fields.
    """
    payload = {"metadata": {field: case_attack}}
    with pytest.raises(GroundTruthLeakageError) as exc_info:
        verify_no_ground_truth_leakage(payload)
    assert "LEAKAGE VIOLATION" in str(exc_info.value)


# =============================================================================
# 2. Smuggling Attacks: Punctuation & Delimiters
# =============================================================================

@pytest.mark.parametrize("field", ["channel", "caller_id", "reporter_id", "phase"])
@pytest.mark.parametrize("delim_attack", [
    "expected:CRITICAL",
    "expected=HIGH",
    "expected-phase",
    "expected.test",
    "expected;val",
    "expected/danger",
    "expected|alert",
    "expected?status",
    "expected&priority",
    "expected#urgent",
    "expected@hq",
    "expected!now",
    "expected critical",
    "expected\tHIGH",
    "expected\nLOW",
    "radio;expected:CRITICAL;dispatch=true",
    "caller_id|expected=HIGH|team=bravo",
    "sim/channel?expected-phase=T+5m",
])
def test_firewall_blocks_punctuation_and_delimiters(field: str, delim_attack: str):
    """
    Ensure ground truth tokens accompanied by various punctuation delimiters
    are detected and blocked across all audited metadata fields.
    """
    payload = {"metadata": {field: delim_attack}}
    with pytest.raises(GroundTruthLeakageError) as exc_info:
        verify_no_ground_truth_leakage(payload)
    assert "LEAKAGE VIOLATION" in str(exc_info.value)


# =============================================================================
# 3. Smuggling Attacks: Obfuscated and Normalized Variants
# =============================================================================

@pytest.mark.parametrize("field", ["channel", "caller_id", "reporter_id", "phase"])
@pytest.mark.parametrize("obfuscated_attack", [
    # Fullwidth Unicode characters
    "ｅｘｐｅｃｔｅｄ_ｕｒｇｅｎｃｙ",
    "ｇｒｏｕｎｄｔｒｕｔｈ",
    "ｔｒｕｅｕｒｇｅｎｃｙ",
    # Accents / diacritics normalized by NFKD
    "éxpècted_urgéncy",
    "trûéûrgéncy",
    "gròùndtrùth",
    # Zero-width spaces and joiners (\u200b, \u200c, \u200d)
    "expected\u200burgency",
    "e\u200bx\u200bp\u200be\u200bc\u200bt\u200be\u200bd",
    "ground\u200ctruth",
    "true\u200durgency",
    # Non-breaking space (\u00a0) and soft hyphen (\u00ad)
    "expected\u00a0urgency",
    "expected\u00adurgency",
    # Letter-by-letter delimiter spacing
    "e_x_p_e_c_t_e_d_u_r_g_e_n_c_y",
    "g.r.o.u.n.d.t.r.u.t.h",
    "t-r-u-e-u-r-g-e-n-c-y",
])
def test_firewall_blocks_obfuscated_variants(field: str, obfuscated_attack: str):
    """
    Ensure obfuscated representations (Unicode fullwidth, accents, zero-width chars,
    non-breaking spaces, letter-spacing) are normalized and blocked.
    """
    payload = {"metadata": {field: obfuscated_attack}}
    with pytest.raises(GroundTruthLeakageError) as exc_info:
        verify_no_ground_truth_leakage(payload)
    assert "LEAKAGE VIOLATION" in str(exc_info.value)


# =============================================================================
# 4. Smuggling Attacks: Nested Containers
# =============================================================================

def test_firewall_blocks_nested_containers_lists_and_dicts():
    """Verify deep nesting in lists, dicts, tuples, sets, and frozensets is intercepted."""
    # List of metadata dicts
    nested_list = {"metadata": [{"channel": "expected:CRITICAL"}]}
    with pytest.raises(GroundTruthLeakageError):
        verify_no_ground_truth_leakage(nested_list)

    # Dicts nested inside metadata fields
    nested_dict = {"metadata": {"channel": {"subchannel": {"tag": "expected=HIGH"}}}}
    with pytest.raises(GroundTruthLeakageError):
        verify_no_ground_truth_leakage(nested_dict)

    # Tuples inside list
    nested_tuple = {"metadata": {"caller_id": [("clean_alias", "expected-phase")]}}
    with pytest.raises(GroundTruthLeakageError):
        verify_no_ground_truth_leakage(nested_tuple)

    # Set inside metadata
    nested_set = {"metadata": {"reporter_id": {"expected_urgency", "source-01"}}}
    with pytest.raises(GroundTruthLeakageError):
        verify_no_ground_truth_leakage(nested_set)

    # Frozenset inside metadata
    nested_frozenset = {"metadata": {"phase": frozenset(["expected_actionable"])}}
    with pytest.raises(GroundTruthLeakageError):
        verify_no_ground_truth_leakage(nested_frozenset)

    # Multi-level arbitrary deep nesting
    deep_nesting = {
        "metadata": {
            "channel": [
                {"level1": [
                    {"level2": ("clean", {"level3": ["EXPECTED_URGENCY"]})}
                ]}
            ]
        }
    }
    with pytest.raises(GroundTruthLeakageError):
        verify_no_ground_truth_leakage(deep_nesting)


# =============================================================================
# 5. False Positive Resistance: Innocent Strings
# =============================================================================

@pytest.mark.parametrize("field", ["channel", "caller_id", "reporter_id", "phase"])
@pytest.mark.parametrize("innocent_string", [
    "underground water pipe",
    "playground flooding",
    "background noise",
    "foreground",
    "ground level station",
    "campground dispatch",
    "above ground pool",
    "battleground radio",
])
def test_firewall_permits_innocent_ground_substrings(field: str, innocent_string: str):
    """
    Ensure innocent strings containing the substring 'ground' (e.g. 'underground water pipe',
    'playground flooding', 'background noise', 'foreground') do NOT trigger false positives.
    """
    payload = {"metadata": {field: innocent_string}}
    verify_no_ground_truth_leakage(payload)  # Must not raise


def test_firewall_permits_innocent_dispatch_body_and_non_audited_metadata():
    """Ensure report text body and non-audited metadata keys are not falsely blocked."""
    payload = {
        "report_id": "rep-innocent-001",
        "text": (
            "Rescue teams are expected to arrive shortly. Significant flooding in the playground "
            "and underground basement parking. Background noise makes audio indistinct."
        ),
        "source": "simulator",
        "is_synthetic": True,
        "metadata": {
            "scenario_id": "flood_rasulgarh",
            "event_id": "evt-expected-phase-001",  # non-audited field can have expected
            "channel": "citizen_hotline",
            "phase": "initial_response",
            "batch_index": 1,
        },
    }
    verify_no_ground_truth_leakage(payload)  # Must not raise


# =============================================================================
# 6. Golden Scenario Validation: All 27 Events
# =============================================================================

def test_all_27_golden_events_across_both_scenarios():
    """
    Audit all 27 golden events across flood_rasulgarh (15) and mixed_hard_negatives (12).
    Verify that public_payload() passes verify_no_ground_truth_leakage() with zero leaks
    and zero false positives.
    """
    scenarios = [FLOOD_ID, HARD_NEG_ID]
    total_events_checked = 0

    for scenario_id in scenarios:
        events = get_scenario(scenario_id)
        assert len(events) > 0
        total_events_checked += len(events)

        for event in events:
            # 1. Public payload must pass firewall cleanly
            public_dict = event.public_payload()
            verify_no_ground_truth_leakage(public_dict)

            # 2. Invariants: synthetic and source
            assert public_dict["is_synthetic"] is True
            assert public_dict["source"] == "simulator"

            # 3. Metadata fields must not contain ground truth keys
            if "metadata" in public_dict and public_dict["metadata"]:
                for audited_key in AUDITED_METADATA_FIELDS:
                    val = public_dict["metadata"].get(audited_key)
                    if val is not None and isinstance(val, str):
                        # Verify string value directly
                        verify_no_ground_truth_leakage({audited_key: val})

    assert total_events_checked == 27, f"Expected 27 golden events, got {total_events_checked}"


# =============================================================================
# 7. Challenger Empirical Discovery: Snake_Case Underscore Delimiter Behavior
# =============================================================================

def test_empirical_underscore_prefix_behavior():
    """
    EMPIRICAL CHALLENGER DISCOVERY:
    Demonstrates that full canonical ground-truth tokens (e.g. 'expected_urgency')
    ARE caught even when prefixed by snake_case identifiers (e.g. 'sim_expected_urgency'),
    because FORBIDDEN_VALUE_TOKENS uses substring matching.

    However, non-canonical / short forms like 'sim_expected:CRITICAL' or 'sim_expected=HIGH'
    bypass the delimiter split because line 160 uses r'[^a-zA-Z0-9_]+', treating '_' as a
    token character rather than a delimiter.
    """
    # Canonical token with snake_case prefix: CAUGHT by substring check in Step 3
    with pytest.raises(GroundTruthLeakageError):
        verify_no_ground_truth_leakage({"channel": "sim_expected_urgency=CRITICAL"})

    with pytest.raises(GroundTruthLeakageError):
        verify_no_ground_truth_leakage({"caller_id": "caller_incident_group_01"})

    with pytest.raises(GroundTruthLeakageError):
        verify_no_ground_truth_leakage({"phase": "phase_expected_actionable"})

    # Non-underscore delimiters: CAUGHT by delimiter split in Step 4
    with pytest.raises(GroundTruthLeakageError):
        verify_no_ground_truth_leakage({"channel": "sim-expected:CRITICAL"})

    with pytest.raises(GroundTruthLeakageError):
        verify_no_ground_truth_leakage({"channel": "sim:expected=HIGH"})

    with pytest.raises(GroundTruthLeakageError):
        verify_no_ground_truth_leakage({"channel": "sim;expected-phase"})

    # Hardened: snake_case underscore delimiter with short form is also strictly blocked
    with pytest.raises(GroundTruthLeakageError):
        verify_no_ground_truth_leakage({"channel": "sim_expected:CRITICAL"})

    with pytest.raises(GroundTruthLeakageError):
        verify_no_ground_truth_leakage({"channel": "sim_expected=HIGH"})

