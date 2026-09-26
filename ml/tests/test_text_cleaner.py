"""
Karen's Ear — Feature 2 Preprocessing & Normalization Tests.

Validates:
- Step 1 TextCleaner and preprocess_report deterministic pipeline
- Unicode normalization (NFKC)
- Control characters and null byte sanitization without word concatenation
- Safe HTML markup and script/style removal without word concatenation
- Whitespace normalization and safe punctuation cleanup
- Strict preservation of emergency signals, keywords, casing, numbers, and locations
- Length validation (min/max boundary) and contractual truncation behavior
- Immutability of raw report text
- Full determinism across repeated executions
- Typed PreprocessedText container and ComponentResult integration
- Safe structured logging without sensitive report text leakage
- Proper ML exception raising
"""

import logging
from unittest.mock import patch

import pytest

from ml.config import MLConfig
from ml.exceptions import MLInferenceError, MLInputError
from ml.preprocessing import (
    PreprocessedText,
    TextCleaner,
    clean_text,
    preprocess_report,
)


# ==============================================================================
# A. Normal Report Processing
# ==============================================================================


def test_normal_report_clean():
    """Verify that a standard emergency report passes through cleanly."""
    raw = "Fire reported near the school"
    res = preprocess_report(raw)

    assert res.normalized_text == "Fire reported near the school"
    assert res.raw_text == raw
    assert res.is_modified is False
    assert res.is_truncated is False
    assert res.processing_status == "SUCCESS"
    assert len(res.warnings) == 0


# ==============================================================================
# B. Whitespace Normalization
# ==============================================================================


def test_repeated_whitespace_and_newlines():
    """Verify collapsing of repeated spaces, tabs, and multiple blank lines."""
    raw = "Fire     reported\n\nnear   school"
    res = preprocess_report(raw)

    assert res.normalized_text == "Fire reported near school"
    assert res.raw_text == raw
    assert res.is_modified is True
    assert res.is_truncated is False


def test_leading_trailing_and_tab_whitespace():
    """Verify stripping of leading, trailing, and inter-word tab characters."""
    raw = "\t\t  Urgent flood warning at sector 5   \n"
    res = preprocess_report(raw)

    assert res.normalized_text == "Urgent flood warning at sector 5"
    assert res.is_modified is True


# ==============================================================================
# C. Punctuation Preservation
# ==============================================================================


def test_punctuation_preservation():
    """Verify that meaningful emergency punctuation is strictly preserved."""
    raw = "HELP!!! People are trapped!!!"
    res = preprocess_report(raw)

    assert res.normalized_text == "HELP!!! People are trapped!!!"
    assert res.is_modified is False


def test_pathological_space_before_punctuation():
    """Verify that spaces before closing punctuation (!, ?, ., ,, :, ;) are safely normalized."""
    raw = "HELP  !!! Are you there ? Please hurry , 5 trapped ."
    res = preprocess_report(raw)

    assert res.normalized_text == "HELP!!! Are you there? Please hurry, 5 trapped."
    assert res.is_modified is True


def test_punctuation_symbols_diversity():
    """Verify that various punctuation characters (-, /, :, ;, ...) survive."""
    raw = "Building 42/3 - Call 112: 5 people trapped... Update; urgent!"
    res = preprocess_report(raw)

    assert res.normalized_text == "Building 42/3 - Call 112: 5 people trapped... Update; urgent!"


# ==============================================================================
# D. Casing Preservation
# ==============================================================================


def test_uppercase_preservation():
    """Verify uppercase signals are NOT forced to lowercase."""
    raw = "FIRE AT SCHOOL"
    res = preprocess_report(raw)

    assert res.normalized_text == "FIRE AT SCHOOL"
    assert "FIRE" in res.normalized_text
    assert "SCHOOL" in res.normalized_text


def test_mixed_case_preservation():
    """Verify mixed case distress phrases retain case sensitivity."""
    raw = "URGENT: Flash Flood near Rasulgarh! Send SAR team ASAP."
    res = preprocess_report(raw)

    assert res.normalized_text == "URGENT: Flash Flood near Rasulgarh! Send SAR team ASAP."


# ==============================================================================
# E. Numbers & Quantities Preservation
# ==============================================================================


def test_numbers_preservation():
    """Verify numbers, floors, casualty counts, and emergency lines survive."""
    raw = "5 people trapped on floor 3"
    res = preprocess_report(raw)

    assert res.normalized_text == "5 people trapped on floor 3"
    assert "5" in res.normalized_text
    assert "3" in res.normalized_text


def test_phone_numbers_and_addresses():
    """Verify complex numeric patterns like phone numbers and building numbers survive."""
    raw = "Call +91-9876543210: 12 victims trapped at Flat 402, Block B-3"
    res = preprocess_report(raw)

    assert res.normalized_text == "Call +91-9876543210: 12 victims trapped at Flat 402, Block B-3"


# ==============================================================================
# F. Unicode & NFKC Normalization
# ==============================================================================


def test_unicode_nfkc_normalization():
    """Verify compatibility decomposition and canonical composition (NFKC)."""
    # Full-width alphanumeric characters
    fullwidth = "ＦＩＲＥ　５　ｐｅｏｐｌｅ"
    res = preprocess_report(fullwidth)
    assert res.normalized_text == "FIRE 5 people"

    # Ligatures (fi ligature -> 'fi')
    ligature = "ﬁre reported near patia"
    res_lig = preprocess_report(ligature)
    assert res_lig.normalized_text == "fire reported near patia"

    # Fraction compatibility character
    fraction = "Water level is ½ meter above road"
    res_frac = preprocess_report(fraction)
    assert res_frac.normalized_text == "Water level is 1⁄2 meter above road"


def test_non_ascii_multilingual_preservation():
    """Verify non-ASCII multilingual scripts (Odia, Hindi, accents) survive without translation."""
    # Odia text ("ନିଆଁ ଲାଗିଛି" = fire caught)
    odia_text = "Emergency: ନିଆଁ ଲାଗିଛି near Rasulgarh"
    res_odia = preprocess_report(odia_text)
    assert "ନିଆଁ ଲାଗିଛି" in res_odia.normalized_text

    # Accented Latin characters
    accented = "Café collapsed near avenue"
    res_acc = preprocess_report(accented)
    assert res_acc.normalized_text == "Café collapsed near avenue"


# ==============================================================================
# G. Control Characters & Null Bytes Handling
# ==============================================================================


def test_null_byte_handling():
    """Verify null bytes are neutralized safely without concatenating words."""
    raw_with_null = "Fire\x00reported near Patia"
    res = preprocess_report(raw_with_null)

    assert "\x00" not in res.normalized_text
    assert res.normalized_text == "Fire reported near Patia"


def test_bom_and_invisible_format_characters():
    """Verify BOM and zero-width spaces are removed without disrupting tokens."""
    # Byte Order Mark (\ufeff)
    raw_bom = "\ufeffFIRE REPORTED"
    res_bom = preprocess_report(raw_bom)
    assert res_bom.normalized_text == "FIRE REPORTED"

    # Zero-width space (\u200b) between words
    raw_zwsp = "building\u200b42"
    res_zwsp = preprocess_report(raw_zwsp)
    assert res_zwsp.normalized_text == "building 42"

    # Control character bell (\x07) and backspace (\x08)
    raw_ctrl = "Alarm\x07 sounded\x08 near hospital"
    res_ctrl = preprocess_report(raw_ctrl)
    assert res_ctrl.normalized_text == "Alarm sounded near hospital"


# ==============================================================================
# H & I. HTML Markup & Script / Style Stripping
# ==============================================================================


def test_html_tag_removal_without_word_concatenation():
    """
    Verify HTML tags are removed and do NOT accidentally concatenate adjoining words.
    Example: 'fire<br>inside building' -> 'fire inside building'
    """
    raw = "fire<br>inside building"
    res = preprocess_report(raw)

    assert res.normalized_text == "fire inside building"
    assert "fireinside" not in res.normalized_text


def test_html_block_tags():
    """Verify multiple block tags, lists, and paragraphs are normalized cleanly."""
    raw = "<p>Building collapse.</p><div>3 people trapped.</div><br/><span>Need ambulance</span>"
    res = preprocess_report(raw)

    assert res.normalized_text == "Building collapse. 3 people trapped. Need ambulance"


def test_html_script_and_style_removal():
    """Verify script and style blocks and their internal code are completely removed."""
    raw = "<script>alert('malicious')</script>Trapped in elevator!<style>body{color:red;}</style>"
    res = preprocess_report(raw)

    assert "malicious" not in res.normalized_text
    assert "color:red" not in res.normalized_text
    assert res.normalized_text == "Trapped in elevator!"


def test_html_comments_and_entities():
    """Verify HTML comments are removed and entities decoded."""
    raw = "Water &amp; food needed <!-- urgent dispatch --> at Patia &quot;Square&quot;"
    res = preprocess_report(raw)

    assert res.normalized_text == 'Water & food needed at Patia "Square"'


def test_math_brackets_preserved():
    """Verify comparison operators like '< 5' or '<5' are not treated as HTML tags."""
    raw = "Trapped count is < 5 people"
    res = preprocess_report(raw)
    assert res.normalized_text == "Trapped count is < 5 people"

    raw2 = "Trapped count is <5 people"
    res2 = preprocess_report(raw2)
    assert res2.normalized_text == "Trapped count is <5 people"


# ==============================================================================
# J, K, L. Input Validation & Error Handling
# ==============================================================================


def test_empty_string_rejection():
    """Verify empty string raises MLInputError."""
    with pytest.raises(MLInputError, match="empty or whitespace-only") as exc_info:
        preprocess_report("")
    assert exc_info.value.details.get("length") == 0


def test_whitespace_only_string_rejection():
    """Verify whitespace-only string raises MLInputError."""
    with pytest.raises(MLInputError, match="empty or whitespace-only"):
        preprocess_report("   \n\t   \r  ")


@pytest.mark.parametrize("invalid_input", [None, 12345, 99.9, ["fire"], {"text": "fire"}])
def test_invalid_non_string_input_rejection(invalid_input):
    """Verify non-string inputs raise typed MLInputError."""
    with pytest.raises(MLInputError, match="must be a string") as exc_info:
        preprocess_report(invalid_input)
    assert exc_info.value.details.get("type") is not None


def test_empty_after_cleaning_rejection():
    """Verify reports that become empty after stripping HTML tags raise MLInputError."""
    with pytest.raises(MLInputError, match="empty after cleaning"):
        preprocess_report("<p>   <br/>   </p>")


# ==============================================================================
# M, N, O. Length Boundaries & Truncation
# ==============================================================================


def test_minimum_length_boundary():
    """Verify minimum length boundary behavior (default min=3)."""
    # 3 characters (boundary: valid)
    res_min = preprocess_report("SOS")
    assert res_min.normalized_text == "SOS"

    # 2 characters (below minimum: raises MLInputError)
    with pytest.raises(MLInputError, match="below minimum required length") as exc_info:
        preprocess_report("No")
    assert exc_info.value.details.get("length") == 2
    assert exc_info.value.details.get("min_length") == 3


def test_maximum_length_boundary_exact():
    """Verify report of exact maximum length (4,000 characters) passes without truncation."""
    text_4000 = "A" * 4000
    res = preprocess_report(text_4000)

    assert len(res.normalized_text) == 4000
    assert res.is_truncated is False
    assert len(res.warnings) == 0


def test_over_limit_truncation_contract():
    """Verify over-limit report (4,050 characters) is deterministically truncated when truncate=True."""
    text_4050 = "A" * 4050
    res = preprocess_report(text_4050, truncate=True)

    assert len(res.normalized_text) == 4000
    assert res.is_truncated is True
    assert res.is_modified is True
    assert len(res.warnings) == 1
    assert "truncated" in res.warnings[0].lower()
    assert "4050" in res.warnings[0]
    assert "4000" in res.warnings[0]


def test_over_limit_rejection_when_truncate_false():
    """Verify over-limit report raises MLInputError when truncate=False."""
    text_4050 = "A" * 4050
    with pytest.raises(MLInputError, match="exceeds maximum allowed length") as exc_info:
        preprocess_report(text_4050, truncate=False)
    assert exc_info.value.details.get("length") == 4050
    assert exc_info.value.details.get("max_length") == 4000


# ==============================================================================
# P & Q. Determinism & Raw Input Preservation
# ==============================================================================


def test_deterministic_repeated_execution():
    """Verify identical results across 50 repeated executions."""
    raw = "HELP!!! 5 people trapped inside building 42 near Patia. Call 112!"

    results = [preprocess_report(raw) for _ in range(50)]
    first_normalized = results[0].normalized_text

    for res in results:
        assert res.normalized_text == first_normalized
        assert res.is_modified == results[0].is_modified
        assert res.is_truncated == results[0].is_truncated
        assert res.warnings == results[0].warnings


def test_raw_input_not_mutated():
    """Verify original input string variable is never mutated and preserved in result."""
    original = "  FIRE near hospital!  "
    snapshot = str(original)

    res = preprocess_report(original)

    assert original == snapshot
    assert res.raw_text == original
    assert res.normalized_text == "FIRE near hospital!"
    assert res.raw_text != res.normalized_text


# ==============================================================================
# R, S, T. Emergency Signals, Keywords, Locations & Numbers Survival
# ==============================================================================


def test_emergency_keywords_survival():
    """Verify all vital emergency and distress keywords survive preprocessing intact."""
    keywords = [
        "HELP",
        "TRAPPED",
        "FIRE",
        "SOS",
        "MAYDAY",
        "DYING",
        "INJURED",
        "MISSING",
        "CASUALTY",
        "AMBULANCE",
    ]
    raw = "SOS! MAYDAY! FIRE reported. 5 INJURED, 2 MISSING, 1 CASUALTY, people TRAPPED and DYING. Send AMBULANCE! HELP!"
    res = preprocess_report(raw)

    for kw in keywords:
        assert kw in res.normalized_text


def test_location_names_survival():
    """Verify location phrasing and landmark entities survive preprocessing intact."""
    locations = [
        "Rasulgarh underpass",
        "Patia square",
        "City Hospital",
        "Market Street",
        "Highway 16",
    ]
    raw = "Flood at Rasulgarh underpass, Patia square, near City Hospital on Market Street along Highway 16."
    res = preprocess_report(raw)

    for loc in locations:
        assert loc in res.normalized_text


def test_regression_prompt_example():
    """
    Regression verification for exact prompt requirement:
    'HELP!!! 5 people trapped inside building 42'
    Expected result must contain: HELP, 5, people, trapped, building, 42, and meaningful punctuation.
    """
    raw = "HELP!!! 5 people trapped inside building 42"
    res = preprocess_report(raw)

    assert res.normalized_text == "HELP!!! 5 people trapped inside building 42"
    assert "HELP" in res.normalized_text
    assert "5" in res.normalized_text
    assert "people" in res.normalized_text
    assert "trapped" in res.normalized_text
    assert "building" in res.normalized_text
    assert "42" in res.normalized_text
    assert "!!!" in res.normalized_text


# ==============================================================================
# Typed Structures, ComponentResult & Logging Integration
# ==============================================================================


def test_preprocessed_text_helpers():
    """Verify PreprocessedText convenience properties and conversion to ComponentResult."""
    res = PreprocessedText(
        raw_text="raw",
        normalized_text="clean",
        is_modified=True,
        is_truncated=False,
        processing_status="SUCCESS",
        warnings=["minor warning"],
    )

    # Property alias
    assert res.text == "clean"
    # String representation
    assert str(res) == "clean"
    # Length
    assert len(res) == 5

    # Conversion to internal ComponentResult
    comp = res.to_component_result()
    assert comp.component == "preprocessing"
    assert comp.status == "SUCCESS"
    assert comp.data["normalized_text"] == "clean"
    assert comp.data["is_modified"] is True
    assert comp.data["is_truncated"] is False
    assert comp.warnings == ["minor warning"]


def test_cleaner_with_custom_config():
    """Verify TextCleaner initializes with custom MLConfig bounds."""
    custom_cfg = MLConfig(min_report_text_length=5, max_report_text_length=20)
    cleaner = TextCleaner(config=custom_cfg)

    # 4 chars should fail with min=5
    with pytest.raises(MLInputError, match="below minimum required length"):
        cleaner.clean("Fire")

    # 25 chars should truncate to 20
    long_text = "This text is too long for this limit"
    res = cleaner.clean(long_text, truncate=True)
    assert len(res.normalized_text) == 20
    assert res.is_truncated is True


def test_functional_aliases():
    """Verify clean_text alias works identically to preprocess_report."""
    raw = "Smoke reported near building 10"
    res1 = preprocess_report(raw)
    res2 = clean_text(raw)

    assert res1.normalized_text == res2.normalized_text
    assert res1.is_modified == res2.is_modified


def test_logging_does_not_leak_raw_emergency_text(caplog):
    """Verify that logging emissions do not contain full raw emergency text."""
    sensitive_report = "SECRET_PATIENT_NAME is bleeding at private address 1234!"

    with caplog.at_level(logging.INFO):
        preprocess_report(sensitive_report, report_id="rep-8888")

    for record in caplog.records:
        # The raw text itself should never be present in the log message
        assert sensitive_report not in record.message
        # Extra metadata should carry safe summary attributes
        if hasattr(record, "input_length"):
            assert record.input_length == len(sensitive_report)


def test_unexpected_exception_wrapped_in_ml_inference_error():
    """Verify unexpected non-input exceptions are caught, logged, and raised as MLInferenceError."""
    cleaner = TextCleaner()

    with patch("unicodedata.normalize", side_effect=RuntimeError("Simulated Unicode system error")):
        with pytest.raises(MLInferenceError, match="Unexpected failure during text preprocessing") as exc_info:
            cleaner.clean("Valid report text")
        assert exc_info.value.details.get("error_type") == "RuntimeError"
