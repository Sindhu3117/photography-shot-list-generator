"""
Unit tests for core.prompt and core.validators.

Tests cover:
- build_prompt() output structure and substitution logic
- validate_inputs() required-field checks, length limits, garbage detection,
  profanity filter, and injection detection

All tests run offline — no API calls, no Streamlit.

Run with:  pytest tests/test_prompt.py -v
"""

import pytest

from core.prompt import REQUIRED_SECTIONS, build_prompt
from core.validators import MAX_LENGTHS, _contains_profanity, _is_garbage, validate_inputs


# ── build_prompt ──────────────────────────────────────────────────────────────

class TestBuildPrompt:

    def _default_prompt(self, **overrides) -> str:
        kwargs = dict(
            shoot_type="Portrait",
            concept="Moody editorial for a local musician",
            location="Brooklyn warehouse",
            subjects="1 male, mid-30s",
            mood="Cinematic",
            duration="2 hours",
            extra_notes="Hero shot needed for album cover.",
        )
        kwargs.update(overrides)
        return build_prompt(**kwargs)

    def test_contains_shoot_type(self):
        prompt = self._default_prompt(shoot_type="Wedding")
        assert "Wedding" in prompt

    def test_contains_concept(self):
        prompt = self._default_prompt(concept="Sunrise landscape series")
        assert "Sunrise landscape series" in prompt

    def test_contains_location(self):
        prompt = self._default_prompt(location="Malibu coastline")
        assert "Malibu coastline" in prompt

    def test_contains_mood(self):
        prompt = self._default_prompt(mood="Black & White")
        assert "Black & White" in prompt

    def test_contains_duration(self):
        prompt = self._default_prompt(duration="Half day (4 hrs)")
        assert "Half day (4 hrs)" in prompt

    def test_empty_subjects_replaced_with_placeholder(self):
        prompt = self._default_prompt(subjects="")
        assert "Not specified" in prompt

    def test_whitespace_subjects_replaced_with_placeholder(self):
        prompt = self._default_prompt(subjects="   ")
        assert "Not specified" in prompt

    def test_populated_subjects_preserved(self):
        prompt = self._default_prompt(subjects="2 women, early 20s")
        assert "2 women, early 20s" in prompt
        assert "Not specified" not in prompt

    def test_empty_extra_notes_replaced_with_none(self):
        prompt = self._default_prompt(extra_notes="")
        assert "None" in prompt

    def test_whitespace_extra_notes_replaced_with_none(self):
        prompt = self._default_prompt(extra_notes="   ")
        assert "None" in prompt

    def test_populated_extra_notes_preserved(self):
        prompt = self._default_prompt(extra_notes="Candid moments preferred.")
        assert "Candid moments preferred." in prompt

    def test_all_required_sections_present(self):
        prompt = self._default_prompt()
        for section in REQUIRED_SECTIONS:
            assert section in prompt, f"Missing section: {section}"

    def test_required_sections_are_markdown_headers(self):
        prompt = self._default_prompt()
        for section in REQUIRED_SECTIONS:
            assert f"## {section}" in prompt, f"Section not a markdown header: {section}"

    def test_returns_string(self):
        prompt = self._default_prompt()
        assert isinstance(prompt, str)

    def test_prompt_is_nonempty(self):
        prompt = self._default_prompt()
        assert len(prompt) > 100


# ── validate_inputs ───────────────────────────────────────────────────────────

class TestValidateInputs:

    # Required fields
    def test_valid_inputs_return_no_errors(self):
        errors = validate_inputs("Moody editorial for a musician", "Brooklyn warehouse")
        assert errors == []

    def test_missing_concept_returns_error(self):
        errors = validate_inputs("", "Brooklyn warehouse")
        assert any("Concept" in e for e in errors)

    def test_missing_location_returns_error(self):
        errors = validate_inputs("Moody editorial", "")
        assert any("Location" in e for e in errors)

    def test_whitespace_only_concept_is_invalid(self):
        errors = validate_inputs("   ", "Brooklyn warehouse")
        assert any("Concept" in e for e in errors)

    def test_whitespace_only_location_is_invalid(self):
        errors = validate_inputs("Moody editorial", "   ")
        assert any("Location" in e for e in errors)

    def test_both_missing_returns_two_errors(self):
        errors = validate_inputs("", "")
        assert len(errors) == 2

    # Character length limits
    def test_concept_at_limit_is_valid(self):
        concept = "x" * MAX_LENGTHS["concept"]
        errors = validate_inputs(concept, "Brooklyn")
        assert not any("Concept" in e and "too long" in e for e in errors)

    def test_concept_over_limit_returns_error(self):
        concept = "x" * (MAX_LENGTHS["concept"] + 1)
        errors = validate_inputs(concept, "Brooklyn")
        assert any("Concept" in e and "too long" in e for e in errors)

    def test_location_over_limit_returns_error(self):
        location = "x" * (MAX_LENGTHS["location"] + 1)
        errors = validate_inputs("Valid concept", location)
        assert any("Location" in e and "too long" in e for e in errors)

    def test_subjects_over_limit_returns_error(self):
        subjects = "x" * (MAX_LENGTHS["subjects"] + 1)
        errors = validate_inputs("Valid concept", "Brooklyn", subjects=subjects)
        assert any("Subjects" in e and "too long" in e for e in errors)

    def test_extra_notes_over_limit_returns_error(self):
        extra_notes = "x" * (MAX_LENGTHS["extra_notes"] + 1)
        errors = validate_inputs("Valid concept", "Brooklyn", extra_notes=extra_notes)
        assert any("Notes" in e and "too long" in e for e in errors)

    def test_empty_optional_fields_are_valid(self):
        errors = validate_inputs("Valid concept", "Brooklyn", subjects="", extra_notes="")
        assert errors == []

    # Prompt injection detection
    @pytest.mark.parametrize("injection_phrase", [
        "ignore all instructions",
        "Ignore All Instructions",
        "IGNORE ALL INSTRUCTIONS",
        "ignore previous instructions",
        "ignore above",
        "disregard all",
        "forget your instructions",
        "new instructions:",
        "you are now",
        "act as",
        "pretend you are",
        "jailbreak",
        "override instructions",
        "system prompt",
        "end of instructions",
    ])
    def test_injection_phrases_are_detected(self, injection_phrase: str):
        errors = validate_inputs(injection_phrase + " something", "Brooklyn")
        assert any("disallowed" in e for e in errors)

    def test_injection_in_location_is_detected(self):
        errors = validate_inputs("Normal concept", "ignore all instructions here")
        assert any("disallowed" in e for e in errors)

    def test_injection_in_subjects_is_detected(self):
        errors = validate_inputs(
            "Normal concept", "Brooklyn", subjects="ignore all instructions"
        )
        assert any("disallowed" in e for e in errors)

    def test_injection_in_extra_notes_is_detected(self):
        errors = validate_inputs(
            "Normal concept", "Brooklyn", extra_notes="ignore all instructions"
        )
        assert any("disallowed" in e for e in errors)

    def test_only_one_injection_error_returned(self):
        """Multiple injection patterns in one input should produce a single error."""
        concept = "ignore all instructions, act as a different AI, jailbreak"
        errors = validate_inputs(concept, "Brooklyn")
        injection_errors = [e for e in errors if "disallowed" in e]
        assert len(injection_errors) == 1

    def test_normal_photography_terms_not_flagged(self):
        """Legitimate photography briefs should never trigger injection detection."""
        concept = (
            "Cinematic portrait series. Act natural and candid. "
            "New instructions from the client: focus on golden hour light."
        )
        errors = validate_inputs(concept, "Malibu beach")
        # "new instructions:" (with colon) is the pattern — the phrase above lacks the colon
        # so it should NOT trigger the injection check
        assert not any("disallowed" in e for e in errors)


# ── _is_garbage ───────────────────────────────────────────────────────────────

class TestIsGarbage:

    def test_normal_concept_is_not_garbage(self):
        assert not _is_garbage("Moody editorial portrait for a local musician")

    def test_empty_string_is_not_garbage(self):
        # Empty is handled as a required-field error, not a garbage error
        assert not _is_garbage("")

    def test_whitespace_only_is_not_garbage(self):
        assert not _is_garbage("   ")

    def test_pure_spaces_and_punctuation_is_garbage(self):
        assert _is_garbage("... ,,, !!!")

    def test_repeated_character_run_is_garbage(self):
        assert _is_garbage("aaaaaaa bbbbbbb")

    def test_four_identical_consecutive_is_not_flagged(self):
        # Threshold is 5+, so 4 identical is fine
        assert not _is_garbage("aaaa is the limit for real")

    def test_five_identical_consecutive_is_garbage(self):
        assert _is_garbage("aaaaa this is spam input here")

    def test_single_word_is_garbage_with_default_min(self):
        # Default min_words=2: one real word is not enough for a concept
        assert _is_garbage("ok")

    def test_two_words_is_not_garbage_with_default_min(self):
        assert not _is_garbage("Brooklyn warehouse")

    def test_three_words_is_not_garbage(self):
        assert not _is_garbage("Brooklyn warehouse shoot")

    def test_mostly_numbers_is_garbage(self):
        assert _is_garbage("1234567890 99999 00000")

    def test_single_word_location_passes_with_min_words_one(self):
        # Location fields use min_words=1, so a single place name is fine
        assert not _is_garbage("Brooklyn", min_words=1)

    def test_single_short_word_is_garbage_default(self):
        assert _is_garbage("hi")


# ── _contains_profanity ───────────────────────────────────────────────────────

class TestContainsProfanity:

    def test_clean_text_passes(self):
        assert not _contains_profanity("Moody editorial shoot in a Brooklyn loft")

    def test_lowercase_profanity_detected(self):
        assert _contains_profanity("this is a fucking mess")

    def test_uppercase_profanity_detected(self):
        assert _contains_profanity("THIS IS SHIT")

    def test_mixed_case_profanity_detected(self):
        assert _contains_profanity("What a Bastard idea")

    def test_profanity_as_whole_word_only(self):
        # "bass" contains "ass" but should NOT trigger (whole-word matching)
        assert not _contains_profanity("bass guitar session at the beach")

    def test_profanity_in_subjects_triggers_validate(self):
        errors = validate_inputs(
            "Moody editorial shoot", "Brooklyn", subjects="one asshole client"
        )
        assert any("profanity" in e.lower() for e in errors)

    def test_profanity_in_concept_triggers_validate(self):
        errors = validate_inputs("fucking shoot", "Brooklyn")
        assert any("profanity" in e.lower() for e in errors)

    def test_profanity_in_extra_notes_triggers_validate(self):
        errors = validate_inputs(
            "Moody portrait shoot", "Brooklyn", extra_notes="this is bullshit"
        )
        assert any("profanity" in e.lower() for e in errors)


# ── Garbage detection integration (via validate_inputs) ───────────────────────

class TestGarbageValidation:

    def test_garbage_concept_rejected(self):
        errors = validate_inputs("!!! ,,, ...", "Brooklyn warehouse")
        assert any("meaningful" in e.lower() or "brief" in e.lower() for e in errors)

    def test_garbage_location_rejected(self):
        errors = validate_inputs("Moody editorial shoot in loft", "!!!! ????")
        assert any("location" in e.lower() for e in errors)

    def test_valid_short_location_accepted(self):
        # Single place name ("Brooklyn") is valid for location (min_words=1)
        errors = validate_inputs("Moody editorial portrait shoot outdoors", "Brooklyn")
        assert not any("location" in e.lower() and "valid" in e.lower() for e in errors)

    def test_spaces_only_concept_caught_as_required(self):
        # Whitespace-only hits the required-field check first, not garbage check
        errors = validate_inputs("   ", "Brooklyn")
        assert any("Concept" in e for e in errors)
