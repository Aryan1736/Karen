"""
Karen's Ear — People-at-Risk Extractor.

Step 2D of the ML pipeline (architecture/ml-pipeline.md Section 3.5).
Extracts reliable people-at-risk numeric counts, qualitative risk indicators,
and deterministic extraction confidence from emergency dispatch text.

HARD NO-HALLUCINATION ARCHITECTURAL INVARIANT:
- Qualitative quantities (e.g. "multiple people trapped", "several injured", "many inside")
  MUST NEVER be converted into an estimated numeric baseline (such as 2).
- If no reliable numeric count exists, count is strictly null and confidence is strictly null.
- Qualitative risk signals (e.g. MULTIPLE_PEOPLE, TRAPPED, INJURED, CHILDREN) are preserved
  separately from the numeric count.
- Unrelated numbers (building numbers, floor numbers, room numbers, emergency dial numbers,
  times, dates, distances) are strictly rejected from being extracted as people counts.

Guarantees:
1. Determinism: Same input text and configuration always produces identical extraction.
2. Explainability: Preserves rich internal evidence (raw span, normalized count, people noun,
   risk context, quantifier type, modifiers) explaining why a count was extracted.
3. Principled Count Selection: Aggregates disjoint demographic subgroups (e.g. "3 children and 2 adults" => 5)
   while avoiding blind summation for non-disjoint/overlapping status counts (e.g. "5 passengers injured and 2 missing" => 5).
4. Deterministic Confidence: Confidence reflects extraction strength and modifier uncertainty
   (explicit > approximate > hedged), never calibrated probability or operational urgency.
5. Privacy & Observability: Uses get_ml_logger; never leaks raw citizen distress text into logs.
6. Zero External APIs: Lightweight, pure Python regex and deterministic rules. Zero heavy ML dependencies.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

from ml.config import ComponentResult, MLConfig, get_ml_config
from ml.exceptions import MLInferenceError, MLInputError
from ml.logging_utils import get_ml_logger
from ml.preprocessing.text_cleaner import PreprocessedText, TextCleaner

# ==============================================================================
# Number Parsing Tables & Dictionaries
# ==============================================================================

_CARDINAL_WORDS: dict[str, int] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fourty": 40,  # common phonetic misspelling
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

_TENS_WORDS: dict[str, int] = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fourty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

_UNITS_WORDS: dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
}


def parse_number_token(token: str) -> int | None:
    """
    Parses a string token into an integer count if it represents a valid number.
    Supports digits, cardinal number words, and compound words (e.g. 'twenty-five', 'twenty five', 'one hundred and five').
    Returns None if the token cannot be parsed into a positive/non-negative integer.
    """
    cleaned = token.strip().lower()
    if not cleaned:
        return None

    # Strip formatting commas if present (e.g., '1,000')
    cleaned_digits = cleaned.replace(",", "")
    if cleaned_digits.isdigit():
        try:
            val = int(cleaned_digits)
            return val if 0 <= val <= 10000 else None
        except ValueError:
            return None

    # Single-word cardinal
    if cleaned in _CARDINAL_WORDS:
        return _CARDINAL_WORDS[cleaned]

    # Hyphenated compound: 'twenty-five'
    if "-" in cleaned:
        parts = cleaned.split("-")
        if len(parts) == 2 and parts[0] in _TENS_WORDS and parts[1] in _UNITS_WORDS:
            return _TENS_WORDS[parts[0]] + _UNITS_WORDS[parts[1]]

    # Space-separated parts
    parts = cleaned.split()

    # Hundred compounds: 'one hundred', 'two hundred', 'a hundred', 'hundred', 'one hundred and five'
    if "hundred" in parts:
        idx = parts.index("hundred")
        multiplier = 1
        if idx > 0 and parts[idx - 1] in _UNITS_WORDS:
            multiplier = _UNITS_WORDS[parts[idx - 1]]
        elif idx > 0 and parts[idx - 1] in ("a", "one"):
            multiplier = 1
        base = multiplier * 100

        # Remaining tokens after 'hundred' (e.g. 'and five', 'twenty five')
        remainder = [p for p in parts[idx + 1 :] if p != "and"]
        if not remainder:
            return base
        rem_str = " ".join(remainder)
        rem_val = parse_number_token(rem_str)
        if rem_val is not None:
            return base + rem_val
        return base

    # Space-separated compound: 'twenty five'
    if len(parts) == 2 and parts[0] in _TENS_WORDS and parts[1] in _UNITS_WORDS:
        return _TENS_WORDS[parts[0]] + _UNITS_WORDS[parts[1]]

    return None


# ==============================================================================
# Demographic Category Taxonomies (for disjoint aggregation)
# ==============================================================================

CHILDREN_TERMS: frozenset[str] = frozenset({
    "child",
    "children",
    "kid",
    "kids",
    "infant",
    "infants",
    "baby",
    "babies",
    "toddler",
    "toddlers",
    "boy",
    "boys",
    "girl",
    "girls",
    "minor",
    "minors",
})

ADULT_TERMS: frozenset[str] = frozenset({
    "adult",
    "adults",
    "man",
    "men",
    "woman",
    "women",
})

ELDERLY_TERMS: frozenset[str] = frozenset({
    "elderly",
    "senior",
    "seniors",
    "pensioner",
    "pensioners",
    "grandparent",
    "grandparents",
})


def _is_disjoint_demographic(noun_a: str, noun_b: str) -> bool:
    """Returns True if noun_a and noun_b belong to provably disjoint demographic groups."""
    a = noun_a.lower()
    b = noun_b.lower()

    if (a in CHILDREN_TERMS and b in ADULT_TERMS) or (a in ADULT_TERMS and b in CHILDREN_TERMS):
        return True
    if (a in CHILDREN_TERMS and b in ELDERLY_TERMS) or (a in ELDERLY_TERMS and b in CHILDREN_TERMS):
        return True
    if (a in ("boy", "boys") and b in ("girl", "girls")) or (a in ("girl", "girls") and b in ("boy", "boys")):
        return True
    if (a in ("man", "men") and b in ("woman", "women")) or (a in ("woman", "women") and b in ("man", "men")):
        return True

    return False


# ==============================================================================
# Negative Context Patterns (Unrelated Numbers to Reject)
# ==============================================================================

_NEGATIVE_CONTEXT_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Emergency call/dispatch/hotline numbers
    re.compile(r"\b(?:call|dial|contact|phone|reach)\s+(?:at\s+)?(?:\+?\d[\d\s-]{2,}\d|\d{3,})\b", re.IGNORECASE),
    re.compile(r"\b(?:call|dial)\s+(?:112|911|999|100|101|108|102)\b", re.IGNORECASE),
    re.compile(r"\b(?:hotline|toll[\s-]free|helpline)\s*:?\s*\d+\b", re.IGNORECASE),
    # Buildings, rooms, floors, apartments, suites, doors, gates, towers
    re.compile(r"\b(?:building|bldg\.?)\s+(?:no\.?\s*)?(\d+|[a-zA-Z0-9-]+)\b", re.IGNORECASE),
    re.compile(r"\b(?:floor|fl\.?|level|story|storey)\s+(?:no\.?\s*)?(\d+|[a-zA-Z0-9-]+)\b", re.IGNORECASE),
    re.compile(r"\b(?:room|rm\.?|apt\.?|apartment|flat|suite|ste\.?|unit)\s+(?:no\.?\s*)?(\d+|[a-zA-Z0-9-]+)\b", re.IGNORECASE),
    re.compile(r"\b(?:block|blk\.?|gate|pier|terminal|door|tower|pillar|pole|bed)\s+(?:no\.?\s*)?(\d+|[a-zA-Z0-9-]+)\b", re.IGNORECASE),
    re.compile(r"\b(?:house|plot|lot)\s+(?:no\.?\s*)?(\d+)\b", re.IGNORECASE),
    # Roads, highways, routes, sectors, exits
    re.compile(r"\b(?:route|rt\.?|highway|hwy\.?|interstate|i-|nh-?|m-?|state\s+highway|sh-?)\s*(\d+)\b", re.IGNORECASE),
    re.compile(r"\b(?:sector|sec\.?|street|st\.?|avenue|ave\.?|exit|mile\s+marker)\s+(\d+)\b", re.IGNORECASE),
    # Vehicles (bus 14, flight 370, train 1204)
    re.compile(r"\b(?:bus|flight|train|engine|car|truck|vehicle)\s+(?:no\.?\s*)?(\d+)\b", re.IGNORECASE),
    # Time expressions: "at 8 PM", "8:30", "8 am", "10 minutes ago", "for 2 hours"
    re.compile(r"\b(?:at\s+)?\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.|o'?clock)\b", re.IGNORECASE),
    re.compile(r"\bat\s+\d{1,2}(?::\d{2})?\b", re.IGNORECASE),
    re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", re.IGNORECASE),
    re.compile(r"\b\d+\s*(?:seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|weeks?|months?|years?)\s*(?:ago|later|prior)?\b", re.IGNORECASE),
    re.compile(r"\b\d{1,2}(?:st|nd|rd|th)\b", re.IGNORECASE),
    re.compile(r"\b(?:jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|september|oct|october|nov|november|dec|december)\s+\d{1,2}\b", re.IGNORECASE),
    # Measurements and units
    re.compile(r"\b\d+(?:\.\d+)?\s*(?:m|meters?|metres?|km|kilometers?|kilometres?|miles?|ft|feet|inches|cm|mm|yards?)\b", re.IGNORECASE),
    re.compile(r"\b\d+(?:\.\d+)?\s*(?:kg|kilos?|kilograms?|lbs?|pounds?|tons?)\b", re.IGNORECASE),
    re.compile(r"\b\d+(?:\.\d+)?\s*(?:mph|kmh|km/h|knots)\b", re.IGNORECASE),
    re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|percent)\b", re.IGNORECASE),
    re.compile(r"(?:\$|€|£|₹|rs\.?\s*)\s*\d+(?:\.\d+)?\b", re.IGNORECASE),
    re.compile(r"\b\d+(?:\.\d+)?\s*(?:dollars?|euros?|pounds?|rupees?|bucks?)\b", re.IGNORECASE),
    re.compile(r"\b\d+(?:\.\d+)?\s*(?:degrees?|celsius|fahrenheit)\b", re.IGNORECASE),
)


def _find_negative_spans(text: str) -> list[tuple[int, int]]:
    """Returns a list of character spans [start, end) matching negative non-people contexts."""
    spans: list[tuple[int, int]] = []
    for pattern in _NEGATIVE_CONTEXT_PATTERNS:
        for match in pattern.finditer(text):
            spans.append((match.start(), match.end()))
    return spans


def _is_span_in_negative_context(start: int, end: int, negative_spans: list[tuple[int, int]]) -> bool:
    """Checks whether [start, end) overlaps or falls inside any negative context span."""
    for n_start, n_end in negative_spans:
        if max(start, n_start) < min(end, n_end):
            return True
    return False


# ==============================================================================
# Qualitative Quantity Patterns (Hard No-Hallucination: Never produce counts)
# ==============================================================================

_QUALITATIVE_QUANTITY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:multiple|several|many|numerous)\s+(?:others?\s+)?(?:are\s+|were\s+)?"
        r"(?:people|persons?|children|kids?|passengers?|victims?|occupants?|workers?|residents?|individuals?|civilians?|casualties|trapped|injured|missing|unconscious|inside|stranded|others?)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:multiple|several|many|numerous)\s+others\b", re.IGNORECASE),
    re.compile(
        r"\b(?:a\s+)?groups?\s+of\s+(?:people|persons?|children|kids?|passengers?|victims?|occupants?|workers?|residents?|individuals?)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:large\s+)?crowds?\b", re.IGNORECASE),
    re.compile(
        r"\bdozens\s+(?:of\s+)?(?:people|persons?|children|kids?|passengers?|victims?|occupants?|workers?|residents?|individuals?|casualties|trapped|injured|missing|inside|stranded)?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:a\s+)?lots?\s+of\s+(?:people|passengers|children|residents|victims|occupants)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bsome\s+(?:people|passengers|children|residents|victims|occupants)\b",
        re.IGNORECASE,
    ),
)

# ==============================================================================
# Qualitative Risk Indicators Taxonomy
# ==============================================================================

_RISK_SIGNAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "TRAPPED",
        re.compile(
            r"\b(?:trapped(?:\s+inside)?|unable\s+to\s+escape|can'?t\s+escape|cannot\s+escape|stuck(?:\s+inside)?|pinned(?:\s+under)?|buried(?:\s+under)?|under\s+rubble|caught\s+inside|stranded)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "INJURED",
        re.compile(
            r"\b(?:badly\s+injured|seriously\s+injured|critically\s+injured|injured|injuries|wounded|wounds|badly\s+hurt|hurt|bleeding|burned|burns|casualties)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "MISSING",
        re.compile(
            r"\b(?:missing\s+persons?|missing|unaccounted\s+for|disappeared|lost)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "UNCONSCIOUS",
        re.compile(
            r"\b(?:unconscious|not\s+responding|unresponsive|passed\s+out|collapsed|fainting|no\s+pulse)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "DROWNING",
        re.compile(
            r"\b(?:drowning|underwater|submerged|swept\s+away|sinking)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "CHILDREN",
        re.compile(
            r"\b(?:children(?:\s+are|\s+inside)?|child|kids?|infants?|babies|baby|toddlers?|minors?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "ELDERLY",
        re.compile(
            r"\b(?:elderly(?:\s+people)?(?:\s+are|\s+inside)?|seniors?|older\s+adults?|geriatric|aged\s+people|pensioners?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "PATIENTS",
        re.compile(
            r"\b(?:patients?(?:\s+are|\s+inside)?|hospital\s+patients?|bedridden|icu\s+patients?)\b",
            re.IGNORECASE,
        ),
    ),
)


# ==============================================================================
# Typed Structures
# ==============================================================================


@dataclass
class RiskEvidence:
    """Internal explainability evidence supporting an extracted count or signal."""

    raw_span: str
    normalized_count: int | None
    people_noun: str | None
    risk_context: str | None
    quantifier_type: str  # "EXPLICIT", "APPROXIMATE", "BOUND", "HEDGED", "QUALITATIVE_ONLY"
    hedges_or_modifiers: list[str] = field(default_factory=list)
    start_char: int = -1
    end_char: int = -1


@dataclass
class PeopleRiskResult:
    """
    Standardized typed result emitted by PeopleRiskExtractor.
    Adheres strictly to Step 2D of the ML pipeline (architecture/ml-pipeline.md Section 3.5)
    and the canonical schema in ml/schemas/incident_output.json.
    """

    count: int | None
    confidence: float | None
    signals: list[str] = field(default_factory=list)
    evidence: list[RiskEvidence] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    processing_status: str = "SUCCESS"  # SUCCESS, PARTIAL, NEEDS_REVIEW, FAILED

    def to_canonical_dict(self) -> dict[str, Any]:
        """
        Converts to the canonical people_at_risk dictionary strictly validating
        against ml/schemas/incident_output.json:
        {
            "count": int | None,
            "confidence": float | None
        }
        """
        return {
            "count": self.count,
            "confidence": self.confidence,
        }

    def to_component_result(self) -> ComponentResult:
        """Converts into a standardized internal ComponentResult."""
        return ComponentResult(
            component="people_at_risk",
            status=self.processing_status,
            data={
                "people_at_risk": self.to_canonical_dict(),
                "signals": list(self.signals),
                "evidence": [
                    {
                        "raw_span": ev.raw_span,
                        "normalized_count": ev.normalized_count,
                        "people_noun": ev.people_noun,
                        "risk_context": ev.risk_context,
                        "quantifier_type": ev.quantifier_type,
                        "hedges_or_modifiers": list(ev.hedges_or_modifiers),
                    }
                    for ev in self.evidence
                ],
            },
            confidence=self.confidence,
            warnings=list(self.warnings),
        )

    def to_entities(self) -> list[dict[str, Any]]:
        """
        Converts extracted victim mentions and risk indicators into canonical
        entity tokens for the pipeline's entities list.
        """
        entities: list[dict[str, Any]] = []
        for ev in self.evidence:
            if ev.normalized_count is not None:
                entities.append({
                    "text": ev.raw_span,
                    "type": "VICTIM",
                    "confidence": self.confidence,
                })
        for sig in self.signals:
            entities.append({
                "text": sig.lower().replace("_", " "),
                "type": sig,
                "confidence": 0.90,
            })
        return entities

    def to_dict(self) -> dict[str, Any]:
        """Comprehensive dictionary representation of the result."""
        return {
            "count": self.count,
            "confidence": self.confidence,
            "signals": list(self.signals),
            "evidence": [
                {
                    "raw_span": ev.raw_span,
                    "normalized_count": ev.normalized_count,
                    "people_noun": ev.people_noun,
                    "risk_context": ev.risk_context,
                    "quantifier_type": ev.quantifier_type,
                    "hedges_or_modifiers": list(ev.hedges_or_modifiers),
                }
                for ev in self.evidence
            ],
            "warnings": list(self.warnings),
            "processing_status": self.processing_status,
        }


# ==============================================================================
# Candidate Extraction Structures & Patterns
# ==============================================================================


@dataclass
class _CandidateCount:
    count: int
    raw_span: str
    noun: str
    risk_context: str | None
    quantifier_type: str
    modifiers: list[str]
    confidence: float
    num_start: int
    num_end: int
    span_start: int
    span_end: int


# Compound number expression regex segment (matches compound words like 'twenty five', 'one hundred and five', 'twenty-five')
_COMPOUND_NUMBER_STR = (
    r"(?:"
    r"\d+(?:,\d{3})*|"
    r"(?:(?:one|two|three|four|five|six|seven|eight|nine|a)\s+)?hundred(?:\s+and)?(?:\s+(?:twenty|thirty|forty|fourty|fifty|sixty|seventy|eighty|ninety))?(?:[\s-]+(?:one|two|three|four|five|six|seven|eight|nine))?|"
    r"(?:twenty|thirty|forty|fourty|fifty|sixty|seventy|eighty|ninety)[\s-]+(?:one|two|three|four|five|six|seven|eight|nine)|"
    r"[a-zA-Z]+"
    r")"
)

# Primary people noun regular expression segment
_PEOPLE_NOUNS = (
    r"(?:people|persons?|passengers?|children|child|kids?|infants?|babies|baby|toddlers?|"
    r"workers?|employees?|laborers?|residents?|occupants?|tenants?|inhabitants?|"
    r"victims?|casualties|patients?|adults?|men|man|women|woman|"
    r"individuals?|citizens?|civilians?|bystanders?|pedestrians?|drivers?|motorists?|"
    r"students?|teachers?|tourists?)"
)

# Optional modifiers preceding numbers
_PREFIX_PATTERN = (
    r"(?P<prefix>(?:approx(?:imately)?|around|about|roughly|nearly|almost|estimated|"
    r"at\s+least|maybe|may\s+be|might\s+be|possibly|perhaps|reportedly|unconfirmed|believed\s+to\s+be)\s+)?"
)

# Adjectives between number and noun (e.g. '3 injured passengers', '2 trapped workers')
_MID_ADJ_PATTERN = (
    r"(?P<mid_adj>(?:trapped|injured|missing|unconscious|drowning|elderly|sick|stranded|"
    r"unaccounted\s+for|seriously\s+injured|badly\s+injured)\s+)?"
)

# Pattern 1: [Prefix] <Number> [Adjective] <PeopleNoun>
_PATTERN_NUMBER_NOUN = re.compile(
    rf"\b{_PREFIX_PATTERN}(?P<num>{_COMPOUND_NUMBER_STR})\s+{_MID_ADJ_PATTERN}(?P<noun>{_PEOPLE_NOUNS})\b",
    re.IGNORECASE,
)

# Pattern 2: Family of <Number>
_PATTERN_FAMILY_OF = re.compile(
    rf"\b(?:family|families)\s+of\s+(?P<num>{_COMPOUND_NUMBER_STR})\b",
    re.IGNORECASE,
)

# Pattern 3: There (are|were|found) [Prefix] <Number> (trapped|injured|missing|unconscious|drowning|stranded|inside)
_PATTERN_THERE_ARE = re.compile(
    rf"\b(?:there\s+(?:are|were)|found)\s+{_PREFIX_PATTERN}(?P<num>{_COMPOUND_NUMBER_STR})\s+"
    r"(?P<pred>trapped(?:\s+inside)?|injured|missing|unconscious|drowning|stranded|inside)\b",
    re.IGNORECASE,
)

# Pattern 4: Explicit Total stated (e.g. 'total of 10 people')
_PATTERN_TOTAL_STATED = re.compile(
    rf"\b(?:total\s+of|in\s+total)\s+{_PREFIX_PATTERN}(?P<num>{_COMPOUND_NUMBER_STR})\s+(?P<noun>{_PEOPLE_NOUNS})?\b",
    re.IGNORECASE,
)

# Pattern 5: <Number> (missing|injured|trapped|unconscious|drowning|stranded)
_PATTERN_NUMBER_STATUS = re.compile(
    rf"\b{_PREFIX_PATTERN}(?P<num>{_COMPOUND_NUMBER_STR})\s+(?:are\s+|were\s+)?(?P<status>missing|injured|trapped|unconscious|drowning|stranded)\b",
    re.IGNORECASE,
)


# ==============================================================================
# People-at-Risk Extractor
# ==============================================================================


class PeopleRiskExtractor:
    """
    Deterministic, explainable extractor for people-at-risk counts and qualitative indicators.
    Adheres strictly to Step 2D of the ML pipeline (architecture/ml-pipeline.md Section 3.5).
    """

    def __init__(self, config: MLConfig | None = None) -> None:
        self.config = config or get_ml_config()
        self.logger = get_ml_logger(
            name="karen.ml.extraction.people_risk",
            component="people_at_risk",
        )
        self._cleaner = TextCleaner(self.config)

    def extract(
        self,
        text: str | PreprocessedText,
        report_id: str | None = None,
    ) -> PeopleRiskResult:
        """
        Extracts people-at-risk count and qualitative indicators from an emergency report.

        Args:
            text: Raw report string or PreprocessedText from TextCleaner.
            report_id: Optional tracking identifier for logging and traceability.

        Returns:
            PeopleRiskResult containing count, confidence, signals, evidence, and warnings.

        Raises:
            MLInputError: If text is empty, whitespace-only, or invalid type.
            MLInferenceError: If an unexpected internal error occurs during execution.
        """
        # Step 1: Input Normalization & Validation (Feature 2 Integration)
        if isinstance(text, PreprocessedText):
            clean_text = text.normalized_text
            warnings = list(text.warnings)
        elif isinstance(text, str):
            preprocessed = self._cleaner.clean(text, report_id=report_id)
            clean_text = preprocessed.normalized_text
            warnings = list(preprocessed.warnings)
        else:
            raise MLInputError(
                f"Input text must be str or PreprocessedText, received {type(text).__name__}",
                details={"type": type(text).__name__},
            )

        try:
            # Step 2: Detect Qualitative Risk Signals & Qualitative Quantities
            signals: list[str] = []
            evidence_list: list[RiskEvidence] = []

            # A. Check for qualitative quantity language (Hard no-hallucination requirement)
            has_qualitative_quantity = False
            for pattern in _QUALITATIVE_QUANTITY_PATTERNS:
                match = pattern.search(clean_text)
                if match:
                    has_qualitative_quantity = True
                    span_text = match.group(0)
                    evidence_list.append(
                        RiskEvidence(
                            raw_span=span_text,
                            normalized_count=None,
                            people_noun="people",
                            risk_context=None,
                            quantifier_type="QUALITATIVE_ONLY",
                            hedges_or_modifiers=[span_text.split()[0].lower()],
                            start_char=match.start(),
                            end_char=match.end(),
                        )
                    )

            if has_qualitative_quantity and "MULTIPLE_PEOPLE" not in signals:
                signals.append("MULTIPLE_PEOPLE")

            # B. Check for standard qualitative risk signals
            for sig_name, pattern in _RISK_SIGNAL_PATTERNS:
                match = pattern.search(clean_text)
                if match and sig_name not in signals:
                    signals.append(sig_name)

            # Step 3: Find Negative Context Spans (reject non-people numbers)
            negative_spans = _find_negative_spans(clean_text)

            # Step 4: Extract Candidate People Counts
            candidate_counts: list[_CandidateCount] = []

            # 4.1 Pattern 1: [Prefix] <Number> [Adjective] <PeopleNoun>
            for match in _PATTERN_NUMBER_NOUN.finditer(clean_text):
                num_str = match.group("num")
                num_start = match.start("num")
                num_end = match.end("num")

                # Reject if number falls inside negative context (e.g. building 42, room 204)
                if _is_span_in_negative_context(num_start, num_end, negative_spans):
                    continue

                parsed = parse_number_token(num_str)
                if parsed is None or parsed < 0:
                    continue

                noun = match.group("noun").lower()
                prefix = match.group("prefix")
                mid_adj = match.group("mid_adj")

                q_type, mods, conf = self._assess_quantifier_confidence(prefix, clean_text, match.start(), match.end())
                risk_ctx = mid_adj.strip().lower() if mid_adj else self._extract_nearby_risk_context(clean_text, match.end())

                candidate_counts.append(
                    _CandidateCount(
                        count=parsed,
                        raw_span=match.group(0),
                        noun=noun,
                        risk_context=risk_ctx,
                        quantifier_type=q_type,
                        modifiers=mods,
                        confidence=conf,
                        num_start=num_start,
                        num_end=num_end,
                        span_start=match.start(),
                        span_end=match.end(),
                    )
                )

            # 4.2 Pattern 2: Family of <Number>
            for match in _PATTERN_FAMILY_OF.finditer(clean_text):
                num_str = match.group("num")
                num_start = match.start("num")
                num_end = match.end("num")

                if _is_span_in_negative_context(num_start, num_end, negative_spans):
                    continue

                parsed = parse_number_token(num_str)
                if parsed is None or parsed < 0:
                    continue

                risk_ctx = self._extract_nearby_risk_context(clean_text, match.end())
                candidate_counts.append(
                    _CandidateCount(
                        count=parsed,
                        raw_span=match.group(0),
                        noun="family",
                        risk_context=risk_ctx,
                        quantifier_type="EXPLICIT",
                        modifiers=[],
                        confidence=0.92,
                        num_start=num_start,
                        num_end=num_end,
                        span_start=match.start(),
                        span_end=match.end(),
                    )
                )

            # 4.3 Pattern 3: There are [Prefix] <Number> <Predicate>
            for match in _PATTERN_THERE_ARE.finditer(clean_text):
                num_str = match.group("num")
                num_start = match.start("num")
                num_end = match.end("num")

                if _is_span_in_negative_context(num_start, num_end, negative_spans):
                    continue

                if any(c.span_start <= match.start() and c.span_end >= match.end() for c in candidate_counts):
                    continue

                parsed = parse_number_token(num_str)
                if parsed is None or parsed < 0:
                    continue

                pred = match.group("pred").lower()
                prefix = match.group("prefix")
                q_type, mods, conf = self._assess_quantifier_confidence(prefix, clean_text, match.start(), match.end())

                candidate_counts.append(
                    _CandidateCount(
                        count=parsed,
                        raw_span=match.group(0),
                        noun="people",
                        risk_context=pred,
                        quantifier_type=q_type,
                        modifiers=mods,
                        confidence=conf,
                        num_start=num_start,
                        num_end=num_end,
                        span_start=match.start(),
                        span_end=match.end(),
                    )
                )

            # 4.4 Pattern 4: Explicit Total stated (e.g. 'total of 10 people')
            explicit_total_candidate: _CandidateCount | None = None
            for match in _PATTERN_TOTAL_STATED.finditer(clean_text):
                num_str = match.group("num")
                num_start = match.start("num")
                num_end = match.end("num")

                if _is_span_in_negative_context(num_start, num_end, negative_spans):
                    continue

                parsed = parse_number_token(num_str)
                if parsed is not None and parsed >= 0:
                    explicit_total_candidate = _CandidateCount(
                        count=parsed,
                        raw_span=match.group(0),
                        noun="total",
                        risk_context=self._extract_nearby_risk_context(clean_text, match.end()),
                        quantifier_type="EXPLICIT",
                        modifiers=["explicit_total"],
                        confidence=0.95,
                        num_start=num_start,
                        num_end=num_end,
                        span_start=match.start(),
                        span_end=match.end(),
                    )

            # 4.5 Pattern 5: <Number> <StatusPredicate> (e.g. '2 missing', '5 injured')
            for match in _PATTERN_NUMBER_STATUS.finditer(clean_text):
                num_str = match.group("num")
                num_start = match.start("num")
                num_end = match.end("num")

                if _is_span_in_negative_context(num_start, num_end, negative_spans):
                    continue

                # Ensure this span does not overlap any already-found candidate
                if any(max(c.span_start, match.start()) < min(c.span_end, match.end()) for c in candidate_counts):
                    continue

                parsed = parse_number_token(num_str)
                if parsed is None or parsed < 0:
                    continue

                status = match.group("status").lower()
                prefix = match.group("prefix")
                q_type, mods, conf = self._assess_quantifier_confidence(prefix, clean_text, match.start(), match.end())

                candidate_counts.append(
                    _CandidateCount(
                        count=parsed,
                        raw_span=match.group(0),
                        noun="people",
                        risk_context=status,
                        quantifier_type=q_type,
                        modifiers=mods,
                        confidence=conf,
                        num_start=num_start,
                        num_end=num_end,
                        span_start=match.start(),
                        span_end=match.end(),
                    )
                )

            # Step 5: Count Selection & Aggregation Logic
            final_count: int | None = None
            final_confidence: float | None = None

            # Deduplicate candidates matching identical character spans
            unique_candidates: list[_CandidateCount] = []
            seen_spans: set[tuple[int, int]] = set()
            for cand in candidate_counts:
                key = (cand.span_start, cand.span_end)
                if key not in seen_spans:
                    seen_spans.add(key)
                    unique_candidates.append(cand)

            if not unique_candidates:
                # No numeric count found
                final_count = None
                final_confidence = None
            elif len(unique_candidates) == 1:
                # Exactly one candidate count
                c = unique_candidates[0]
                final_count = c.count
                final_confidence = c.confidence
                evidence_list.append(
                    RiskEvidence(
                        raw_span=c.raw_span,
                        normalized_count=c.count,
                        people_noun=c.noun,
                        risk_context=c.risk_context,
                        quantifier_type=c.quantifier_type,
                        hedges_or_modifiers=c.modifiers,
                        start_char=c.span_start,
                        end_char=c.span_end,
                    )
                )
            else:
                # Multiple candidates present: Determine aggregation vs selection
                if explicit_total_candidate is not None:
                    # Prefer explicitly stated total
                    final_count = explicit_total_candidate.count
                    final_confidence = explicit_total_candidate.confidence
                    evidence_list.append(
                        RiskEvidence(
                            raw_span=explicit_total_candidate.raw_span,
                            normalized_count=final_count,
                            people_noun="total",
                            risk_context=explicit_total_candidate.risk_context,
                            quantifier_type="EXPLICIT",
                            hedges_or_modifiers=["explicit_total"],
                            start_char=explicit_total_candidate.span_start,
                            end_char=explicit_total_candidate.span_end,
                        )
                    )
                else:
                    # Check for Disjoint Demographic Conjunction (e.g. "3 children and 2 adults are trapped")
                    is_disjoint_conjunction = False
                    if len(unique_candidates) == 2:
                        c1, c2 = unique_candidates[0], unique_candidates[1]
                        if _is_disjoint_demographic(c1.noun, c2.noun):
                            in_between = clean_text[c1.span_end : c2.span_start].strip().lower()
                            if in_between in ("and", ",", ", and", "&"):
                                is_disjoint_conjunction = True
                                final_count = c1.count + c2.count
                                final_confidence = round(min(c1.confidence, c2.confidence), 2)
                                evidence_list.append(
                                    RiskEvidence(
                                        raw_span=f"{c1.raw_span} and {c2.raw_span}",
                                        normalized_count=final_count,
                                        people_noun=f"{c1.noun}+{c2.noun}",
                                        risk_context=c2.risk_context or c1.risk_context,
                                        quantifier_type="EXPLICIT",
                                        hedges_or_modifiers=["disjoint_aggregation"],
                                        start_char=c1.span_start,
                                        end_char=c2.span_end,
                                    )
                                )

                    if not is_disjoint_conjunction:
                        # Non-disjoint or status-based counts (e.g. "5 passengers injured and 2 missing")
                        # Do NOT blindly sum! Select maximum defensible count.
                        sorted_by_count = sorted(unique_candidates, key=lambda x: x.count, reverse=True)
                        chosen = sorted_by_count[0]
                        final_count = chosen.count
                        final_confidence = chosen.confidence

                        counts_summary = ", ".join(str(c.count) for c in unique_candidates)
                        warnings.append(
                            f"Multiple non-disjoint people counts detected ({counts_summary}); "
                            f"preserved maximum defensible count {final_count} without blind summation."
                        )

                        for cand in unique_candidates:
                            evidence_list.append(
                                RiskEvidence(
                                    raw_span=cand.raw_span,
                                    normalized_count=cand.count,
                                    people_noun=cand.noun,
                                    risk_context=cand.risk_context,
                                    quantifier_type=cand.quantifier_type,
                                    hedges_or_modifiers=cand.modifiers,
                                    start_char=cand.span_start,
                                    end_char=cand.span_end,
                                )
                            )

            # Step 6: Observability (Privacy-safe structured logging)
            self.logger.info(
                "Extracted people-at-risk analysis",
                extra={
                    "report_id": report_id,
                    "count": final_count,
                    "confidence": final_confidence,
                    "signals_count": len(signals),
                    "evidence_count": len(evidence_list),
                },
            )

            return PeopleRiskResult(
                count=final_count,
                confidence=final_confidence,
                signals=signals,
                evidence=evidence_list,
                warnings=warnings,
                processing_status="SUCCESS",
            )

        except (MLInputError, MLInferenceError):
            raise
        except Exception as exc:
            self.logger.error(
                f"Unexpected error in PeopleRiskExtractor: {type(exc).__name__}: {exc}",
                extra={"report_id": report_id},
            )
            raise MLInferenceError(
                f"People-at-risk extraction failed: {type(exc).__name__}: {exc}",
                details={"report_id": report_id},
            ) from exc

    def _assess_quantifier_confidence(
        self,
        prefix: str | None,
        text: str,
        start_idx: int,
        end_idx: int,
    ) -> tuple[str, list[str], float]:
        """
        Determines quantifier type, modifiers, and deterministic confidence score.
        Differentiates:
        - Direct / Explicit: ~0.92
        - Bound ('at least', 'or more'): ~0.80
        - Approximate ('around', 'about', 'roughly', 'nearly'): ~0.75
        - Hedged / Uncertain ('maybe', 'might be', 'reportedly'): ~0.60
        """
        prefix_clean = prefix.strip().lower() if prefix else ""
        modifiers: list[str] = []

        surrounding_context = text[max(0, start_idx - 25) : min(len(text), end_idx + 25)].lower()

        # Check for hedging / uncertainty
        if any(h in prefix_clean for h in ("maybe", "may be", "might be", "possibly", "perhaps", "believed to be")):
            modifiers.append(prefix_clean)
            return "HEDGED", modifiers, 0.60

        if any(h in surrounding_context for h in ("reportedly", "unconfirmed", "suspected", "allegedly")):
            modifiers.append("reportedly")
            return "HEDGED", modifiers, 0.65

        # Check for bound modifiers
        if "at least" in prefix_clean or "or more" in surrounding_context:
            modifiers.append("at least")
            return "BOUND", modifiers, 0.80

        # Check for approximation modifiers
        if any(a in prefix_clean for a in ("approx", "approximately", "around", "about", "roughly", "nearly", "almost", "close to", "estimated")):
            modifiers.append(prefix_clean)
            return "APPROXIMATE", modifiers, 0.75

        # Direct explicit count
        return "EXPLICIT", modifiers, 0.92

    def _extract_nearby_risk_context(self, text: str, end_idx: int) -> str | None:
        """Finds any risk predicates immediately following the entity mention."""
        window = text[end_idx : min(len(text), end_idx + 35)].lower()
        if re.search(r"\b(?:trapped|stuck|pinned|buried|under\s+rubble|stranded)\b", window):
            return "trapped"
        if re.search(r"\b(?:injured|hurt|wounded|bleeding|burned)\b", window):
            return "injured"
        if re.search(r"\b(?:missing|lost|unaccounted)\b", window):
            return "missing"
        if re.search(r"\b(?:unconscious|passed\s+out|unresponsive)\b", window):
            return "unconscious"
        if re.search(r"\b(?:drowning|underwater|submerged)\b", window):
            return "drowning"
        if re.search(r"\b(?:inside|in\s+the\s+building|in\s+the\s+house)\b", window):
            return "inside"
        return None


def extract_people_at_risk(
    text: str | PreprocessedText,
    report_id: str | None = None,
    config: MLConfig | None = None,
) -> PeopleRiskResult:
    """
    Convenience function for extracting people-at-risk count and qualitative indicators.
    Instantiates a temporary PeopleRiskExtractor with the specified or default configuration.
    """
    extractor = PeopleRiskExtractor(config=config)
    return extractor.extract(text, report_id=report_id)
