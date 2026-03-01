"""
Prompt builder for the FRAME shot list generator.

Keeping prompt construction separate from the UI and API layers makes it easy
to iterate on the prompt wording, add new fields, or write unit tests without
touching Streamlit or OpenAI code.
"""

# The exact section headers the AI must produce. The PDF generator and result
# panel both depend on these being consistent, so they are defined once here.
REQUIRED_SECTIONS: list[str] = [
    "Shot List",
    "Hero Shots",
    "Gear Recommendations",
    "Session Flow",
    "Director's Notes",
]


def build_prompt(
    shoot_type: str,
    concept: str,
    location: str,
    subjects: str,
    mood: str,
    duration: str,
    extra_notes: str,
) -> str:
    """
    Build the user prompt sent to OpenAI.

    Optional fields (subjects, extra_notes) are replaced with neutral
    placeholders so the model always receives a complete, well-formed brief.
    """
    subjects_str = subjects.strip() if subjects.strip() else "Not specified"
    extra_str = extra_notes.strip() if extra_notes.strip() else "None"

    sections_block = "\n\n".join(
        f"## {section}\n(See instructions above.)" for section in REQUIRED_SECTIONS
    )

    return f"""You are a world-class photographer's creative director. \
Generate a detailed, practical shot list for the shoot described below.

Shoot Details:
- Type: {shoot_type}
- Concept/Brief: {concept}
- Location: {location}
- Subjects: {subjects_str}
- Mood/Style: {mood}
- Duration: {duration}
- Extra Notes: {extra_str}

Use exactly these markdown sections in this order:

## Shot List
(Numbered shots — composition, angle, focal length, lighting setup. Be specific.)

## Hero Shots
(The 2–3 must-capture frames. These define the shoot.)

## Gear Recommendations
(Lenses, lighting, accessories for this specific shoot.)

## Session Flow
(Time-structured breakdown of the {duration} session.)

## Director's Notes
(2–3 sharp, specific pro tips. No fluff. Write like a pro briefing the crew.)

Write like you're handing this to a working photographer 10 minutes before the shoot. \
Do not add any sections beyond those listed above."""
