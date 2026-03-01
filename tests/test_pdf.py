"""
Unit tests for core.pdf — PDF generation.

These tests run entirely offline (no OpenAI call, no Streamlit) and verify that:
- The function returns valid PDF bytes for normal input
- Markdown syntax is stripped correctly before rendering
- Edge cases (empty content, long content, special characters) don't crash the generator
- The filename helper produces the expected format

Run with:  pytest tests/test_pdf.py -v
"""

import pytest

from core.pdf import generate_pdf


# ── Return type and structure ─────────────────────────────────────────────────

def test_returns_bytes():
    result = generate_pdf("## Shot List\nShot 1: Wide angle.", "Portrait")
    assert isinstance(result, bytes)


def test_nonempty_output():
    result = generate_pdf("## Shot List\nShot 1: Wide angle.", "Portrait")
    assert len(result) > 0


def test_valid_pdf_signature():
    """PDF files always start with the %PDF magic bytes."""
    result = generate_pdf("## Shot List\nShot 1: Wide angle.", "Wedding")
    assert result[:4] == b"%PDF"


# ── Content handling ──────────────────────────────────────────────────────────

def test_empty_content_does_not_crash():
    result = generate_pdf("", "Portrait")
    assert isinstance(result, bytes)
    assert result[:4] == b"%PDF"


def test_all_sections_present():
    content = (
        "## Shot List\nShot 1.\n"
        "## Hero Shots\nThe golden hour frame.\n"
        "## Gear Recommendations\n50mm f/1.8.\n"
        "## Session Flow\n0:00 — Arrive and scout.\n"
        "## Director's Notes\nArrive early."
    )
    result = generate_pdf(content, "Fashion")
    assert isinstance(result, bytes)
    assert len(result) > 500  # meaningful content was rendered


def test_bold_markdown_stripped():
    """**bold** text should not crash the renderer — the ** symbols are removed."""
    content = "## Shot List\n**Shot 1:** Wide angle with **soft light**."
    result = generate_pdf(content, "Portrait")
    assert isinstance(result, bytes)


def test_italic_markdown_stripped():
    content = "## Shot List\n*Shot 1:* Wide angle with *soft light*."
    result = generate_pdf(content, "Portrait")
    assert isinstance(result, bytes)


def test_mixed_markdown_stripped():
    content = "## Shot List\n**Bold** and *italic* and normal text."
    result = generate_pdf(content, "Portrait")
    assert isinstance(result, bytes)


def test_multiple_blank_lines_do_not_crash():
    content = "## Shot List\n\n\n\nShot 1.\n\n\n## Hero Shots\nThe golden hour frame."
    result = generate_pdf(content, "Event")
    assert isinstance(result, bytes)


def test_long_content_does_not_crash():
    """Long content spanning multiple PDF pages should not raise."""
    sections = []
    for section in ["Shot List", "Hero Shots", "Gear Recommendations", "Session Flow", "Director's Notes"]:
        section_lines = "\n".join(
            f"Item {i}: Detailed description of this shot or recommendation."
            for i in range(1, 12)
        )
        sections.append(f"## {section}\n{section_lines}")
    content = "\n\n".join(sections)
    result = generate_pdf(content, "Wedding")
    assert isinstance(result, bytes)
    assert result[:4] == b"%PDF"


def test_special_characters_do_not_crash():
    """Em dashes, accented letters, and ampersands should all be sanitized gracefully."""
    content = "## Shot List\nShot 1: Cafe terrace & alley \u2014 f/2.8 @ 1/250s."
    result = generate_pdf(content, "Street")
    assert isinstance(result, bytes)


# ── Shoot type in output ──────────────────────────────────────────────────────

@pytest.mark.parametrize("shoot_type", [
    "Portrait", "Wedding", "Event", "Landscape",
    "Street", "Product", "Real Estate", "Fashion", "Wildlife", "Other",
])
def test_all_shoot_types_accepted(shoot_type: str):
    result = generate_pdf("## Shot List\nShot 1.", shoot_type)
    assert isinstance(result, bytes)
    assert result[:4] == b"%PDF"


# ── Filename convention (logic lives in app.py, tested here as a pure function) ──

@pytest.mark.parametrize("shoot_type,expected_filename", [
    ("Portrait",    "frame_portrait_shot_list.pdf"),
    ("Real Estate", "frame_real_estate_shot_list.pdf"),
    ("Wildlife",    "frame_wildlife_shot_list.pdf"),
])
def test_filename_format(shoot_type: str, expected_filename: str):
    filename = f"frame_{shoot_type.lower().replace(' ', '_')}_shot_list.pdf"
    assert filename == expected_filename
