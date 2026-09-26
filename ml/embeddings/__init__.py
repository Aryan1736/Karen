"""
Karen's Ear — Dense Semantic Embeddings Subpackage.

Step 3 of the ML pipeline (architecture/ml-pipeline.md Section 3.7).
Responsible for generating 384-dimensional unit-norm dense vector embeddings
(using sentence-transformers/all-MiniLM-L6-v2) to power backend incident
deduplication and corroboration triangulation.
"""

from ml.embeddings.embedder import (
    EmbeddingEngine,
    SentenceTransformerEmbedder,
    compute_similarity,
    embed_report,
    embed_reports,
    is_model_loaded,
    reset_model_cache,
)
from ml.embeddings.evaluator import (
    EmbeddingEvaluationReport,
    EmbeddingEvaluator,
    run_embedding_evaluation,
)

__all__: list[str] = [
    "EmbeddingEngine",
    "EmbeddingEvaluationReport",
    "EmbeddingEvaluator",
    "SentenceTransformerEmbedder",
    "compute_similarity",
    "embed_report",
    "embed_reports",
    "is_model_loaded",
    "reset_model_cache",
    "run_embedding_evaluation",
]
