"""
Input validation and prompt injection protection for the FRAME shot list generator.

Validation runs before any data reaches the OpenAI API:
- Required field checks
- Character length limits (cap token costs)
- Garbage / meaningless text detection
- Basic profanity filter
- Prompt injection pattern detection
"""

import re

MAX_LENGTHS: dict[str, int] = {
    "concept": 1000,
    "location": 200,
    "subjects": 200,
    "extra_notes": 500,
}

# Phrases commonly used in prompt injection attacks. Checked case-insensitively.
_INJECTION_PATTERNS: list[str] = [
    "ignore all instructions",
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
]

# Common profanity words (moderate list — not exhaustive, but covers clear cases).
_PROFANITY_WORDS: set[str] = {
    "fuck", "fucking", "fucked", "fucker", "fucks",
    "shit", "shitting", "shitty",
    "ass", "asshole", "asshat",
    "bitch", "bitches",
    "cunt", "cunts",
    "dick", "dicks",
    "cock", "cocks",
    "pussy", "pussies",
    "bastard", "bastards",
    "damn", "damned",
    "hell",
    "crap",
    "piss", "pissed",
    "slut", "slutty",
    "whore", "whores",
    "nigger", "nigga",
    "faggot", "fag",
    "retard", "retarded",
    "motherfucker", "motherfucking",
    "bullshit",
    "horseshit",
    "dumbass",
    "jackass",
    "dipshit",
    "shithead",
    "arsehole",
    "twat",
}

# Minimum ratio of alphabetic characters required in a field value.
# Prevents pure-punctuation / pure-number / pure-symbol input.
_MIN_ALPHA_RATIO = 0.35

# Maximum allowed consecutive identical characters (catches "aaaaaaa", "!!!!!")
_MAX_CONSECUTIVE_IDENTICAL = 4

def _is_garbage(text: str, min_words: int = 2) -> bool:
    """
    Return True if the text looks like meaningless / garbage input.

    Checks for:
    - Insufficient alphabetic content (too many symbols / numbers / spaces)
    - Runs of repeated identical characters ("aaaaaa", "!!!!!")
    - Fewer real words than min_words (words with len > 1)

    Args:
        text:      The string to evaluate.
        min_words: Minimum number of real words (len > 1) required.
                   Use 2 for descriptive fields (concept), 1 for short fields (location).
    """
    stripped = text.strip()
    if not stripped:
        return False  # Empty is handled separately as a required-field error

    # Ratio of alphabetic characters must meet the minimum threshold
    alpha_count = sum(1 for c in stripped if c.isalpha())
    if alpha_count / len(stripped) < _MIN_ALPHA_RATIO:
        return True

    # Reject runs of 5+ identical characters: "aaaaaaa", "!!!!!!!!", "........"
    if re.search(r"(.)\1{" + str(_MAX_CONSECUTIVE_IDENTICAL) + r",}", stripped):
        return True

    # Require at least min_words real words (length > 1)
    words = [w for w in re.split(r"\W+", stripped) if len(w) > 1]
    if len(words) < min_words:
        return True

    return False


def _contains_profanity(text: str) -> bool:
    """
    Return True if the text contains any word from the profanity list.
    Matches whole words only (case-insensitive).
    """
    # Extract all word tokens, lowercased
    words = set(re.findall(r"\b\w+\b", text.lower()))
    return bool(words & _PROFANITY_WORDS)


def validate_inputs(
    concept: str,
    location: str,
    subjects: str = "",
    extra_notes: str = "",
) -> list[str]:
    """
    Validate user-supplied form inputs.

    Returns a list of human-readable error strings. An empty list means all
    inputs are valid and safe to pass to the prompt builder.
    """
    errors: list[str] = []

    # ── Required fields ───────────────────────────────────────────────────────
    if not concept.strip():
        errors.append("Concept / Brief is required.")
    if not location.strip():
        errors.append("Location is required.")

    # ── Character length limits ───────────────────────────────────────────────
    if len(concept) > MAX_LENGTHS["concept"]:
        errors.append(
            f"Concept is too long — max {MAX_LENGTHS['concept']} characters "
            f"(yours: {len(concept)})."
        )
    if len(location) > MAX_LENGTHS["location"]:
        errors.append(
            f"Location is too long — max {MAX_LENGTHS['location']} characters "
            f"(yours: {len(location)})."
        )
    if subjects and len(subjects) > MAX_LENGTHS["subjects"]:
        errors.append(
            f"Subjects is too long — max {MAX_LENGTHS['subjects']} characters "
            f"(yours: {len(subjects)})."
        )
    if extra_notes and len(extra_notes) > MAX_LENGTHS["extra_notes"]:
        errors.append(
            f"Director's Notes is too long — max {MAX_LENGTHS['extra_notes']} characters "
            f"(yours: {len(extra_notes)})."
        )

    # ── Garbage / meaningless text detection ──────────────────────────────────
    # Only check required fields — optional fields can be short by design.
    # Concept needs at least 2 real words; location can be a single place name.
    if concept.strip() and _is_garbage(concept, min_words=2):
        errors.append(
            "Concept doesn't look like a meaningful shoot brief. "
            "Please describe your shoot in a few words "
            "(e.g. 'Moody editorial portrait in a Brooklyn warehouse')."
        )
    if location.strip() and _is_garbage(location, min_words=1):
        errors.append(
            "Location doesn't look valid. "
            "Please enter a real place (e.g. 'Brooklyn warehouse', 'Malibu beach')."
        )

    # ── Profanity filter ──────────────────────────────────────────────────────
    all_text = f"{concept} {location} {subjects} {extra_notes}"
    if _contains_profanity(all_text):
        errors.append("Please keep your input professional — profanity is not allowed.")

    # ── Prompt injection detection ────────────────────────────────────────────
    combined = all_text.lower()
    for pattern in _INJECTION_PATTERNS:
        if pattern in combined:
            errors.append(
                "Input contains disallowed content. Please revise your brief "
                "and avoid instruction-like phrases."
            )
            break  # One injection error is enough

    return errors
