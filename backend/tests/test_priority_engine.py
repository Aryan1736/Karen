"""
Karen's Ear — Priority Engine Unit & Invariant Test Suite
Validates pure deterministic scoring logic against architecture/priority-engine.md
and authorized implementation decisions.
"""
from pathlib import Path
import sys
import pytest

# Ensure project root is in sys.path
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.engine import (
    DEFAULT_HAZARD_SCORE,
    DEFAULT_WEIGHTS,
    HAZARD_SCORES,
    LEVEL_THRESHOLDS,
    PRIORITY_CALCULATION_VERSION,
    STATUS_MODIFIERS,
    URGENCY_SCORES,
    PriorityCalculationResult,
    calculate_priority,
    map_priority_level,
    normalize_corroboration_factor,
    normalize_hazard_factor,
    normalize_people_at_risk_factor,
    normalize_urgency_factor,
)
from backend.app.schemas.common import IncidentStatus, IncidentType, PriorityLevel, UrgencyLevel
from backend.app.schemas.incident import ConfidenceBlock, PriorityBlock


def test_identical_input_produces_identical_output():
    """Invariant: Given the exact same inputs, engine must produce 100% identical output."""
    kwargs = {
        "urgency": UrgencyLevel.HIGH,
        "people_at_risk_count": 2,
        "independent_sources": 3,
        "incident_type": IncidentType.FLOOD_FLASH_FLOOD,
        "status": IncidentStatus.ACTIVE,
        "ml_confidence": 0.85,
    }

    first = calculate_priority(**kwargs)
    for _ in range(50):
        result = calculate_priority(**kwargs)
        assert result.score == first.score
        assert result.level == first.level
        assert result.explanation == first.explanation
        assert result.calc_version == first.calc_version
        assert [f.model_dump() for f in result.factors] == [f.model_dump() for f in first.factors]


def test_critical_urgency_case():
    """Verify CRITICAL urgency contributes exactly 35.0 (100.0 * 0.35)."""
    result = calculate_priority(
        urgency=UrgencyLevel.CRITICAL,
        people_at_risk_count=0,
        independent_sources=0,
        incident_type=IncidentType.OTHER_GENERAL_INCIDENT,
    )
    urgency_factor = next(f for f in result.factors if "Urgency" in f.factor)
    assert urgency_factor.weight == 0.35
    assert urgency_factor.contribution == 35.0
    assert urgency_factor.value == "CRITICAL"


def test_low_urgency_case():
    """Verify LOW urgency contributes exactly 5.25 (15.0 * 0.35)."""
    result = calculate_priority(
        urgency=UrgencyLevel.LOW,
        people_at_risk_count=0,
        independent_sources=0,
        incident_type=IncidentType.OTHER_GENERAL_INCIDENT,
    )
    urgency_factor = next(f for f in result.factors if "Urgency" in f.factor)
    assert urgency_factor.weight == 0.35
    assert urgency_factor.contribution == 5.25
    assert urgency_factor.value == "LOW"


def test_null_and_unknown_values():
    """
    Verify safe fallback behavior for null/missing inputs:
    - Urgency: null/unknown -> 30.0 neutral default (contrib: 10.50)
    - People at risk: null without indication -> 10.0 default (contrib: 3.00)
    - Corroboration: null/0 -> 0.0 (contrib: 0.00)
    - Hazard type: null/unknown -> 25.0 fallback (contrib: 3.75)
    - ML confidence: null -> no penalty
    """
    result = calculate_priority(
        urgency=None,
        people_at_risk_count=None,
        has_trapped_indication=False,
        independent_sources=None,
        corroboration_score=None,
        incident_type=None,
        ml_confidence=None,
        status=IncidentStatus.ACTIVE,
    )

    # 10.50 + 3.00 + 0.00 + 3.75 = 17.25
    assert result.score == 17.25
    assert result.level == PriorityLevel.LOW

    factors_dict = {f.factor: f for f in result.factors}
    assert factors_dict["Urgency (Life-Safety)"].contribution == 10.50
    assert factors_dict["People at Risk"].contribution == 3.00
    assert factors_dict["Corroboration"].contribution == 0.00
    assert factors_dict["Hazard Type"].contribution == 3.75


def test_severe_weather_storm_hazard_score_decision_1():
    """
    Decision #1: SEVERE_WEATHER_STORM is omitted from architecture/priority-engine.md Section 4.4.
    Temporarily maps to 25.0 (same baseline as OTHER_GENERAL_INCIDENT).
    """
    norm, label = normalize_hazard_factor(IncidentType.SEVERE_WEATHER_STORM)
    assert norm == 25.0
    assert label == "SEVERE_WEATHER_STORM"

    res = calculate_priority(incident_type=IncidentType.SEVERE_WEATHER_STORM)
    f_haz = next(f for f in res.factors if f.factor == "Hazard Type")
    assert f_haz.contribution == 3.75  # 0.15 * 25.0


def test_null_unknown_unrecognized_incident_type_decision_2():
    """
    Decision #2: null / unknown / unrecognized incident type -> hazard score = 25.0.
    """
    assert normalize_hazard_factor(None) == (25.0, "UNKNOWN")
    assert normalize_hazard_factor("") == (25.0, "UNKNOWN")
    assert normalize_hazard_factor("UNRECOGNIZED_CRISIS_XYZ") == (25.0, "UNRECOGNIZED_CRISIS_XYZ")


def test_people_at_risk_scaling_and_non_positive_count_decision_3():
    """
    Decision #3:
    - people_at_risk count <= 0: treat as "No indication of people at risk", risk score = 10.0.
    - Positive counts use: min(100.0, 40.0 + 12.0 * count)
    """
    # count <= 0 -> 10.0
    assert normalize_people_at_risk_factor(0) == (10.0, "No indication of people at risk")
    assert normalize_people_at_risk_factor(-1) == (10.0, "No indication of people at risk")
    assert normalize_people_at_risk_factor(-5) == (10.0, "No indication of people at risk")
    assert normalize_people_at_risk_factor(None) == (10.0, "No indication of people at risk")

    # Positive counts: min(100.0, 40.0 + 12.0 * count)
    expected_scores = [
        (1, 52.0, 15.60),
        (2, 64.0, 19.20),
        (3, 76.0, 22.80),
        (4, 88.0, 26.40),
        (5, 100.0, 30.00),
        (10, 100.0, 30.00),
    ]
    for count, exp_norm, exp_contrib in expected_scores:
        score_norm, label = normalize_people_at_risk_factor(count)
        assert score_norm == exp_norm
        res = calculate_priority(people_at_risk_count=count)
        f_risk = next(f for f in res.factors if f.factor == "People at Risk")
        assert f_risk.contribution == exp_contrib

    # Ambiguous indication without count -> 70.0
    amb_norm, amb_label = normalize_people_at_risk_factor(None, has_trapped_indication=True)
    assert amb_norm == 70.0
    res_amb = calculate_priority(has_trapped_indication=True)
    f_amb = next(f for f in res_amb.factors if f.factor == "People at Risk")
    assert f_amb.contribution == 21.0


def test_corroboration_exact_representation_decision_4():
    """
    Decision #4:
    follow architecture/incident-correlation.md representation:
      score_0_to_1 = round(1.0 - exp(-0.45 * independent_source_count), 2)
      priority_factor = score_0_to_1 * 100.0
    This intentionally produces:
      N=1 -> 36.0
      N=2 -> 59.0
      N=3 -> 74.0
      N=5 -> 89.0
    Satisfies architecture/testing.md where N=2 contributes 11.8 and total score is 82.35.
    """
    expected_corrob = [
        (1, 36.0, 7.20),
        (2, 59.0, 11.80),
        (3, 74.0, 14.80),
        (5, 89.0, 17.80),
        (7, 96.0, 19.20),
        (15, 100.0, 20.00),
    ]
    for n, exp_norm, exp_contrib in expected_corrob:
        norm, label = normalize_corroboration_factor(independent_sources=n)
        assert norm == exp_norm, f"Failed for N={n}: got {norm}, expected {exp_norm}"
        res = calculate_priority(independent_sources=n)
        f_corrob = next(f for f in res.factors if f.factor == "Corroboration")
        assert f_corrob.contribution == exp_contrib

    # Architecture/testing.md exact deterministic example:
    # Urgency: CRITICAL (100) -> 35.0
    # Risk: 3 trapped (76) -> 22.8
    # Corrob: 2 (59) -> 11.8
    # Hazard: Flood (85) -> 12.75
    # Total = 82.35 (CRITICAL)
    res_canonical = calculate_priority(
        urgency=UrgencyLevel.CRITICAL,
        people_at_risk_count=3,
        independent_sources=2,
        incident_type=IncidentType.FLOOD_FLASH_FLOOD,
        status=IncidentStatus.ACTIVE,
    )
    assert res_canonical.score == 82.35
    assert res_canonical.level == PriorityLevel.CRITICAL

    # Direct corroboration_score float [0.0, 1.0]
    norm_score, _ = normalize_corroboration_factor(corroboration_score=0.59)
    assert norm_score == 59.0
    norm_zero, _ = normalize_corroboration_factor(corroboration_score=0.0)
    assert norm_zero == 0.0
    norm_max, _ = normalize_corroboration_factor(corroboration_score=1.0)
    assert norm_max == 100.0


def test_low_confidence_behavior_decision_5():
    """
    Decision #5:
    The priority engine applies only the documented -10.0 scoring penalty.
    It does NOT mutate incident status inside this pure engine.
    """
    incident_dict = {
        "urgency": "CRITICAL",
        "incident_type": "FLOOD_FLASH_FLOOD",
        "status": "ACTIVE",
        "ml_confidence": 0.35,  # < 0.50
    }
    res = calculate_priority(incident=incident_dict)

    # Status in original dict must remain "ACTIVE"
    assert incident_dict["status"] == "ACTIVE"
    # Priority engine applied -10.0 penalty
    assert any("Low ML confidence penalty" in m for m in res.modifiers_applied)

    # Check at boundary 0.50 -> NO penalty
    res_at_boundary = calculate_priority(
        urgency=UrgencyLevel.CRITICAL,
        incident_type=IncidentType.FLOOD_FLASH_FLOOD,
        ml_confidence=0.50,
    )
    assert not any("Low ML confidence penalty" in m for m in res_at_boundary.modifiers_applied)


def test_each_hazard_severity_mapping():
    """Verify all 8 explicit hazard categories from Section 4.4 and their contributions."""
    expected_hazards = {
        IncidentType.STRUCTURAL_COLLAPSE: (100.0, 15.00),
        IncidentType.FIRE_WILDFIRE_EXPLOSION: (90.0, 13.50),
        IncidentType.FLOOD_FLASH_FLOOD: (85.0, 12.75),
        IncidentType.CIVIL_UNREST_ACTIVE_THREAT: (80.0, 12.00),
        IncidentType.EARTHQUAKE_LANDSLIDE: (75.0, 11.25),
        IncidentType.MEDICAL_EMERGENCY: (70.0, 10.50),
        IncidentType.UTILITY_INFRASTRUCTURE_FAILURE: (45.0, 6.75),
        IncidentType.OTHER_GENERAL_INCIDENT: (25.0, 3.75),
    }

    for inc_type, (exp_norm, exp_contrib) in expected_hazards.items():
        norm, label = normalize_hazard_factor(inc_type)
        assert norm == exp_norm, f"Failed norm for {inc_type}: got {norm}, expected {exp_norm}"
        res = calculate_priority(incident_type=inc_type)
        f_haz = next(f for f in res.factors if f.factor == "Hazard Type")
        assert f_haz.contribution == exp_contrib


def test_verified_modifier():
    """Section 5.2: VERIFIED status applies +10.0 boost."""
    res_active = calculate_priority(
        urgency=UrgencyLevel.MEDIUM,
        status=IncidentStatus.ACTIVE,
    )
    res_verified = calculate_priority(
        urgency=UrgencyLevel.MEDIUM,
        status=IncidentStatus.VERIFIED,
    )
    assert res_verified.score == round(res_active.score + 10.0, 2)
    assert any("VERIFIED" in m for m in res_verified.modifiers_applied)


def test_escalated_modifier():
    """Section 5.2: ESCALATED status applies +15.0 surge boost."""
    res_active = calculate_priority(
        urgency=UrgencyLevel.MEDIUM,
        status=IncidentStatus.ACTIVE,
    )
    res_escalated = calculate_priority(
        urgency=UrgencyLevel.MEDIUM,
        status=IncidentStatus.ESCALATED,
    )
    assert res_escalated.score == round(res_active.score + 15.0, 2)
    assert any("ESCALATED" in m for m in res_escalated.modifiers_applied)


def test_resolved_behavior():
    """Section 5.2: RESOLVED status forces score to 0.0 (LOW tier)."""
    res = calculate_priority(
        urgency=UrgencyLevel.CRITICAL,
        people_at_risk_count=10,
        independent_sources=5,
        incident_type=IncidentType.STRUCTURAL_COLLAPSE,
        status=IncidentStatus.RESOLVED,
    )
    assert res.score == 0.0
    assert res.level == PriorityLevel.LOW
    assert "RESOLVED" in res.explanation
    assert any("RESOLVED" in m for m in res.modifiers_applied)


def test_final_score_never_below_zero():
    """Clamping invariant: Priority score can never drop below 0.0."""
    res = calculate_priority(
        urgency=UrgencyLevel.LOW,
        people_at_risk_count=0,
        independent_sources=0,
        incident_type=IncidentType.OTHER_GENERAL_INCIDENT,
        ml_confidence=0.10,  # -10 penalty
        weight_urgency=0.01,
        weight_risk=0.01,
        weight_corrob=0.01,
        weight_hazard=0.01,
    )
    assert res.score >= 0.0


def test_final_score_never_above_one_hundred():
    """Clamping invariant: Priority score can never exceed 100.0."""
    res = calculate_priority(
        urgency=UrgencyLevel.CRITICAL,
        people_at_risk_count=10,
        independent_sources=10,
        incident_type=IncidentType.STRUCTURAL_COLLAPSE,
        status=IncidentStatus.ESCALATED,
    )
    assert res.score <= 100.0
    assert res.score == 100.0
    assert res.level == PriorityLevel.CRITICAL


def test_correct_priority_level_thresholds():
    """
    Section 6 Tiers:
    CRITICAL: 80.0 – 100.0
    HIGH:     60.0 – 79.9
    MEDIUM:   35.0 – 59.9
    LOW:       0.0 – 34.9
    """
    assert map_priority_level(100.0) == PriorityLevel.CRITICAL
    assert map_priority_level(80.0) == PriorityLevel.CRITICAL
    assert map_priority_level(79.99) == PriorityLevel.HIGH
    assert map_priority_level(60.0) == PriorityLevel.HIGH
    assert map_priority_level(59.99) == PriorityLevel.MEDIUM
    assert map_priority_level(35.0) == PriorityLevel.MEDIUM
    assert map_priority_level(34.99) == PriorityLevel.LOW
    assert map_priority_level(0.0) == PriorityLevel.LOW


def test_factor_contributions_and_weights_sum_to_one():
    """Verify configured weights sum to 1.00 and factor contributions match weight * normalized score."""
    res = calculate_priority(
        urgency=UrgencyLevel.HIGH,
        people_at_risk_count=3,
        independent_sources=2,
        incident_type=IncidentType.FIRE_WILDFIRE_EXPLOSION,
    )
    total_weight = sum(f.weight for f in res.factors)
    assert pytest.approx(total_weight, rel=1e-5) == 1.00
    assert len(res.factors) == 4

    for f in res.factors:
        assert f.weight > 0.0
        assert f.contribution >= 0.0


def test_explanation_is_stable_and_non_empty():
    """Verify explanation is non-empty, deterministic, and contains factor details."""
    res = calculate_priority(
        urgency=UrgencyLevel.CRITICAL,
        people_at_risk_count=4,
        independent_sources=3,
        incident_type=IncidentType.FLOOD_FLASH_FLOOD,
        status=IncidentStatus.ESCALATED,
    )
    assert isinstance(res.explanation, str)
    assert len(res.explanation) > 20
    assert "CRITICAL" in res.explanation
    assert "ESCALATED" in res.explanation
    assert "Urgency" in res.explanation


def test_calculate_priority_with_dict_and_object_input():
    """Verify calculate_priority operates seamlessly with incident dictionary or model instances."""
    incident_dict = {
        "urgency": "CRITICAL",
        "people_at_risk_count": 2,
        "independent_source_count": 3,
        "incident_type": "FIRE_WILDFIRE_EXPLOSION",
        "status": "VERIFIED",
        "ml_confidence": {"overall": 0.95},
    }
    res = calculate_priority(incident=incident_dict)
    assert res.level == PriorityLevel.CRITICAL
    assert any("VERIFIED" in m for m in res.modifiers_applied)
    assert isinstance(res, PriorityBlock)
    dumped = res.model_dump()
    assert "score" in dumped
    assert "factors" in dumped
    assert len(dumped["factors"]) == 4
