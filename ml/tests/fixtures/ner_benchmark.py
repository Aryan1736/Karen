"""
Karen's Ear — Location & Entity Extraction Curated Benchmark Dataset.

This dataset provides an independent, hand-curated engineering benchmark for:
1. Primary incident location extraction and textual precision
2. Named entity extraction (LOCATION, VEHICLE, INFRASTRUCTURE, FACILITY, ROAD, LANDMARK, PERSON, ORGANIZATION)
3. Negative rejection (rejecting room numbers, building numbers, hotline numbers, non-location digits)

BENCHMARK INTEGRITY & LEAKAGE AVOIDANCE:
- These examples were independently curated to represent realistic emergency dispatch reports.
- Ground truth spans reflect natural human dispatch interpretation.
- They are NOT verbatim copies of internal gazetteers or regex pattern strings.
- This is a curated engineering benchmark for comparing extraction strategies (spaCy vs BERT vs Deterministic vs Hybrid);
  it does not claim to represent wild real-world emergency distribution accuracy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExpectedEntity:
    text: str
    type: str  # LOCATION, VEHICLE, INFRASTRUCTURE, FACILITY, ROAD, LANDMARK, PERSON, ORGANIZATION


@dataclass(frozen=True)
class NERBenchmarkSample:
    sample_id: str
    text: str
    expected_location: str | None
    expected_precision: str  # "exact", "approximate", "unknown"
    expected_entities: tuple[ExpectedEntity, ...] = field(default_factory=tuple)
    is_negative: bool = False
    category: str = "general"
    notes: str = ""


NER_BENCHMARK_DATASET: tuple[NERBenchmarkSample, ...] = (
    # --------------------------------------------------------------------------
    # 1. Real emergency reports with explicit / approximate prepositions
    # --------------------------------------------------------------------------
    NERBenchmarkSample(
        sample_id="bench_01",
        text="Three people trapped inside a bus near Rasulgarh flyover.",
        expected_location="Rasulgarh flyover",
        expected_precision="approximate",
        expected_entities=(
            ExpectedEntity("bus", "VEHICLE"),
            ExpectedEntity("Rasulgarh flyover", "LOCATION"),
        ),
        category="transport_accident",
        notes="Prompt target example: bus is VEHICLE, Rasulgarh flyover is LOCATION.",
    ),
    NERBenchmarkSample(
        sample_id="bench_02",
        text="Fire reported behind the railway station.",
        expected_location="railway station",
        expected_precision="approximate",
        expected_entities=(
            ExpectedEntity("railway station", "FACILITY"),
        ),
        category="fire",
        notes="Facility location behind railway station.",
    ),
    NERBenchmarkSample(
        sample_id="bench_03",
        text="Ambulance blocked on NH16 near Patia.",
        expected_location="NH16 near Patia",
        expected_precision="approximate",
        expected_entities=(
            ExpectedEntity("ambulance", "VEHICLE"),
            ExpectedEntity("NH16", "ROAD"),
            ExpectedEntity("Patia", "LOCATION"),
        ),
        category="medical_transit",
        notes="Roadway and local area extraction.",
    ),
    NERBenchmarkSample(
        sample_id="bench_04",
        text="Smoke coming from the transformer beside the school.",
        expected_location="transformer beside the school",
        expected_precision="approximate",
        expected_entities=(
            ExpectedEntity("transformer", "INFRASTRUCTURE"),
            ExpectedEntity("school", "FACILITY"),
        ),
        category="electrical",
        notes="Infrastructure and facility beside each other.",
    ),
    NERBenchmarkSample(
        sample_id="bench_05",
        text="Crash at the intersection of Janpath and Master Canteen Road.",
        expected_location="intersection of Janpath and Master Canteen Road",
        expected_precision="exact",
        expected_entities=(
            ExpectedEntity("Janpath", "ROAD"),
            ExpectedEntity("Master Canteen Road", "ROAD"),
        ),
        category="traffic",
        notes="Intersection of two named roads.",
    ),
    NERBenchmarkSample(
        sample_id="bench_06",
        text="Fire at Patia.",
        expected_location="Patia",
        expected_precision="exact",
        expected_entities=(
            ExpectedEntity("Patia", "LOCATION"),
        ),
        category="fire",
        notes="Short explicit place name.",
    ),
    NERBenchmarkSample(
        sample_id="bench_07",
        text="Severe waterlogging inside Cuttack Medical College.",
        expected_location="Cuttack Medical College",
        expected_precision="exact",
        expected_entities=(
            ExpectedEntity("Cuttack Medical College", "FACILITY"),
        ),
        category="flood",
        notes="Medical facility compound.",
    ),
    NERBenchmarkSample(
        sample_id="bench_08",
        text="Tanker overturned 3 km from Khandagiri square.",
        expected_location="3 km from Khandagiri square",
        expected_precision="approximate",
        expected_entities=(
            ExpectedEntity("tanker", "VEHICLE"),
            ExpectedEntity("Khandagiri square", "LANDMARK"),
        ),
        category="hazmat",
        notes="Relative distance offset from landmark.",
    ),
    NERBenchmarkSample(
        sample_id="bench_09",
        text="People stranded on roof near Baramunda bus stand.",
        expected_location="Baramunda bus stand",
        expected_precision="approximate",
        expected_entities=(
            ExpectedEntity("Baramunda bus stand", "FACILITY"),
        ),
        category="flood",
        notes="Transit facility landmark.",
    ),
    NERBenchmarkSample(
        sample_id="bench_10",
        text="Gas leakage outside Kalinga Hospital building.",
        expected_location="Kalinga Hospital building",
        expected_precision="approximate",
        expected_entities=(
            ExpectedEntity("Kalinga Hospital", "FACILITY"),
            ExpectedEntity("building", "INFRASTRUCTURE"),
        ),
        category="gas_leak",
        notes="Facility and infrastructure outside.",
    ),
    NERBenchmarkSample(
        sample_id="bench_11",
        text="Tree fell on a car at Rasulgarh square.",
        expected_location="Rasulgarh square",
        expected_precision="exact",
        expected_entities=(
            ExpectedEntity("car", "VEHICLE"),
            ExpectedEntity("Rasulgarh square", "LANDMARK"),
        ),
        category="storm",
        notes="Landmark junction.",
    ),
    NERBenchmarkSample(
        sample_id="bench_12",
        text="Fire started near Patia and spread toward Rasulgarh.",
        expected_location="Patia",
        expected_precision="approximate",
        expected_entities=(
            ExpectedEntity("Patia", "LOCATION"),
            ExpectedEntity("Rasulgarh", "LOCATION"),
        ),
        category="multi_location",
        notes="Multiple locations: primary origin Patia, secondary spread toward Rasulgarh.",
    ),
    NERBenchmarkSample(
        sample_id="bench_13",
        text="Van caught fire on the bridge over the river.",
        expected_location="bridge over the river",
        expected_precision="approximate",
        expected_entities=(
            ExpectedEntity("van", "VEHICLE"),
            ExpectedEntity("bridge", "INFRASTRUCTURE"),
        ),
        category="transport_fire",
        notes="Infrastructure feature as location.",
    ),
    NERBenchmarkSample(
        sample_id="bench_14",
        text="Power line snapped near the municipal market.",
        expected_location="municipal market",
        expected_precision="approximate",
        expected_entities=(
            ExpectedEntity("power line", "INFRASTRUCTURE"),
            ExpectedEntity("market", "FACILITY"),
        ),
        category="utility",
        notes="Infrastructure and commercial landmark.",
    ),
    NERBenchmarkSample(
        sample_id="bench_15",
        text="Flooding reported somewhere around Saheed Nagar.",
        expected_location="Saheed Nagar",
        expected_precision="approximate",
        expected_entities=(
            ExpectedEntity("Saheed Nagar", "LOCATION"),
        ),
        category="flood",
        notes="Approximate modifier around named place.",
    ),
    NERBenchmarkSample(
        sample_id="bench_16",
        text="Two trucks collided on the highway.",
        expected_location="highway",
        expected_precision="approximate",
        expected_entities=(
            ExpectedEntity("trucks", "VEHICLE"),
            ExpectedEntity("highway", "ROAD"),
        ),
        category="traffic",
        notes="Generic road mention.",
    ),
    NERBenchmarkSample(
        sample_id="bench_17",
        text="Motorcycle crashed near Utkal University campus gate.",
        expected_location="Utkal University campus gate",
        expected_precision="approximate",
        expected_entities=(
            ExpectedEntity("motorcycle", "VEHICLE"),
            ExpectedEntity("Utkal University", "FACILITY"),
        ),
        category="traffic",
        notes="Educational institution gate.",
    ),
    NERBenchmarkSample(
        sample_id="bench_18",
        text="Heavy smoke near the tunnel entrance.",
        expected_location="tunnel entrance",
        expected_precision="approximate",
        expected_entities=(
            ExpectedEntity("tunnel", "INFRASTRUCTURE"),
        ),
        category="fire",
        notes="Infrastructure entrance.",
    ),
    NERBenchmarkSample(
        sample_id="bench_19",
        text="Pipeline burst at Chandrasekharpur industrial area.",
        expected_location="Chandrasekharpur industrial area",
        expected_precision="exact",
        expected_entities=(
            ExpectedEntity("pipeline", "INFRASTRUCTURE"),
            ExpectedEntity("Chandrasekharpur", "LOCATION"),
        ),
        category="utility",
        notes="Industrial zone location.",
    ),
    NERBenchmarkSample(
        sample_id="bench_20",
        text="Train derailed between Mancheswar and Vani Vihar.",
        expected_location="between Mancheswar and Vani Vihar",
        expected_precision="approximate",
        expected_entities=(
            ExpectedEntity("train", "VEHICLE"),
            ExpectedEntity("Mancheswar", "LOCATION"),
            ExpectedEntity("Vani Vihar", "LOCATION"),
        ),
        category="rail_accident",
        notes="Span between two stations/locations.",
    ),
    # --------------------------------------------------------------------------
    # 2. Negative Examples (No location / False positives to reject)
    # --------------------------------------------------------------------------
    NERBenchmarkSample(
        sample_id="bench_neg_01",
        text="Building 42 is on fire.",
        expected_location=None,
        expected_precision="unknown",
        expected_entities=(
            ExpectedEntity("building", "INFRASTRUCTURE"),
        ),
        is_negative=True,
        category="negative",
        notes="Building 42 must NOT extract '42' as a location.",
    ),
    NERBenchmarkSample(
        sample_id="bench_neg_02",
        text="Room 204 is filled with smoke.",
        expected_location=None,
        expected_precision="unknown",
        expected_entities=(),
        is_negative=True,
        category="negative",
        notes="Room 204 must NOT extract '204' as a location.",
    ),
    NERBenchmarkSample(
        sample_id="bench_neg_03",
        text="Call 112 immediately.",
        expected_location=None,
        expected_precision="unknown",
        expected_entities=(),
        is_negative=True,
        category="negative",
        notes="Dial number must NOT be extracted as location.",
    ),
    NERBenchmarkSample(
        sample_id="bench_neg_04",
        text="Five people are trapped.",
        expected_location=None,
        expected_precision="unknown",
        expected_entities=(),
        is_negative=True,
        category="negative",
        notes="Pure victim count: no location, no unrelated entity extraction.",
    ),
    NERBenchmarkSample(
        sample_id="bench_neg_05",
        text="Send police and medical assistance immediately.",
        expected_location=None,
        expected_precision="unknown",
        expected_entities=(),
        is_negative=True,
        category="negative",
        notes="Service request without location.",
    ),
    NERBenchmarkSample(
        sample_id="bench_neg_06",
        text="The situation is under control now.",
        expected_location=None,
        expected_precision="unknown",
        expected_entities=(),
        is_negative=True,
        category="negative",
        notes="Advisory status text.",
    ),
    NERBenchmarkSample(
        sample_id="bench_neg_07",
        text="Water levels are rising rapidly everywhere.",
        expected_location=None,
        expected_precision="unknown",
        expected_entities=(),
        is_negative=True,
        category="negative",
        notes="Broad hazard statement without named or prepositional location.",
    ),
    NERBenchmarkSample(
        sample_id="bench_neg_08",
        text="Three people trapped inside a bus.",
        expected_location=None,
        expected_precision="unknown",
        expected_entities=(
            ExpectedEntity("bus", "VEHICLE"),
        ),
        is_negative=True,
        category="negative",
        notes="Prompt negative requirement: location text is null, bus is VEHICLE.",
    ),
    NERBenchmarkSample(
        sample_id="bench_neg_09",
        text="Please call 911 right now.",
        expected_location=None,
        expected_precision="unknown",
        expected_entities=(),
        is_negative=True,
        category="negative",
        notes="Hotline dial rejection.",
    ),
    NERBenchmarkSample(
        sample_id="bench_neg_10",
        text="Floor 3 has collapsed.",
        expected_location=None,
        expected_precision="unknown",
        expected_entities=(),
        is_negative=True,
        category="negative",
        notes="Floor number rejection.",
    ),
)
