"""
Karen's Ear — Incident Correlation & Deduplication Engine Test Suite
Tests pure deterministic three-dimensional correlation, dynamic thresholding,
relationship classification, and corroboration saturation.

Authority:
- architecture/incident-correlation.md
- architecture/database.md
- architecture/failure-handling.md
- architecture/testing.md
- docs/data-schema.md
- docs/api-contract.md
"""
from datetime import datetime, timedelta, timezone
import math
from pathlib import Path
import sys
import pytest

# Ensure project root is in sys.path
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.engine.correlation import (
    DEFAULT_CORROBORATION_THRESHOLD,
    DEFAULT_DUPLICATE_THRESHOLD,
    DEFAULT_SPATIAL_CLUSTER_RADIUS_KM,
    DEFAULT_TEMPORAL_CUTOFF_HOURS,
    DEFAULT_TEMPORAL_DECAY_HOURS,
    DEFAULT_WEIGHT_SEMANTIC,
    DEFAULT_WEIGHT_SPATIAL,
    DEFAULT_WEIGHT_TEMPORAL,
    calculate_composite_score,
    calculate_corroboration_score,
    calculate_cosine_similarity,
    calculate_spatial_similarity,
    calculate_temporal_similarity,
    classify_relationship,
    correlate_report_to_incident,
    find_best_incident_match,
    generate_corroboration_explanation,
    haversine_distance_km,
)
from backend.app.schemas.common import RelationshipType


# =============================================================================
# Helper Fixtures & Utilities
# =============================================================================
def make_unit_vector(dimension: int = 384, primary_idx: int = 0) -> list[float]:
    """Creates a normalized unit vector with 1.0 at primary_idx."""
    v = [0.0] * dimension
    v[primary_idx] = 1.0
    return v


def make_dense_normalized_vector(seed_val: float = 1.0, dimension: int = 384) -> list[float]:
    """Creates a deterministic dense normalized 384-dimensional vector."""
    raw = [math.sin(i * 0.1 + seed_val) for i in range(dimension)]
    norm = math.sqrt(sum(x * x for x in raw))
    return [x / norm for x in raw]


# =============================================================================
# 1. Semantic Similarity Tests
# =============================================================================
def test_identical_embeddings_produce_similarity_one():
    """Identical 384-dimensional normalized vectors must yield exactly 1.0 similarity."""
    v = make_dense_normalized_vector(seed_val=1.0)
    score, warnings = calculate_cosine_similarity(v, v)
    assert score is not None
    assert math.isclose(score, 1.0, abs_tol=1e-4)
    assert warnings == []


def test_orthogonal_embeddings_produce_similarity_zero():
    """Orthogonal vectors must yield 0.0 similarity."""
    v1 = make_unit_vector(384, 0)
    v2 = make_unit_vector(384, 1)
    score, warnings = calculate_cosine_similarity(v1, v2)
    assert score is not None
    assert math.isclose(score, 0.0, abs_tol=1e-4)


def test_opposite_embeddings_produce_similarity_negative_one():
    """Opposite vectors must yield -1.0 similarity."""
    v1 = make_unit_vector(384, 0)
    v2 = [-x for x in v1]
    score, warnings = calculate_cosine_similarity(v1, v2)
    assert score is not None
    assert math.isclose(score, -1.0, abs_tol=1e-4)


def test_clearly_dissimilar_embeddings():
    """Dissimilar vectors must produce low or negative similarity score."""
    v1 = make_dense_normalized_vector(seed_val=1.0)
    v2 = make_dense_normalized_vector(seed_val=50.0)
    score, warnings = calculate_cosine_similarity(v1, v2)
    assert score is not None
    assert score < 0.50  # Distinct patterns


def test_malformed_non_384_embeddings():
    """Vectors with length != 384 must fail safely without throwing exceptions."""
    v_short = [0.1] * 10
    v_383 = [0.1] * 383
    v_384 = make_dense_normalized_vector()
    v_385 = [0.1] * 385

    score1, warn1 = calculate_cosine_similarity(v_short, v_384)
    assert score1 is None
    assert any("dimension" in w.lower() for w in warn1)

    score2, warn2 = calculate_cosine_similarity(v_384, v_383)
    assert score2 is None

    score3, warn3 = calculate_cosine_similarity(v_385, v_384)
    assert score3 is None


def test_missing_embeddings_do_not_crash():
    """None embeddings must return None safely and log warning."""
    v_valid = make_dense_normalized_vector()
    score, warnings = calculate_cosine_similarity(None, v_valid)
    assert score is None
    assert any("missing" in w.lower() for w in warnings)

    score2, warnings2 = calculate_cosine_similarity(None, None)
    assert score2 is None


def test_non_numeric_nan_infinite_embeddings():
    """Vectors with NaN, Infinity, or non-numeric types must fail safely."""
    v_nan = make_dense_normalized_vector()
    v_nan[5] = float("nan")
    v_valid = make_dense_normalized_vector()

    score, warnings = calculate_cosine_similarity(v_nan, v_valid)
    assert score is None
    assert any("nan" in w.lower() for w in warnings)

    v_inf = make_dense_normalized_vector()
    v_inf[10] = float("inf")
    score2, warnings2 = calculate_cosine_similarity(v_inf, v_valid)
    assert score2 is None

    v_str = make_dense_normalized_vector()
    v_str[0] = "bad"  # type: ignore[assignment]
    score3, warnings3 = calculate_cosine_similarity(v_str, v_valid)
    assert score3 is None


def test_zero_norm_embedding_returns_zero():
    """All-zero vector returns 0.0 with diagnostic warning."""
    v_zero = [0.0] * 384
    v_valid = make_dense_normalized_vector()
    score, warnings = calculate_cosine_similarity(v_zero, v_valid)
    assert score == 0.0
    assert any("zero-norm" in w.lower() for w in warnings)


# =============================================================================
# 2. Temporal Similarity Tests
# =============================================================================
def test_temporal_similarity_at_zero_elapsed_time():
    """Same timestamp produces temporal similarity 1.0."""
    t0 = datetime(2026, 9, 26, 14, 30, 0, tzinfo=timezone.utc)
    s_temp, delta_hours, warnings = calculate_temporal_similarity(t0, t0)
    assert math.isclose(s_temp, 1.0, abs_tol=1e-4)
    assert delta_hours == 0.0
    assert warnings == []


def test_temporal_decay_boundaries():
    """Validates exact temporal decay curve exp(-Delta_t / 3.0) and cutoff at 6.0h."""
    t0 = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)

    # 1.0 hour elapsed -> exp(-1/3) ≈ 0.7165
    t_1h = t0 + timedelta(hours=1)
    s_1h, delta_1h, _ = calculate_temporal_similarity(t_1h, t0)
    assert math.isclose(s_1h, math.exp(-1.0 / 3.0), abs_tol=1e-3)
    assert math.isclose(delta_1h, 1.0, abs_tol=1e-3)

    # 3.0 hours elapsed (half-life window) -> exp(-1) ≈ 0.3679
    t_3h = t0 + timedelta(hours=3)
    s_3h, delta_3h, _ = calculate_temporal_similarity(t_3h, t0)
    assert math.isclose(s_3h, math.exp(-1.0), abs_tol=1e-3)
    assert math.isclose(delta_3h, 3.0, abs_tol=1e-3)

    # 6.0 hours elapsed (cutoff boundary) -> exp(-2) ≈ 0.1353
    t_6h = t0 + timedelta(hours=6)
    s_6h, delta_6h, _ = calculate_temporal_similarity(t_6h, t0)
    assert math.isclose(s_6h, math.exp(-2.0), abs_tol=1e-3)

    # > 6.0 hours elapsed -> Section 4.2 Invariant: S_temp -> 0
    t_6h_1m = t0 + timedelta(hours=6, minutes=1)
    s_cutoff, delta_cutoff, _ = calculate_temporal_similarity(t_6h_1m, t0)
    assert s_cutoff == 0.0
    assert delta_cutoff > 6.0

    # 24 hours elapsed -> 0.0
    t_24h = t0 + timedelta(hours=24)
    s_24h, _, _ = calculate_temporal_similarity(t_24h, t0)
    assert s_24h == 0.0


def test_timezone_aware_timestamps():
    """Timestamps in different timezones representing the same instant must yield Delta t = 0."""
    t_utc = datetime(2026, 9, 26, 14, 0, 0, tzinfo=timezone.utc)
    # UTC+05:30 (Indian Standard Time) is 19:30:00
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    t_ist = datetime(2026, 9, 26, 19, 30, 0, tzinfo=ist_tz)

    s_temp, delta_hours, warnings = calculate_temporal_similarity(t_utc, t_ist)
    assert math.isclose(s_temp, 1.0, abs_tol=1e-4)
    assert delta_hours == 0.0


def test_iso_string_and_future_timestamps():
    """ISO strings and future time deltas must be handled safely and symmetrically."""
    t_str1 = "2026-09-26T14:00:00Z"
    t_str2 = "2026-09-26T15:30:00+00:00"

    s_temp1, d1, _ = calculate_temporal_similarity(t_str1, t_str2)
    s_temp2, d2, _ = calculate_temporal_similarity(t_str2, t_str1)
    assert math.isclose(s_temp1, s_temp2, abs_tol=1e-4)
    assert math.isclose(d1, 1.5, abs_tol=1e-3)
    assert math.isclose(d2, 1.5, abs_tol=1e-3)


# =============================================================================
# 3. Spatial Similarity & Haversine Tests
# =============================================================================
def test_identical_coordinates_produce_similarity_one():
    """Identical coordinates yield distance 0 km and spatial similarity 1.0."""
    lat, lon = 20.2961, 85.8245
    s_spatial, dist_km, match_type, _ = calculate_spatial_similarity(
        lat_report=lat,
        lon_report=lon,
        lat_incident=lat,
        lon_incident=lon,
        d_max_km=2.5,
    )
    assert math.isclose(s_spatial, 1.0, abs_tol=1e-4)
    assert dist_km == 0.0
    assert match_type == "COORDINATES"


def test_nearby_coordinates_proportional_decay():
    """At half cluster radius (1.25 km with d_max = 2.5 km), similarity should be ~0.50."""
    # Approximate ~1.25 km distance north from Patia
    lat1, lon1 = 20.3533, 85.8266
    # 0.0112 degrees latitude is approx 1.25 km
    lat2 = lat1 + (1.25 / 111.0)
    lon2 = lon1

    d_km = haversine_distance_km(lat1, lon1, lat2, lon2)
    assert math.isclose(d_km, 1.25, abs_tol=0.05)

    s_spatial, dist, match_type, _ = calculate_spatial_similarity(
        lat_report=lat1,
        lon_report=lon1,
        lat_incident=lat2,
        lon_incident=lon2,
        d_max_km=2.5,
    )
    assert math.isclose(s_spatial, 1.0 - (d_km / 2.5), abs_tol=1e-3)
    assert 0.45 <= s_spatial <= 0.55
    assert match_type == "COORDINATES"


def test_distant_coordinates_produce_similarity_zero():
    """Coordinates separated by > d_max produce similarity 0.0."""
    # Bhubaneswar (20.2961, 85.8245) to Cuttack (20.4625, 85.8830) ~20 km
    s_spatial, dist_km, match_type, _ = calculate_spatial_similarity(
        lat_report=20.2961,
        lon_report=85.8245,
        lat_incident=20.4625,
        lon_incident=85.8830,
        d_max_km=2.5,
    )
    assert s_spatial == 0.0
    assert dist_km is not None and dist_km > 15.0
    assert match_type == "COORDINATES"


def test_missing_coordinates_fall_back_to_text():
    """Missing coordinates must safely fall back to textual location comparison without crashing."""
    s_spatial, dist, match_type, warnings = calculate_spatial_similarity(
        lat_report=None,
        lon_report=None,
        lat_incident=None,
        lon_incident=None,
        text_report="Patia Square",
        text_incident="patia square",
    )
    assert s_spatial == 0.90
    assert dist is None
    assert match_type == "EXACT_TEXT"


def test_textual_exact_landmark_match():
    """Section 4.3 Case B: Exact landmark match yields 0.90."""
    s, _, m, _ = calculate_spatial_similarity(
        text_report="Rasulgarh underpass",
        text_incident="rasulgarh underpass",
    )
    assert s == 0.90
    assert m == "EXACT_TEXT"


def test_textual_partial_substring_match():
    """Section 4.3 Case B: Substring / token overlap yields 0.60."""
    s, _, m, _ = calculate_spatial_similarity(
        text_report="Patia",
        text_incident="Patia square underpass",
    )
    assert s == 0.60
    assert m == "SUBSTRING_TEXT"


def test_textual_both_unknown_neutral_score():
    """Section 4.3 Case B: Both locations unknown yields neutral 0.50 score."""
    s, _, m, _ = calculate_spatial_similarity(
        text_report=None,
        text_incident=None,
    )
    assert s == 0.50
    assert m == "BOTH_UNKNOWN"

    s2, _, m2, _ = calculate_spatial_similarity(
        text_report="unknown",
        text_incident="",
    )
    assert s2 == 0.50
    assert m2 == "BOTH_UNKNOWN"


def test_no_hallucinated_location_fallback_when_one_unknown():
    """When one location is unknown, returns neutral 0.50 without inventing coordinates."""
    s, dist, m, warn = calculate_spatial_similarity(
        text_report="near market",
        text_incident=None,
    )
    assert s == 0.50
    assert dist is None
    assert m == "ONE_UNKNOWN"
    assert any("neutral" in w.lower() for w in warn)


def test_explicitly_conflicting_locations_hard_veto():
    """Section 4.3 Case B: Explicitly conflicting locations yield S_spatial = 0.0 (hard veto)."""
    s, _, m, _ = calculate_spatial_similarity(
        text_report="Bhubaneswar",
        text_incident="Cuttack",
    )
    assert s == 0.0
    assert m == "CONFLICTING_TEXT"


# =============================================================================
# 4. Combined Correlation & Missing Dimension Tests
# =============================================================================
def test_composite_score_exact_baseline_weights():
    """C_score = 0.55 * S_sem + 0.20 * S_temp + 0.25 * S_spatial."""
    score, is_reweighted, weights, _ = calculate_composite_score(
        s_sem=1.0,
        s_temp=1.0,
        s_spatial=1.0,
    )
    assert math.isclose(score, 1.0, abs_tol=1e-4)
    assert not is_reweighted
    assert weights["semantic"] == DEFAULT_WEIGHT_SEMANTIC
    assert weights["temporal"] == DEFAULT_WEIGHT_TEMPORAL
    assert weights["spatial"] == DEFAULT_WEIGHT_SPATIAL

    # Partial scores: 0.55*0.80 + 0.20*0.50 + 0.25*0.60 = 0.44 + 0.10 + 0.15 = 0.69
    score2, _, _, _ = calculate_composite_score(
        s_sem=0.80,
        s_temp=0.50,
        s_spatial=0.60,
    )
    assert math.isclose(score2, 0.69, abs_tol=1e-3)


def test_missing_semantic_embedding_reweights_proportionally():
    """
    When semantic embedding is missing, non-vector triangulation dimensions
    (temporal, spatial) are reweighted proportionally so absence of ML vector
    does not unfairly force a non-match.
    """
    # Available weights: temporal=0.20, spatial=0.25 -> sum=0.45
    # w_temp' = 0.20 / 0.45 ≈ 0.4444, w_spatial' = 0.25 / 0.45 ≈ 0.5556
    score, is_reweighted, weights, warnings = calculate_composite_score(
        s_sem=None,
        s_temp=1.0,
        s_spatial=1.0,
        reweight_missing=True,
    )
    assert is_reweighted
    assert math.isclose(score, 1.0, abs_tol=1e-3)
    assert math.isclose(weights["temporal"], 0.20 / 0.45, abs_tol=1e-3)
    assert math.isclose(weights["spatial"], 0.25 / 0.45, abs_tol=1e-3)
    assert any("semantic" in w.lower() for w in warnings)


def test_missing_semantic_embedding_without_reweighting():
    """When reweight_missing is False, missing dimensions contribute 0.0."""
    score, is_reweighted, _, _ = calculate_composite_score(
        s_sem=None,
        s_temp=1.0,
        s_spatial=1.0,
        reweight_missing=False,
    )
    assert not is_reweighted
    # 0.20 * 1.0 + 0.25 * 1.0 = 0.45
    assert math.isclose(score, 0.45, abs_tol=1e-3)


def test_similarity_and_composite_bounds():
    """All components and composite score must strictly adhere to documented bounds."""
    # Negative semantic dot product
    score_low, _, _, _ = calculate_composite_score(
        s_sem=-1.0,
        s_temp=0.0,
        s_spatial=0.0,
    )
    assert score_low == 0.0  # Clamped to 0.0

    score_high, _, _, _ = calculate_composite_score(
        s_sem=1.0,
        s_temp=1.0,
        s_spatial=1.0,
    )
    assert score_high == 1.0  # Clamped to 1.0


# =============================================================================
# 5. Relationship Classification Tests
# =============================================================================
def test_first_report_initial_classification():
    """First report establishing an incident is classified as INITIAL."""
    rel, is_match, expl = classify_relationship(
        c_score=0.95,
        s_sem=0.95,
        s_temp=1.0,
        s_spatial=1.0,
        spatial_match_type="COORDINATES",
        delta_hours=0.0,
        is_first_report=True,
    )
    assert rel == RelationshipType.INITIAL
    assert is_match is True
    assert "establishing" in expl.lower()


def test_duplicate_classification_verbatim_text():
    """Report with verbatim identical text is classified as DUPLICATE."""
    rel, is_match, expl = classify_relationship(
        c_score=0.88,
        s_sem=0.90,
        s_temp=0.95,
        s_spatial=0.80,
        spatial_match_type="COORDINATES",
        delta_hours=0.2,
        report_text="Flash flood at Patia square, 3 people trapped",
        candidate_texts=["Flash flood at Patia square, 3 people trapped"],
        report_source_id="+91-9999999999",
        candidate_source_ids=["+91-1111111111"],  # Even with different phone!
    )
    assert rel == RelationshipType.DUPLICATE
    assert is_match is True
    assert "duplicate" in expl.lower()


def test_duplicate_classification_same_source():
    """Report from the same phone/source is classified as DUPLICATE."""
    rel, is_match, expl = classify_relationship(
        c_score=0.78,
        s_sem=0.80,
        s_temp=0.90,
        s_spatial=0.70,
        spatial_match_type="COORDINATES",
        delta_hours=0.5,
        report_text="Water is now reaching waist level",
        candidate_texts=["Flooding here near market"],
        report_source_id="caller_alice",
        candidate_source_ids=["caller_alice"],  # Repeated caller
    )
    assert rel == RelationshipType.DUPLICATE
    assert is_match is True
    assert "source 'caller_alice'" in expl


def test_corroborating_classification():
    """Distinct source with formatted variation and consistent facts -> CORROBORATING."""
    rel, is_match, expl = classify_relationship(
        c_score=0.78,
        s_sem=0.82,
        s_temp=0.90,
        s_spatial=0.75,
        spatial_match_type="COORDINATES",
        delta_hours=0.3,
        report_text="Water has entered homes near Patia temple",
        candidate_texts=["Heavy flooding reported on Patia main road"],
        report_source_id="+91-9876543210",
        candidate_source_ids=["+91-1234567890"],
    )
    assert rel == RelationshipType.CORROBORATING
    assert is_match is True
    assert "corroboration" in expl.lower()


def test_related_classification_secondary_effect():
    """Report reporting secondary hazard effect is classified as RELATED."""
    rel, is_match, expl = classify_relationship(
        c_score=0.75,
        s_sem=0.76,
        s_temp=0.90,
        s_spatial=0.70,
        spatial_match_type="COORDINATES",
        delta_hours=0.4,
        is_secondary_effect=True,
    )
    assert rel == RelationshipType.RELATED
    assert is_match is True
    assert "secondary" in expl.lower()


def test_uncertain_classification_high_semantic_conflicting_location():
    """Section 6.1: High semantic match with conflicting location -> UNCERTAIN."""
    rel, is_match, expl = classify_relationship(
        c_score=0.60,
        s_sem=0.88,  # High semantic match
        s_temp=0.95,
        s_spatial=0.0,
        spatial_match_type="CONFLICTING_TEXT",  # Bhubaneswar vs Cuttack
        delta_hours=0.2,
    )
    assert rel == RelationshipType.UNCERTAIN
    assert is_match is True
    assert "uncertain" in expl.lower()
    assert "conflicting location" in expl.lower()


def test_uncertain_classification_high_semantic_contradictory_time():
    """Section 6.1: High semantic match with contradictory time (>6h) -> UNCERTAIN."""
    rel, is_match, expl = classify_relationship(
        c_score=0.55,
        s_sem=0.85,  # High semantic match
        s_temp=0.0,   # S_temp = 0 due to Delta t > 6h
        s_spatial=0.90,
        spatial_match_type="COORDINATES",
        delta_hours=10.0,  # 10 hours later
    )
    assert rel == RelationshipType.UNCERTAIN
    assert is_match is True
    assert "uncertain" in expl.lower()
    assert "elapsed time" in expl.lower()


def test_distinct_incident_below_threshold():
    """Score below corroboration threshold (0.70) is treated as distinct incident."""
    rel, is_match, expl = classify_relationship(
        c_score=0.45,
        s_sem=0.40,
        s_temp=0.50,
        s_spatial=0.50,
        spatial_match_type="SUBSTRING_TEXT",
        delta_hours=2.0,
    )
    assert rel == RelationshipType.INITIAL
    assert is_match is False
    assert "distinct incident" in expl.lower()


# =============================================================================
# 6. Corroboration Metric Formulation Tests (Section 6.3)
# =============================================================================
def test_corroboration_score_asymptotic_saturation():
    """
    Validates exact saturation curve: Score = round(1.0 - exp(-0.45 * N), 2)
    Section 6.3 values:
      N=1 -> 0.36
      N=2 -> 0.59
      N=3 -> 0.74
      N=5 -> 0.89
      N>=7 -> 0.96 -> 1.0
    """
    assert calculate_corroboration_score(0) == 0.0
    assert calculate_corroboration_score(1) == 0.36
    assert calculate_corroboration_score(2) == 0.59
    assert calculate_corroboration_score(3) == 0.74
    assert calculate_corroboration_score(5) == 0.89
    assert calculate_corroboration_score(7) == 0.96
    assert calculate_corroboration_score(10) == 0.99
    assert calculate_corroboration_score(100) == 1.0


def test_corroboration_explanation_formatting():
    """Plain-language corroboration explanation format."""
    expl0 = generate_corroboration_explanation(0, 0, 0.0)
    assert "No independent verification" in expl0

    expl1 = generate_corroboration_explanation(1, 1, 0.36)
    assert "Single eyewitness source" in expl1

    expl2 = generate_corroboration_explanation(2, 2, 0.59)
    assert "Corroborated by 2 distinct field reports" in expl2


# =============================================================================
# 7. Testing.md Section 4 Integration Simulation
# =============================================================================
def test_architecture_testing_pyramid_scenario_2():
    """
    Directly verifies testing.md Section 4 Scenario 2:
    - Ingest Report A (flood at Patia) -> Spawns Incident 1.
    - Ingest Report B (identical wording, different phone) -> DUPLICATE, sources=1.
    - Ingest Report C (different wording, same coordinates) -> CORROBORATING, sources=2.
    """
    emb_patia = make_dense_normalized_vector(seed_val=1.0)
    t0 = datetime(2026, 9, 26, 14, 0, 0, tzinfo=timezone.utc)

    # 1. Report A spawns Incident 1
    res_a = correlate_report_to_incident(
        report_text="Flash flood at Patia square, cars submerged",
        report_embedding=emb_patia,
        report_timestamp=t0,
        report_latitude=20.3533,
        report_longitude=85.8266,
        report_location_text="Patia square",
        report_source_id="caller_alice",
        is_first_report=True,
    )
    assert res_a.relationship == RelationshipType.INITIAL
    assert res_a.independent_sources_count == 1
    assert res_a.corroboration_score == 0.36

    # Incident 1 state spawned by Report A
    incident_1 = {
        "incident_id": "inc-patia-01",
        "embedding": emb_patia,
        "updated_at": t0,
        "latitude": 20.3533,
        "longitude": 85.8266,
        "location_text": "Patia square",
        "report_count": 1,
        "independent_source_count": 1,
    }

    # 2. Report B: Identical wording, different phone
    t_b = t0 + timedelta(minutes=5)
    res_b = correlate_report_to_incident(
        report_text="Flash flood at Patia square, cars submerged",  # Identical wording
        report_embedding=emb_patia,
        report_timestamp=t_b,
        report_latitude=20.3533,
        report_longitude=85.8266,
        report_location_text="Patia square",
        report_source_id="caller_bob",  # Different phone
        incident=incident_1,
        candidate_texts=["Flash flood at Patia square, cars submerged"],
        candidate_source_ids=["caller_alice"],
    )
    assert res_b.relationship == RelationshipType.DUPLICATE
    assert res_b.independent_sources_count == 1  # 0 increase
    assert res_b.corroboration_score == 0.36

    # 3. Report C: Different wording, same coordinates, different phone
    t_c = t0 + timedelta(minutes=15)
    # Slightly varied embedding (cos ~ 0.85)
    emb_c = make_dense_normalized_vector(seed_val=1.1)
    res_c = correlate_report_to_incident(
        report_text="Water rising rapidly near Patia market, residents evacuating",
        report_embedding=emb_c,
        report_timestamp=t_c,
        report_latitude=20.3533,
        report_longitude=85.8266,
        report_location_text="Patia market",
        report_source_id="caller_charlie",  # Distinct source
        incident=incident_1,
        candidate_texts=[
            "Flash flood at Patia square, cars submerged",
            "Flash flood at Patia square, cars submerged",
        ],
        candidate_source_ids=["caller_alice", "caller_bob"],
        current_report_count=2,
        current_independent_sources=1,
    )
    assert res_c.relationship == RelationshipType.CORROBORATING
    assert res_c.independent_sources_count == 2  # +1 increase
    assert res_c.corroboration_score == 0.59


# =============================================================================
# 8. Deterministic Repeatability & Multi-Candidate Matching
# =============================================================================
def test_deterministic_repeatability():
    """Running correlation 100 times on identical inputs produces identical results."""
    v1 = make_dense_normalized_vector(1.5)
    v2 = make_dense_normalized_vector(1.8)
    t1 = datetime(2026, 9, 26, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 26, 11, 0, 0, tzinfo=timezone.utc)

    first_res = correlate_report_to_incident(
        report_text="Trapped civilians near Rasulgarh",
        report_embedding=v1,
        report_timestamp=t1,
        report_latitude=20.2961,
        report_longitude=85.8245,
        incident_embedding=v2,
        incident_timestamp=t2,
        incident_latitude=20.2970,
        incident_longitude=85.8250,
        report_source_id="src_1",
        candidate_source_ids=["src_2"],
    )

    for _ in range(50):
        res = correlate_report_to_incident(
            report_text="Trapped civilians near Rasulgarh",
            report_embedding=v1,
            report_timestamp=t1,
            report_latitude=20.2961,
            report_longitude=85.8245,
            incident_embedding=v2,
            incident_timestamp=t2,
            incident_latitude=20.2970,
            incident_longitude=85.8250,
            report_source_id="src_1",
            candidate_source_ids=["src_2"],
        )
        assert res.relationship == first_res.relationship
        assert res.composite_score == first_res.composite_score
        assert res.triangulation.semantic_similarity == first_res.triangulation.semantic_similarity
        assert res.triangulation.temporal_similarity == first_res.triangulation.temporal_similarity
        assert res.triangulation.spatial_similarity == first_res.triangulation.spatial_similarity


def test_find_best_incident_match():
    """Finds best matching candidate among multiple candidate incidents."""
    emb_target = make_dense_normalized_vector(1.0)
    t_now = datetime(2026, 9, 26, 14, 0, 0, tzinfo=timezone.utc)

    # Candidate 1: Close in space and time
    cand_1 = {
        "incident_id": "inc-close",
        "embedding": make_dense_normalized_vector(1.05),
        "updated_at": t_now - timedelta(minutes=10),
        "location": {"latitude": 20.2961, "longitude": 85.8245, "text": "Rasulgarh"},
        "report_count": 2,
        "independent_source_count": 2,
    }

    # Candidate 2: Distant in space (Cuttack)
    cand_2 = {
        "incident_id": "inc-distant",
        "embedding": make_dense_normalized_vector(1.05),
        "updated_at": t_now - timedelta(minutes=10),
        "location": {"latitude": 20.4625, "longitude": 85.8830, "text": "Cuttack"},
        "report_count": 1,
        "independent_source_count": 1,
    }

    report = {
        "text": "Rising water in Rasulgarh underpass",
        "embedding": emb_target,
        "reported_at": t_now,
        "location": {"latitude": 20.2965, "longitude": 85.8250, "text": "Rasulgarh underpass"},
        "metadata": {"caller_id": "+91-9999900000"},
    }

    best_cand, result = find_best_incident_match(report, [cand_1, cand_2])
    assert best_cand is not None
    assert best_cand["incident_id"] == "inc-close"
    assert result.is_match is True
    assert result.composite_score >= DEFAULT_CORROBORATION_THRESHOLD


def test_find_best_incident_match_no_match_returns_initial():
    """When no candidate matches, returns None and INITIAL relationship."""
    emb = make_dense_normalized_vector(1.0)
    t_now = datetime(2026, 9, 26, 14, 0, 0, tzinfo=timezone.utc)

    # Distant and old candidate
    cand_old = {
        "incident_id": "inc-old",
        "embedding": make_dense_normalized_vector(50.0),
        "updated_at": t_now - timedelta(hours=24),
        "location": {"latitude": 20.4625, "longitude": 85.8830, "text": "Cuttack"},
        "report_count": 1,
        "independent_source_count": 1,
    }

    report = {
        "text": "Structural damage in Patia",
        "embedding": emb,
        "reported_at": t_now,
        "location": {"latitude": 20.3533, "longitude": 85.8266, "text": "Patia"},
    }

    best_cand, result = find_best_incident_match(report, [cand_old])
    assert best_cand is None
    assert result.relationship == RelationshipType.INITIAL
    assert result.is_match is True  # Spawns new incident
