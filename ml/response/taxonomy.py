"""
Karen's Ear — Canonical Response Taxonomy & Evidence Catalog.

Step 2E of the ML pipeline (architecture/ml-pipeline.md Section 3.6 and gemini.md Section 6.2).
Codifies the 5 canonical emergency response categories:
1. SEARCH_AND_RESCUE
2. MEDICAL_EMS
3. FIRE_HAZMAT
4. POLICE_SECURITY
5. PUBLIC_WORKS_UTILITY

CRITICAL ARCHITECTURAL PRINCIPLE:
Required-response extraction is ADVISORY ML OUTPUT.
It must NOT directly determine final operational priority, incident ranking,
dispatch ordering, emergency contact, or backend response orchestration.
It answers: "What response categories appear relevant from the report?"

Guarantees:
- Strict canonical 5-category taxonomy (zero invented categories).
- Multi-label: zero, one, or multiple categories per report.
- Evidence-based: strong, supporting, contextual, negative, and negation patterns.
- Deterministic, explainable, and independent confidence per label.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Mapping

from ml.config import CANONICAL_RESPONSE_TYPES


# ==============================================================================
# Response Category Definition Descriptor
# ==============================================================================

@dataclass(frozen=True)
class ResponseCategoryDefinition:
    """Canonical specification, linguistic patterns, and evidence rules for a response category."""

    category: str
    display_name: str
    description: str
    strong_patterns: tuple[re.Pattern[str], ...]
    supporting_patterns: tuple[re.Pattern[str], ...]
    negative_patterns: tuple[re.Pattern[str], ...]
    negation_patterns: tuple[re.Pattern[str], ...]
    base_strong_confidence: float = 0.94
    base_supporting_confidence: float = 0.72


# ==============================================================================
# Common Negation & Uncertainty Regexes
# ==============================================================================

UNCERTAINTY_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:possible|possibly|potential|potentially|suspected|maybe|might\s+be|may\s+be|"
    r"looks\s+like|alleged|allegedly|reportedly|unconfirmed|believed\s+to\s+be|could\s+be|"
    r"appears\s+to\s+be|seemingly|seems\s+like)\b",
    re.IGNORECASE,
)


# ==============================================================================
# Canonical 5-Category Evidence Definitions
# ==============================================================================

RESPONSE_TAXONOMY_CATALOG: dict[str, ResponseCategoryDefinition] = {
    # --------------------------------------------------------------------------
    # 1. SEARCH_AND_RESCUE
    # --------------------------------------------------------------------------
    "SEARCH_AND_RESCUE": ResponseCategoryDefinition(
        category="SEARCH_AND_RESCUE",
        display_name="Search & Rescue",
        description=(
            "Locating and extricating individuals who are trapped under rubble, inside collapsed "
            "structures or vehicles, stranded by rising waters/floods, or unaccounted for/missing."
        ),
        strong_patterns=(
            # Trapped under rubble / debris / collapsed structure
            re.compile(
                r"\b(?:trapped|buried|pinned)\s+(?:under|beneath|in)\s+"
                r"(?:rubble|debris|concrete|wreckage|collapsed|ruins|mud|landslide|snow|earth|soil)\b",
                re.IGNORECASE,
            ),
            # Trapped inside building / house / vehicle / elevator / car
            re.compile(
                r"\b(?:trapped|stuck|pinned)\s+(?:inside|in)\s+(?:a\s+|the\s+)?"
                r"(?:building|house|structure|vehicle|car|van|bus|truck|train|elevator|lift|room|basement|wreckage)\b",
                re.IGNORECASE,
            ),
            # People trapped / children trapped / driver trapped / person trapped
            re.compile(
                r"\b(?:\b(?:many|several|multiple|few|some|all|elderly|young|\d+)\s+)?(?:people|persons?|residents?|passengers?|workers?|children|kids?|victims?|family|driver|someone|anyone|individuals?)\s+"
                r"(?:are\s+|is\s+|were\s+|being\s+)?(?:trapped|buried|pinned|stuck\s+inside)\b",
                re.IGNORECASE,
            ),
            # Child trapped inside
            re.compile(
                r"\b(?:child|kid|baby|toddler)\s+trapped\s+inside\b",
                re.IGNORECASE,
            ),
            # Stranded after flood / rising water / on roof
            re.compile(
                r"\b(?:stranded|marooned)\s+(?:after|by|in|on)\s+"
                r"(?:flood|floods|flooding|floodwaters?|water|rising\s+water|rooftop|roof|island|current|river)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:\b(?:many|several|multiple|few|some|all|elderly|young|\d+)\s+)?(?:people|persons?|residents?|passengers?|family|children|hikers?)\s+"
                r"(?:are\s+|is\s+|were\s+)?(?:stranded|marooned)\b",
                re.IGNORECASE,
            ),
            # Missing person / unaccounted for
            re.compile(
                r"\b(?:missing\s+persons?|people\s+missing|person\s+missing|child\s+missing|children\s+missing|"
                r"missing\s+hikers?|unaccounted\s+for|search\s+operation\s+needed)\b",
                re.IGNORECASE,
            ),
            # Explicit rescue phrases
            re.compile(
                r"\b(?:search\s+and\s+rescue|rescue\s+needed|rescue\s+required|rescue\s+team\s+(?:needed|requested)|"
                r"send\s+rescue|extrication\s+needed|need\s+rescue|extrication\s+required|evacuation\s+rescue)\b",
                re.IGNORECASE,
            ),
            # Collapsed building with people inside
            re.compile(
                r"\b(?:collapsed\s+building\s+with\s+people\s+inside|building\s+collapsed\s+with\s+residents?\s+trapped|"
                r"roof\s+collapsed\s+on\s+people)\b",
                re.IGNORECASE,
            ),
            # Swept away by flood / current
            re.compile(
                r"\b(?:swept\s+away\s+by\s+(?:flood|water|current|river)|drowning\s+victim\s+requiring\s+rescue|"
                r"boat\s+capsized\s+with\s+passengers)\b",
                re.IGNORECASE,
            ),
            # People unable to escape
            re.compile(
                r"\b(?:unable\s+to\s+escape|cannot\s+escape|can't\s+escape|no\s+way\s+out\s+for\s+residents)\b",
                re.IGNORECASE,
            ),
        ),
        supporting_patterns=(
            re.compile(r"\b(?:trapped|stranded|buried|pinned|unaccounted|missing)\b", re.IGNORECASE),
            re.compile(r"\b(?:stuck\s+inside|cut\s+off\s+by\s+water|isolated\s+by\s+flood)\b", re.IGNORECASE),
            re.compile(r"\b(?:rescue|extricate|evacuate\s+victims)\b", re.IGNORECASE),
        ),
        negative_patterns=(
            # Metaphorical or non-emergency trapped
            re.compile(
                r"\b(?:trapped\s+in\s+(?:a\s+)?(?:video\s+)?game|trapped\s+in\s+traffic|trapped\s+in\s+(?:a\s+)?meeting|"
                r"trapped\s+in\s+routine|trapped\s+in\s+an?\s+elevator\s+yesterday)\b",
                re.IGNORECASE,
            ),
            # Already completed rescue
            re.compile(
                r"\b(?:already\s+rescued|everyone\s+rescued|all\s+rescued|rescue\s+completed|"
                r"safely\s+evacuated|evacuated\s+safely|safe\s+and\s+sound)\b",
                re.IGNORECASE,
            ),
        ),
        negation_patterns=(
            re.compile(
                r"\b(?:no\s+one|nobody|no-one|noone|no\s+person|zero\s+people)\s+(?:is\s+|are\s+|was\s+|were\s+)?"
                r"(?:trapped|buried|stranded|missing|pinned)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:not\s+trapped|nobody\s+trapped|no\s+one\s+trapped|zero\s+trapped|no\s+people\s+trapped)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:no\s+(?:missing|stranded)\s+(?:persons?|people|victims?))\b",
                re.IGNORECASE,
            ),
        ),
        base_strong_confidence=0.94,
        base_supporting_confidence=0.72,
    ),

    # --------------------------------------------------------------------------
    # 2. MEDICAL_EMS
    # --------------------------------------------------------------------------
    "MEDICAL_EMS": ResponseCategoryDefinition(
        category="MEDICAL_EMS",
        display_name="Medical / EMS",
        description=(
            "Urgent pre-hospital medical care, paramedic triage, and ambulance response for "
            "physical trauma, casualties, bleeding, burns, unconsciousness, or acute medical distress."
        ),
        strong_patterns=(
            # Bleeding heavily / people bleeding / three people bleeding
            re.compile(
                r"\b(?:\b(?:many|several|multiple|few|some|all|elderly|young|\d+)\s+)?(?:people|persons?|passengers?|workers?|victims?|three|two|four|five|several|\d+)\s+"
                r"(?:are\s+|were\s+)?bleeding(?:\s+heavily|\s+profusely|\s+severely)?\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:bleeding\s+(?:heavily|profusely|severely)|severe\s+bleeding|profuse\s+bleeding|loss\s+of\s+blood)\b",
                re.IGNORECASE,
            ),
            # Unconscious / unresponsive / passed out
            re.compile(
                r"\b(?:unconscious(?:\s+person|\s+victim|\s+and\s+unresponsive)?|unresponsive(?:\s+victim|\s+person)?|"
                r"passed\s+out|not\s+waking\s+up|found\s+unresponsive|loss\s+of\s+consciousness)\b",
                re.IGNORECASE,
            ),
            # Breathing emergencies / cardiac arrest
            re.compile(
                r"\b(?:not\s+breathing|difficulty\s+breathing|stopped\s+breathing|gasping\s+for\s+air|"
                r"cardiac\s+arrest|heart\s+attack|stroke\s+symptoms?|severe\s+chest\s+pain)\b",
                re.IGNORECASE,
            ),
            # Explicit injury mention: injured passengers / three people injured / critically injured
            re.compile(
                r"\b(?:\b(?:many|several|multiple|few|some|all|elderly|young|\d+)\s+)?(?:passengers?|workers?|people|persons?|victims?|civilians?|children|two|three|four|five|\d+)\s+"
                r"(?:are\s+|were\s+)?(?:injured|wounded|hurt|critically\s+injured|severely\s+injured)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:injured\s+(?:passengers?|workers?|people|persons?|victims?|civilians?|children|two|three|four|five|several|multiple|\d+)|"
                r"severely\s+injured|critically\s+injured|serious\s+injuries|major\s+trauma)\b",
                re.IGNORECASE,
            ),
            # Shot / stabbing / violent trauma
            re.compile(
                r"\b(?:shot\s+(?:two|three|four|five|several|multiple|\d+|people|patrons?|bystanders?|victims?)|"
                r"two\s+shot|three\s+shot|gunshot\s+wound|stabbed|stabbing\s+victim)\b",
                re.IGNORECASE,
            ),
            # Severe burns / smoke inhalation victim
            re.compile(
                r"\b(?:severe\s+burns?|third[\s-]degree\s+burns?|second[\s-]degree\s+burns?|chemical\s+burns?|"
                r"burn\s+victim|smoke\s+inhalation\s+victim)\b",
                re.IGNORECASE,
            ),
            # Explicit EMS / ambulance / medical emergency
            re.compile(
                r"\b(?:medical\s+emergency|ambulance\s+needed|paramedics?\s+needed|dispatch\s+ambulance|"
                r"send\s+ems|send\s+ambulance|urgent\s+medical\s+(?:care|attention)|patient\s+in\s+distress)\b",
                re.IGNORECASE,
            ),
            # Drowning / near drowning / hypothermia
            re.compile(
                r"\b(?:drowning\s+victim|near\s+drowning|severe\s+hypothermia|acute\s+overdose)\b",
                re.IGNORECASE,
            ),
            # Traumatic injuries
            re.compile(
                r"\b(?:head\s+injury|spinal\s+injury|compound\s+fracture|severe\s+lacerations?|crush\s+injury)\b",
                re.IGNORECASE,
            ),
        ),
        supporting_patterns=(
            re.compile(r"\b(?:injured|injuries|casualty|casualties|wounded|bleeding|burns?|trauma|first\s+aid|paramedic|ambulance)\b", re.IGNORECASE),
            re.compile(r"\b(?:hospitalized|medical\s+care|triage|paramedics)\b", re.IGNORECASE),
        ),
        negative_patterns=(
            # Hospital mention without active patient need (e.g. "Hospital is nearby")
            re.compile(
                r"\b(?:hospital\s+(?:is\s+)?(?:nearby|two\s+blocks\s+away|close\s+by|down\s+the\s+street|"
                r"across\s+the\s+street|in\s+the\s+area))\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:near\s+(?:the\s+)?hospital|at\s+(?:the\s+)?hospital\s+gate|outside\s+(?:the\s+)?hospital\s+building)\b",
                re.IGNORECASE,
            ),
            # Static ambulance without patient emergency ("Ambulance parked outside")
            re.compile(
                r"\b(?:ambulance\s+(?:is\s+)?parked\s+outside|empty\s+ambulance|parked\s+ambulance|"
                r"ambulance\s+in\s+parking\s+lot)\b",
                re.IGNORECASE,
            ),
            # Irrelevant medical mentions
            re.compile(
                r"\b(?:doctor\s+on\s+vacation|medical\s+conference|health\s+insurance|medical\s+records?|"
                r"pharmacy\s+sale|hospital\s+parking)\b",
                re.IGNORECASE,
            ),
        ),
        negation_patterns=(
            re.compile(
                r"\b(?:no\s+one|nobody|no-one|noone|no\s+person|zero\s+people)\s+(?:is\s+|are\s+|was\s+|were\s+)?"
                r"(?:injured|hurt|bleeding|wounded|killed|dead)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:no\s+(?:reported\s+|apparent\s+|visible\s+)?(?:injuries|casualties|fatalities|medical\s+emergenc(?:y|ies)))\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:zero\s+(?:injuries|casualties|fatalities))\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:without\s+(?:any\s+)?(?:injuries|injury|harm|casualties))\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:unhurt|uninjured|everyone\s+(?:is\s+|was\s+)?fine|everyone\s+(?:is\s+|was\s+)?ok(?:ay)?)\b",
                re.IGNORECASE,
            ),
        ),
        base_strong_confidence=0.92,
        base_supporting_confidence=0.70,
    ),

    # --------------------------------------------------------------------------
    # 3. FIRE_HAZMAT
    # --------------------------------------------------------------------------
    "FIRE_HAZMAT": ResponseCategoryDefinition(
        category="FIRE_HAZMAT",
        display_name="Fire / Hazmat",
        description=(
            "Fire suppression, structural blazes, wildland fires, chemical spills, "
            "toxic gas releases, hazardous materials, and explosive hazards."
        ),
        strong_patterns=(
            # Building on fire / active blaze
            re.compile(
                r"\b(?:building\s+(?:is\s+)?on\s+fire|house\s+(?:is\s+)?on\s+fire|apartment\s+(?:is\s+)?on\s+fire|"
                r"factory\s+(?:is\s+)?on\s+fire|warehouse\s+(?:is\s+)?on\s+fire|commercial\s+building\s+fire|"
                r"structure\s+fire|roof\s+(?:is\s+)?on\s+fire)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:engulfed\s+in\s+flames|burst\s+into\s+flames|active\s+fire|flames\s+visible|"
                r"heavy\s+black\s+smoke\s+pouring|blaze\s+spreading|wildfire\s+approaching|forest\s+fire|"
                r"set\s+fire\s+to|flames\s+shooting\s+from)\b",
                re.IGNORECASE,
            ),
            # Chemical spill / toxic leak / hazardous materials
            re.compile(
                r"\b(?:chemical\s+spill|toxic\s+chemical\s+leak|hazardous\s+materials?|hazmat\s+incident|"
                r"acid\s+spill|ammonia\s+leak|chlorine\s+gas|toxic\s+release|toxic\s+fumes|hazardous\s+waste\s+spill)\b",
                re.IGNORECASE,
            ),
            # Gas leak
            re.compile(
                r"\b(?:gas\s+leak|smell\s+of\s+gas|natural\s+gas\s+leak|propane\s+leak|methane\s+leak|"
                r"gas\s+pipeline\s+leak)\b",
                re.IGNORECASE,
            ),
            # Fuel leak / tanker leak
            re.compile(
                r"\b(?:fuel\s+tanker\s+leaking|fuel\s+leak|oil\s+tanker\s+spill|gasoline\s+leaking|"
                r"diesel\s+spill|oil\s+slick\s+fire)\b",
                re.IGNORECASE,
            ),
            # Explosion / transformer exploded
            re.compile(
                r"\b(?:massive\s+explosion|chemical\s+explosion|industrial\s+explosion|explosion\s+heard|"
                r"detonation|bomb\s+blast|boiler\s+explosion|transformer\s+exploded|transformer\s+explosion)\b",
                re.IGNORECASE,
            ),
            # Explicit firefighter / fire brigade request
            re.compile(
                r"\b(?:firefighters?\s+needed|fire\s+department\s+needed|fire\s+brigade\s+requested|"
                r"send\s+fire\s+trucks?|hazmat\s+team\s+needed)\b",
                re.IGNORECASE,
            ),
        ),
        supporting_patterns=(
            re.compile(r"\b(?:fire|flames|smoke|explosion|hazmat|chemical|toxic|fumes|gas\s+leak|ignited|combustion|blaze)\b", re.IGNORECASE),
            re.compile(r"\b(?:chemical\s+burn|smoldering|burning)\b", re.IGNORECASE),
        ),
        negative_patterns=(
            # Fire extinguisher available / mounted
            re.compile(
                r"\b(?:fire\s+extinguisher\s+(?:is\s+)?available|fire\s+extinguisher\s+mounted|"
                r"fire\s+extinguisher\s+on\s+wall|check\s+fire\s+extinguishers?)\b",
                re.IGNORECASE,
            ),
            # Fire station nearby / Fire truck parked outside
            re.compile(
                r"\b(?:fire\s+truck\s+(?:is\s+)?parked\s+outside|fire\s+station\s+(?:is\s+)?(?:nearby|two\s+blocks\s+away|close\s+by)|"
                r"near\s+(?:the\s+)?fire\s+station|old\s+fire\s+truck)\b",
                re.IGNORECASE,
            ),
            # Cooking smoke / barbecue / food
            re.compile(
                r"\b(?:only\s+smoke\s+from\s+cooking|smoke\s+from\s+cooking|cooking\s+smoke|barbecue\s+smoke|"
                r"bbq\s+smoke|burnt\s+toast|bonfire|controlled\s+burn)\b",
                re.IGNORECASE,
            ),
            # Fire drill / alarm testing
            re.compile(
                r"\b(?:fire\s+drill|fire\s+alarm\s+test|routine\s+drill|false\s+alarm\s+for\s+fire)\b",
                re.IGNORECASE,
            ),
            # Metaphorical fire
            re.compile(
                r"\b(?:fired\s+from\s+(?:his|her|their|a)?\s*job|rapid\s+fire\s+questions)\b",
                re.IGNORECASE,
            ),
            # Fire already extinguished
            re.compile(
                r"\b(?:fire\s+was\s+extinguished|fire\s+is\s+out|fire\s+put\s+out|fire\s+under\s+control)\b",
                re.IGNORECASE,
            ),
        ),
        negation_patterns=(
            re.compile(
                r"\b(?:no\s+(?:active\s+)?(?:fire|flames|blaze|gas\s+leak|chemical\s+spill|leak|explosion))\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:not\s+on\s+fire|no\s+signs?\s+of\s+fire|no\s+fire\s+reported)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:no\s+fire,\s+only\s+smoke)\b",
                re.IGNORECASE,
            ),
        ),
        base_strong_confidence=0.94,
        base_supporting_confidence=0.72,
    ),

    # --------------------------------------------------------------------------
    # 4. POLICE_SECURITY
    # --------------------------------------------------------------------------
    "POLICE_SECURITY": ResponseCategoryDefinition(
        category="POLICE_SECURITY",
        display_name="Police / Security",
        description=(
            "Law enforcement intervention for violent threats, active shooters, armed individuals, "
            "assaults, civil disturbances, perimeter/crowd control, or criminal acts."
        ),
        strong_patterns=(
            # Armed person / gunman / attacker
            re.compile(
                r"\b(?:armed\s+person(?:\s+inside)?|armed\s+man|armed\s+suspect|armed\s+gunman|armed\s+attacker|"
                r"armed\s+individual|person\s+with\s+a\s+gun|man\s+with\s+a\s+knife|armed\s+with\s+(?:a\s+)?weapon)\b",
                re.IGNORECASE,
            ),
            # Active shooting / shots fired
            re.compile(
                r"\b(?:active\s+shooting|active\s+shooter|shots\s+fired|gunshots\s+heard|gunfire\s+reported|"
                r"shooting\s+spree|sniper\s+fire|shooting\s+incident)\b",
                re.IGNORECASE,
            ),
            # Hostage situation / kidnapping
            re.compile(
                r"\b(?:hostage\s+situation|hostages\s+taken|holding\s+(?:people|someone)\s+hostage|"
                r"kidnapping\s+in\s+progress)\b",
                re.IGNORECASE,
            ),
            # Violent attack / assault / robbery
            re.compile(
                r"\b(?:violent\s+attacker|stabbing\s+attack|physical\s+assault|assault\s+in\s+progress|"
                r"mob\s+violence|lynching|armed\s+robbery|violent\s+robbery)\b",
                re.IGNORECASE,
            ),
            # Break-in / burglary / riots / looting
            re.compile(
                r"\b(?:break[\s-]in|burglary\s+in\s+progress|intruder\s+inside|looting\s+reported|"
                r"rioting\s+and\s+vandalism|violent\s+disturbance|violent\s+clash|riot\s+underway)\b",
                re.IGNORECASE,
            ),
            # Suspicious armed activity / bomb threat
            re.compile(
                r"\b(?:suspicious\s+armed\s+activity|bomb\s+threat|terrorist\s+attack|terrorist\s+suspect)\b",
                re.IGNORECASE,
            ),
            # Explicit police / security needed
            re.compile(
                r"\b(?:police\s+needed|send\s+police|call\s+police|law\s+enforcement\s+needed|"
                r"security\s+forces\s+requested|police\s+dispatch\s+requested)\b",
                re.IGNORECASE,
            ),
        ),
        supporting_patterns=(
            re.compile(r"\b(?:gun|gunman|knife|weapon|weapons|hostage|attacker|riot|rioting|vandalism)\b", re.IGNORECASE),
            re.compile(r"\b(?:security|police|officer|patrol|lockdown)\b", re.IGNORECASE),
        ),
        negative_patterns=(
            # Police station nearby
            re.compile(
                r"\b(?:police\s+station\s+(?:is\s+)?(?:nearby|two\s+blocks\s+away|close\s+by|around\s+the\s+corner)|"
                r"near\s+(?:the\s+)?police\s+station|outside\s+(?:the\s+)?police\s+station)\b",
                re.IGNORECASE,
            ),
            # Police car parked
            re.compile(
                r"\b(?:police\s+car\s+parked|police\s+vehicle\s+parked|patrol\s+car\s+parked)\b",
                re.IGNORECASE,
            ),
            # Toy weapons / water gun
            re.compile(
                r"\b(?:water\s+gun|toy\s+gun|toy\s+weapon|nerf\s+gun|bb\s+gun)\b",
                re.IGNORECASE,
            ),
            # Suspect already arrested
            re.compile(
                r"\b(?:suspect\s+(?:is\s+)?already\s+arrested|suspect\s+in\s+custody|perpetrator\s+arrested|"
                r"situation\s+(?:is\s+)?under\s+control\s+by\s+police)\b",
                re.IGNORECASE,
            ),
            # Flames shooting / sparks shooting (motion verb, not firearm)
            re.compile(
                r"\b(?:flames\s+shooting|sparks\s+shooting|water\s+shooting)\b",
                re.IGNORECASE,
            ),
        ),
        negation_patterns=(
            re.compile(
                r"\b(?:no\s+(?:weapons?|guns?|knives|firearms?)\s*(?:seen|found|spotted|reported)?)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:unarmed|no\s+sign\s+of\s+weapons?)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:no\s+violence|peaceful\s+gathering|false\s+alarm\s+about\s+weapons?)\b",
                re.IGNORECASE,
            ),
        ),
        base_strong_confidence=0.93,
        base_supporting_confidence=0.70,
    ),

    # --------------------------------------------------------------------------
    # 5. PUBLIC_WORKS_UTILITY
    # --------------------------------------------------------------------------
    "PUBLIC_WORKS_UTILITY": ResponseCategoryDefinition(
        category="PUBLIC_WORKS_UTILITY",
        display_name="Public Works / Utility",
        description=(
            "Repair and hazard mitigation for fallen power lines, exploding transformers, "
            "water main bursts, sewer ruptures, gas main physical failures, damaged bridges/roads, "
            "and municipal infrastructure blockage."
        ),
        strong_patterns=(
            # Power lines fallen across road / live electrical wires
            re.compile(
                r"\b(?:power\s+lines?\s+(?:have\s+)?fallen(?:\s+across\s+the\s+road)?|downed\s+power\s+lines?|"
                r"fallen\s+electrical\s+wires?|live\s+wires?\s+(?:on|across)\s+(?:ground|road|street)|"
                r"sparking\s+power\s+lines?|snapped\s+power\s+pole|fallen\s+utility\s+pole|power\s+lines\s+are\s+down)\b",
                re.IGNORECASE,
            ),
            # Transformer exploded / substation explosion
            re.compile(
                r"\b(?:transformer\s+exploded|transformer\s+explosion|transformer\s+blew\s+up|"
                r"electrical\s+substation\s+explosion|transformer\s+caught\s+fire)\b",
                re.IGNORECASE,
            ),
            # Water main burst / sewer rupture
            re.compile(
                r"\b(?:water\s+main\s+burst|ruptured\s+water\s+main|broken\s+water\s+pipe\s+flooding|"
                r"burst\s+water\s+pipe|sewer\s+line\s+rupture|sewer\s+pipe\s+burst)\b",
                re.IGNORECASE,
            ),
            # Bridge damaged / blocked by infrastructure
            re.compile(
                r"\b(?:bridge\s+damaged(?:\s+and\s+blocking)?|bridge\s+collapsed\s+and\s+blocking|"
                r"structural\s+bridge\s+damage|flyover\s+structural\s+damage)\b",
                re.IGNORECASE,
            ),
            # Road blocked by infrastructure / fallen tree / sinkhole
            re.compile(
                r"\b(?:road\s+blocked\s+by\s+infrastructure|debris\s+blocking\s+(?:road|highway|street)|"
                r"tree\s+fallen\s+across\s+road|fallen\s+tree\s+blocking|giant\s+sinkhole\s+opened|"
                r"sinkhole\s+in\s+road|roadway\s+undermined|massive\s+sinkhole)\b",
                re.IGNORECASE,
            ),
            # Gas pipeline damage / utility outage with hazard
            re.compile(
                r"\b(?:gas\s+pipeline\s+damage|damaged\s+public\s+infrastructure|traffic\s+signals?\s+out|"
                r"utility\s+outage\s+with\s+physical\s+infrastructure\s+hazard)\b",
                re.IGNORECASE,
            ),
            # Explicit public works request
            re.compile(
                r"\b(?:public\s+works\s+required|utility\s+crew\s+needed|linemen\s+needed|"
                r"send\s+public\s+works|road\s+crew\s+needed)\b",
                re.IGNORECASE,
            ),
        ),
        supporting_patterns=(
            re.compile(r"\b(?:power\s+outage|blackout|grid\s+failure|transformer|power\s+lines?|water\s+main|sewer|sinkhole|fallen\s+tree|debris\s+blocking|infrastructure\s+damage)\b", re.IGNORECASE),
            re.compile(r"\b(?:utility\s+pole|traffic\s+lights?\s+down|road\s+closed|water\s+supply\s+disrupted)\b", re.IGNORECASE),
        ),
        negative_patterns=(
            # Power restored yesterday / Electricity restored
            re.compile(
                r"\b(?:power\s+(?:was\s+|has\s+been\s+|is\s+)?restored(?:\s+yesterday|\s+earlier)?|"
                r"electricity\s+(?:was\s+|has\s+been\s+|is\s+)?restored)\b",
                re.IGNORECASE,
            ),
            # Routine roadwork / utility bill / office
            re.compile(
                r"\b(?:power\s+company\s+office|utility\s+bill|scheduled\s+outage|routine\s+roadwork|"
                r"water\s+turned\s+off\s+for\s+maintenance)\b",
                re.IGNORECASE,
            ),
        ),
        negation_patterns=(
            re.compile(
                r"\b(?:power\s+restored\s+yesterday|power\s+was\s+restored|electricity\s+restored)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:no\s+(?:power\s+outage|infrastructure\s+damage|utility\s+damage|wire\s+damage))\b",
                re.IGNORECASE,
            ),
        ),
        base_strong_confidence=0.94,
        base_supporting_confidence=0.70,
    ),
}


def get_response_definition(category: str) -> ResponseCategoryDefinition | None:
    """Returns the taxonomy definition for a canonical response category."""
    return RESPONSE_TAXONOMY_CATALOG.get(category)


def is_canonical_response_type(category: str) -> bool:
    """Validates whether a string is one of the 5 canonical response types."""
    return category in CANONICAL_RESPONSE_TYPES
