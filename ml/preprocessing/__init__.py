"""
Karen's Ear — Preprocessing Subpackage.

Step 1 of the ML pipeline (architecture/ml-pipeline.md Section 3.1).
Responsible for text cleaning, unicode normalization (NFKC),
sanitizing control characters/null bytes, while strictly preserving
punctuation and casing signals critical for distress and urgency scoring.
"""

from ml.preprocessing.text_cleaner import (
    PreprocessedText,
    TextCleaner,
    clean_text,
    preprocess_report,
)

__all__: list[str] = [
    "PreprocessedText",
    "TextCleaner",
    "clean_text",
    "preprocess_report",
]
