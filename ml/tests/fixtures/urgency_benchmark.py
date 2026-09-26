"""
Karen's Ear — Curated Engineering Urgency Benchmark.

An independently curated engineering benchmark for operational urgency scoring and tiering:
- CRITICAL (80–100)
- HIGH (60–79)
- MEDIUM (35–59)
- LOW (0–34)

CRITICAL DATASET NOTICE:
This benchmark dataset is an internal engineering test fixture containing curated engineering
reference labels. It is used to verify deterministic score behavior, component breakdown,
boundary threshold mapping, confidence calibration, and latency.

IT IS STRICTLY NOT:
- Ground truth from CrisiText (CrisiText does NOT provide operational urgency labels).
- Evidence of real-world 100% field accuracy on unconstrained disaster dispatches.
- A training set (no model in this feature was trained on these labels).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UrgencyBenchmarkSample:
    """A single evaluation record in the curated engineering urgency benchmark."""

    id: str
    text: str
    expected_reference_label: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    scenario_category: str
    difficulty: str  # "straightforward", "paraphrased", "challenging", "boundary"
    upstream_incident_type: str | None = None
    upstream_people_count: int | None = None
    upstream_people_signals: tuple[str, ...] = ()
    upstream_response_categories: tuple[str, ...] = ()
    expected_score_range: tuple[float, float] = (0.0, 100.0)
    notes: str = ""


CURATED_URGENCY_BENCHMARK: tuple[UrgencyBenchmarkSample, ...] = (
    # ==========================================================================
    # 1. CRITICAL Scenarios (Score >= 80)
    # ==========================================================================
    UrgencyBenchmarkSample(
        id="crit_01",
        text="Emergency! Four residents trapped under heavy concrete rubble after building collapse in Sector 4!",
        expected_reference_label="CRITICAL",
        scenario_category="critical",
        difficulty="straightforward",
        upstream_incident_type="STRUCTURAL_COLLAPSE",
        upstream_people_count=4,
        upstream_people_signals=("TRAPPED",),
        upstream_response_categories=("SEARCH_AND_RESCUE",),
        expected_score_range=(80.0, 100.0),
        notes="High life-safety (trapped + count 4) and structural collapse.",
    ),
    UrgencyBenchmarkSample(
        id="crit_02",
        text="HELP! Flash flood waters rising fast, family of five stranded on rooftop unable to get down!",
        expected_reference_label="CRITICAL",
        scenario_category="critical",
        difficulty="straightforward",
        upstream_incident_type="FLOOD_FLASH_FLOOD",
        upstream_people_count=5,
        upstream_people_signals=("TRAPPED", "MULTIPLE_PEOPLE"),
        upstream_response_categories=("SEARCH_AND_RESCUE",),
        expected_score_range=(80.0, 100.0),
        notes="Rising fast velocity + trapped family with distress scream.",
    ),
    UrgencyBenchmarkSample(
        id="crit_03",
        text="Active shooter firing at crowd near the central transit plaza, multiple people down bleeding heavily!",
        expected_reference_label="CRITICAL",
        scenario_category="critical",
        difficulty="challenging",
        upstream_incident_type="CIVIL_UNREST_ACTIVE_THREAT",
        upstream_people_signals=("INJURED", "MULTIPLE_PEOPLE"),
        upstream_response_categories=("POLICE_SECURITY", "MEDICAL_EMS"),
        expected_score_range=(80.0, 100.0),
        notes="Active ongoing threat with severe bleeding casualties.",
    ),

    # ==========================================================================
    # 2. HIGH Scenarios (Score 60–79)
    # ==========================================================================
    UrgencyBenchmarkSample(
        id="high_01",
        text="Structure fire on 2nd floor of apartment complex. Heavy black smoke pouring out, one person suffered burns.",
        expected_reference_label="HIGH",
        scenario_category="high",
        difficulty="straightforward",
        upstream_incident_type="FIRE_WILDFIRE_EXPLOSION",
        upstream_people_count=1,
        upstream_people_signals=("INJURED",),
        upstream_response_categories=("FIRE_HAZMAT", "MEDICAL_EMS"),
        expected_score_range=(60.0, 79.9),
        notes="Active fire with single injury, no trapped occupants.",
    ),
    UrgencyBenchmarkSample(
        id="high_02",
        text="Severe two-vehicle collision on highway overpass. Driver is unconscious and pinned behind wheel.",
        expected_reference_label="HIGH",
        scenario_category="high",
        difficulty="challenging",
        upstream_incident_type="OTHER_GENERAL_INCIDENT",
        upstream_people_count=1,
        upstream_people_signals=("UNCONSCIOUS", "TRAPPED"),
        upstream_response_categories=("SEARCH_AND_RESCUE", "MEDICAL_EMS"),
        expected_score_range=(60.0, 79.9),
        notes="Single pinned unconscious victim in vehicle collision.",
    ),
    UrgencyBenchmarkSample(
        id="high_03",
        text="Commercial gas line rupture emitting strong hiss and vapor plume, nearby shops evacuating.",
        expected_reference_label="HIGH",
        scenario_category="high",
        difficulty="straightforward",
        upstream_incident_type="FIRE_WILDFIRE_EXPLOSION",
        upstream_response_categories=("FIRE_HAZMAT",),
        expected_score_range=(60.0, 79.9),
        notes="High hazard velocity (gas leak spreading) without reported casualties.",
    ),

    # ==========================================================================
    # 3. MEDIUM Scenarios (Score 35–59)
    # ==========================================================================
    UrgencyBenchmarkSample(
        id="med_01",
        text="Heavy rain causing water accumulation across Main Street, road blocked by standing water up to knee height.",
        expected_reference_label="MEDIUM",
        scenario_category="medium",
        difficulty="straightforward",
        upstream_incident_type="FLOOD_FLASH_FLOOD",
        upstream_response_categories=("PUBLIC_WORKS_UTILITY",),
        expected_score_range=(35.0, 59.9),
        notes="Standing flood water blocking traffic, no injuries or trapped persons.",
    ),
    UrgencyBenchmarkSample(
        id="med_02",
        text="Transformer blown on utility pole resulting in power blackout for two city blocks.",
        expected_reference_label="MEDIUM",
        scenario_category="medium",
        difficulty="straightforward",
        upstream_incident_type="UTILITY_INFRASTRUCTURE_FAILURE",
        upstream_response_categories=("PUBLIC_WORKS_UTILITY",),
        expected_score_range=(35.0, 59.9),
        notes="Localized utility infrastructure failure.",
    ),
    UrgencyBenchmarkSample(
        id="med_03",
        text="Large bough of oak tree fell across two lanes of traffic, vehicles are detouring safely.",
        expected_reference_label="MEDIUM",
        scenario_category="medium",
        difficulty="straightforward",
        upstream_incident_type="OTHER_GENERAL_INCIDENT",
        upstream_response_categories=("PUBLIC_WORKS_UTILITY",),
        expected_score_range=(35.0, 59.9),
        notes="Road obstruction with no casualties.",
    ),

    # ==========================================================================
    # 4. LOW Scenarios (Score 0–34)
    # ==========================================================================
    UrgencyBenchmarkSample(
        id="low_01",
        text="Advisory notice: Municipal water department scheduled pipeline maintenance tomorrow between 9am and 1pm.",
        expected_reference_label="LOW",
        scenario_category="low",
        difficulty="straightforward",
        upstream_incident_type="UTILITY_INFRASTRUCTURE_FAILURE",
        expected_score_range=(0.0, 34.9),
        notes="Informational scheduled maintenance with no emergency.",
    ),
    UrgencyBenchmarkSample(
        id="low_02",
        text="Information desk opened at town hall to assist citizens with filing storm damage claims.",
        expected_reference_label="LOW",
        scenario_category="low",
        difficulty="challenging",
        upstream_incident_type="OTHER_GENERAL_INCIDENT",
        expected_score_range=(0.0, 34.9),
        notes="Casual mention of help desk; must not trigger emergency distress.",
    ),
    UrgencyBenchmarkSample(
        id="low_03",
        text="Light drizzle observed in western suburbs, roadways remain clear and dry.",
        expected_reference_label="LOW",
        scenario_category="low",
        difficulty="straightforward",
        upstream_incident_type="SEVERE_WEATHER_STORM",
        expected_score_range=(0.0, 34.9),
        notes="Minor weather observation without hazard.",
    ),

    # ==========================================================================
    # 5. Ambiguous / Hedged Scenarios
    # ==========================================================================
    UrgencyBenchmarkSample(
        id="amb_01",
        text="Someone said there might possibly be people trapped near the old mill, not sure if anyone is actually inside.",
        expected_reference_label="MEDIUM",
        scenario_category="ambiguous",
        difficulty="challenging",
        upstream_people_signals=("TRAPPED",),
        expected_score_range=(35.0, 59.9),
        notes="Hedged report reduces confidence while preserving medium score.",
    ),
    UrgencyBenchmarkSample(
        id="amb_02",
        text="Unconfirmed rumors of a small chemical leak behind the warehouse, situation unclear.",
        expected_reference_label="MEDIUM",
        scenario_category="ambiguous",
        difficulty="challenging",
        expected_score_range=(35.0, 59.9),
        notes="Unverified hazard mention yields medium score with low confidence.",
    ),

    # ==========================================================================
    # 6. Historical / Past / Non-Active Incidents
    # ==========================================================================
    UrgencyBenchmarkSample(
        id="hist_01",
        text="Warehouse burned yesterday evening; fire is fully extinguished and area is now secured by patrol.",
        expected_reference_label="LOW",
        scenario_category="historical/non-active",
        difficulty="challenging",
        upstream_incident_type="FIRE_WILDFIRE_EXPLOSION",
        expected_score_range=(0.0, 34.9),
        notes="Historical burned yesterday + extinguished suppresses velocity.",
    ),
    UrgencyBenchmarkSample(
        id="hist_02",
        text="Old pedestrian bridge collapsed yesterday afternoon; barriers in place and river traffic cleared.",
        expected_reference_label="LOW",
        scenario_category="historical/non-active",
        difficulty="challenging",
        upstream_incident_type="STRUCTURAL_COLLAPSE",
        expected_score_range=(0.0, 34.9),
        notes="Historical collapse from yesterday with secured scene.",
    ),

    # ==========================================================================
    # 7. Negated Incidents
    # ==========================================================================
    UrgencyBenchmarkSample(
        id="neg_01",
        text="Delivery van collided with concrete barrier; zero casualties, no one is injured and driver is safe.",
        expected_reference_label="LOW",
        scenario_category="negated",
        difficulty="challenging",
        upstream_incident_type="OTHER_GENERAL_INCIDENT",
        expected_score_range=(0.0, 34.9),
        notes="Explicit negation of injuries suppresses life safety to 0.",
    ),
    UrgencyBenchmarkSample(
        id="neg_02",
        text="Basement flooded with water but all occupants evacuated safely, no reports of people trapped.",
        expected_reference_label="MEDIUM",
        scenario_category="negated",
        difficulty="challenging",
        upstream_incident_type="FLOOD_FLASH_FLOOD",
        expected_score_range=(35.0, 59.9),
        notes="Flooding hazard remains but life safety is negated.",
    ),

    # ==========================================================================
    # 8. Sparse Reports
    # ==========================================================================
    UrgencyBenchmarkSample(
        id="sparse_01",
        text="Road blocked.",
        expected_reference_label="LOW",
        scenario_category="sparse",
        difficulty="straightforward",
        expected_score_range=(0.0, 34.9),
        notes="Ultra-sparse two-word dispatch with minimal obstruction.",
    ),
    UrgencyBenchmarkSample(
        id="sparse_02",
        text="Power out.",
        expected_reference_label="LOW",
        scenario_category="sparse",
        difficulty="straightforward",
        expected_score_range=(0.0, 34.9),
        notes="Sparse utility report.",
    ),

    # ==========================================================================
    # 9. Multi-Signal Composite Incidents
    # ==========================================================================
    UrgencyBenchmarkSample(
        id="multi_01",
        text="URGENT! Live power lines sparking across flooded street with two passengers trapped in partially submerged vehicle!",
        expected_reference_label="CRITICAL",
        scenario_category="multi-signal",
        difficulty="challenging",
        upstream_incident_type="UTILITY_INFRASTRUCTURE_FAILURE",
        upstream_people_count=2,
        upstream_people_signals=("TRAPPED",),
        upstream_response_categories=("SEARCH_AND_RESCUE", "PUBLIC_WORKS_UTILITY"),
        expected_score_range=(80.0, 100.0),
        notes="Multi-signal convergence: arcing wires + flood + trapped victims.",
    ),
    UrgencyBenchmarkSample(
        id="multi_02",
        text="Factory explosion causing rapid spreading fire, six workers injured with severe burns, others missing.",
        expected_reference_label="CRITICAL",
        scenario_category="multi-signal",
        difficulty="challenging",
        upstream_incident_type="FIRE_WILDFIRE_EXPLOSION",
        upstream_people_count=6,
        upstream_people_signals=("INJURED", "MISSING"),
        upstream_response_categories=("FIRE_HAZMAT", "MEDICAL_EMS", "SEARCH_AND_RESCUE"),
        expected_score_range=(80.0, 100.0),
        notes="Explosion + spreading fire + multiple burn casualties.",
    ),

    # ==========================================================================
    # 10. Vulnerable Populations
    # ==========================================================================
    UrgencyBenchmarkSample(
        id="vuln_01",
        text="Daycare center on Riverside Road has floodwaters entering ground floor, ten toddlers and caregivers stuck upstairs!",
        expected_reference_label="CRITICAL",
        scenario_category="vulnerable_populations",
        difficulty="challenging",
        upstream_incident_type="FLOOD_FLASH_FLOOD",
        upstream_people_count=10,
        upstream_people_signals=("CHILDREN", "TRAPPED"),
        upstream_response_categories=("SEARCH_AND_RESCUE",),
        expected_score_range=(80.0, 100.0),
        notes="Toddlers and daycare facility at risk elevates vulnerability.",
    ),
    UrgencyBenchmarkSample(
        id="vuln_02",
        text="Nursing home lost electrical power for medical ventilators, eight bedridden elderly patients in urgent danger.",
        expected_reference_label="CRITICAL",
        scenario_category="vulnerable_populations",
        difficulty="challenging",
        upstream_incident_type="UTILITY_INFRASTRUCTURE_FAILURE",
        upstream_people_count=8,
        upstream_people_signals=("ELDERLY", "PATIENTS"),
        upstream_response_categories=("MEDICAL_EMS",),
        expected_score_range=(80.0, 100.0),
        notes="Bedridden elderly patients needing power for life support.",
    ),
    UrgencyBenchmarkSample(
        id="vuln_03",
        text="Traffic stalled on Elm Street passing by the elementary school, school is closed for holidays.",
        expected_reference_label="LOW",
        scenario_category="vulnerable_populations",
        difficulty="challenging",
        upstream_incident_type="OTHER_GENERAL_INCIDENT",
        expected_score_range=(0.0, 34.9),
        notes="Passive school mention with zero children present.",
    ),

    # ==========================================================================
    # 11. High Hazard Velocity
    # ==========================================================================
    UrgencyBenchmarkSample(
        id="vel_01",
        text="Irrigation dam breach in progress, wall of water rushing rapidly toward low-lying agricultural settlement!",
        expected_reference_label="CRITICAL",
        scenario_category="high_hazard_velocity",
        difficulty="straightforward",
        upstream_incident_type="FLOOD_FLASH_FLOOD",
        upstream_response_categories=("SEARCH_AND_RESCUE",),
        expected_score_range=(80.0, 100.0),
        notes="Dam breach in progress represents extreme velocity and mortal threat.",
    ),
    UrgencyBenchmarkSample(
        id="vel_02",
        text="Flames spreading rapidly between commercial row houses, wind gusting strongly driving fire across alley.",
        expected_reference_label="HIGH",
        scenario_category="high_hazard_velocity",
        difficulty="straightforward",
        upstream_incident_type="FIRE_WILDFIRE_EXPLOSION",
        upstream_response_categories=("FIRE_HAZMAT",),
        expected_score_range=(60.0, 79.9),
        notes="Rapid spreading fire driven by wind.",
    ),

    # ==========================================================================
    # 12. Strong Distress Language
    # ==========================================================================
    UrgencyBenchmarkSample(
        id="dist_01",
        text="PLEASE HELP! We are drowning in the basement, water level rising fast, we cannot hold on much longer!",
        expected_reference_label="CRITICAL",
        scenario_category="strong_distress",
        difficulty="challenging",
        upstream_incident_type="FLOOD_FLASH_FLOOD",
        upstream_people_signals=("DROWNING", "TRAPPED"),
        upstream_response_categories=("SEARCH_AND_RESCUE",),
        expected_score_range=(80.0, 100.0),
        notes="Extreme distress plea with imminent drowning threat.",
    ),
    UrgencyBenchmarkSample(
        id="dist_02",
        text="SOS! Fire jumping to our roof, smoke is suffocating us, please send help now!",
        expected_reference_label="CRITICAL",
        scenario_category="strong_distress",
        difficulty="challenging",
        upstream_incident_type="FIRE_WILDFIRE_EXPLOSION",
        upstream_people_signals=("TRAPPED",),
        upstream_response_categories=("FIRE_HAZMAT", "SEARCH_AND_RESCUE"),
        expected_score_range=(80.0, 100.0),
        notes="SOS distress call with suffocating smoke and spreading fire.",
    ),

    # ==========================================================================
    # 13. Utility / Public Works
    # ==========================================================================
    UrgencyBenchmarkSample(
        id="util_01",
        text="Water main ruptured under 5th Avenue spewing mud across sidewalk, utility crew notified.",
        expected_reference_label="MEDIUM",
        scenario_category="utility_public_works",
        difficulty="straightforward",
        upstream_incident_type="UTILITY_INFRASTRUCTURE_FAILURE",
        upstream_response_categories=("PUBLIC_WORKS_UTILITY",),
        expected_score_range=(35.0, 59.9),
        notes="Standard municipal utility infrastructure issue without life threat.",
    ),
    UrgencyBenchmarkSample(
        id="util_02",
        text="Streetlights non-functional along arterial ring road due to substation tripped breaker.",
        expected_reference_label="LOW",
        scenario_category="utility_public_works",
        difficulty="straightforward",
        upstream_incident_type="UTILITY_INFRASTRUCTURE_FAILURE",
        expected_score_range=(0.0, 34.9),
        notes="Minor lighting outage.",
    ),

    # ==========================================================================
    # 14. Medical Emergency
    # ==========================================================================
    UrgencyBenchmarkSample(
        id="med_emerg_01",
        text="Elderly man collapsed on train platform, stopped breathing, bystander performing CPR right now.",
        expected_reference_label="CRITICAL",
        scenario_category="medical",
        difficulty="challenging",
        upstream_incident_type="MEDICAL_EMERGENCY",
        upstream_people_count=1,
        upstream_people_signals=("UNCONSCIOUS", "ELDERLY"),
        upstream_response_categories=("MEDICAL_EMS",),
        expected_score_range=(80.0, 100.0),
        notes="Not breathing + cardiac arrest elevates life safety to maximum.",
    ),
    UrgencyBenchmarkSample(
        id="med_emerg_02",
        text="Cyclist struck by car, bleeding heavily from open leg fracture but conscious and talking.",
        expected_reference_label="HIGH",
        scenario_category="medical",
        difficulty="straightforward",
        upstream_incident_type="MEDICAL_EMERGENCY",
        upstream_people_count=1,
        upstream_people_signals=("INJURED",),
        upstream_response_categories=("MEDICAL_EMS",),
        expected_score_range=(60.0, 79.9),
        notes="Profuse bleeding trauma victim.",
    ),

    # ==========================================================================
    # 15. Fire / Hazmat
    # ==========================================================================
    UrgencyBenchmarkSample(
        id="fire_01",
        text="Ammonia leak spreading from fertilizer plant, pungent toxic cloud drifting toward residential subdivisions.",
        expected_reference_label="HIGH",
        scenario_category="fire_hazmat",
        difficulty="straightforward",
        upstream_incident_type="FIRE_WILDFIRE_EXPLOSION",
        upstream_response_categories=("FIRE_HAZMAT",),
        expected_score_range=(60.0, 79.9),
        notes="Toxic gas leak spreading dynamically.",
    ),
    UrgencyBenchmarkSample(
        id="fire_02",
        text="Dumpster fire in alley behind grocery store, contained within metal bin with no exposure.",
        expected_reference_label="LOW",
        scenario_category="fire_hazmat",
        difficulty="straightforward",
        upstream_incident_type="FIRE_WILDFIRE_EXPLOSION",
        upstream_response_categories=("FIRE_HAZMAT",),
        expected_score_range=(0.0, 34.9),
        notes="Contained fire with low velocity and zero life risk.",
    ),

    # ==========================================================================
    # 16. Security / Active Threat
    # ==========================================================================
    UrgencyBenchmarkSample(
        id="sec_01",
        text="Assailant with machete attacking passengers inside metro station, several people wounded and screaming!",
        expected_reference_label="CRITICAL",
        scenario_category="security",
        difficulty="challenging",
        upstream_incident_type="CIVIL_UNREST_ACTIVE_THREAT",
        upstream_people_signals=("INJURED", "MULTIPLE_PEOPLE"),
        upstream_response_categories=("POLICE_SECURITY", "MEDICAL_EMS"),
        expected_score_range=(80.0, 100.0),
        notes="Active violent threat with wounded victims.",
    ),
    UrgencyBenchmarkSample(
        id="sec_02",
        text="Peaceful demonstration gathering outside municipal offices, traffic slowed but orderly.",
        expected_reference_label="LOW",
        scenario_category="security",
        difficulty="straightforward",
        upstream_incident_type="CIVIL_UNREST_ACTIVE_THREAT",
        expected_score_range=(0.0, 34.9),
        notes="Non-violent civic event without peril.",
    ),

    # ==========================================================================
    # 17. Structural Collapse
    # ==========================================================================
    UrgencyBenchmarkSample(
        id="coll_01",
        text="Market canopy collapsing right now under weight of storm debris, vendors scrambling to get out!",
        expected_reference_label="CRITICAL",
        scenario_category="structural_collapse",
        difficulty="challenging",
        upstream_incident_type="STRUCTURAL_COLLAPSE",
        upstream_response_categories=("SEARCH_AND_RESCUE",),
        expected_score_range=(80.0, 100.0),
        notes="Collapse in progress with victims scrambling to escape.",
    ),
    UrgencyBenchmarkSample(
        id="coll_02",
        text="Cracks observed along supporting pillar of old parking garage, vehicles being redirected as precaution.",
        expected_reference_label="MEDIUM",
        scenario_category="structural_collapse",
        difficulty="straightforward",
        upstream_incident_type="STRUCTURAL_COLLAPSE",
        expected_score_range=(35.0, 59.9),
        notes="Precautionary structural damage without active failure.",
    ),

    # ==========================================================================
    # 18. Flooding
    # ==========================================================================
    UrgencyBenchmarkSample(
        id="flood_01",
        text="River embankment overflowed, floodwaters entering residential compound with depth reaching 4 feet.",
        expected_reference_label="HIGH",
        scenario_category="flooding",
        difficulty="straightforward",
        upstream_incident_type="FLOOD_FLASH_FLOOD",
        upstream_response_categories=("SEARCH_AND_RESCUE",),
        expected_score_range=(60.0, 79.9),
        notes="Active inundation into residential homes.",
    ),
    UrgencyBenchmarkSample(
        id="flood_02",
        text="Ditch overflow causing minor water pooling on bicycle path, easily passable on foot.",
        expected_reference_label="LOW",
        scenario_category="flooding",
        difficulty="straightforward",
        upstream_incident_type="FLOOD_FLASH_FLOOD",
        expected_score_range=(0.0, 34.9),
        notes="Minor pooling without obstruction.",
    ),
)
