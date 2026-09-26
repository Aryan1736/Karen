"""
Karen's Ear — Required Response Mapping Subpackage.

Step 2E of the ML pipeline (architecture/ml-pipeline.md Section 3.6 and gemini.md Section 6.2).
Responsible for multi-label identification of needed emergency responder units:
- SEARCH_AND_RESCUE
- MEDICAL_EMS
- FIRE_HAZMAT
- POLICE_SECURITY
- PUBLIC_WORKS_UTILITY
"""

from ml.config import CANONICAL_RESPONSE_TYPES
from ml.response.evaluator import (
    CategoryMetrics,
    MultiLabelEvaluationReport,
    ResponseEvaluator,
)
from ml.response.response_extractor import (
    RequiredResponseExtractor,
    ResponseEvidence,
    ResponseExtractionResult,
    ResponseExtractor,
    ResponseNeed,
    extract_required_response,
)
from ml.response.taxonomy import (
    RESPONSE_TAXONOMY_CATALOG,
    ResponseCategoryDefinition,
    get_response_definition,
    is_canonical_response_type,
)

__all__ = [
    "CANONICAL_RESPONSE_TYPES",
    "CategoryMetrics",
    "MultiLabelEvaluationReport",
    "RequiredResponseExtractor",
    "ResponseCategoryDefinition",
    "ResponseEvaluator",
    "ResponseEvidence",
    "ResponseExtractionResult",
    "ResponseExtractor",
    "ResponseNeed",
    "RESPONSE_TAXONOMY_CATALOG",
    "extract_required_response",
    "get_response_definition",
    "is_canonical_response_type",
]
