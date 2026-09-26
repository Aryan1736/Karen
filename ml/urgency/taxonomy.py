"""
Karen's Ear — Operational Urgency Taxonomy & Signal Definitions.

Step 2B of the ML pipeline (architecture/ml-pipeline.md Section 3.3 and gemini.md Section 6.2).
Provides centralized signal vocabularies, weights, threshold constants, regex patterns,
and feature definitions for the deterministic Urgency Engine:
1. Life Safety (weight: 0.50)
2. Hazard Velocity (weight: 0.30)
3. Vulnerability (weight: 0.20)

CRITICAL ARCHITECTURAL PRINCIPLES:
- ADR-003: Operational urgency is feature-derived and deterministic.
  CrisiText does NOT provide categorical operational urgency ground truth.
  No claims of CrisiText supervised urgency training or accuracy.
- ADR-004: Strict separation of ML confidence from operational priority.
  urgency != ML confidence.
  urgency_score != backend priority_score.
- Bounded, explainable feature scoring.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from ml.config import CANONICAL_URGENCY_LEVELS

# ==============================================================================
# Canonical Urgency Tiers & Weights
# (Matching ml/config.py and architecture/ml-pipeline.md Section 3.3)
# ==============================================================================

WEIGHT_LIFE_SAFETY: Final[float] = 0.50
WEIGHT_HAZARD_VELOCITY: Final[float] = 0.30
WEIGHT_VULNERABILITY: Final[float] = 0.20

THRESHOLD_CRITICAL: Final[float] = 80.0
THRESHOLD_HIGH: Final[float] = 60.0
THRESHOLD_MEDIUM: Final[float] = 35.0

# Canonical Urgency Labels
LABEL_CRITICAL: Final[str] = "CRITICAL"
LABEL_HIGH: Final[str] = "HIGH"
LABEL_MEDIUM: Final[str] = "MEDIUM"
LABEL_LOW: Final[str] = "LOW"

VALID_URGENCY_LABELS: Final[frozenset[str]] = frozenset(CANONICAL_URGENCY_LEVELS)


def is_canonical_urgency_label(label: str | None) -> bool:
    """Returns True if the label is a valid canonical urgency tier."""
    return label in VALID_URGENCY_LABELS


# ==============================================================================
# Signal Group 1: Life Safety Patterns (Weight: 50%)
# ==============================================================================

@dataclass(frozen=True)
class LifeSafetySignalDefinition:
    """Descriptor for an explicit life-safety signal pattern."""

    signal_id: str
    base_score: float
    description: str
    pattern: re.Pattern[str]


LIFE_SAFETY_SIGNALS: tuple[LifeSafetySignalDefinition, ...] = (
    LifeSafetySignalDefinition(
        signal_id="NOT_BREATHING",
        base_score=95.0,
        description="Victim not breathing, suffocating, choking, or in asphyxiation",
        pattern=re.compile(
            r"\b(?:not\s+breathing|cannot\s+breathe|can'?t\s+breathe|stopped\s+breathing|"
            r"suffocating|suffocation|asphyxiat(?:ion|ed)|choking|no\s+pulse|gasping\s+for\s+air|"
            r"unable\s+to\s+breathe|respiratory\s+arrest)\b",
            re.IGNORECASE,
        ),
    ),
    LifeSafetySignalDefinition(
        signal_id="COLLAPSE_WITH_OCCUPANTS",
        base_score=92.0,
        description="Structural collapse with people trapped or occupants inside",
        pattern=re.compile(
            r"\b(?:trapped\s+(?:under|inside|beneath|in)\s+(?:rubble|debris|collapsed|wreckage)|"
            r"(?:building|roof|wall|structure|bridge|flyover)\s+(?:collaps\w+|caved\s+in)\s+(?:with|on)\s+(?:people|victims?|occupants?|workers?|residents?)|"
            r"people\s+buried\s+(?:alive|under|beneath)|buried\s+under\s+rubble)\b",
            re.IGNORECASE,
        ),
    ),
    LifeSafetySignalDefinition(
        signal_id="ACTIVE_THREAT_TO_PEOPLE",
        base_score=90.0,
        description="Active armed threat, shooting, or violent assault directed at individuals",
        pattern=re.compile(
            r"\b(?:active\s+shooter|gunman\s+(?:shooting|firing|inside)|shooting\s+at\s+people|"
            r"attacker\s+(?:stabbing|shooting|inside)|shots\s+fired\s+at\s+(?:crowd|people|civilians?)|"
            r"mass\s+stabbing|hostage\s+situation|armed\s+assailant\s+firing|"
            r"assailant\s+with\s+(?:machete|gun|weapon|knife)\s+attacking)\b",
            re.IGNORECASE,
        ),
    ),
    LifeSafetySignalDefinition(
        signal_id="TRAPPED",
        base_score=85.0,
        description="People trapped, pinned, stuck, or unable to evacuate",
        pattern=re.compile(
            r"\b(?:trapped|pinned|stuck\s+inside|unable\s+to\s+(?:escape|get\s+out|evacuate)|"
            r"can'?t\s+get\s+out|we\s+are\s+trapped|people\s+inside\s+cannot\s+escape|"
            r"locked\s+inside\s+burning|surrounded\s+by\s+(?:water|fire)\s+on\s+roof)\b",
            re.IGNORECASE,
        ),
    ),
    LifeSafetySignalDefinition(
        signal_id="DROWNING",
        base_score=85.0,
        description="People drowning, submerged, or being swept away in waters",
        pattern=re.compile(
            r"\b(?:drowning|swept\s+away(?:\s+by\s+(?:water|flood|current|river))?|"
            r"submerged\s+in\s+water|sinking\s+in\s+water|underwater\s+car|"
            r"clinging\s+to\s+(?:tree|pole|roof)\s+in\s+flood)\b",
            re.IGNORECASE,
        ),
    ),
    LifeSafetySignalDefinition(
        signal_id="UNCONSCIOUS",
        base_score=80.0,
        description="Victims unconscious, unresponsive, or in a coma",
        pattern=re.compile(
            r"\b(?:unconscious|unresponsive|passed\s+out|collapsed\s+and\s+unresponsive|"
            r"in\s+a\s+coma|knocked\s+out|fainted\s+and\s+not\s+waking)\b",
            re.IGNORECASE,
        ),
    ),
    LifeSafetySignalDefinition(
        signal_id="BLEEDING_SEVERE_INJURY",
        base_score=75.0,
        description="Profuse bleeding, hemorrhage, critical trauma, or severed limbs",
        pattern=re.compile(
            r"\b(?:bleeding\s+(?:heavily|profusely|severely)|arterial\s+bleeding|hemorrhag\w+|"
            r"critical\s+injur\w+|severe\s+(?:burns?|trauma|head\s+injury|fractures?)|"
            r"severed\s+limb|crush\s+injury|amputat\w+)\b",
            re.IGNORECASE,
        ),
    ),
    LifeSafetySignalDefinition(
        signal_id="SEVERE_MEDICAL_DISTRESS",
        base_score=75.0,
        description="Cardiac arrest, heart attack, stroke, seizure, severe anaphylaxis",
        pattern=re.compile(
            r"\b(?:cardiac\s+arrest|heart\s+attack|stroke|massive\s+heart\s+attack|"
            r"seizure|anaphylaxis|anaphylactic\s+shock|overdose|diabetic\s+coma)\b",
            re.IGNORECASE,
        ),
    ),
    LifeSafetySignalDefinition(
        signal_id="POPULATION_IMMINENT_PERIL",
        base_score=68.0,
        description="Hazard directly advancing toward residential or populated area",
        pattern=re.compile(
            r"\b(?:drifting\s+toward\s+residential|spreading\s+(?:\w+\s+)?(?:to|between)\s+(?:commercial|row\s+houses?|homes|houses)|"
            r"water\s+entering\s+residential\s+compound|chemical\s+cloud\s+drifting|toxic\s+cloud\s+drifting|"
            r"shops?\s+evacuat\w+|gas\s+line\s+rupture|vapor\s+plume|(?:residents?|occupants?)\s+evacuat\w+)\b",
            re.IGNORECASE,
        ),
    ),
    LifeSafetySignalDefinition(
        signal_id="PEOPLE_AT_IMMEDIATE_RISK",
        base_score=60.0,
        description="General immediate peril or threat to human life",
        pattern=re.compile(
            r"\b(?:lives?\s+at\s+risk|mortal\s+danger|imminent\s+danger\s+to\s+life|"
            r"people\s+in\s+danger|life[\s-]threatening\s+situation)\b",
            re.IGNORECASE,
        ),
    ),
    LifeSafetySignalDefinition(
        signal_id="INJURED",
        base_score=50.0,
        description="Reported injuries, casualties, or wounded persons",
        pattern=re.compile(
            r"\b(?:injur(?:ed|ies|y)|wounded|casualties|hurt|burns?|broken\s+bones?|"
            r"lacerations?|blunt\s+trauma)\b",
            re.IGNORECASE,
        ),
    ),
    LifeSafetySignalDefinition(
        signal_id="MISSING",
        base_score=45.0,
        description="Missing, unaccounted for, or separated persons in disaster",
        pattern=re.compile(
            r"\b(?:missing\s+(?:people|persons?|children|family|residents?)|unaccounted\s+for|"
            r"lost\s+in\s+(?:flood|rubble|storm)|separated\s+from\s+family)\b",
            re.IGNORECASE,
        ),
    ),
)


# Distress language patterns (elevate life-safety score and explicitness)
DISTRESS_PATTERNS: tuple[tuple[str, re.Pattern[str], float], ...] = (
    (
        "EXTREME_DISTRESS",
        re.compile(
            r"\b(?:dying|we\s+are\s+dying|going\s+to\s+die|save\s+us|sos|we\s+cannot\s+hold\s+on|"
            r"please\s+hurry|send\s+help\s+now|screaming\s+for\s+help)\b|"
            r"\bhelp\s*!+|"
            r"\bplease\s+help\b|"
            r"\bsend\s+help\b",
            re.IGNORECASE,
        ),
        25.0,
    ),
    (
        "URGENT_DISTRESS",
        re.compile(
            r"\b(?:urgent|emergency|critical\s+emergency|life\s+or\s+death|hurry|immediate\s+help|"
            r"need\s+help\s+asap|emergency\s+assistance\s+needed)\b",
            re.IGNORECASE,
        ),
        15.0,
    ),
)

# Casual / informational context where "help" does not imply active life peril
INFORMATIONAL_HELP_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:help\s+(?:desk|line|center|counter|booth|available|provided)|"
    r"can\s+help|self[\s-]help|offer\s+help|helpful|to\s+help\s+with\s+(?:traffic|cleanup))\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SignalNegationDefinition:
    """Descriptor for targeted, signal-specific negation rules."""

    negation_id: str
    target_signals: tuple[str, ...]
    pattern: re.Pattern[str]
    description: str


SIGNAL_NEGATION_DEFINITIONS: tuple[SignalNegationDefinition, ...] = (
    SignalNegationDefinition(
        negation_id="NEGATION_NO_INJURIES_OR_CASUALTIES",
        target_signals=("INJURED", "BLEEDING_SEVERE_INJURY"),
        pattern=re.compile(
            r"\b(?:no\s+(?:one\s+(?:is|was)\s+)?(?:injur\w*|hurt|wounded|casualties|fatalities)|"
            r"zero\s+(?:injuries|casualties|fatalities)|without\s+(?:any\s+)?(?:injuries|casualties|fatalities)|"
            r"no\s+(?:injuries|casualties)\s+reported|no\s+reports\s+of\s+(?:injuries|casualties))\b",
            re.IGNORECASE,
        ),
        description="Explicit negation of casualties, injuries, or bleeding trauma",
    ),
    SignalNegationDefinition(
        negation_id="NEGATION_NO_PEOPLE_TRAPPED",
        target_signals=("TRAPPED",),
        pattern=re.compile(
            r"\b(?:no\s+(?:one\s+(?:is|was)\s+)?(?:trapped|pinned|stuck)|"
            r"no\s+reports\s+of\s+people\s+trapped|nobody\s+(?:is|was)\s+trapped|"
            r"no\s+one\s+is\s+trapped)\b",
            re.IGNORECASE,
        ),
        description="Explicit negation of trapped, pinned, or stuck individuals",
    ),
    SignalNegationDefinition(
        negation_id="NEGATION_NO_DROWNING",
        target_signals=("DROWNING",),
        pattern=re.compile(
            r"\b(?:no\s+(?:one\s+(?:is|was)\s+)?(?:drowning|swept\s+away)|"
            r"no\s+drowning\s+reported)\b",
            re.IGNORECASE,
        ),
        description="Explicit negation of drowning or swept away victims",
    ),
    SignalNegationDefinition(
        negation_id="NEGATION_NO_ACTIVE_THREAT",
        target_signals=("ACTIVE_THREAT_TO_PEOPLE", "ACTIVE_SHOOTING_ATTACK"),
        pattern=re.compile(
            r"\b(?:no\s+active\s+(?:threat|shooter|attacker|assailant)|"
            r"(?:shooter|attacker|assailant|gunman)\s+(?:arrested|in\s+custody|neutralized|apprehended|down))\b",
            re.IGNORECASE,
        ),
        description="Explicit negation or neutralization of active shooter / violent threat",
    ),
    SignalNegationDefinition(
        negation_id="NEGATION_NO_MEDICAL_DISTRESS",
        target_signals=("UNCONSCIOUS", "NOT_BREATHING_CARDIORESPIRATORY", "SEVERE_MEDICAL_DISTRESS"),
        pattern=re.compile(
            r"\b(?:conscious\s+and\s+breathing|breathing\s+normally|patient\s+is\s+conscious|"
            r"no\s+medical\s+distress|vital\s+signs\s+stable)\b",
            re.IGNORECASE,
        ),
        description="Explicit negation of cardiorespiratory or unconscious medical crisis",
    ),
    SignalNegationDefinition(
        negation_id="NEGATION_GENERAL_OCCUPANTS_SAFE",
        target_signals=("TRAPPED", "INJURED", "MISSING", "PEOPLE_AT_IMMEDIATE_RISK"),
        pattern=re.compile(
            r"\b(?:everyone\s+(?:is|was)\s+safe(?:\s+and\s+accounted\s+for)?|"
            r"all\s+(?:occupants|residents|people)\s+(?:are|were)\s+safe|"
            r"all\s+(?:occupants|residents|people)\s+(?:are|were)\s+accounted\s+for(?:\s+and\s+safe)?|"
            r"all\s+occupants\s+evacuated\s+safely)\b",
            re.IGNORECASE,
        ),
        description="General statement that occupants are evacuated, safe, or accounted for",
    ),
)

# Tuple of negation patterns for general inspection / backwards compatibility
LIFE_SAFETY_NEGATION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    defn.pattern for defn in SIGNAL_NEGATION_DEFINITIONS
)


# ==============================================================================
# Signal Group 2: Hazard Velocity Patterns (Weight: 30%)
# ==============================================================================

@dataclass(frozen=True)
class HazardVelocitySignalDefinition:
    """Descriptor for an explicit hazard velocity signal pattern."""

    signal_id: str
    base_score: float
    description: str
    pattern: re.Pattern[str]


HAZARD_VELOCITY_SIGNALS: tuple[HazardVelocitySignalDefinition, ...] = (
    HazardVelocitySignalDefinition(
        signal_id="COLLAPSE_IN_PROGRESS",
        base_score=95.0,
        description="Structural collapse occurring right now or imminent structural failure",
        pattern=re.compile(
            r"\b(?:collapsing(?:\s+(?:now|right\s+now))?|collapse\s+in\s+progress|"
            r"about\s+to\s+collapse|building\s+is\s+collapsing|walls?\s+caving\s+in|"
            r"structural\s+failure\s+in\s+progress|roof\s+giving\s+way|active\s+collapse|"
            r"roof\s+caved\s+in|caved\s+in\s+on|canopy\s+collapsing)\b",
            re.IGNORECASE,
        ),
    ),
    HazardVelocitySignalDefinition(
        signal_id="RAPIDLY_RISING_WATER",
        base_score=90.0,
        description="Rapidly rising floodwaters, flash flood surge, or dam breach",
        pattern=re.compile(
            r"\b(?:water\s+(?:is\s+)?rising\s+(?:rapidly|fast|quickly)|flash\s+flood(?:\s+surge)?|"
            r"water\s+level\s+rising\s+fast|river\s+bursting\s+banks|dam\s+breach(?:\s+in\s+progress)?|"
            r"floodwaters\s+surging|fast[\s-]moving\s+currents?|fast[\s-]?(?:moving\s+)?floodwaters?|"
            r"fast\s+floodwater|water\s+rushing\s+rapidly)\b",
            re.IGNORECASE,
        ),
    ),
    HazardVelocitySignalDefinition(
        signal_id="SPREADING_FIRE",
        base_score=90.0,
        description="Rapidly spreading fire, wildfire front, or structure engulfed in flames",
        pattern=re.compile(
            r"\b(?:fire\s+(?:is\s+)?spreading(?:\s+(?:rapidly|fast|to\s+other\s+buildings))?|"
            r"spreading\s+fire|wildfire\s+advancing|flames\s+spreading|fire\s+jumping|"
            r"engulfed\s+in\s+flames|fully\s+involved|uncontrolled\s+blaze)\b",
            re.IGNORECASE,
        ),
    ),
    HazardVelocitySignalDefinition(
        signal_id="ACTIVE_SHOOTING_ATTACK",
        base_score=90.0,
        description="Active shooting in progress, ongoing armed assault",
        pattern=re.compile(
            r"\b(?:active\s+shooter|shooting\s+in\s+progress|ongoing\s+attack|"
            r"shots\s+fired\s+right\s+now|gunman\s+on\s+the\s+loose|active\s+stabbing|"
            r"assailant\s+with\s+(?:machete|gun|weapon|knife)\s+attacking)\b",
            re.IGNORECASE,
        ),
    ),
    HazardVelocitySignalDefinition(
        signal_id="EXPLOSION_BLAST",
        base_score=85.0,
        description="Explosion, active detonation, blast wave, or tank exploding",
        pattern=re.compile(
            r"\b(?:explosion|exploded|blast(?:\s+wave)?|detonat\w+|tanker\s+explod\w+|"
            r"gas\s+cylinder\s+explosion|secondary\s+explosions?)\b",
            re.IGNORECASE,
        ),
    ),
    HazardVelocitySignalDefinition(
        signal_id="GAS_LEAK_HAZMAT_SPREAD",
        base_score=85.0,
        description="Spreading gas leak, toxic chemical plume, pipeline rupture",
        pattern=re.compile(
            r"\b(?:gas\s+leak(?:\s+spreading)?|chemical\s+leak|toxic\s+fumes?\s+spreading|chemical\s+plume|"
            r"ammonia\s+leak|chlorine\s+leak|pipeline\s+rupture|hazmat\s+leak|"
            r"toxic\s+chemical\s+cloud|gas\s+line\s+rupture)\b",
            re.IGNORECASE,
        ),
    ),
    HazardVelocitySignalDefinition(
        signal_id="ELECTRICAL_ARCING_LIVE_WIRES",
        base_score=80.0,
        description="Live electrical wires sparking, arcing, down across water or road with active peril",
        pattern=re.compile(
            r"\b(?:live\s+(?:power\s+)?lines?\s+(?:(?:are\s+)?(?:down|sparking|arcing|in\s+water))|"
            r"sparking\s+(?:power\s+lines?|wires?|transformer)|high\s+voltage\s+wire\s+down|"
            r"electrical\s+arcing|electrified\s+water)\b",
            re.IGNORECASE,
        ),
    ),
    HazardVelocitySignalDefinition(
        signal_id="ENCLOSED_ENTRAPMENT_PERIL",
        base_score=80.0,
        description="Entrapment in enclosed perilous space (basement, mine shaft, suffocating)",
        pattern=re.compile(
            r"\b(?:trapped\s+in\s+(?:basement|mine\s+shaft|elevator|tunnel|shaft)|"
            r"trapped\s+inside\s+mine|cannot\s+breathe\s+in|smoke\s+is\s+suffocating)\b",
            re.IGNORECASE,
        ),
    ),
    HazardVelocitySignalDefinition(
        signal_id="ACTIVE_FIRE",
        base_score=65.0,
        description="Active fire reported without explicit rapid spread",
        pattern=re.compile(
            r"\b(?:building\s+on\s+fire|structure\s+fire|house\s+on\s+fire|"
            r"active\s+fire|flames\s+visible|smoke\s+and\s+flames|"
            r"(?:warehouse|factory|commercial|plant|shop)\s+fire)\b",
            re.IGNORECASE,
        ),
    ),
    HazardVelocitySignalDefinition(
        signal_id="ACTIVE_FLOODING",
        base_score=55.0,
        description="Active flooding entering structures or roads",
        pattern=re.compile(
            r"\b(?:flooding|basement\s+flooded|flooded\s+with\s+water|water\s+entering\s+homes?|street\s+flooded|"
            r"waterlogged|inundated\s+with\s+water|roads?\s+underwater|"
            r"water\s+accumulation(?:\s+across)?|floodwaters?\s+entering|"
            r"river\s+embankment\s+overflow\w*)\b",
            re.IGNORECASE,
        ),
    ),
    HazardVelocitySignalDefinition(
        signal_id="UTILITY_FAILURE",
        base_score=50.0,
        description="Power outage, utility disruption, blackout, broken water main",
        pattern=re.compile(
            r"\b(?:power\s+outage|blackout|transformer\s+blown|water\s+main\s+(?:break|ruptured)|"
            r"utility\s+failure|power\s+grid\s+down|no\s+electricity|streetlights?\s+non-functional)\b",
            re.IGNORECASE,
        ),
    ),
    HazardVelocitySignalDefinition(
        signal_id="STRUCTURAL_DAMAGE",
        base_score=45.0,
        description="Structural damage, cracked walls, partial damage without active collapse",
        pattern=re.compile(
            r"\b(?:damaged\s+(?:building|structure|bridge|roof)|cracked\s+walls?|"
            r"structural\s+damage|partial\s+damage|shattered\s+windows?|"
            r"cracks\s+observed|cracks\s+along\s+supporting)\b",
            re.IGNORECASE,
        ),
    ),
    HazardVelocitySignalDefinition(
        signal_id="ROAD_OBSTRUCTION",
        base_score=35.0,
        description="Fallen tree, blocked road, debris on street without life threat",
        pattern=re.compile(
            r"\b(?:road\s+blocked|tree\s+fell\s+across\s+road|fallen\s+tree|"
            r"traffic\s+disrupted|debris\s+on\s+road|lane\s+closed|fell\s+across\s+two\s+lanes)\b",
            re.IGNORECASE,
        ),
    ),
    HazardVelocitySignalDefinition(
        signal_id="LOCALIZED_DUMPSTER_FIRE",
        base_score=40.0,
        description="Localized small fire in trash or dumpster",
        pattern=re.compile(
            r"\b(?:dumpster\s+fire|trash\s+fire|rubbish\s+fire)\b",
            re.IGNORECASE,
        ),
    ),
)


# Temporal / dynamic markers that accelerate or confirm ongoing velocity
TEMPORAL_ACTIVE_MARKERS: re.Pattern[str] = re.compile(
    r"\b(?:now|right\s+now|currently|ongoing|active|in\s+progress|"
    r"rapidly|fast|spreading|getting\s+worse|escalating|rising\s+fast)\b",
    re.IGNORECASE,
)


# Historical / Past / Extinguished markers that suppress hazard velocity
HISTORICAL_OR_CONTROLLED_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "EXTINGUISHED_OR_CONTAINED",
        re.compile(
            r"\b(?:extinguished|put\s+out|under\s+control|hazard\s+controlled|"
            r"doused|fire\s+is\s+out|flames\s+extinguished|"
            r"no\s+current\s+danger|no\s+ongoing\s+threat|no\s+immediate\s+danger)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "HISTORICAL_INCIDENT",
        re.compile(
            r"\b(?:burned\s+yesterday|collapsed\s+yesterday|flooded\s+yesterday|"
            r"happened\s+yesterday|occurred\s+yesterday|police\s+arrested\s+(?:attacker|suspect)\s+yesterday|"
            r"damage\s+from\s+yesterday|last\s+(?:night|week|month)|earlier\s+today\s+and\s+(?:now\s+cleared|receded)|"
            r"historical|past\s+incident|area\s+is\s+now\s+secured|power\s+restored)\b",
            re.IGNORECASE,
        ),
    ),
)


# ==============================================================================
# Signal Group 3: Vulnerability Patterns (Weight: 20%)
# ==============================================================================

@dataclass(frozen=True)
class VulnerabilitySignalDefinition:
    """Descriptor for an explicit vulnerability signal pattern."""

    signal_id: str
    base_score: float
    description: str
    pattern: re.Pattern[str]


VULNERABILITY_SIGNALS: tuple[VulnerabilitySignalDefinition, ...] = (
    VulnerabilitySignalDefinition(
        signal_id="CHILDREN_AT_RISK",
        base_score=85.0,
        description="Children, infants, toddlers, or daycare/school occupants at risk",
        pattern=re.compile(
            r"\b(?:children|child|kids?|infants?|babies|baby|toddlers?|underage\s+minors?|unaccompanied\s+minors?|"
            r"daycare\s+children|schoolchildren|elementary\s+school\s+students?)\b",
            re.IGNORECASE,
        ),
    ),
    VulnerabilitySignalDefinition(
        signal_id="PATIENTS_AT_RISK",
        base_score=85.0,
        description="Hospital patients, ICU patients, or bedridden individuals affected",
        pattern=re.compile(
            r"\b(?:hospital\s+patients?|icu\s+patients?|bedridden|ventilator\s+dependent|"
            r"dialysis\s+patients?|infirmary\s+residents?|patients?\s+trapped)\b",
            re.IGNORECASE,
        ),
    ),
    VulnerabilitySignalDefinition(
        signal_id="ELDERLY_AT_RISK",
        base_score=80.0,
        description="Elderly, senior citizens, nursing home or aged care residents affected",
        pattern=re.compile(
            r"\b(?:elderly|seniors?|older\s+adults?|geriatric|pensioners?|"
            r"nursing\s+home\s+residents?|assisted\s+living\s+residents?)\b",
            re.IGNORECASE,
        ),
    ),
    VulnerabilitySignalDefinition(
        signal_id="DISABLED_OR_MOBILITY_IMPAIRED",
        base_score=80.0,
        description="Individuals with physical disabilities, wheelchair users, or limited mobility",
        pattern=re.compile(
            r"\b(?:wheelchair\s+users?|disabled(?:\s+persons?|\s+people)?|"
            r"limited\s+mobility|handicapped|blind|deaf|unable\s+to\s+walk)\b",
            re.IGNORECASE,
        ),
    ),
    VulnerabilitySignalDefinition(
        signal_id="PEOPLE_TRAPPED_VULNERABILITY",
        base_score=75.0,
        description="People physically trapped, unable to self-evacuate without rescue intervention",
        pattern=re.compile(
            r"\b(?:people\s+trapped|persons?\s+trapped|trapped\s+inside|trapped\s+in\s+(?:car|vehicle|building|elevator|wreckage|debris|rubble|basement|mine)|"
            r"are\s+trapped|workers\s+trapped|victims?\s+trapped|unable\s+to\s+escape|unable\s+to\s+evacuate)\b",
            re.IGNORECASE,
        ),
    ),
    VulnerabilitySignalDefinition(
        signal_id="VULNERABLE_FACILITY_AFFECTED",
        base_score=70.0,
        description="Critical care or vulnerable population facility experiencing active emergency with occupants",
        pattern=re.compile(
            r"\b(?:nursing\s+home|assisted\s+living|daycare(?:\s+center)?|orphanage|"
            r"hospice|kindergarten|special\s+needs\s+school)\b",
            re.IGNORECASE,
        ),
    ),
    VulnerabilitySignalDefinition(
        signal_id="INFRASTRUCTURE_TRANSIT_VULNERABILITY",
        base_score=65.0,
        description="Critical public transit thoroughfare, arterial roadway, utility grid node, or public area",
        pattern=re.compile(
            r"\b(?:(?:main\s+street|arterial\s+road|highway|overpass|flyover|bridge|transit|subway|railway)\s+(?:blocked|flooded|impassable|closed|water\s+accumulation)|"
            r"water\s+main|power\s+blackout|two\s+city\s+blocks|5th\s+avenue|transformer\s+blown|"
            r"residential\s+(?:compound|neighborhood|subdivisions?)|metro\s+station|shopping\s+(?:complex|mall)|row\s+houses?|"
            r"fell\s+across\s+(?:two\s+)?lanes|two\s+lanes\s+of\s+traffic|vehicles\s+are\s+detouring|"
            r"parking\s+garage|supporting\s+pillar|vehicles\s+being\s+redirected|"
            r"basement\s+flooded|flooded\s+with\s+water|shops?\s+evacuat\w+|gas\s+line\s+rupture|"
            r"chemical\s+leak|warehouse)\b|"
            r"\b(?:live\s+(?:power\s+)?lines?\s+down\s+across\s+(?:road|street)|road\s+blocked\s+by\s+standing\s+water)\b",
            re.IGNORECASE,
        ),
    ),
    VulnerabilitySignalDefinition(
        signal_id="INCAPACITATED_VICTIM_VULNERABILITY",
        base_score=55.0,
        description="Victim incapacitated by collision, trauma, or medical distress",
        pattern=re.compile(
            r"\b(?:cyclist\s+struck|pinned\s+behind\s+wheel|severe\s+burns?|burns\s+and\s+injured)\b",
            re.IGNORECASE,
        ),
    ),
)


# Passive facility mention pattern (e.g. "Hospital is nearby") that should NOT inflate vulnerability
PASSIVE_FACILITY_MENTION_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:near(?:by)?\s+(?:the\s+)?(?:hospital|school|clinic|nursing\s+home|station)|"
    r"opposite\s+(?:the\s+)?(?:hospital|school)|in\s+front\s+of\s+(?:the\s+)?(?:hospital|school)|"
    r"behind\s+(?:the\s+)?(?:hospital|school)|passing\s+by\s+(?:the\s+)?(?:hospital|school)|"
    r"hospital\s+is\s+nearby|school\s+is\s+closed)\b",
    re.IGNORECASE,
)


# Vulnerability negation
VULNERABILITY_NEGATION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:no\s+children\s+(?:present|inside|affected)|"
        r"all\s+patients\s+(?:evacuated|safe)|"
        r"school\s+was\s+empty|no\s+elderly\s+residents\s+remaining|"
        r"daycare\s+was\s+closed)\b",
        re.IGNORECASE,
    ),
)


# ==============================================================================
# Uncertainty, Hedging & Ambiguity Patterns
# (Reduces ML confidence, but preserves transparent score)
# ==============================================================================

HEDGING_OR_UNCERTAINTY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:possible|possibly|might|maybe|could\s+be|suspected|unconfirmed|"
        r"rumored|alleged|not\s+sure|unclear|looks\s+like|appears\s+to\s+be|"
        r"unverified|someone\s+said|hearing\s+reports\s+that)\b",
        re.IGNORECASE,
    ),
)
