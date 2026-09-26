"""
Karen's Ear — Required-Response Multi-Label 45-Sample Curated Engineering Benchmark.

An independently curated engineering benchmark for multi-label required response extraction:
1. SEARCH_AND_RESCUE
2. MEDICAL_EMS
3. FIRE_HAZMAT
4. POLICE_SECURITY
5. PUBLIC_WORKS_UTILITY

Covers:
- All 5 canonical categories individually (straightforward and paraphrased).
- Mandatory multi-label composite dispatches (2-label and 3-label).
- Mandatory negative context examples (passive entities, hospital nearby, video game, etc.).
- Explicit negation scenarios ("no fire", "no one is injured", "no weapons seen").
- Uncertainty-hedged reports ("possible gas leak", "looks like people may be injured").
- Empty / general / non-emergency dispatches (producing empty lists []).
- Interaction dispatches (people count without response, location without response).

BENCHMARK INTEGRITY NOTICE:
This benchmark dataset is an internal engineering test fixture used to verify multi-label
exact-set matching, micro/macro precision, recall, F1, false-positive resistance, and latency.
It is NOT evidence of real-world 100% accuracy on unconstrained field distributions.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResponseBenchmarkSample:
    """A single evaluation record in the required response benchmark."""

    id: str
    text: str
    expected_categories: tuple[str, ...]  # Expected canonical response types (or empty tuple)
    scenario_type: str  # "single_label", "multi_label", "negative", "negation", "uncertainty", "no_response", "feature_interaction"
    difficulty: str  # "straightforward", "paraphrased", "challenging", "adversarial"
    notes: str = ""


RESPONSE_BENCHMARK_DATASET: tuple[ResponseBenchmarkSample, ...] = (
    # ==========================================================================
    # 1. SEARCH_AND_RESCUE (Single-Label)
    # ==========================================================================
    ResponseBenchmarkSample(
        id="sar_01",
        text="People trapped under rubble following the roof collapse at the market.",
        expected_categories=("SEARCH_AND_RESCUE",),
        scenario_type="single_label",
        difficulty="straightforward",
        notes="Mandatory taxonomy prompt sample: people trapped under rubble.",
    ),
    ResponseBenchmarkSample(
        id="sar_02",
        text="A child trapped inside building on the third floor, doors are jammed shut.",
        expected_categories=("SEARCH_AND_RESCUE",),
        scenario_type="single_label",
        difficulty="straightforward",
        notes="Mandatory taxonomy prompt sample: child trapped inside building.",
    ),
    ResponseBenchmarkSample(
        id="sar_03",
        text="Person stranded after flood surrounded by deep rushing water on the rooftop.",
        expected_categories=("SEARCH_AND_RESCUE",),
        scenario_type="single_label",
        difficulty="straightforward",
        notes="Mandatory taxonomy prompt sample: person stranded after flood.",
    ),
    ResponseBenchmarkSample(
        id="sar_04",
        text="Missing person requiring search in the dense wooded area near the riverbank.",
        expected_categories=("SEARCH_AND_RESCUE",),
        scenario_type="single_label",
        difficulty="straightforward",
        notes="Mandatory taxonomy prompt sample: missing person requiring search.",
    ),

    # ==========================================================================
    # 2. MEDICAL_EMS (Single-Label)
    # ==========================================================================
    ResponseBenchmarkSample(
        id="med_01",
        text="Three people bleeding from deep cuts after shattered glass rained down.",
        expected_categories=("MEDICAL_EMS",),
        scenario_type="single_label",
        difficulty="straightforward",
        notes="Mandatory taxonomy prompt sample: three people bleeding.",
    ),
    ResponseBenchmarkSample(
        id="med_02",
        text="Unconscious person lying on the sidewalk, completely unresponsive.",
        expected_categories=("MEDICAL_EMS",),
        scenario_type="single_label",
        difficulty="straightforward",
        notes="Mandatory taxonomy prompt sample: unconscious person.",
    ),
    ResponseBenchmarkSample(
        id="med_03",
        text="Elderly victim is not breathing, bystander initiating chest compressions.",
        expected_categories=("MEDICAL_EMS",),
        scenario_type="single_label",
        difficulty="straightforward",
        notes="Mandatory taxonomy prompt sample: person not breathing.",
    ),
    ResponseBenchmarkSample(
        id="med_04",
        text="Multiple injured passengers requiring emergency triage after the bus collision.",
        expected_categories=("MEDICAL_EMS",),
        scenario_type="single_label",
        difficulty="straightforward",
        notes="Mandatory taxonomy prompt sample: injured passengers.",
    ),

    # ==========================================================================
    # 3. FIRE_HAZMAT (Single-Label)
    # ==========================================================================
    ResponseBenchmarkSample(
        id="fire_01",
        text="The two-story commercial building is on fire with thick black smoke pouring out.",
        expected_categories=("FIRE_HAZMAT",),
        scenario_type="single_label",
        difficulty="straightforward",
        notes="Mandatory taxonomy prompt sample: building is on fire.",
    ),
    ResponseBenchmarkSample(
        id="fire_02",
        text="Major chemical spill of corrosive industrial acid at the manufacturing plant.",
        expected_categories=("FIRE_HAZMAT",),
        scenario_type="single_label",
        difficulty="straightforward",
        notes="Mandatory taxonomy prompt sample: chemical spill.",
    ),
    ResponseBenchmarkSample(
        id="fire_03",
        text="Strong gas leak detected near the central heating utility room, smell of sulfur.",
        expected_categories=("FIRE_HAZMAT",),
        scenario_type="single_label",
        difficulty="straightforward",
        notes="Mandatory taxonomy prompt sample: gas leak.",
    ),
    ResponseBenchmarkSample(
        id="fire_04",
        text="A large fuel tanker leaking gallons of diesel across the highway pavement.",
        expected_categories=("FIRE_HAZMAT",),
        scenario_type="single_label",
        difficulty="straightforward",
        notes="Mandatory taxonomy prompt sample: fuel tanker leaking.",
    ),

    # ==========================================================================
    # 4. POLICE_SECURITY (Single-Label)
    # ==========================================================================
    ResponseBenchmarkSample(
        id="pol_01",
        text="Armed person inside the mall carrying a visible firearm in the food court.",
        expected_categories=("POLICE_SECURITY",),
        scenario_type="single_label",
        difficulty="straightforward",
        notes="Mandatory taxonomy prompt sample: armed person inside mall.",
    ),
    ResponseBenchmarkSample(
        id="pol_02",
        text="Active shooting reported near the transit plaza, continuous gunfire heard.",
        expected_categories=("POLICE_SECURITY",),
        scenario_type="single_label",
        difficulty="straightforward",
        notes="Mandatory taxonomy prompt sample: active shooting.",
    ),
    ResponseBenchmarkSample(
        id="pol_03",
        text="Hostage situation underway inside the bank branch with employees detained.",
        expected_categories=("POLICE_SECURITY",),
        scenario_type="single_label",
        difficulty="straightforward",
        notes="Mandatory taxonomy prompt sample: hostage situation.",
    ),
    ResponseBenchmarkSample(
        id="pol_04",
        text="Violent attacker wielding a large blade assaulting pedestrians on the sidewalk.",
        expected_categories=("POLICE_SECURITY",),
        scenario_type="single_label",
        difficulty="straightforward",
        notes="Mandatory taxonomy prompt sample: violent attacker.",
    ),

    # ==========================================================================
    # 5. PUBLIC_WORKS_UTILITY (Single-Label)
    # ==========================================================================
    ResponseBenchmarkSample(
        id="util_01",
        text="High-voltage power lines fallen across road sparking against wet asphalt.",
        expected_categories=("PUBLIC_WORKS_UTILITY",),
        scenario_type="single_label",
        difficulty="straightforward",
        notes="Mandatory taxonomy prompt sample: power lines fallen across road.",
    ),
    ResponseBenchmarkSample(
        id="util_02",
        text="Electrical transformer exploded on 4th Street, knocking out power to the grid.",
        expected_categories=("FIRE_HAZMAT", "PUBLIC_WORKS_UTILITY"),
        scenario_type="multi_label",
        difficulty="challenging",
        notes="Transformer explosion constitutes both an explosion/fire hazard and electrical utility disruption.",
    ),
    ResponseBenchmarkSample(
        id="util_03",
        text="A municipal water main burst, sending thousands of gallons flooding the street.",
        expected_categories=("PUBLIC_WORKS_UTILITY",),
        scenario_type="single_label",
        difficulty="straightforward",
        notes="Mandatory taxonomy prompt sample: water main burst.",
    ),
    ResponseBenchmarkSample(
        id="util_04",
        text="Highway bridge damaged and blocking traffic with exposed structural rebar.",
        expected_categories=("PUBLIC_WORKS_UTILITY",),
        scenario_type="single_label",
        difficulty="straightforward",
        notes="Mandatory taxonomy prompt sample: bridge damaged and blocking traffic.",
    ),

    # ==========================================================================
    # 6. MANDATORY MULTI-LABEL TESTS (Prompt Mandatory 1–6)
    # ==========================================================================
    ResponseBenchmarkSample(
        id="multi_01",
        text="People trapped under rubble and three are bleeding.",
        expected_categories=("SEARCH_AND_RESCUE", "MEDICAL_EMS"),
        scenario_type="multi_label",
        difficulty="straightforward",
        notes="Mandatory prompt multi-label 1: trapped under rubble + bleeding.",
    ),
    ResponseBenchmarkSample(
        id="multi_02",
        text="Three people trapped inside a burning building.",
        expected_categories=("SEARCH_AND_RESCUE", "FIRE_HAZMAT"),
        scenario_type="multi_label",
        difficulty="straightforward",
        notes="Mandatory prompt multi-label 2: trapped inside + burning building.",
    ),
    ResponseBenchmarkSample(
        id="multi_03",
        text="Armed person injured two people inside the mall.",
        expected_categories=("MEDICAL_EMS", "POLICE_SECURITY"),
        scenario_type="multi_label",
        difficulty="straightforward",
        notes="Mandatory prompt multi-label 3: armed person + injured two people.",
    ),
    ResponseBenchmarkSample(
        id="multi_04",
        text="Power lines have fallen across the road and a driver is trapped in the car.",
        expected_categories=("SEARCH_AND_RESCUE", "PUBLIC_WORKS_UTILITY"),
        scenario_type="multi_label",
        difficulty="straightforward",
        notes="Mandatory prompt multi-label 4: fallen power lines + driver trapped.",
    ),
    ResponseBenchmarkSample(
        id="multi_05",
        text="Chemical explosion injured several workers.",
        expected_categories=("MEDICAL_EMS", "FIRE_HAZMAT"),
        scenario_type="multi_label",
        difficulty="straightforward",
        notes="Mandatory prompt multi-label 5: chemical explosion + injured workers.",
    ),
    ResponseBenchmarkSample(
        id="multi_06",
        text="Gas leak reported near a school, no injuries.",
        expected_categories=("FIRE_HAZMAT",),
        scenario_type="multi_label",
        difficulty="challenging",
        notes="Mandatory prompt multi-label 6: gas leak reported, injuries explicitly negated.",
    ),

    # ==========================================================================
    # 7. ADDITIONAL MULTI-LABEL COMBINATIONS (3-Label & Complex)
    # ==========================================================================
    ResponseBenchmarkSample(
        id="multi_07",
        text="Three people trapped inside a burning building, two injured.",
        expected_categories=("SEARCH_AND_RESCUE", "MEDICAL_EMS", "FIRE_HAZMAT"),
        scenario_type="multi_label",
        difficulty="challenging",
        notes="Triple category: rescue + fire + medical.",
    ),
    ResponseBenchmarkSample(
        id="multi_08",
        text="Armed attacker set fire to the store and shot two patrons.",
        expected_categories=("MEDICAL_EMS", "FIRE_HAZMAT", "POLICE_SECURITY"),
        scenario_type="multi_label",
        difficulty="challenging",
        notes="Triple category: police security + fire hazmat + medical ems.",
    ),
    ResponseBenchmarkSample(
        id="multi_09",
        text="Transformer exploded and power lines are down.",
        expected_categories=("FIRE_HAZMAT", "PUBLIC_WORKS_UTILITY"),
        scenario_type="multi_label",
        difficulty="straightforward",
        notes="Explosion/fire hazard plus utility infrastructure failure.",
    ),
    ResponseBenchmarkSample(
        id="multi_10",
        text="Massive sinkhole opened on the avenue, a vehicle fell in with occupants trapped.",
        expected_categories=("SEARCH_AND_RESCUE", "PUBLIC_WORKS_UTILITY"),
        scenario_type="multi_label",
        difficulty="challenging",
        notes="Public works sinkhole hazard + search and rescue trapped occupants.",
    ),

    # ==========================================================================
    # 8. MANDATORY NEGATIVE TESTS (Prompt Negative Samples)
    # ==========================================================================
    ResponseBenchmarkSample(
        id="neg_01",
        text="No one is injured.",
        expected_categories=(),
        scenario_type="negation",
        difficulty="adversarial",
        notes="Mandatory negative test: explicit negation of medical injury.",
    ),
    ResponseBenchmarkSample(
        id="neg_02",
        text="No fire, only smoke from cooking.",
        expected_categories=(),
        scenario_type="negation",
        difficulty="adversarial",
        notes="Mandatory negative test: negated fire with harmless cooking smoke.",
    ),
    ResponseBenchmarkSample(
        id="neg_03",
        text="Police station is nearby.",
        expected_categories=(),
        scenario_type="negative",
        difficulty="adversarial",
        notes="Mandatory negative test: passive facility mention.",
    ),
    ResponseBenchmarkSample(
        id="neg_04",
        text="Hospital is nearby.",
        expected_categories=(),
        scenario_type="negative",
        difficulty="adversarial",
        notes="Mandatory negative test: passive facility mention.",
    ),
    ResponseBenchmarkSample(
        id="neg_05",
        text="Fire truck is parked outside.",
        expected_categories=(),
        scenario_type="negative",
        difficulty="adversarial",
        notes="Mandatory negative test: parked emergency apparatus.",
    ),
    ResponseBenchmarkSample(
        id="neg_06",
        text="Power was restored yesterday.",
        expected_categories=(),
        scenario_type="negative",
        difficulty="adversarial",
        notes="Mandatory negative test: historical resolved status update.",
    ),
    ResponseBenchmarkSample(
        id="neg_07",
        text="No weapons seen.",
        expected_categories=(),
        scenario_type="negation",
        difficulty="adversarial",
        notes="Mandatory negative test: explicit weapon negation.",
    ),
    ResponseBenchmarkSample(
        id="neg_08",
        text="Fire extinguisher is available in the building.",
        expected_categories=(),
        scenario_type="negative",
        difficulty="adversarial",
        notes="Mandatory negative test: equipment presence without incident.",
    ),
    ResponseBenchmarkSample(
        id="neg_09",
        text="People are trapped in a video game.",
        expected_categories=(),
        scenario_type="negative",
        difficulty="adversarial",
        notes="Mandatory negative test: metaphorical / game phrasing.",
    ),

    # ==========================================================================
    # 9. UNCERTAINTY-HEDGED TESTS
    # ==========================================================================
    ResponseBenchmarkSample(
        id="unc_01",
        text="Possible gas leak reported in the residential basement.",
        expected_categories=("FIRE_HAZMAT",),
        scenario_type="uncertainty",
        difficulty="challenging",
        notes="Uncertainty marker 'possible': should extract FIRE_HAZMAT with reduced confidence.",
    ),
    ResponseBenchmarkSample(
        id="unc_02",
        text="Looks like several people may be injured near the intersection.",
        expected_categories=("MEDICAL_EMS",),
        scenario_type="uncertainty",
        difficulty="challenging",
        notes="Uncertainty markers 'looks like' and 'may be': should extract MEDICAL_EMS with reduced confidence.",
    ),
    ResponseBenchmarkSample(
        id="unc_03",
        text="Someone might be trapped in the elevator on the second floor.",
        expected_categories=("SEARCH_AND_RESCUE",),
        scenario_type="uncertainty",
        difficulty="challenging",
        notes="Uncertainty marker 'might be': should extract SEARCH_AND_RESCUE with reduced confidence.",
    ),
    ResponseBenchmarkSample(
        id="unc_04",
        text="Suspected armed individual reported wandering around the perimeter.",
        expected_categories=("POLICE_SECURITY",),
        scenario_type="uncertainty",
        difficulty="challenging",
        notes="Uncertainty marker 'suspected': should extract POLICE_SECURITY with reduced confidence.",
    ),

    # ==========================================================================
    # 10. EMPTY / GENERAL DISPATCHES (Zero Response Required)
    # ==========================================================================
    ResponseBenchmarkSample(
        id="gen_01",
        text="Traffic is slow today.",
        expected_categories=(),
        scenario_type="no_response",
        difficulty="straightforward",
        notes="General observation: no response needed.",
    ),
    ResponseBenchmarkSample(
        id="gen_02",
        text="Heavy rain reported across the northern district.",
        expected_categories=(),
        scenario_type="no_response",
        difficulty="straightforward",
        notes="Weather report without emergency consequence: no response needed.",
    ),
    ResponseBenchmarkSample(
        id="gen_03",
        text="Road is wet following afternoon shower.",
        expected_categories=(),
        scenario_type="no_response",
        difficulty="straightforward",
        notes="Minor road advisory: no response needed.",
    ),
    ResponseBenchmarkSample(
        id="gen_04",
        text="There is noise near the market square.",
        expected_categories=(),
        scenario_type="no_response",
        difficulty="straightforward",
        notes="Vague nuisance: no emergency response needed.",
    ),

    # ==========================================================================
    # 11. FEATURE 4/5 INTERACTION & NON-INFERRED CASES
    # ==========================================================================
    ResponseBenchmarkSample(
        id="feat_01",
        text="20 people are inside the stadium enjoying the concert.",
        expected_categories=(),
        scenario_type="feature_interaction",
        difficulty="adversarial",
        notes="Feature 4 people count alone must NOT trigger emergency response.",
    ),
    ResponseBenchmarkSample(
        id="feat_02",
        text="Ambulance parked outside the mall near the south entrance.",
        expected_categories=(),
        scenario_type="feature_interaction",
        difficulty="adversarial",
        notes="Feature 5 VEHICLE entity mention must NOT trigger MEDICAL_EMS.",
    ),
    ResponseBenchmarkSample(
        id="feat_03",
        text="Fire station nearby on Janpath road.",
        expected_categories=(),
        scenario_type="feature_interaction",
        difficulty="adversarial",
        notes="Feature 5 FACILITY entity mention must NOT trigger FIRE_HAZMAT.",
    ),
    ResponseBenchmarkSample(
        id="feat_04",
        text="Power outage reported, no physical damage visible.",
        expected_categories=("PUBLIC_WORKS_UTILITY",),
        scenario_type="single_label",
        difficulty="challenging",
        notes="Service disruption without physical hazard: extracts PUBLIC_WORKS_UTILITY with appropriate confidence.",
    ),
)
