"""
Karen's Ear — Canonical Incident Taxonomy & Knowledge Structures.

Codifies the 9 canonical crisis hazard categories (matching ml/schemas/incident_output.json
and gemini.md Section 6.2 / architecture/ml-pipeline.md Section 3.2):
1. FLOOD_FLASH_FLOOD
2. FIRE_WILDFIRE_EXPLOSION
3. STRUCTURAL_COLLAPSE
4. EARTHQUAKE_LANDSLIDE
5. SEVERE_WEATHER_STORM
6. MEDICAL_EMERGENCY
7. CIVIL_UNREST_ACTIVE_THREAT
8. UTILITY_INFRASTRUCTURE_FAILURE
9. OTHER_GENERAL_INCIDENT

Also provides:
- Structured keyword and multi-word phrase vocabularies derived from CrisiText FEMA
  scenarios, HumAID humanitarian disaster categories, and emergency dispatch corpora.
- Semantic descriptive prototypes for embedding similarity classification.
- Documented CrisiText scenario mapping relationships.
- Multi-hazard priority and tie-breaking ordering rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from ml.config import CANONICAL_INCIDENT_TYPES

# ==============================================================================
# 1. CrisiText Scenario Mapping Documentation
# ==============================================================================
# CrisiText (LanD-FBK/crisitext) contains FEMA IPAWS alert scenarios and GTD terror events.
# It does NOT directly supervise our operational taxonomy.
# Below is the verified research mapping from CrisiText disaster scenarios
# to Karen's Ear canonical taxonomy:
CRISITEXT_SCENARIO_MAPPING: dict[str, str] = {
    # Natural Hazards
    "flood": "FLOOD_FLASH_FLOOD",
    "flash flood": "FLOOD_FLASH_FLOOD",
    "tsunami": "FLOOD_FLASH_FLOOD",  # Extreme coastal flood hazard
    "wildfire": "FIRE_WILDFIRE_EXPLOSION",
    "explosion": "FIRE_WILDFIRE_EXPLOSION",
    "arson": "FIRE_WILDFIRE_EXPLOSION",
    "earthquake": "EARTHQUAKE_LANDSLIDE",
    "landslide": "EARTHQUAKE_LANDSLIDE",
    "mudslide": "EARTHQUAKE_LANDSLIDE",
    "hurricane": "SEVERE_WEATHER_STORM",
    "thunderstorm": "SEVERE_WEATHER_STORM",
    "tornado": "SEVERE_WEATHER_STORM",
    # Human-induced Hazards
    "terrorism": "CIVIL_UNREST_ACTIVE_THREAT",
    "armed attack": "CIVIL_UNREST_ACTIVE_THREAT",
    "active shooter": "CIVIL_UNREST_ACTIVE_THREAT",
    # Unmapped in CrisiText (Provided by HumAID / Operational Dispatch)
    # STRUCTURAL_COLLAPSE -> QCRI HumAID "infrastructure damage"
    # MEDICAL_EMERGENCY   -> QCRI HumAID "injured or dead people"
    # UTILITY_INFRASTRUCTURE_FAILURE -> QCRI HumAID "infrastructure damage"
}


# ==============================================================================
# 2. Class Definition Descriptor
# ==============================================================================
@dataclass(frozen=True)
class IncidentClassDefinition:
    """Canonical specification and linguistic evidence structures for an incident category."""

    label: str
    display_name: str
    description: str
    primary_phrases: tuple[str, ...]
    keywords: tuple[str, ...]
    prototypes: tuple[str, ...]
    weight_modifier: float = 1.0


# ==============================================================================
# 3. Canonical Class Evidence Catalog
# Derived from CrisiText scenario narratives, FEMA alerts, HumAID crisis tweets,
# and standard public safety dispatch terminologies.
# ==============================================================================
INCIDENT_TAXONOMY_CATALOG: dict[str, IncidentClassDefinition] = {
    "FLOOD_FLASH_FLOOD": IncidentClassDefinition(
        label="FLOOD_FLASH_FLOOD",
        display_name="Flood / Flash Flood",
        description="Rising water, river overflow, flash flooding, inundated streets, levee/dam failures.",
        primary_phrases=(
            "flash flood",
            "flash flooding",
            "rising water",
            "water rising",
            "flood water",
            "flood waters",
            "overflowing river",
            "river overflow",
            "river burst",
            "submerged vehicles",
            "submerged cars",
            "inundated roads",
            "inundated streets",
            "washed out road",
            "washed away bridge",
            "water level rising",
            "levee breached",
            "dam failure",
            "dam overflow",
            "water entering homes",
            "flooded underpass",
        ),
        keywords=(
            "flood",
            "flooding",
            "flooded",
            "inundation",
            "inundated",
            "submerged",
            "submersion",
            "deluge",
            "overflow",
            "overflowing",
            "waterlog",
            "waterlogging",
            "waterlogged",
            "levee",
            "dike",
            "canal",
        ),
        prototypes=(
            "Severe flash flooding with rapidly rising water submerging roads, bridges, and vehicles.",
            "River overflowing its banks causing extensive flooding in residential and commercial areas.",
            "Heavy floodwaters inundating streets and trapping residents inside their homes.",
            "Water level rising to dangerous levels following heavy rain, dam overflow, and levee breach.",
        ),
        weight_modifier=1.0,
    ),
    "FIRE_WILDFIRE_EXPLOSION": IncidentClassDefinition(
        label="FIRE_WILDFIRE_EXPLOSION",
        display_name="Fire / Wildfire / Explosion",
        description="Building fires, residential/industrial blazes, wildfires, brush fires, explosions, blasts.",
        primary_phrases=(
            "building fire",
            "house fire",
            "apartment fire",
            "warehouse fire",
            "structural fire",
            "wild fire",
            "wildfire",
            "brush fire",
            "forest fire",
            "massive explosion",
            "gas explosion",
            "chemical explosion",
            "thick smoke",
            "black smoke",
            "flames visible",
            "engulfed in flames",
            "burning building",
            "secondary explosion",
            "blast wave",
            "smoke inhalation",
        ),
        keywords=(
            "fire",
            "wildfire",
            "explosion",
            "explode",
            "exploded",
            "exploding",
            "blast",
            "blaze",
            "blazing",
            "flames",
            "flame",
            "smoke",
            "smoking",
            "burning",
            "burn",
            "burned",
            "burnt",
            "arson",
            "combustion",
            "ignited",
            "inferno",
        ),
        prototypes=(
            "Massive structural building fire with heavy flames and thick black smoke engulfing the premises.",
            "Rapidly spreading wildfire and brush fire threatening residential homes, structures, and forests.",
            "Industrial explosion and massive blast resulting in a raging fire, shockwave, and heavy smoke.",
            "Severe gas leak explosion causing intense fire and secondary explosions in a commercial facility.",
        ),
        weight_modifier=1.0,
    ),
    "STRUCTURAL_COLLAPSE": IncidentClassDefinition(
        label="STRUCTURAL_COLLAPSE",
        display_name="Structural Collapse",
        description="Building collapse, wall/roof failure, bridge collapse, cave-ins, people trapped in rubble.",
        primary_phrases=(
            "building collapse",
            "building collapsed",
            "structure collapsed",
            "structural collapse",
            "roof collapse",
            "roof collapsed",
            "ceiling collapsed",
            "wall collapsed",
            "walls caved in",
            "bridge collapsed",
            "bridge collapse",
            "trapped under rubble",
            "under the rubble",
            "under debris",
            "concrete debris",
            "foundation crumbled",
            "scaffolding collapsed",
            "structural failure",
            "cave in",
            "caved in",
        ),
        keywords=(
            "collapse",
            "collapsed",
            "collapsing",
            "rubble",
            "debris",
            "cavein",
            "crumbled",
            "crumbing",
            "wreckage",
            "scaffolding",
        ),
        prototypes=(
            "Catastrophic building collapse with victims trapped under fallen concrete beams and heavy rubble.",
            "Structural failure of a multi-story building, collapsed walls, caved in roof, and debris blocking exits.",
            "Major highway bridge collapsed with vehicles fallen into river below and severe structural destruction.",
            "Roof and floors caved in suddenly, trapping occupants under crushed concrete and twisted metal.",
        ),
        weight_modifier=1.0,
    ),
    "EARTHQUAKE_LANDSLIDE": IncidentClassDefinition(
        label="EARTHQUAKE_LANDSLIDE",
        display_name="Earthquake / Landslide",
        description="Seismic ground shaking, tremors, aftershocks, landslides, mudslides, rockslides, hillside collapse.",
        primary_phrases=(
            "major earthquake",
            "severe earthquake",
            "ground shaking",
            "seismic tremor",
            "earthquake tremor",
            "strong tremor",
            "after shock",
            "aftershock",
            "aftershocks",
            "massive landslide",
            "mud slide",
            "mudslide",
            "rock slide",
            "rockslide",
            "hillside collapsed",
            "slope failure",
            "ground fissure",
            "soil liquefaction",
            "earth slip",
        ),
        keywords=(
            "earthquake",
            "tremor",
            "tremors",
            "seismic",
            "landslide",
            "mudslide",
            "rockslide",
            "aftershock",
            "aftershocks",
            "liquefaction",
            "fissure",
            "faultline",
        ),
        prototypes=(
            "Major earthquake causing violent ground shaking, destructive tremors, and strong aftershocks.",
            "Massive landslide and mudslide tumbling down mountainside, burying roads, houses, and vehicles.",
            "Severe rockslide down hillside blocking main transit corridors following geological slope failure.",
            "Strong seismic shock resulting in ground fissures, structural damage, and ongoing aftershocks.",
        ),
        weight_modifier=1.0,
    ),
    "SEVERE_WEATHER_STORM": IncidentClassDefinition(
        label="SEVERE_WEATHER_STORM",
        display_name="Severe Weather / Storm",
        description="Hurricanes, tornadoes, cyclones, severe thunderstorms, destructive winds, hail, blizzards.",
        primary_phrases=(
            "severe storm",
            "severe thunderstorm",
            "tropical storm",
            "category hurricane",
            "tornado touchdown",
            "tornado warning",
            "funnel cloud",
            "gale force winds",
            "damaging winds",
            "high winds",
            "destructive winds",
            "massive hailstorm",
            "heavy hail",
            "blizzard conditions",
            "heavy snowfall",
            "winter storm",
            "ice storm",
            "cyclone warning",
            "typhoon warning",
        ),
        keywords=(
            "storm",
            "thunderstorm",
            "tornado",
            "tornadoes",
            "cyclone",
            "hurricane",
            "typhoon",
            "blizzard",
            "hail",
            "hailstorm",
            "gale",
            "squall",
            "lightning",
            "windstorm",
            "snowstorm",
        ),
        prototypes=(
            "Violent severe thunderstorm with damaging hurricane-force winds, intense lightning, and torrential rain.",
            "Destructive tornado touchdown with violent rotating winds tearing roofs off structures and tossing debris.",
            "Severe hailstorm and gale-force windstorm causing widespread exterior damage and hazardous conditions.",
            "Blizzard and extreme winter storm with zero-visibility whiteout conditions and heavy snow accumulation.",
        ),
        weight_modifier=1.0,
    ),
    "MEDICAL_EMERGENCY": IncidentClassDefinition(
        label="MEDICAL_EMERGENCY",
        display_name="Medical Emergency",
        description="Cardiac arrest, unconsciousness, severe bleeding/trauma, stroke, respiratory failure, mass casualties.",
        primary_phrases=(
            "cardiac arrest",
            "heart attack",
            "unconscious person",
            "person unresponsive",
            "not breathing",
            "difficulty breathing",
            "stopped breathing",
            "severe bleeding",
            "heavy bleeding",
            "arterial bleeding",
            "chest pain",
            "diabetic emergency",
            "anaphylactic shock",
            "severe allergic reaction",
            "allergic reaction",
            "anaphylactic reaction",
            "unable to breathe",
            "throat swelling",
            "overdose emergency",
            "mass casualty",
            "critically injured",
            "paramedics needed",
            "ambulance required",
            "medical triage",
        ),
        keywords=(
            "medical",
            "paramedic",
            "paramedics",
            "ambulance",
            "unconscious",
            "unresponsive",
            "resuscitation",
            "cpr",
            "bleeding",
            "hemorrhage",
            "stroke",
            "seizure",
            "poisoning",
            "overdose",
            "injured",
            "injury",
            "injuries",
            "trauma",
            "allergic",
            "anaphylaxis",
            "allergy",
            "anaphylactic",
        ),
        prototypes=(
            "Critical medical emergency with patient in cardiac arrest, unconscious, unresponsive, and not breathing.",
            "Severe acute trauma with massive arterial bleeding and head injuries requiring urgent paramedic response.",
            "Patient suffering acute stroke symptoms, respiratory distress, and loss of consciousness.",
            "Multiple injured casualties requiring immediate ambulance dispatch, field resuscitation, and medical triage.",
        ),
        weight_modifier=1.0,
    ),
    "CIVIL_UNREST_ACTIVE_THREAT": IncidentClassDefinition(
        label="CIVIL_UNREST_ACTIVE_THREAT",
        display_name="Civil Unrest / Active Threat",
        description="Active shooters, armed hostility, gunfire, riots, violent civil unrest, hostage situations, terrorism.",
        primary_phrases=(
            "active shooter",
            "shots fired",
            "gun fire",
            "gunfire",
            "armed gunman",
            "armed suspect",
            "armed assailant",
            "hostage situation",
            "hostages taken",
            "violent riot",
            "civil unrest",
            "rioting and looting",
            "violent mob",
            "terrorist attack",
            "bomb threat",
            "explosive device found",
            "stabbing attack",
            "mass shooting",
        ),
        keywords=(
            "gunfire",
            "gunshot",
            "gunshots",
            "shooter",
            "shooting",
            "hostage",
            "hostages",
            "riot",
            "rioting",
            "rioters",
            "looting",
            "terrorist",
            "terrorism",
            "assailant",
            "stabbing",
            "sniper",
        ),
        prototypes=(
            "Active shooter incident with multiple gunshots fired, armed suspect actively attacking civilians.",
            "Violent civil unrest and rioting with crowds looting stores, throwing projectiles, and setting fires.",
            "Armed hostility and hostage situation with suspects holding victims at gunpoint in public facility.",
            "Terrorist threat and armed assault creating immediate public danger and panic.",
        ),
        weight_modifier=1.0,
    ),
    "UTILITY_INFRASTRUCTURE_FAILURE": IncidentClassDefinition(
        label="UTILITY_INFRASTRUCTURE_FAILURE",
        display_name="Utility / Infrastructure Failure",
        description="Power grid blackouts, gas pipeline ruptures, water main bursts, telecommunication collapse, downed lines.",
        primary_phrases=(
            "power outage",
            "widespread blackout",
            "electrical blackout",
            "grid failure",
            "power grid down",
            "substation failure",
            "substation explosion",
            "gas leak",
            "gas main rupture",
            "gas main break",
            "natural gas",
            "gas main",
            "pipeline rupture",
            "water main break",
            "water main burst",
            "water main",
            "sewage pipe burst",
            "sewer overflow",
            "downed power line",
            "downed power lines",
            "cell tower down",
            "telecom outage",
            "water supply disrupted",
        ),
        keywords=(
            "blackout",
            "outage",
            "substation",
            "pipeline",
            "sewer",
            "sewage",
            "telecom",
            "telecommunications",
            "grid",
            "transformer",
            "utility",
            "utilities",
        ),
        prototypes=(
            "Widespread electrical power grid failure causing complete blackout across residential and hospital sectors.",
            "Major natural gas pipeline rupture and high-pressure leak threatening neighborhood with hazardous gas.",
            "Municipal water main burst tearing up asphalt roadway, flooding street and disrupting clean water supply.",
            "Downed high-voltage power transmission lines sparking across roadway with total utility failure.",
        ),
        weight_modifier=1.0,
    ),
    "OTHER_GENERAL_INCIDENT": IncidentClassDefinition(
        label="OTHER_GENERAL_INCIDENT",
        display_name="Other / General Incident",
        description="Ambiguous reports, non-specific emergencies, minor disturbances, low-confidence or unclassified events.",
        primary_phrases=(
            "general emergency",
            "suspicious activity",
            "something strange",
            "unusual incident",
            "disturbance reported",
            "need assistance",
            "send someone",
            "lost animal",
            "noise complaint",
            "minor altercation",
            "traffic jam",
            "car broken down",
            "unspecified problem",
            "unknown issue",
        ),
        keywords=(
            "disturbance",
            "suspicious",
            "unusual",
            "inquiry",
            "routine",
            "unclear",
            "strange",
            "complaint",
            "nuisance",
            "traffic",
        ),
        prototypes=(
            "General emergency situation requiring public safety assistance without specific hazard identified.",
            "Ambiguous report describing unusual or suspicious activity near public street.",
            "Miscellaneous non-critical disturbance or municipal service request.",
            "Unspecified citizen call requesting help without identifiable disaster markers.",
        ),
        weight_modifier=0.9,  # Slightly penalized to prevent stealing clear specific incidents
    ),
}

# Verify at definition time that every canonical type has an entry
for _c_type in CANONICAL_INCIDENT_TYPES:
    if _c_type not in INCIDENT_TAXONOMY_CATALOG:
        raise RuntimeError(f"Missing taxonomy catalog definition for: {_c_type}")


# ==============================================================================
# 4. Multi-Hazard Precedence & Tie-Breaking Rules
# ==============================================================================
# When an emergency report contains evidence of multiple interacting hazards
# (e.g., an explosion that starts a fire, or a storm that causes a power outage),
# the primary incident type should reflect the initiating or dominant physical hazard.
# Tie-breaking priority order (from highest priority initiating hazard to lowest):
HAZARD_PRECEDENCE_ORDER: tuple[str, ...] = (
    "FIRE_WILDFIRE_EXPLOSION",       # Direct explosive / thermal life hazard
    "STRUCTURAL_COLLAPSE",          # Immediate collapse / trapped victim hazard
    "EARTHQUAKE_LANDSLIDE",          # Major geophysical initiating event
    "FLOOD_FLASH_FLOOD",             # Rapid rising water hazard
    "SEVERE_WEATHER_STORM",          # Initiating meteorological cause
    "CIVIL_UNREST_ACTIVE_THREAT",    # Hostile human threat
    "MEDICAL_EMERGENCY",             # Secondary to physical disaster (or standalone)
    "UTILITY_INFRASTRUCTURE_FAILURE",# Secondary infrastructure symptom
    "OTHER_GENERAL_INCIDENT",        # Catch-all fallback
)
