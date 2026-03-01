import base64
import logging
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from core.ai_client import FrameAIError, FrameAuthError, FrameRateLimitError, generate_shot_list
from core.pdf import generate_pdf
from core.prompt import build_prompt
from core.validators import MAX_LENGTHS, validate_inputs

# Load .env once at startup so all modules can read environment variables via os.getenv()
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ── Session state initialisation ──────────────────────────────────────────────
# Streamlit reruns the entire script on every widget interaction, so results
# must be stored in session_state to survive across reruns.
def _init_session_state() -> None:
    defaults = {
        "result": None,          # str  — last successful AI response
        "shoot_type": None,      # str  — shoot type used for the last generation
        "error": None,           # str  — last error message, or None
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


_init_session_state()

st.set_page_config(
    page_title="FRAME — Shot List Generator",
    page_icon="◼",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Load hero image as base64 ─────────────────────────────────────────────────
hero_path = Path(__file__).parent / "assets" / "hero.png"
hero_b64 = base64.b64encode(hero_path.read_bytes()).decode()

# ── Styles ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;0,900;1,400&family=Inter:wght@300;400;500;600;700&display=swap');

*, *::before, *::after {{ box-sizing: border-box; }}

:root {{
    --bg-page:    #181818;
    --bg-card:    #212121;
    --bg-input:   #2a2a2a;
    --border:     #383838;
    --border-sub: #2e2e2e;
    --text-high:  #f0f0f0;
    --text-body:  #d0d0d0;
    --text-muted: #909090;
    --text-faint: #585858;
    --accent:     #c9a050;
}}

.stApp {{
    background-color: var(--bg-page);
    font-family: 'Inter', sans-serif;
    color: var(--text-high);
}}

/* ── Streamlit markdown text — force readable colour globally ── */
.stMarkdown p,
.stMarkdown li,
.stMarkdown ol li,
.stMarkdown ul li {{
    color: var(--text-high) !important;
    font-size: 0.9rem !important;
    line-height: 1.8 !important;
}}
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {{
    color: var(--text-high) !important;
}}
.stMarkdown strong {{ color: #ffffff !important; font-weight: 600 !important; }}
.stMarkdown a {{ color: var(--accent) !important; }}

#MainMenu, footer, header {{ visibility: hidden; }}

.main .block-container {{
    padding: 0 0 4rem 0;
    max-width: 100%;
}}

/* ── Hero ── */
.hero {{
    position: relative;
    width: 100%;
    height: 420px;
    background-image: url('data:image/png;base64,{hero_b64}');
    background-size: cover;
    background-position: center 55%;
    overflow: hidden;
    margin-bottom: 0;
}}

.hero-overlay {{
    position: absolute;
    inset: 0;
    background: linear-gradient(
        to right,
        rgba(18,18,18,0.97) 0%,
        rgba(18,18,18,0.82) 32%,
        rgba(18,18,18,0.35) 65%,
        rgba(18,18,18,0.1)  100%
    );
}}

/* Bottom fade so hero blends into page */
.hero-overlay::after {{
    content: '';
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 120px;
    background: linear-gradient(to bottom, transparent, #181818);
}}

.hero-content {{
    position: absolute;
    bottom: 2.75rem;
    left: 5rem;
    z-index: 2;
}}

.hero-eyebrow {{
    display: block;
    font-family: 'Inter', sans-serif;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.32em;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 0.75rem;
}}

.hero-title {{
    font-family: 'Playfair Display', serif;
    font-size: 5.5rem;
    font-weight: 900;
    color: #ffffff;
    line-height: 0.9;
    letter-spacing: -0.02em;
    margin: 0 0 1rem 0;
}}

.hero-sub {{
    font-family: 'Inter', sans-serif;
    font-size: 0.72rem;
    font-weight: 400;
    letter-spacing: 0.2em;
    color: #888888;
    margin: 0;
}}

/* Photo credit */
.hero-credit {{
    position: absolute;
    bottom: 1rem;
    right: 1.5rem;
    font-family: 'Inter', sans-serif;
    font-size: 0.6rem;
    letter-spacing: 0.12em;
    color: rgba(255,255,255,0.25);
    z-index: 2;
    text-transform: uppercase;
}}

/* ── Main content area ── */
.content-wrap {{
    padding: 2.5rem 5rem 0 5rem;
    max-width: 1500px;
    margin: 0 auto;
}}

/* ── Eyebrow ── */
.eyebrow {{
    display: block;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.3em;
    text-transform: uppercase;
    color: var(--accent) !important;
    margin-bottom: 0.5rem;
}}

/* ── Section title ── */
.section-title {{
    font-family: 'Playfair Display', serif;
    font-size: 1.85rem;
    font-weight: 700;
    color: var(--text-high) !important;
    margin: 0.2rem 0 1.75rem 0;
    line-height: 1.25;
}}

/* ── Labels ── */
.stTextInput label p,
.stTextArea label p,
.stSelectbox label p {{
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.14em !important;
    text-transform: uppercase !important;
    color: var(--text-muted) !important;
}}

/* ── Text inputs ── */
.stTextInput input {{
    background-color: var(--bg-input) !important;
    border: 1px solid var(--border) !important;
    border-radius: 2px !important;
    color: var(--text-high) !important;
    font-size: 0.925rem !important;
    padding: 0.8rem 1rem !important;
    line-height: 1.5 !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}}
.stTextInput input::placeholder {{ color: var(--text-faint) !important; font-style: italic; }}
.stTextInput input:focus {{
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px rgba(201,160,80,0.12) !important;
    outline: none !important;
}}

/* ── Text areas ── */
.stTextArea textarea {{
    background-color: var(--bg-input) !important;
    border: 1px solid var(--border) !important;
    border-radius: 2px !important;
    color: var(--text-high) !important;
    font-size: 0.925rem !important;
    padding: 0.8rem 1rem !important;
    line-height: 1.65 !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
    resize: none !important;
}}
.stTextArea textarea::placeholder {{ color: var(--text-faint) !important; font-style: italic; }}
.stTextArea textarea:focus {{
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px rgba(201,160,80,0.12) !important;
    outline: none !important;
}}

/* ── Selectbox ── */
.stSelectbox > div > div {{
    background-color: var(--bg-input) !important;
    border: 1px solid var(--border) !important;
    border-radius: 2px !important;
    color: var(--text-high) !important;
    font-size: 0.925rem !important;
}}
.stSelectbox svg {{ fill: var(--text-muted) !important; }}

/* ── Generate button ── */
.stButton > button {{
    background-color: var(--accent) !important;
    color: #111111 !important;
    border: none !important;
    border-radius: 2px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.22em !important;
    text-transform: uppercase !important;
    padding: 1rem 2rem !important;
    margin-top: 0.75rem !important;
    width: 100% !important;
    transition: background-color 0.2s ease, transform 0.15s ease !important;
}}
.stButton > button:hover {{
    background-color: #d4ac5a !important;
    transform: translateY(-2px) !important;
}}
.stButton > button:active {{ transform: translateY(0) !important; }}

/* ── Download button ── */
.stDownloadButton > button {{
    background-color: transparent !important;
    color: var(--text-muted) !important;
    border: 1px solid var(--border) !important;
    border-radius: 2px !important;
    font-size: 0.7rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.18em !important;
    text-transform: uppercase !important;
    padding: 0.85rem 1.5rem !important;
    width: 100% !important;
    transition: all 0.2s ease !important;
}}
.stDownloadButton > button:hover {{
    border-color: var(--accent) !important;
    color: var(--accent) !important;
    background-color: rgba(201,160,80,0.06) !important;
}}

/* ── Divider ── */
hr {{
    border: none !important;
    border-top: 1px solid var(--border-sub) !important;
    margin: 0 0 2.5rem 0 !important;
}}

/* ── Alert ── */
.stAlert {{
    background-color: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 2px !important;
}}
.stAlert p {{ color: var(--text-body) !important; font-size: 0.875rem !important; }}

/* ── Spinner ── */
.stSpinner p {{
    color: var(--text-muted) !important;
    font-size: 0.82rem !important;
}}

/* ── Result panel ── */
.result-panel {{
    background-color: var(--bg-card);
    border: 1px solid var(--border-sub);
    border-left: 3px solid var(--accent);
    padding: 2rem 2.25rem 2.25rem;
}}
.result-panel h2 {{
    font-family: 'Inter', sans-serif !important;
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.22em !important;
    text-transform: uppercase !important;
    color: var(--accent) !important;
    margin-top: 1.75rem !important;
    margin-bottom: 0.6rem !important;
    padding-bottom: 0.5rem !important;
    border-bottom: 1px solid var(--border-sub) !important;
}}
.result-panel h2:first-child {{ margin-top: 0 !important; }}
.result-panel p {{
    font-size: 0.9rem !important;
    color: var(--text-body) !important;
    line-height: 1.8 !important;
}}
.result-panel li {{
    font-size: 0.9rem !important;
    color: var(--text-body) !important;
    line-height: 1.8 !important;
    margin-bottom: 0.4rem !important;
}}
.result-panel strong {{ color: var(--text-high) !important; font-weight: 600 !important; }}
.result-panel ol, .result-panel ul {{ padding-left: 1.5rem !important; }}

/* ── Placeholder panel ── */
.placeholder-panel {{
    background-color: var(--bg-card);
    border: 1px solid var(--border-sub);
    padding: 2.75rem 2.5rem;
    min-height: 400px;
}}
.placeholder-panel .aperture {{
    font-size: 2.25rem;
    color: var(--accent) !important;
    opacity: 0.45;
    display: block;
    margin-bottom: 1.25rem;
    line-height: 1;
}}
.placeholder-panel h4 {{
    font-family: 'Playfair Display', serif !important;
    font-size: 1.15rem !important;
    font-style: italic !important;
    font-weight: 400 !important;
    color: var(--text-body) !important;
    margin-bottom: 0.4rem !important;
}}
.placeholder-panel .sub {{
    font-size: 0.82rem !important;
    color: var(--text-faint) !important;
    line-height: 1.7 !important;
    margin-bottom: 2rem !important;
}}
.placeholder-list {{
    list-style: none !important;
    padding: 0 !important;
    margin: 0 !important;
    border-top: 1px solid var(--border-sub);
}}
.placeholder-list li {{
    font-size: 0.8rem !important;
    color: #686868 !important;
    padding: 0.65rem 0 !important;
    border-bottom: 1px solid var(--border-sub);
    display: flex;
    align-items: center;
    gap: 0.75rem;
    letter-spacing: 0.02em;
}}
.placeholder-list li::before {{
    content: '';
    width: 5px;
    height: 5px;
    background: var(--accent);
    opacity: 0.45;
    border-radius: 50%;
    flex-shrink: 0;
}}
</style>
""", unsafe_allow_html=True)


# ── Startup check — fail fast if the API key is missing ───────────────────────
if not os.getenv("OPENAI_API_KEY"):
    st.error(
        "**OPENAI_API_KEY is not set.** "
        "Create a `.env` file in the project root with `OPENAI_API_KEY=your-key-here` "
        "and restart the app."
    )
    st.stop()


# ── Hero Banner ───────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="hero">
    <div class="hero-overlay"></div>
    <div class="hero-content">
        <span class="hero-eyebrow">AI-Powered Creative Tool for Photographers</span>
        <h1 class="hero-title">FRAME</h1>
        <p class="hero-sub">SHOT LIST GENERATOR &nbsp;·&nbsp; PLAN YOUR SHOOT &nbsp;·&nbsp; POWERED BY AI</p>
    </div>
    <span class="hero-credit">Photo by the creator</span>
</div>
""", unsafe_allow_html=True)

# ── Content wrapper ───────────────────────────────────────────────────────────
st.markdown('<div class="content-wrap">', unsafe_allow_html=True)

st.divider()

col1, spacer, col2 = st.columns([5, 0.15, 6])


# ── Left Panel — The Brief ────────────────────────────────────────────────────
with col1:
    st.markdown('<span class="eyebrow">01 — The Brief</span>', unsafe_allow_html=True)
    st.markdown('<p class="section-title">Tell me about your shoot.</p>', unsafe_allow_html=True)

    shoot_type = st.selectbox(
        "Type of Shoot",
        ["Portrait", "Wedding", "Event", "Landscape", "Street", "Product",
         "Real Estate", "Fashion", "Wildlife", "Other"],
    )

    concept = st.text_area(
        f"Concept / Brief  (max {MAX_LENGTHS['concept']} chars)",
        placeholder="e.g. A moody editorial portrait series for a local musician. Dark, cinematic tones, industrial setting.",
        height=115,
        max_chars=MAX_LENGTHS["concept"],
    )

    col_a, col_b = st.columns(2)
    with col_a:
        location = st.text_input(
            f"Location  (max {MAX_LENGTHS['location']} chars)",
            placeholder="e.g. Brooklyn warehouse",
            max_chars=MAX_LENGTHS["location"],
        )
    with col_b:
        subjects = st.text_input(
            f"Subjects  (max {MAX_LENGTHS['subjects']} chars)",
            placeholder="e.g. 1 male, mid-30s",
            max_chars=MAX_LENGTHS["subjects"],
        )

    col_c, col_d = st.columns(2)
    with col_c:
        mood = st.selectbox(
            "Mood / Style",
            ["Moody & Dark", "Light & Airy", "Vibrant & Colorful", "Black & White",
             "Cinematic", "Documentary", "Editorial", "Natural & Candid"],
        )
    with col_d:
        duration = st.selectbox(
            "Duration",
            ["1 hour", "2 hours", "Half day (4 hrs)", "Full day (8 hrs)"],
        )

    extra_notes = st.text_area(
        f"Director's Notes  — optional  (max {MAX_LENGTHS['extra_notes']} chars)",
        placeholder="e.g. Hero shot needed for album cover. Client wants candid moments too.",
        height=90,
        max_chars=MAX_LENGTHS["extra_notes"],
    )

    generate_btn = st.button("Generate Shot List", type="primary", use_container_width=True)


# ── Column Divider ────────────────────────────────────────────────────────────
with spacer:
    st.markdown(
        '<div style="border-left:1px solid #2e2e2e; height:100%; min-height:640px;"></div>',
        unsafe_allow_html=True,
    )


# ── Right Panel — Output ──────────────────────────────────────────────────────
with col2:
    st.markdown('<span class="eyebrow">02 — Your Shot List</span>', unsafe_allow_html=True)
    st.markdown('<p class="section-title">Settings and recommendations.</p>', unsafe_allow_html=True)

    if generate_btn:
        # 1. Validate inputs before touching the API
        errors = validate_inputs(concept, location, subjects, extra_notes)
        if errors:
            for msg in errors:
                st.warning(msg)
            # Clear any previous result so a failed attempt doesn't show stale data
            st.session_state["result"] = None
            st.session_state["error"] = None
        else:
            prompt = build_prompt(
                shoot_type=shoot_type,
                concept=concept,
                location=location,
                subjects=subjects,
                mood=mood,
                duration=duration,
                extra_notes=extra_notes,
            )

            # 2. Call the AI — all error handling lives in the client module
            with st.spinner("Generating your shot list..."):
                try:
                    result = generate_shot_list(prompt)
                    st.session_state["result"] = result
                    st.session_state["shoot_type"] = shoot_type
                    st.session_state["error"] = None
                    logger.info("Shot list stored in session state for shoot type: %s", shoot_type)

                except FrameRateLimitError as exc:
                    st.session_state["error"] = str(exc)
                    st.session_state["result"] = None

                except FrameAuthError as exc:
                    st.session_state["error"] = str(exc)
                    st.session_state["result"] = None

                except FrameAIError as exc:
                    st.session_state["error"] = str(exc)
                    st.session_state["result"] = None

    # 3. Show error if the last generation failed
    if st.session_state["error"]:
        st.error(st.session_state["error"])

    # 4. Show result panel — persists across reruns via session_state
    if st.session_state["result"]:
        st.markdown('<div class="result-panel">', unsafe_allow_html=True)
        st.markdown(st.session_state["result"])
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        pdf_bytes = generate_pdf(st.session_state["result"], st.session_state["shoot_type"])
        filename = (
            f"frame_{st.session_state['shoot_type'].lower().replace(' ', '_')}_shot_list.pdf"
        )

        st.download_button(
            label="Export Shot List  —  Download as PDF",
            data=pdf_bytes,
            file_name=filename,
            mime="application/pdf",
            use_container_width=True,
        )

    elif not st.session_state["error"]:
        # No result and no error — show the empty state placeholder
        st.markdown("""
<div class="placeholder-panel">
    <span class="aperture">◎</span>
    <h4>Your shot list will appear here.</h4>
    <p class="sub">
        Fill in the brief on the left — concept, location, mood and duration —<br>
        then hit <strong style="color:#909090;">Generate Shot List</strong> to get started.
    </p>
    <ul class="placeholder-list">
        <li>Full numbered shot list with angles &amp; lighting notes</li>
        <li>Hero shots — the must-capture frames</li>
        <li>Lens &amp; gear recommendations</li>
        <li>Session timing &amp; structured flow</li>
        <li>Director's notes from a pro eye</li>
    </ul>
</div>
""", unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
