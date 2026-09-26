"""
Karen's Ear — Emergency Report Text Preprocessor & Normalizer.

Step 1 of the ML pipeline (architecture/ml-pipeline.md Section 3.1).
Provides a deterministic, safe preprocessing component that converts raw
emergency-report text into normalized text for downstream ML components.

Core Guarantees:
1. Determinism: Same input + config always produces identical output. Zero randomness, zero external APIs.
2. Signal Preservation: Never destroys emergency signals (HELP, FIRE, SOS, numbers, casing, punctuation).
3. Safe Sanitization: Strips unsafe scripts, styles, HTML markup, control characters, null bytes without word concatenation.
4. Unicode Normalization: Canonical NFKC decomposition and composition.
5. Contractual Length Enforcement: Validates min/max length against MLConfig, recording deterministic truncation if required.
6. Traceability: Original raw_text is strictly preserved alongside normalized_text.
7. Privacy: Never logs full raw report text; only emits safe structural metadata.
"""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass, field

from ml.config import ComponentResult, MLConfig, get_ml_config
from ml.exceptions import MLInferenceError, MLInputError
from ml.logging_utils import get_ml_logger

# Regular expression to match script and style tags including their contents (unrolled loop, linear runtime)
_SCRIPT_STYLE_RE = re.compile(
    r"<(script|style)\b[^>]*>[^<]*(?:<(?!/\1>)[^<]*)*</\1>",
    flags=re.IGNORECASE,
)
_UNCLOSED_SCRIPT_STYLE_RE = re.compile(
    r"<(script|style)\b[^>]*>[^<]*(?:<(?!/\1>)[^<]*)*$",
    flags=re.IGNORECASE,
)
# Regular expression to match HTML comments (unrolled loop, linear runtime)
_HTML_COMMENT_RE = re.compile(r"<!--[^-]*(?:-(?!->)[^-]*)*-->")

# Regular expression to match general HTML tags without backtracking
_HTML_TAG_RE = re.compile(r"</?[a-zA-Z][a-zA-Z0-9:-]*\b[^>]*>")

# Regular expression for consecutive whitespace
_WHITESPACE_RE = re.compile(r"\s+")

# Regular expression for whitespace before closing punctuation (!, ?, ., ,, :, ;)
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([!?,.:;])")


@dataclass
class PreprocessedText:
    """
    Lightweight typed result emitted by the ML text preprocessing component.
    Adheres to Step 1 of the ML pipeline (architecture/ml-pipeline.md Section 3.1).
    """

    raw_text: str
    normalized_text: str
    is_modified: bool
    is_truncated: bool
    processing_status: str = "SUCCESS"
    warnings: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        """Convenience alias for normalized_text."""
        return self.normalized_text

    def to_component_result(self) -> ComponentResult:
        """Converts to a standardized internal ComponentResult."""
        return ComponentResult(
            component="preprocessing",
            status=self.processing_status,
            data={
                "normalized_text": self.normalized_text,
                "is_modified": self.is_modified,
                "is_truncated": self.is_truncated,
            },
            warnings=list(self.warnings),
        )

    def __str__(self) -> str:
        return self.normalized_text

    def __len__(self) -> int:
        return len(self.normalized_text)


class TextCleaner:
    """
    Deterministic, safety-preserving preprocessor for emergency dispatches.
    Converts raw report text into normalized text for downstream ML components.
    """

    def __init__(self, config: MLConfig | None = None) -> None:
        self.config = config or get_ml_config()
        self.logger = get_ml_logger(
            name="karen.ml.preprocessing",
            component="preprocessing",
        )

    def clean(
        self,
        text: str,
        report_id: str | None = None,
        truncate: bool = True,
    ) -> PreprocessedText:
        """
        Executes the deterministic preprocessing pipeline on raw report text.

        Pipeline stages:
          1. Input validation (type check, empty/whitespace check)
          2. Unicode normalization (NFKC)
          3. Markup neutralization & control-character removal (with word boundary preservation)
          4. Whitespace normalization
          5. Meaningful punctuation & signal preservation
          6. Length validation & contractual truncation
          7. Output packaging into PreprocessedText

        Args:
            text: Raw emergency report string.
            report_id: Optional identifier for logging and tracing.
            truncate: If True, deterministically truncates text exceeding max_report_text_length
                      and records a warning. If False, raises MLInputError on excess length.

        Returns:
            PreprocessedText container with raw and normalized text, change flags, and warnings.

        Raises:
            MLInputError: If input is not a string, is empty/whitespace-only, or violates length constraints.
            MLInferenceError: If an unexpected error occurs during preprocessing execution.
        """
        # ----------------------------------------------------------------------
        # Stage 1: Input Validation
        # ----------------------------------------------------------------------
        if not isinstance(text, str):
            raise MLInputError(
                f"Input report text must be a string, received {type(text).__name__}",
                details={"type": type(text).__name__},
            )

        if not text or not text.strip():
            raise MLInputError(
                "Report text cannot be empty or whitespace-only",
                details={"length": len(text)},
            )

        raw_text = text

        try:
            # ------------------------------------------------------------------
            # Stage 2: Unicode Normalization (NFKC)
            # ------------------------------------------------------------------
            cleaned = unicodedata.normalize("NFKC", text)

            # ------------------------------------------------------------------
            # Stage 3: Unsafe Markup Neutralization
            # ------------------------------------------------------------------
            # Remove scripts and styles completely (including embedded executable code)
            cleaned = _SCRIPT_STYLE_RE.sub(" ", cleaned)
            cleaned = _UNCLOSED_SCRIPT_STYLE_RE.sub(" ", cleaned)
            # Remove HTML comments
            cleaned = _HTML_COMMENT_RE.sub(" ", cleaned)
            # Replace HTML tags with space to prevent accidental word concatenation
            cleaned = _HTML_TAG_RE.sub(" ", cleaned)
            # Unescape standard HTML entities (e.g., &amp; -> &, &quot; -> ")
            cleaned = html.unescape(cleaned)

            # ------------------------------------------------------------------
            # Stage 4: Control Characters & Null Bytes
            # ------------------------------------------------------------------
            cleaned = self._sanitize_control_characters(cleaned)

            # ------------------------------------------------------------------
            # Stage 5: Whitespace Normalization & Punctuation Cleanup
            # ------------------------------------------------------------------
            # Collapse repeated spaces, tabs, and newlines into single spaces
            cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()
            # Safely normalize pathological whitespace immediately preceding closing punctuation
            cleaned = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", cleaned)

            # ------------------------------------------------------------------
            # Stage 6: Post-cleaning Validation & Length Handling
            # ------------------------------------------------------------------
            if not cleaned:
                raise MLInputError(
                    "Report text is empty after cleaning and preprocessing",
                    details={"raw_length": len(raw_text), "cleaned_length": 0},
                )

            if len(cleaned) < self.config.min_report_text_length:
                raise MLInputError(
                    f"Preprocessed report text length ({len(cleaned)}) is below minimum required "
                    f"length of {self.config.min_report_text_length} characters",
                    details={
                        "length": len(cleaned),
                        "min_length": self.config.min_report_text_length,
                    },
                )

            is_truncated = False
            warnings: list[str] = []

            if len(cleaned) > self.config.max_report_text_length:
                if truncate:
                    orig_len = len(cleaned)
                    cleaned = cleaned[: self.config.max_report_text_length].rstrip()
                    is_truncated = True
                    warnings.append(
                        f"Report text truncated from {orig_len} to {len(cleaned)} characters "
                        f"(maximum allowed: {self.config.max_report_text_length})"
                    )
                else:
                    raise MLInputError(
                        f"Preprocessed report text length ({len(cleaned)}) exceeds maximum allowed "
                        f"length of {self.config.max_report_text_length} characters",
                        details={
                            "length": len(cleaned),
                            "max_length": self.config.max_report_text_length,
                        },
                    )

            is_modified = cleaned != raw_text

            # ------------------------------------------------------------------
            # Stage 7: Logging (Safe Metadata Only)
            # ------------------------------------------------------------------
            logger = self.logger
            if report_id:
                logger = logger.with_context(report_id=report_id)

            logger.info(
                "Text preprocessing completed successfully",
                extra={
                    "input_length": len(raw_text),
                    "output_length": len(cleaned),
                    "is_modified": is_modified,
                    "is_truncated": is_truncated,
                    "processing_status": "SUCCESS",
                    "warning_count": len(warnings),
                },
            )

            return PreprocessedText(
                raw_text=raw_text,
                normalized_text=cleaned,
                is_modified=is_modified,
                is_truncated=is_truncated,
                processing_status="SUCCESS",
                warnings=warnings,
            )

        except MLInputError:
            # Re-raise user / constraint input errors cleanly
            raise
        except Exception as exc:
            self.logger.error(
                "Unexpected failure during text preprocessing",
                extra={
                    "error_type": type(exc).__name__,
                    "report_id": report_id,
                    "processing_status": "FAILED",
                },
                exc_info=True,
            )
            raise MLInferenceError(
                f"Unexpected failure during text preprocessing: {type(exc).__name__}",
                details={"error_type": type(exc).__name__},
            ) from exc

    @staticmethod
    def _sanitize_control_characters(text: str) -> str:
        """
        Removes unsafe invisible control characters and null bytes while preserving
        natural whitespace (tabs, newlines) and Unicode typography.
        """
        # Remove Byte Order Mark (BOM)
        text = text.replace("\ufeff", "")

        # Filter characters: preserve \t, \n, \r; replace other Cc / invisible Cf with space
        filtered_chars: list[str] = []
        for ch in text:
            if ch in ("\t", "\n", "\r"):
                filtered_chars.append(ch)
            else:
                cat = unicodedata.category(ch)
                if cat == "Cc":  # Control characters (including \x00 null byte, DEL, etc.)
                    filtered_chars.append(" ")
                elif cat == "Cf":  # Invisible formatting characters (e.g., zero-width space)
                    filtered_chars.append(" ")
                else:
                    filtered_chars.append(ch)

        return "".join(filtered_chars)


def preprocess_report(
    text: str,
    config: MLConfig | None = None,
    report_id: str | None = None,
    truncate: bool = True,
) -> PreprocessedText:
    """
    Public functional interface for emergency report preprocessing.
    Convenience wrapper around TextCleaner.clean().
    """
    cleaner = TextCleaner(config=config)
    return cleaner.clean(text=text, report_id=report_id, truncate=truncate)


# Functional alias
clean_text = preprocess_report
