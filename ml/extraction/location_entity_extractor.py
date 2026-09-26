"""
Karen's Ear — Location & Entity Extractor.

Steps 2C & 2E of the ML pipeline (architecture/ml-pipeline.md Section 3.4 and
gemini.md Section 6.2). Extracts primary incident location text, geographic precision,
and domain named entities (LOCATION, VEHICLE, INFRASTRUCTURE, FACILITY, ROAD,
LANDMARK, PERSON, ORGANIZATION) from emergency dispatch text.

HARD NO-HALLUCINATION ARCHITECTURAL INVARIANT:
- Coordinates (latitude and longitude) MUST ALWAYS remain null unless verified
  from an authoritative, controlled source.
- Feature 5 does NOT perform geocoding.
- NEVER infer or fabricate coordinates from model memory, LLM generation,
  gazetteer entry alone, landmark recognition, or geographic intuition.
- Even for world-famous or regional landmarks ("Rasulgarh flyover", "Patia", "Janpath"),
  latitude = null and longitude = null.

KEY CAPABILITIES:
1. Spatial Syntax & Preposition Parsing:
   - Exact prepositions: "at <LOC>", "inside <LOC>", "intersection of <A> and <B>" -> precision: "exact"
   - Approximate prepositions: "near <LOC>", "around <LOC>", "behind <LOC>", "beside <LOC>",
     "outside <LOC>", "on <ROAD>", "<N> km from <LOC>", "between <A> and <B>",
     "spreading toward <LOC>" -> precision: "approximate"
   - Missing / unlocalized reports: precision: "unknown", location text: null.
2. Domain Taxonomy & Compound Recognition:
   - Detects compound landmarks and facility names ("Rasulgarh flyover", "Baramunda bus stand",
     "Kalinga Hospital", "Cuttack Medical College", "Utkal University", "Master Canteen Road")
     using suffix-driven and gazetteer patterns.
   - Extracts domain entities: LOCATION, VEHICLE, INFRASTRUCTURE, FACILITY, ROAD, LANDMARK,
     PERSON, ORGANIZATION.
3. Multi-Location Preservation:
   - Selects primary origin/incident location deterministically while preserving
     secondary / destination locations in the entities collection.
4. False-Positive Rejection (Negative Contexts):
   - Strictly ignores non-location numbers (room numbers like "Room 204", building numbers
     like "Building 42", floor numbers like "Floor 3", emergency dials like "112" or "911").
   - Ignores hazard state predicates ("on fire", "in flames", "under control").
   - Container vehicle mentions alone without location ("inside a bus") extract VEHICLE
     entity while keeping location text null.
5. Deterministic & Explainable Confidence:
   - Confidence reflects syntax and evidence clarity, bounded in [0.0, 1.0].
   - Location confidence is strictly null when location text is null.
6. Graceful Degradation & Resilience:
   - Supports deterministic rules by default with optional transformer/spaCy NER hybrid hook.
   - Never crashes on malformed inputs or missing models; emits diagnostic warnings.
7. Privacy & Observability:
   - Uses structured JSON logging without dumping unredacted citizen distress text.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Sequence

from ml.config import ComponentResult, MLConfig, get_ml_config
from ml.exceptions import MLInferenceError, MLInputError
from ml.logging_utils import get_ml_logger
from ml.preprocessing.text_cleaner import PreprocessedText, TextCleaner


# ==============================================================================
# Domain Vocabularies & Gazetteers
# ==============================================================================

DEFAULT_VEHICLES: frozenset[str] = frozenset({
    "bus", "buses", "truck", "trucks", "car", "cars", "van", "vans",
    "ambulance", "ambulances", "tanker", "tankers", "motorcycle", "motorcycles",
    "bike", "bikes", "train", "trains", "autorickshaw", "auto", "vehicle", "vehicles",
    "boat", "boats", "scooter", "scooters", "suv", "jeep", "trailer", "tractor",
})

DEFAULT_INFRASTRUCTURE: frozenset[str] = frozenset({
    "bridge", "bridges", "flyover", "flyovers", "tunnel", "tunnels",
    "building", "buildings", "power line", "power lines", "transformer", "transformers",
    "pipeline", "pipelines", "overpass", "underpass", "dam", "dams",
    "substation", "substations", "transmission line", "tower", "sewage line",
})

DEFAULT_FACILITIES: frozenset[str] = frozenset({
    "hospital", "hospitals", "school", "schools", "college", "colleges",
    "shelter", "shelters", "station", "stations", "railway station", "railway stations",
    "bus stand", "bus stands", "bus terminal", "airport", "airports",
    "clinic", "clinics", "market", "markets", "campus", "campuses",
    "godown", "warehouse", "factory", "refinery", "fire station", "police station",
})

DEFAULT_LANDMARKS: frozenset[str] = frozenset({
    "square", "squares", "junction", "junctions", "intersection", "intersections",
    "roundabout", "circle", "crossing", "temple", "temples", "stadium", "stadiums",
    "mall", "malls", "plaza", "monument", "fountain", "park",
})

DEFAULT_ROADS: frozenset[str] = frozenset({
    "road", "roads", "street", "streets", "highway", "highways",
    "expressway", "expressways", "lane", "avenue", "janpath", "nh16", "nh-16",
    "nh5", "nh-5", "nh55", "nh-55", "bypass", "boulevard", "corridor",
})

DEFAULT_LOCAL_NAMES: frozenset[str] = frozenset({
    "rasulgarh", "patia", "khandagiri", "saheed nagar", "master canteen",
    "baramunda", "cuttack", "bhubaneswar", "chandrasekharpur", "mancheswar",
    "vani vihar", "kalinga", "utkal", "puri", "jayadev vihar", "nayapalli",
    "old town", "kalpana", "palasuni", "acharya vihar", "crp square",
})

DEFAULT_ORGANIZATIONS: frozenset[str] = frozenset({
    "police", "fire department", "fire brigade", "fire service",
    "odrf", "ndrf", "red cross", "ems", "traffic police", "municipal corporation",
})

# State predicates that follow "on", "in", "under" but represent conditions, not locations
STATE_PREDICATES: frozenset[str] = frozenset({
    "fire", "flames", "flame", "smoke", "water", "rubble", "collapse",
    "control", "investigation", "progress", "risk", "site", "scene",
    "strike", "protest", "duty", "patrol", "alert", "repair",
})

# Suffixes that indicate compound landmark / facility / infrastructure names
COMPOUND_SUFFIXES: tuple[str, ...] = (
    "flyover", "square", "junction", "intersection", "circle", "crossing",
    "bridge", "underpass", "overpass", "tunnel",
    "railway station", "bus stand", "bus stop", "bus terminal", "airport", "station",
    "hospital", "college", "school", "university", "institute", "clinic",
    "market", "temple", "stadium", "mall", "plaza", "complex", "building",
    "road", "street", "highway", "lane", "avenue", "bypass",
    "industrial area", "industrial estate",
)


@dataclass
class GazetteerConfig:
    """
    Configurable repository of domain vocabulary and local place names.
    Allows dynamic extension without hardcoding extensive dictionaries in extractor logic.
    """

    vehicles: frozenset[str] = DEFAULT_VEHICLES
    infrastructure: frozenset[str] = DEFAULT_INFRASTRUCTURE
    facilities: frozenset[str] = DEFAULT_FACILITIES
    landmarks: frozenset[str] = DEFAULT_LANDMARKS
    roads: frozenset[str] = DEFAULT_ROADS
    local_names: frozenset[str] = DEFAULT_LOCAL_NAMES
    organizations: frozenset[str] = DEFAULT_ORGANIZATIONS

    @classmethod
    def default(cls) -> GazetteerConfig:
        return cls()

    def extend(
        self,
        vehicles: Sequence[str] | None = None,
        infrastructure: Sequence[str] | None = None,
        facilities: Sequence[str] | None = None,
        landmarks: Sequence[str] | None = None,
        roads: Sequence[str] | None = None,
        local_names: Sequence[str] | None = None,
        organizations: Sequence[str] | None = None,
    ) -> GazetteerConfig:
        """Creates an extended gazetteer copy with additional domain vocabulary."""
        return GazetteerConfig(
            vehicles=self.vehicles.union({v.lower() for v in (vehicles or [])}),
            infrastructure=self.infrastructure.union({i.lower() for i in (infrastructure or [])}),
            facilities=self.facilities.union({f.lower() for f in (facilities or [])}),
            landmarks=self.landmarks.union({l.lower() for l in (landmarks or [])}),
            roads=self.roads.union({r.lower() for r in (roads or [])}),
            local_names=self.local_names.union({n.lower() for n in (local_names or [])}),
            organizations=self.organizations.union({o.lower() for o in (organizations or [])}),
        )


# ==============================================================================
# Regex Patterns for Spatial Syntax & Negative Contexts
# ==============================================================================

# Negative context patterns (numbers that must NEVER be extracted as locations)
_NEGATIVE_CONTEXT_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Building numbers: "Building 42", "Bldg 5"
    re.compile(r"\b(?:building|bldg\.?)\s+(?:no\.?\s*)?(\d+|[a-zA-Z0-9-]+)\b", re.IGNORECASE),
    # Room / apartment / floor / bed numbers: "Room 204", "Floor 3"
    re.compile(r"\b(?:room|rm\.?|floor|fl\.?|level|story|storey|apt\.?|apartment|suite|ste\.?|unit|block|blk\.?|door|gate|pillar|pole|bed)\s+(?:no\.?\s*)?(\d+|[a-zA-Z0-9-]+)\b", re.IGNORECASE),
    # Emergency telephone numbers: "Call 112", "Dial 911"
    re.compile(r"\b(?:call|dial|contact|phone|reach)\s+(?:at\s+)?(?:\+?\d[\d\s-]{2,}\d|\d{3,})\b", re.IGNORECASE),
    re.compile(r"\b(?:call|dial)\s+(?:112|911|999|100|101|108|102)\b", re.IGNORECASE),
    # Victim counts: "Five people are trapped", "3 injured"
    re.compile(r"\b\d+\s+(?:people|persons|passengers|victims|civilians|children|adults|individuals|bodies)\b", re.IGNORECASE),
    # Plain time expressions: "at 8:30 pm", "at 10 am"
    re.compile(r"\bat\s+\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)\b", re.IGNORECASE),
)

# Spatial prepositions mapped to canonical precision
_EXACT_PREPOSITIONS: tuple[str, ...] = ("at", "inside", "within")
_APPROXIMATE_PREPOSITIONS: tuple[str, ...] = (
    "near", "around", "somewhere around", "close to", "beside", "behind",
    "outside", "across from", "adjacent to", "opposite", "on",
)


# ==============================================================================
# Typed Structures
# ==============================================================================

@dataclass
class LocationPrediction:
    """
    Tactical location object strictly matching ml/schemas/incident_output.json.
    Coordinates are ALWAYS null in Feature 5 (Hard No-Hallucination Invariant).
    """

    text: str | None
    latitude: float | None = None
    longitude: float | None = None
    precision: str = "unknown"  # "exact", "approximate", "unknown"
    confidence: float | None = None

    def to_canonical_dict(self) -> dict[str, Any]:
        """Converts to dictionary adhering strictly to canonical schema."""
        return {
            "text": self.text,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "precision": self.precision,
            "confidence": self.confidence,
        }


@dataclass
class EntityMention:
    """
    Extracted named entity token strictly matching ml/schemas/incident_output.json.
    """

    text: str
    type: str  # LOCATION, VEHICLE, INFRASTRUCTURE, FACILITY, ROAD, LANDMARK, PERSON, ORGANIZATION
    confidence: float | None = None
    start_char: int = -1
    end_char: int = -1

    def to_canonical_dict(self) -> dict[str, Any]:
        """Converts to dictionary adhering strictly to canonical schema."""
        return {
            "text": self.text,
            "type": self.type,
            "confidence": self.confidence,
        }


@dataclass
class LocationEntityResult:
    """
    Standardized result emitted by LocationEntityExtractor.
    """

    location: LocationPrediction
    entities: list[EntityMention] = field(default_factory=list)
    secondary_locations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    processing_status: str = "SUCCESS"  # SUCCESS, PARTIAL, NEEDS_REVIEW, FAILED

    def to_canonical_dict(self) -> dict[str, Any]:
        """
        Converts to canonical dictionary fragment matching ml/schemas/incident_output.json.
        """
        return {
            "location": self.location.to_canonical_dict(),
            "entities": [ent.to_canonical_dict() for ent in self.entities],
        }

    def to_component_result(self) -> ComponentResult:
        """Converts into a standardized internal ComponentResult."""
        return ComponentResult(
            component="location_and_entities",
            status=self.processing_status,
            data={
                "location": self.location.to_canonical_dict(),
                "entities": [ent.to_canonical_dict() for ent in self.entities],
                "secondary_locations": list(self.secondary_locations),
            },
            confidence=self.location.confidence,
            warnings=list(self.warnings),
        )


# ==============================================================================
# Helper Utilities
# ==============================================================================

def _clean_location_span(span: str) -> str:
    """Cleans leading articles, trailing punctuation, and extra whitespace."""
    s = span.strip()
    s = re.sub(r"^(?:the|a|an)\s+", "", s, flags=re.IGNORECASE)
    s = re.sub(r"[\.,;:!\?]+$", "", s).strip()
    return s


def _is_span_overlapping(start: int, end: int, spans: Sequence[tuple[int, int]]) -> bool:
    """Checks if interval [start, end] intersects any interval in spans."""
    for s, e in spans:
        if max(start, s) < min(end, e):
            return True
    return False


# ==============================================================================
# Main Location & Entity Extractor Class
# ==============================================================================

class LocationEntityExtractor:
    """
    Deterministic & Hybrid Extractor for emergency incident locations and entities.
    Executes Step 2C of the ML Pipeline.
    """

    def __init__(
        self,
        config: MLConfig | None = None,
        gazetteer: GazetteerConfig | None = None,
        text_cleaner: TextCleaner | None = None,
    ) -> None:
        self.config = config or get_ml_config()
        self.gazetteer = gazetteer or GazetteerConfig.default()
        self.text_cleaner = text_cleaner or TextCleaner(config=self.config)
        self.logger = get_ml_logger(
            name="karen.ml.extraction.location",
            component="location_and_entities",
            model_version=self.config.model_version,
        )

        # Optional NER backend pipeline (lazy-loaded if configured)
        self._ner_pipeline: Any = None
        self._ner_loaded: bool = False

    def _get_ner_pipeline(self) -> Any:
        """
        Lazily loads optional transformer token classification pipeline if configured.
        Safe against import or missing weight errors.
        """
        if self._ner_loaded:
            return self._ner_pipeline

        self._ner_loaded = True
        ner_model = self.config.ner_model_name

        if not ner_model:
            return None

        try:
            from transformers import pipeline  # type: ignore

            self.logger.info(f"Loading optional NER model: {ner_model}")
            self._ner_pipeline = pipeline(
                "ner",
                model=ner_model,
                aggregation_strategy="simple",
                device=self.config.device,
            )
            return self._ner_pipeline
        except Exception as exc:
            self.logger.warning(
                f"Failed to load optional NER model '{ner_model}': {exc}. "
                "Falling back to deterministic extraction.",
            )
            self._ner_pipeline = None
            return None

    def extract(
        self,
        text: str | PreprocessedText,
        report_id: str | None = None,
    ) -> LocationEntityResult:
        """
        Extracts primary location and named entities from emergency dispatch text.

        Args:
            text: Raw string or PreprocessedText from TextCleaner.
            report_id: Optional tracking identifier for observability.

        Returns:
            LocationEntityResult containing canonical location and entities.
        """
        start_time = time.perf_counter()
        warnings: list[str] = []

        # Step 1: Input Preprocessing & Validation
        try:
            if isinstance(text, PreprocessedText):
                preprocessed = text
            else:
                preprocessed = self.text_cleaner.clean(text)

            clean_text = preprocessed.normalized_text
        except MLInputError as exc:
            self.logger.warning(
                f"Input validation error in LocationEntityExtractor: {exc.message}",
                extra={"report_id": report_id},
            )
            return LocationEntityResult(
                location=LocationPrediction(text=None, precision="unknown", confidence=None),
                entities=[],
                warnings=[f"Input error: {exc.message}"],
                processing_status="PARTIAL",
            )
        except Exception as exc:
            self.logger.error(
                f"Unexpected preprocessing failure: {exc}",
                extra={"report_id": report_id},
            )
            return LocationEntityResult(
                location=LocationPrediction(text=None, precision="unknown", confidence=None),
                entities=[],
                warnings=[f"Preprocessing failure: {exc}"],
                processing_status="PARTIAL",
            )

        if not clean_text:
            return LocationEntityResult(
                location=LocationPrediction(text=None, precision="unknown", confidence=None),
                entities=[],
                warnings=["Empty input report text."],
                processing_status="PARTIAL",
            )

        try:
            # Step 2: Identify Negative Spans (Room, building, dial numbers, victim counts)
            negative_spans: list[tuple[int, int]] = []
            for pat in _NEGATIVE_CONTEXT_PATTERNS:
                for match in pat.finditer(clean_text):
                    negative_spans.append((match.start(), match.end()))

            # Step 3: Named Entity Extraction
            extracted_entities: list[EntityMention] = []
            seen_entity_spans: list[tuple[int, int]] = []

            # 3.1 Compound proper-noun + suffix matching (e.g. "Rasulgarh flyover", "Kalinga Hospital")
            extracted_compounds = self._extract_compound_entities(clean_text, negative_spans)
            for comp in extracted_compounds:
                span = (comp.start_char, comp.end_char)
                if not _is_span_overlapping(span[0], span[1], seen_entity_spans):
                    seen_entity_spans.append(span)
                    extracted_entities.append(comp)

            # 3.2 Specific multi-word road and infrastructure entities (e.g. "Master Canteen Road", "NH16")
            specific_roads = self._extract_specific_road_entities(clean_text, negative_spans)
            for road in specific_roads:
                span = (road.start_char, road.end_char)
                if not _is_span_overlapping(span[0], span[1], seen_entity_spans):
                    seen_entity_spans.append(span)
                    extracted_entities.append(road)

            # 3.3 Domain vocabulary scanning (VEHICLES, INFRASTRUCTURE, FACILITIES, LANDMARKS, ROADS, LOCAL_NAMES)
            vocab_entities = self._extract_vocabulary_entities(clean_text, negative_spans, seen_entity_spans)
            for ent in vocab_entities:
                span = (ent.start_char, ent.end_char)
                if not _is_span_overlapping(span[0], span[1], seen_entity_spans):
                    seen_entity_spans.append(span)
                    extracted_entities.append(ent)

            # 3.4 Optional NER pipeline enrichment (if configured)
            ner_pipe = self._get_ner_pipeline()
            if ner_pipe:
                ner_entities = self._enrich_with_ner(clean_text, ner_pipe, negative_spans, seen_entity_spans)
                for ent in ner_entities:
                    span = (ent.start_char, ent.end_char)
                    if not _is_span_overlapping(span[0], span[1], seen_entity_spans):
                        seen_entity_spans.append(span)
                        extracted_entities.append(ent)

            # Step 4: Primary Incident Location Extraction & Precision Inference
            primary_loc, precision, confidence, secondaries = self._extract_primary_location(
                clean_text=clean_text,
                extracted_entities=extracted_entities,
                negative_spans=negative_spans,
            )

            # Deduplicate entity list by text and type
            deduped_entities: list[EntityMention] = []
            seen_tuples: set[tuple[str, str]] = set()
            for ent in extracted_entities:
                key = (ent.text.lower(), ent.type)
                if key not in seen_tuples:
                    seen_tuples.add(key)
                    deduped_entities.append(ent)

            # Sort entities by appearance in text
            deduped_entities.sort(key=lambda e: (e.start_char if e.start_char >= 0 else 9999))

            # HARD INVARIANT: Coordinates must remain null
            location_pred = LocationPrediction(
                text=primary_loc,
                latitude=None,
                longitude=None,
                precision=precision,
                confidence=confidence,
            )

            # Step 5: Observability
            latency_ms = (time.perf_counter() - start_time) * 1000
            self.logger.info(
                "Extracted location and entities",
                extra={
                    "report_id": report_id,
                    "location_extracted": primary_loc is not None,
                    "precision": precision,
                    "confidence": confidence,
                    "entity_count": len(deduped_entities),
                    "latency_ms": round(latency_ms, 2),
                },
            )

            return LocationEntityResult(
                location=location_pred,
                entities=deduped_entities,
                secondary_locations=secondaries,
                warnings=warnings,
                processing_status="SUCCESS",
            )

        except (MLInputError, MLInferenceError):
            raise
        except Exception as exc:
            self.logger.error(
                f"Unexpected failure in LocationEntityExtractor: {type(exc).__name__}: {exc}",
                extra={"report_id": report_id},
            )
            raise MLInferenceError(
                f"Location and entity extraction failed: {type(exc).__name__}: {exc}",
                details={"report_id": report_id},
            ) from exc

    # ==========================================================================
    # Entity Extraction Subroutines
    # ==========================================================================

    def _extract_compound_entities(
        self,
        text: str,
        negative_spans: Sequence[tuple[int, int]],
    ) -> list[EntityMention]:
        """
        Extracts compound proper nouns and facility/infrastructure phrases.
        Example: 'Rasulgarh flyover', 'Kalinga Hospital', 'Cuttack Medical College',
        'railway station', 'Baramunda bus stand'.
        """
        compounds: list[EntityMention] = []
        boundary_words = frozenset({
            "the", "a", "an", "this", "that", "these", "those",
            "near", "at", "in", "on", "behind", "beside", "outside", "inside",
            "from", "to", "toward", "towards", "between", "under", "over", "across",
            "and", "or", "of", "with", "by", "for", "about",
            "is", "was", "are", "were", "has", "had", "have",
            "reported", "coming", "trapped", "injured", "blocked", "crashed",
            "hit", "overturned", "caught", "burst", "snapped", "fell", "derailed",
            "into", "onto",
        })

        # Sorted by length descending so longer suffixes match first
        sorted_suffixes = sorted(COMPOUND_SUFFIXES, key=len, reverse=True)
        seen_spans: list[tuple[int, int]] = []

        for suffix in sorted_suffixes:
            # Pattern: up to 3 words before suffix, or suffix standalone
            pattern = re.compile(
                rf"\b([A-Za-z0-9\-]+(?:\s+[A-Za-z0-9\-]+){{0,2}}\s+)?{re.escape(suffix)}\b",
                re.IGNORECASE,
            )
            for match in pattern.finditer(text):
                raw_prefix = match.group(1) or ""
                prefix_tokens = raw_prefix.strip().split()

                valid_prefix_tokens: list[str] = []
                for tok in reversed(prefix_tokens):
                    tok_lower = tok.lower()
                    if tok_lower in boundary_words or tok_lower in self.gazetteer.vehicles or tok_lower in ("transformer", "power"):
                        break
                    valid_prefix_tokens.insert(0, tok)

                if valid_prefix_tokens:
                    target_text = f"{' '.join(valid_prefix_tokens)} {suffix}"
                else:
                    # Suffix standalone
                    target_text = suffix

                # Find exact match position in the matched span
                match_text = match.group(0)
                idx = match_text.lower().rfind(target_text.lower())
                if idx < 0:
                    continue

                start = match.start() + idx
                end = start + len(target_text)

                if _is_span_overlapping(start, end, negative_spans):
                    continue
                if _is_span_overlapping(start, end, seen_spans):
                    continue

                # Determine entity type based on suffix
                suffix_lower = suffix.lower()
                if suffix_lower == "flyover":
                    etype = "LOCATION"
                elif suffix_lower in ("bridge", "underpass", "overpass", "tunnel", "building"):
                    etype = "INFRASTRUCTURE"
                elif suffix_lower in (
                    "hospital", "college", "school", "university", "institute", "clinic",
                    "railway station", "bus stand", "bus stop", "bus terminal", "airport", "station",
                ):
                    etype = "FACILITY"
                elif suffix_lower in ("square", "junction", "intersection", "circle", "crossing", "temple", "stadium", "mall", "plaza"):
                    etype = "LANDMARK"
                elif suffix_lower in ("road", "street", "highway", "lane", "avenue", "bypass"):
                    etype = "ROAD"
                elif suffix_lower in ("industrial area", "industrial estate"):
                    etype = "LOCATION"
                else:
                    etype = "LOCATION"

                seen_spans.append((start, end))
                compounds.append(
                    EntityMention(
                        text=target_text,
                        type=etype,
                        confidence=0.90 if valid_prefix_tokens else 0.85,
                        start_char=start,
                        end_char=end,
                    )
                )
        return compounds

    def _extract_specific_road_entities(
        self,
        text: str,
        negative_spans: Sequence[tuple[int, int]],
    ) -> list[EntityMention]:
        """Extracts specific highway and roadway designations (e.g. NH16, NH-55, Janpath)."""
        roads: list[EntityMention] = []

        # Highway patterns: NH16, NH-16, SH10, National Highway 16
        hw_pattern = re.compile(
            r"\b(?:NH-?\s*\d+|SH-?\s*\d+|National\s+Highway\s+\d+|State\s+Highway\s+\d+)\b",
            re.IGNORECASE,
        )
        for match in hw_pattern.finditer(text):
            start, end = match.start(), match.end()
            if not _is_span_overlapping(start, end, negative_spans):
                roads.append(
                    EntityMention(
                        text=match.group(0),
                        type="ROAD",
                        confidence=0.95,
                        start_char=start,
                        end_char=end,
                    )
                )

        # Named roads: Janpath, Master Canteen Road
        for r_name in ("janpath", "master canteen road", "ring road", "cuttack road", "puri road"):
            pattern = re.compile(rf"\b{re.escape(r_name)}\b", re.IGNORECASE)
            for match in pattern.finditer(text):
                start, end = match.start(), match.end()
                if not _is_span_overlapping(start, end, negative_spans):
                    roads.append(
                        EntityMention(
                            text=match.group(0),
                            type="ROAD",
                            confidence=0.92,
                            start_char=start,
                            end_char=end,
                        )
                    )

        return roads

    def _extract_vocabulary_entities(
        self,
        text: str,
        negative_spans: Sequence[tuple[int, int]],
        seen_spans: Sequence[tuple[int, int]],
    ) -> list[EntityMention]:
        """Extracts individual vocabulary tokens for vehicles, facilities, infrastructure, landmarks."""
        entities: list[EntityMention] = []

        # Multi-word gazetteer items first
        multi_words = [
            ("railway station", "FACILITY"),
            ("bus stand", "FACILITY"),
            ("bus terminal", "FACILITY"),
            ("power line", "INFRASTRUCTURE"),
            ("transmission line", "INFRASTRUCTURE"),
            ("saheed nagar", "LOCATION"),
            ("master canteen", "LOCATION"),
            ("vani vihar", "LOCATION"),
            ("jayadev vihar", "LOCATION"),
            ("acharya vihar", "LOCATION"),
            ("old town", "LOCATION"),
            ("fire department", "ORGANIZATION"),
            ("traffic police", "ORGANIZATION"),
        ]

        for term, etype in multi_words:
            pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
            for match in pattern.finditer(text):
                start, end = match.start(), match.end()
                if not _is_span_overlapping(start, end, negative_spans) and not _is_span_overlapping(start, end, seen_spans):
                    entities.append(
                        EntityMention(
                            text=match.group(0),
                            type=etype,
                            confidence=0.90,
                            start_char=start,
                            end_char=end,
                        )
                    )

        # Single word token scan
        token_pattern = re.compile(r"\b[A-Za-z0-9\-]+\b")
        for match in token_pattern.finditer(text):
            start, end = match.start(), match.end()
            if _is_span_overlapping(start, end, negative_spans) or _is_span_overlapping(start, end, seen_spans):
                continue

            word = match.group(0).lower()

            etype: str | None = None
            conf: float = 0.85

            if word in self.gazetteer.vehicles:
                etype = "VEHICLE"
            elif word in self.gazetteer.infrastructure:
                etype = "INFRASTRUCTURE"
            elif word in self.gazetteer.facilities:
                etype = "FACILITY"
            elif word in self.gazetteer.landmarks:
                etype = "LANDMARK"
            elif word in self.gazetteer.roads:
                etype = "ROAD"
            elif word in self.gazetteer.local_names:
                etype = "LOCATION"
            elif word in self.gazetteer.organizations:
                etype = "ORGANIZATION"

            if etype:
                entities.append(
                    EntityMention(
                        text=match.group(0),
                        type=etype,
                        confidence=conf,
                        start_char=start,
                        end_char=end,
                    )
                )

        return entities

    def _enrich_with_ner(
        self,
        text: str,
        pipeline: Any,
        negative_spans: Sequence[tuple[int, int]],
        seen_spans: Sequence[tuple[int, int]],
    ) -> list[EntityMention]:
        """Runs optional pretrained NER model to detect named persons, orgs, and locations."""
        entities: list[EntityMention] = []
        try:
            preds = pipeline(text)
            for pred in preds:
                start = pred.get("start", -1)
                end = pred.get("end", -1)
                if start < 0 or end < 0 or _is_span_overlapping(start, end, negative_spans):
                    continue
                if _is_span_overlapping(start, end, seen_spans):
                    continue

                group = pred.get("entity_group", "")
                word = pred.get("word", "").strip()
                score = round(float(pred.get("score", 0.70)), 2)

                # Skip sub-word artifacts or pure numbers
                if word.startswith("##") or word.isdigit() or len(word) < 2:
                    continue

                etype: str | None = None
                if group == "LOC":
                    etype = "LOCATION"
                elif group == "PER":
                    # Reject known vehicle nouns that CoNLL NER mistakenly calls PER (e.g. "Van")
                    if word.lower() in self.gazetteer.vehicles:
                        etype = "VEHICLE"
                    else:
                        etype = "PERSON"
                elif group == "ORG":
                    etype = "ORGANIZATION"

                if etype:
                    entities.append(
                        EntityMention(
                            text=word,
                            type=etype,
                            confidence=min(1.0, max(0.0, score)),
                            start_char=start,
                            end_char=end,
                        )
                    )
        except Exception as exc:
            self.logger.warning(f"Error during optional NER inference: {exc}")

        return entities

    # ==========================================================================
    # Primary Location Extraction Logic
    # ==========================================================================

    def _extract_primary_location(
        self,
        clean_text: str,
        extracted_entities: Sequence[EntityMention],
        negative_spans: Sequence[tuple[int, int]],
    ) -> tuple[str | None, str, float | None, list[str]]:
        """
        Determines the primary incident location, precision, and secondary locations.
        """
        primary_location: str | None = None
        precision: str = "unknown"
        confidence: float | None = None
        secondaries: list[str] = []

        def _is_neg(start: int, end: int) -> bool:
            return _is_span_overlapping(start, end, negative_spans)

        # 1. Intersection pattern: "intersection of <A> and <B>"
        inter_match = re.search(
            r"\b(?:at\s+the\s+)?intersection\s+of\s+([A-Za-z0-9\s]+?)\s+and\s+([A-Za-z0-9\s]+?)(?=[,\.]|\s+(?:is|was|are|blocking)|$)",
            clean_text,
            re.IGNORECASE,
        )
        if inter_match and not _is_neg(inter_match.start(), inter_match.end()):
            road1 = _clean_location_span(inter_match.group(1))
            road2 = _clean_location_span(inter_match.group(2))
            primary_location = f"intersection of {road1} and {road2}"
            precision = "exact"
            confidence = 0.92

        # 2. Highway / Road + Area combo: "on NH16 near Patia"
        if not primary_location:
            combo_match = re.search(
                r"\bon\s+(?:the\s+)?([A-Za-z0-9\-]+)\s+near\s+(?:the\s+)?([A-Za-z0-9\s\-]+?)(?=[,\.]|\s+(?:is|was|are)|$)",
                clean_text,
                re.IGNORECASE,
            )
            if combo_match and not _is_neg(combo_match.start(), combo_match.end()):
                road = combo_match.group(1)
                area = _clean_location_span(combo_match.group(2))
                primary_location = f"{road} near {area}"
                precision = "approximate"
                confidence = 0.89

        # 3. Distance offset: "<N> km from <TARGET>"
        if not primary_location:
            dist_match = re.search(
                r"\b(\d+(?:\.\d+)?\s*(?:km|kilometers?|kilometres?|miles?))\s+from\s+(?:the\s+)?([A-Za-z0-9\s\-]+?)(?=[,\.]|\s+(?:is|was|are)|$)",
                clean_text,
                re.IGNORECASE,
            )
            if dist_match and not _is_neg(dist_match.start(), dist_match.end()):
                dist_str = dist_match.group(1)
                landmark = _clean_location_span(dist_match.group(2))
                primary_location = f"{dist_str} from {landmark}"
                precision = "approximate"
                confidence = 0.88

        # 4. Between two locations: "between <A> and <B>"
        if not primary_location:
            betw_match = re.search(
                r"\bbetween\s+([A-Za-z0-9\s]+?)\s+and\s+([A-Za-z0-9\s]+?)(?=[,\.]|\s+(?:is|was|are)|$)",
                clean_text,
                re.IGNORECASE,
            )
            if betw_match and not _is_neg(betw_match.start(), betw_match.end()):
                loc1 = _clean_location_span(betw_match.group(1))
                loc2 = _clean_location_span(betw_match.group(2))
                primary_location = f"between {loc1} and {loc2}"
                precision = "approximate"
                confidence = 0.88
                secondaries.extend([loc1, loc2])

        # 5. Multi-location origin + spread: "Fire started near Patia and spread toward Rasulgarh"
        if not primary_location:
            spread_match = re.search(
                r"\b(?:near|at)\s+(?:the\s+)?([A-Za-z0-9\s\-]+?)\s+(?:and\s+spread|spreading|heading)\s+toward(?:s)?\s+(?:the\s+)?([A-Za-z0-9\s\-]+?)(?=[,\.]|$)",
                clean_text,
                re.IGNORECASE,
            )
            if spread_match and not _is_neg(spread_match.start(), spread_match.end()):
                origin = _clean_location_span(spread_match.group(1))
                dest = _clean_location_span(spread_match.group(2))
                primary_location = origin
                precision = "approximate"
                confidence = 0.88
                secondaries.append(dest)

        # 6. Prepositional phrases: "near <LOC>", "at <LOC>", "inside <LOC>", "behind <LOC>", "beside <LOC>", "outside <LOC>"
        if not primary_location:
            prep_rules = [
                # Exact markers
                (
                    re.compile(
                        r"\b(?:inside|within)\s+(?:the\s+)?([A-Za-z0-9\s\-]+?)(?=[,\.]|\s+(?:and\s+spread|spreading|is|was|are|with)|$)",
                        re.IGNORECASE,
                    ),
                    "exact",
                    0.90,
                ),
                (
                    re.compile(
                        r"\bat\s+(?:the\s+)?([A-Za-z0-9\s\-]+?)(?=[,\.]|\s+(?:and\s+spread|spreading|is|was|are|with)|$)",
                        re.IGNORECASE,
                    ),
                    "exact",
                    0.90,
                ),
                # Approximate markers
                (
                    re.compile(
                        r"\b(?:near|around|somewhere\s+around|close\s+to|beside|behind|outside|across\s+from)\s+(?:the\s+)?([A-Za-z0-9\s\-]+?)(?=[,\.]|\s+(?:and\s+spread|spreading|is|was|are|with)|$)",
                        re.IGNORECASE,
                    ),
                    "approximate",
                    0.87,
                ),
                (
                    re.compile(
                        r"\b(?:on)\s+(?:the\s+)?([A-Za-z0-9\s\-]+?)(?=[,\.]|\s+(?:near|at|is|was|are)|$)",
                        re.IGNORECASE,
                    ),
                    "approximate",
                    0.82,
                ),
            ]

            for pat, prec, conf in prep_rules:
                match = pat.search(clean_text)
                if match and not _is_neg(match.start(1), match.end(1)):
                    candidate = _clean_location_span(match.group(1))
                    candidate_lower = candidate.lower()

                    # Guard A: reject hazard state predicates ("fire", "flames", "control")
                    if candidate_lower in STATE_PREDICATES:
                        continue

                    # Guard B: container vehicle mentions (e.g. "inside a bus")
                    # If candidate is purely a vehicle, search for subsequent geographic phrase (e.g. "near Rasulgarh flyover")
                    if candidate_lower in self.gazetteer.vehicles or candidate_lower in ("a bus", "a car", "a van", "a truck"):
                        remainder = clean_text[match.end():]
                        near_m = re.search(r"\bnear\s+(?:the\s+)?([A-Za-z0-9\s\-]+?)(?=[,\.]|\s+(?:is|was|are)|$)", remainder, re.IGNORECASE)
                        if near_m:
                            target = _clean_location_span(near_m.group(1))
                            if target.lower() not in STATE_PREDICATES and target.lower() not in self.gazetteer.vehicles:
                                primary_location = target
                                precision = "approximate"
                                confidence = 0.87
                                break
                        continue

                    # Guard C: reject pure numeric tokens
                    if re.match(r"^\d+$", candidate):
                        continue

                    # Guard D: nested "near" inside candidate ("roof near Baramunda bus stand")
                    if "near " in candidate_lower:
                        parts = re.split(r"\bnear\s+", candidate, flags=re.IGNORECASE)
                        if len(parts) > 1:
                            candidate = _clean_location_span(parts[-1])
                            prec = "approximate"

                    primary_location = candidate
                    precision = prec
                    confidence = conf
                    break

        # 7. Unprepositioned entity fallback: check if report contains a recognized location or landmark mention
        if not primary_location:
            for ent in extracted_entities:
                if ent.type in ("LOCATION", "LANDMARK", "FACILITY", "ROAD") and not _is_neg(ent.start_char, ent.end_char):
                    # Exclude generic words without modifiers ("building", "station")
                    if ent.text.lower() not in ("building", "station", "road", "street", "market"):
                        primary_location = ent.text
                        precision = "approximate"
                        confidence = 0.78
                        break

        # 8. Clean up secondary locations if multiple exist
        if primary_location:
            for ent in extracted_entities:
                if ent.type in ("LOCATION", "LANDMARK", "ROAD"):
                    if ent.text.lower() not in primary_location.lower() and primary_location.lower() not in ent.text.lower():
                        if ent.text not in secondaries:
                            secondaries.append(ent.text)

        return primary_location, precision, confidence, secondaries


# ==============================================================================
# Public API Convenience Function
# ==============================================================================

def extract_location_and_entities(
    text: str | PreprocessedText,
    report_id: str | None = None,
    config: MLConfig | None = None,
    gazetteer: GazetteerConfig | None = None,
) -> LocationEntityResult:
    """
    Convenience function for extracting location and named entities from an emergency dispatch.
    Instantiates a LocationEntityExtractor with the specified configuration.
    """
    extractor = LocationEntityExtractor(config=config, gazetteer=gazetteer)
    return extractor.extract(text, report_id=report_id)
