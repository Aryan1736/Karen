"""
Karen's Ear — Incident Classification 63-Sample Curated Engineering Benchmark.

A 63-sample curated engineering benchmark containing representative emergency reports
across all 9 canonical incident categories (7 items per class):
1. FLOOD_FLASH_FLOOD
2. FIRE_WILDFIRE_EXPLOSION
3. STRUCTURAL_COLLAPSE
4. EARTHQUAKE_LANDSLIDE
5. SEVERE_WEATHER_STORM
6. MEDICAL_EMERGENCY
7. CIVIL_UNREST_ACTIVE_THREAT
8. UTILITY_INFRASTRUCTURE_FAILURE
9. OTHER_GENERAL_INCIDENT

IMPORTANT EVALUATION NOTICE:
This dataset is an internal engineering benchmark and smoke fixture used to verify
pipeline determinism, regression safety, and relative behavior between classification
modes (keyword baseline vs semantic prototype vs hybrid).
It is NOT evidence of real-world 100% classification accuracy on unconstrained, noisy
field distributions.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkItem:
    """A single evaluation record in the classification benchmark."""

    id: str
    text: str
    expected_label: str
    source: str
    difficulty: str  # "straightforward", "conversational", "challenging"


INCIDENT_BENCHMARK_DATASET: tuple[BenchmarkItem, ...] = (
    # ==========================================================================
    # 1. FLOOD_FLASH_FLOOD (7 items)
    # ==========================================================================
    BenchmarkItem(
        id="flood_01",
        text="Storm runoff overwhelmed the drainage ditch along Highway 16, several sedans stalled in deep water.",
        expected_label="FLOOD_FLASH_FLOOD",
        source="fema_ipaws_alert",
        difficulty="straightforward",
    ),
    BenchmarkItem(
        id="flood_02",
        text="The river has overflowed its banks near the northern district. Roads are completely inundated.",
        expected_label="FLOOD_FLASH_FLOOD",
        source="crisitext_derived",
        difficulty="straightforward",
    ),
    BenchmarkItem(
        id="flood_03",
        text="Water is entering our ground floor rapidly, please send help! The street is like a raging torrent.",
        expected_label="FLOOD_FLASH_FLOOD",
        source="emergency_call_transcript",
        difficulty="conversational",
    ),
    BenchmarkItem(
        id="flood_04",
        text="Underpass on Highway 10 is flooded under 6 feet of water with two motorists stranded on their car roofs.",
        expected_label="FLOOD_FLASH_FLOOD",
        source="dispatch_log",
        difficulty="conversational",
    ),
    BenchmarkItem(
        id="flood_05",
        text="Canal levee has breached east of town. Massive floodwaters sweeping across agricultural fields toward houses.",
        expected_label="FLOOD_FLASH_FLOOD",
        source="crisitext_derived",
        difficulty="straightforward",
    ),
    BenchmarkItem(
        id="flood_06",
        text="Severe deluge has washed out the culvert and bridge on River Road. Entire area is submerged.",
        expected_label="FLOOD_FLASH_FLOOD",
        source="humaid_derived",
        difficulty="challenging",
    ),
    BenchmarkItem(
        id="flood_07",
        text="Water levels still rising dangerous amounts near the reservoir dam, spillway is overflowing into neighborhoods.",
        expected_label="FLOOD_FLASH_FLOOD",
        source="fema_ipaws_alert",
        difficulty="challenging",
    ),

    # ==========================================================================
    # 2. FIRE_WILDFIRE_EXPLOSION (7 items)
    # ==========================================================================
    BenchmarkItem(
        id="fire_01",
        text="Heavy smoke plume visible over the lumber yard off the bypass, fire crews responding to 2nd alarm blaze.",
        expected_label="FIRE_WILDFIRE_EXPLOSION",
        source="emergency_call_transcript",
        difficulty="straightforward",
    ),
    BenchmarkItem(
        id="fire_02",
        text="Massive explosion at chemical storage facility followed by raging secondary blazes across the industrial park.",
        expected_label="FIRE_WILDFIRE_EXPLOSION",
        source="crisitext_derived",
        difficulty="straightforward",
    ),
    BenchmarkItem(
        id="fire_03",
        text="Wildfire burning out of control on the eastern ridge, spreading fast with wind toward residential neighborhoods.",
        expected_label="FIRE_WILDFIRE_EXPLOSION",
        source="fema_ipaws_alert",
        difficulty="straightforward",
    ),
    BenchmarkItem(
        id="fire_04",
        text="A gas line exploded inside an apartment building, the entire upper structure is engulfed in flames.",
        expected_label="FIRE_WILDFIRE_EXPLOSION",
        source="dispatch_log",
        difficulty="conversational",
    ),
    BenchmarkItem(
        id="fire_05",
        text="Brush fire rapidly advancing along the interstate, heavy smoke blowing across traffic lanes causing zero visibility.",
        expected_label="FIRE_WILDFIRE_EXPLOSION",
        source="crisitext_derived",
        difficulty="conversational",
    ),
    BenchmarkItem(
        id="fire_06",
        text="The two-story residential house is ablaze, flames shooting through the roof and sparks catching trees.",
        expected_label="FIRE_WILDFIRE_EXPLOSION",
        source="humaid_derived",
        difficulty="challenging",
    ),
    BenchmarkItem(
        id="fire_07",
        text="Loud blast heard and fireball erupted near the gas station depot, structural fire department units responding.",
        expected_label="FIRE_WILDFIRE_EXPLOSION",
        source="emergency_call_transcript",
        difficulty="challenging",
    ),

    # ==========================================================================
    # 3. STRUCTURAL_COLLAPSE (7 items)
    # ==========================================================================
    BenchmarkItem(
        id="collapse_01",
        text="Old parking garage structure gave way on Market St, two concrete decks pancaked onto parked cars.",
        expected_label="STRUCTURAL_COLLAPSE",
        source="humaid_derived",
        difficulty="straightforward",
    ),
    BenchmarkItem(
        id="collapse_02",
        text="Roof of the community sports arena caved in suddenly under heavy weight, multiple people underneath the wreckage.",
        expected_label="STRUCTURAL_COLLAPSE",
        source="dispatch_log",
        difficulty="straightforward",
    ),
    BenchmarkItem(
        id="collapse_03",
        text="Highway overpass structure collapsed onto the street below, crushing several vehicles under massive concrete slabs.",
        expected_label="STRUCTURAL_COLLAPSE",
        source="emergency_call_transcript",
        difficulty="straightforward",
    ),
    BenchmarkItem(
        id="collapse_04",
        text="Old residential apartment wall gave way and collapsed into the alleyway, foundation appears unstable.",
        expected_label="STRUCTURAL_COLLAPSE",
        source="dispatch_log",
        difficulty="conversational",
    ),
    BenchmarkItem(
        id="collapse_05",
        text="Major cave-in at the underground pedestrian tunnel, fallen concrete and rubble blocking all emergency exits.",
        expected_label="STRUCTURAL_COLLAPSE",
        source="humaid_derived",
        difficulty="conversational",
    ),
    BenchmarkItem(
        id="collapse_06",
        text="Scaffolding and facade sheared off the high-rise tower, crashing down onto the sidewalk with heavy debris.",
        expected_label="STRUCTURAL_COLLAPSE",
        source="emergency_call_transcript",
        difficulty="challenging",
    ),
    BenchmarkItem(
        id="collapse_07",
        text="Structural failure observed in warehouse support columns, ceiling buckling downward and crumbling rapidly.",
        expected_label="STRUCTURAL_COLLAPSE",
        source="humaid_derived",
        difficulty="challenging",
    ),

    # ==========================================================================
    # 4. EARTHQUAKE_LANDSLIDE (7 items)
    # ==========================================================================
    BenchmarkItem(
        id="quake_01",
        text="Violent seismic shock felt across town, bookshelves knocked over and plaster falling from walls during the tremor.",
        expected_label="EARTHQUAKE_LANDSLIDE",
        source="crisitext_derived",
        difficulty="straightforward",
    ),
    BenchmarkItem(
        id="quake_02",
        text="Saturated mountain slope gave way after days of rain, mud and pine trees sliding down and blocking both highway lanes.",
        expected_label="EARTHQUAKE_LANDSLIDE",
        source="crisitext_derived",
        difficulty="straightforward",
    ),
    BenchmarkItem(
        id="quake_03",
        text="Heavy mudslide rushing down the valley road after soil liquefaction, vehicles caught in the mud flow.",
        expected_label="EARTHQUAKE_LANDSLIDE",
        source="fema_ipaws_alert",
        difficulty="straightforward",
    ),
    BenchmarkItem(
        id="quake_04",
        text="Powerful aftershock hit just now, ground trembling violently and new cracks opening in the pavement.",
        expected_label="EARTHQUAKE_LANDSLIDE",
        source="emergency_call_transcript",
        difficulty="conversational",
    ),
    BenchmarkItem(
        id="quake_05",
        text="Rockslide tumbling down cliff face onto Route 21, boulders blocking both transit lanes.",
        expected_label="EARTHQUAKE_LANDSLIDE",
        source="dispatch_log",
        difficulty="conversational",
    ),
    BenchmarkItem(
        id="quake_06",
        text="Major seismic event caused ground fissures along the faultline, several slope failures reported on hillsides.",
        expected_label="EARTHQUAKE_LANDSLIDE",
        source="crisitext_derived",
        difficulty="challenging",
    ),
    BenchmarkItem(
        id="quake_07",
        text="The entire embankment gave way in an earth slip, soil and rocks sliding into the neighborhood below.",
        expected_label="EARTHQUAKE_LANDSLIDE",
        source="humaid_derived",
        difficulty="challenging",
    ),

    # ==========================================================================
    # 5. SEVERE_WEATHER_STORM (7 items)
    # ==========================================================================
    BenchmarkItem(
        id="storm_01",
        text="Emergency spotters report a twister on the ground near County Line, sheet metal torn from barns and debris flying.",
        expected_label="SEVERE_WEATHER_STORM",
        source="fema_ipaws_alert",
        difficulty="straightforward",
    ),
    BenchmarkItem(
        id="storm_02",
        text="Severe microburst event with 75 mph gusts blew down roadside billboards and triggered intense lightning strikes.",
        expected_label="SEVERE_WEATHER_STORM",
        source="crisitext_derived",
        difficulty="straightforward",
    ),
    BenchmarkItem(
        id="storm_03",
        text="Hurricane approaching coastline with dangerous storm surge, category 4 wind speeds, and severe squalls.",
        expected_label="SEVERE_WEATHER_STORM",
        source="fema_ipaws_alert",
        difficulty="straightforward",
    ),
    BenchmarkItem(
        id="storm_04",
        text="Destructive hailstorm with baseball-sized hail smashing car windshields and puncturing skylights across town.",
        expected_label="SEVERE_WEATHER_STORM",
        source="dispatch_log",
        difficulty="conversational",
    ),
    BenchmarkItem(
        id="storm_05",
        text="Whiteout driving conditions along Route 4, howling winds and four-foot snow drifts trapping several vehicles.",
        expected_label="SEVERE_WEATHER_STORM",
        source="crisitext_derived",
        difficulty="conversational",
    ),
    BenchmarkItem(
        id="storm_06",
        text="Intense tropical cyclone bringing torrential winds and flying debris, residents urged to shelter in interior rooms.",
        expected_label="SEVERE_WEATHER_STORM",
        source="fema_ipaws_alert",
        difficulty="challenging",
    ),
    BenchmarkItem(
        id="storm_07",
        text="A sudden windstorm squall knocked down numerous large trees across roadways, high winds persisting.",
        expected_label="SEVERE_WEATHER_STORM",
        source="humaid_derived",
        difficulty="challenging",
    ),

    # ==========================================================================
    # 6. MEDICAL_EMERGENCY (7 items)
    # ==========================================================================
    BenchmarkItem(
        id="med_01",
        text="Elderly man collapsed on the sidewalk, unresponsive and not breathing. CPR in progress, send ambulance immediately!",
        expected_label="MEDICAL_EMERGENCY",
        source="emergency_call_transcript",
        difficulty="straightforward",
    ),
    BenchmarkItem(
        id="med_02",
        text="Suspected heart attack, patient experiencing severe chest pains, sweating, and difficulty breathing.",
        expected_label="MEDICAL_EMERGENCY",
        source="emergency_call_transcript",
        difficulty="straightforward",
    ),
    BenchmarkItem(
        id="med_03",
        text="Worker suffered deep leg laceration from power equipment at the jobsite, heavy bleeding requiring ambulance.",
        expected_label="MEDICAL_EMERGENCY",
        source="dispatch_log",
        difficulty="straightforward",
    ),
    BenchmarkItem(
        id="med_04",
        text="Young child having an acute anaphylactic allergic reaction after bee sting, throat swelling and unable to breathe.",
        expected_label="MEDICAL_EMERGENCY",
        source="emergency_call_transcript",
        difficulty="conversational",
    ),
    BenchmarkItem(
        id="med_05",
        text="Individual suffered a major seizure and fell unconscious, head laceration bleeding heavily on the floor.",
        expected_label="MEDICAL_EMERGENCY",
        source="dispatch_log",
        difficulty="conversational",
    ),
    BenchmarkItem(
        id="med_06",
        text="Possible drug overdose at the transit center, victim is unresponsive with shallow breathing, naloxone needed.",
        expected_label="MEDICAL_EMERGENCY",
        source="dispatch_log",
        difficulty="challenging",
    ),
    BenchmarkItem(
        id="med_07",
        text="Patient displaying acute stroke symptoms including facial droop and total slurred speech, urgent medical triage.",
        expected_label="MEDICAL_EMERGENCY",
        source="emergency_call_transcript",
        difficulty="challenging",
    ),

    # ==========================================================================
    # 7. CIVIL_UNREST_ACTIVE_THREAT (7 items)
    # ==========================================================================
    BenchmarkItem(
        id="threat_01",
        text="Active shooter at the downtown shopping mall, multiple gunshots fired and people screaming running for exits.",
        expected_label="CIVIL_UNREST_ACTIVE_THREAT",
        source="emergency_call_transcript",
        difficulty="straightforward",
    ),
    BenchmarkItem(
        id="threat_02",
        text="Armed suspect with a rifle barricaded inside a commercial building holding two hostages at gunpoint.",
        expected_label="CIVIL_UNREST_ACTIVE_THREAT",
        source="dispatch_log",
        difficulty="straightforward",
    ),
    BenchmarkItem(
        id="threat_03",
        text="Protest turned hostile on 3rd St, demonstrators throwing pavers and breaking storefront glass in violent clash.",
        expected_label="CIVIL_UNREST_ACTIVE_THREAT",
        source="crisitext_derived",
        difficulty="straightforward",
    ),
    BenchmarkItem(
        id="threat_04",
        text="Gunfire heard outside the metro station, several shots fired from a passing vehicle, citizens taking cover.",
        expected_label="CIVIL_UNREST_ACTIVE_THREAT",
        source="emergency_call_transcript",
        difficulty="conversational",
    ),
    BenchmarkItem(
        id="threat_05",
        text="Civil unrest expanding through city center with rioters setting dumpsters on fire and smashing store windows.",
        expected_label="CIVIL_UNREST_ACTIVE_THREAT",
        source="crisitext_derived",
        difficulty="conversational",
    ),
    BenchmarkItem(
        id="threat_06",
        text="Armed assailant wielding a machete attacking pedestrians near the market square, immediate police response required.",
        expected_label="CIVIL_UNREST_ACTIVE_THREAT",
        source="dispatch_log",
        difficulty="challenging",
    ),
    BenchmarkItem(
        id="threat_07",
        text="Bomb threat called into the municipal courthouse claiming an explosive device was planted in the lobby.",
        expected_label="CIVIL_UNREST_ACTIVE_THREAT",
        source="crisitext_derived",
        difficulty="challenging",
    ),

    # ==========================================================================
    # 8. UTILITY_INFRASTRUCTURE_FAILURE (7 items)
    # ==========================================================================
    BenchmarkItem(
        id="utility_01",
        text="North district substation tripped, traffic signals dark and emergency generators kicked in at local clinic.",
        expected_label="UTILITY_INFRASTRUCTURE_FAILURE",
        source="humaid_derived",
        difficulty="straightforward",
    ),
    BenchmarkItem(
        id="utility_02",
        text="Major natural gas main break on Elm Street, loud hissing sound and strong odor of rotten egg gas filling the street.",
        expected_label="UTILITY_INFRASTRUCTURE_FAILURE",
        source="dispatch_log",
        difficulty="straightforward",
    ),
    BenchmarkItem(
        id="utility_03",
        text="High-pressure water line ruptured under the street, geyser eroding pavement and cutting pressure to homes.",
        expected_label="UTILITY_INFRASTRUCTURE_FAILURE",
        source="dispatch_log",
        difficulty="straightforward",
    ),
    BenchmarkItem(
        id="utility_04",
        text="High-voltage power lines have fallen down across the road, sparking actively and cutting power to entire neighborhood.",
        expected_label="UTILITY_INFRASTRUCTURE_FAILURE",
        source="emergency_call_transcript",
        difficulty="conversational",
    ),
    BenchmarkItem(
        id="utility_05",
        text="Electrical substation transformer blew out, total power outage reported across three zip codes.",
        expected_label="UTILITY_INFRASTRUCTURE_FAILURE",
        source="humaid_derived",
        difficulty="conversational",
    ),
    BenchmarkItem(
        id="utility_06",
        text="Underground sewage pipe rupture leaking wastewater into the road and bubbling up through manholes.",
        expected_label="UTILITY_INFRASTRUCTURE_FAILURE",
        source="dispatch_log",
        difficulty="challenging",
    ),
    BenchmarkItem(
        id="utility_07",
        text="Critical telecommunications cellular tower failure, no cell phone or 911 service across the rural valley.",
        expected_label="UTILITY_INFRASTRUCTURE_FAILURE",
        source="humaid_derived",
        difficulty="challenging",
    ),

    # ==========================================================================
    # 9. OTHER_GENERAL_INCIDENT (7 items)
    # ==========================================================================
    BenchmarkItem(
        id="other_01",
        text="I saw something strange happening down near the market earlier today, thought I should report it.",
        expected_label="OTHER_GENERAL_INCIDENT",
        source="citizen_report",
        difficulty="straightforward",
    ),
    BenchmarkItem(
        id="other_02",
        text="Can someone send a patrol car to check on a suspicious vehicle parked outside the vacant building for two days?",
        expected_label="OTHER_GENERAL_INCIDENT",
        source="citizen_report",
        difficulty="straightforward",
    ),
    BenchmarkItem(
        id="other_03",
        text="Neighbor is playing extremely loud music late at night, calling to make a persistent noise complaint.",
        expected_label="OTHER_GENERAL_INCIDENT",
        source="citizen_report",
        difficulty="straightforward",
    ),
    BenchmarkItem(
        id="other_04",
        text="Lost golden retriever dog wandering near the central park playground, seems friendly but has no collar.",
        expected_label="OTHER_GENERAL_INCIDENT",
        source="citizen_report",
        difficulty="conversational",
    ),
    BenchmarkItem(
        id="other_05",
        text="Car has broken down on the shoulder of the highway, hazard lights are on waiting for a tow truck.",
        expected_label="OTHER_GENERAL_INCIDENT",
        source="dispatch_log",
        difficulty="conversational",
    ),
    BenchmarkItem(
        id="other_06",
        text="General disturbance reported near the bus terminal, two people arguing loudly about a ticket.",
        expected_label="OTHER_GENERAL_INCIDENT",
        source="dispatch_log",
        difficulty="challenging",
    ),
    BenchmarkItem(
        id="other_07",
        text="Citizen calling to ask about road closures and municipal schedule for tomorrow morning.",
        expected_label="OTHER_GENERAL_INCIDENT",
        source="citizen_report",
        difficulty="challenging",
    ),
)
