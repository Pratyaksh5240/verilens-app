"""VeriLens — AI-Assisted Misinformation & Credibility Screening Interface.

Streamlit frontend and orchestration layer.
"""

import html
import logging
import time
from typing import Dict, List, Optional, Tuple

import streamlit as st

from config import (
    CATALOG_LIMITATIONS_NOTE,
    RATE_LIMIT_COOLDOWN_SECONDS,
    RATE_LIMIT_MAX_PER_MINUTE,
    RECOGNIZED_OUTLETS,
    has_news_api_key,
    set_runtime_news_api_key,
)
from emotion import analyze_emotion
from extraction import extract_article_content
from scoring import analyze_credibility
from verification import clean_headline_title, verify_with_newsapi

# Configure root verilens logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("verilens.app")

# Page Configuration with proper real emoji favicon
st.set_page_config(
    page_title="VeriLens — Credibility & Misinformation Screener",
    page_icon="🛡️",
    layout="wide",
)


# --- Cached Network Helpers ---
@st.cache_data(show_spinner=False, ttl=1800)
def cached_extract_article(url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Cached wrapper around SSRF-safe article extraction."""
    return extract_article_content(url)


@st.cache_data(show_spinner=False, ttl=1800)
def cached_verify_newsapi(query: str) -> Tuple[List[Dict[str, object]], str, str]:
    """Cached wrapper around NewsAPI cross-verification."""
    return verify_with_newsapi(query)


# --- Session State & Rate Limiting ---
def initialize_session_state() -> None:
    """Ensure required session state keys are initialized."""
    defaults = {
        "news_api_key": "",
        "url_input": "",
        "user_text": "",
        "text_source_url": "",
        "text_outlet": "",
        "active_demo_case": "",
        "last_request_timestamp": 0.0,
        "request_history": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def check_rate_limit() -> Tuple[bool, Optional[str]]:
    """Verify that current session has not exceeded rate limits (anti-abuse / SSRF guard)."""
    now = time.time()
    last_time = float(st.session_state.get("last_request_timestamp", 0.0))

    if now - last_time < RATE_LIMIT_COOLDOWN_SECONDS:
        remaining = round(RATE_LIMIT_COOLDOWN_SECONDS - (now - last_time), 1)
        return False, f"Please wait {remaining}s before initiating another analysis (rate limit safeguard)."

    history: List[float] = st.session_state.get("request_history", [])
    recent_history = [t for t in history if now - t < 60.0]

    if len(recent_history) >= RATE_LIMIT_MAX_PER_MINUTE:
        return False, "Rate limit reached (max 15 requests per minute). Please pause before submitting more requests."

    recent_history.append(now)
    st.session_state["request_history"] = recent_history
    st.session_state["last_request_timestamp"] = now
    return True, None


def sanitize_html(text: Optional[str]) -> str:
    """Escape HTML entities in third-party strings to prevent injection."""
    return html.escape(str(text or "")).strip()


DEMO_CASES = [
    {
        "id": "official_url",
        "label": "Official Wire Article (URL)",
        "description": "Full URL extraction and live corroboration of an Associated Press report.",
        "mode": "url",
        "url": "https://apnews.com/article/86a91afa7be96d8821c7bbfed9e5a623",
    },
    {
        "id": "climate_summary",
        "label": "Science Summary Excerpt (Text)",
        "description": "Structured climate change reporting excerpt tested with outlet attribution.",
        "mode": "text",
        "text": (
            "Scientists reported that Arctic sea ice tied its lowest recorded winter maximum, continuing a long-term "
            "decline linked to global warming. Researchers said reduced ice cover means less sunlight is reflected "
            "away from Earth, allowing the ocean to absorb more heat and increasing climate risks."
        ),
        "outlet": "AP News",
    },
    {
        "id": "disaster_news",
        "label": "Earthquake Crisis (High Fear)",
        "description": "Legitimate high-emotion crisis reporting to demonstrate that fear does NOT degrade score.",
        "mode": "text",
        "text": (
            "A powerful 7.4-magnitude earthquake struck eastern Taiwan on Wednesday, killing at least nine people and "
            "injuring over 900. Rescue teams worked through the night to reach dozens of miners trapped in quarries, "
            "as terrified residents evacuated collapsed apartment blocks amid aftershocks."
        ),
        "outlet": "Reuters",
    },
    {
        "id": "conspiracy_forward",
        "label": "Risky Viral Forward (Manipulative)",
        "description": "Sensational forward with conspiracy wording, excessive punctuation, and urgency tactics.",
        "mode": "text",
        "text": (
            "SHOCKING ALERT!!! Share immediately before it is deleted! The government secretly introduced toxic "
            "chemicals into the water supply and the mainstream media is covering it up! They don't want you to know!"
        ),
        "outlet": "",
    },
]


def load_demo(case: Dict[str, str]) -> None:
    st.session_state["active_demo_case"] = case["id"]
    if case["mode"] == "url":
        st.session_state["url_input"] = case["url"]
        st.session_state["user_text"] = ""
        st.session_state["text_source_url"] = ""
        st.session_state["text_outlet"] = ""
    else:
        st.session_state["user_text"] = case["text"]
        st.session_state["text_source_url"] = ""
        st.session_state["text_outlet"] = case.get("outlet", "")
        st.session_state["url_input"] = ""


initialize_session_state()

# Sync runtime key from secrets if available
secret_key = ""
try:
    secret_key = str(st.secrets.get("NEWS_API_KEY", "")).strip()
except Exception:
    pass

session_key = str(st.session_state.get("news_api_key", "")).strip()
set_runtime_news_api_key(session_key or secret_key)


# --- Custom CSS Styling ---
st.markdown(
    """
    <style>
    :root {
        --bg-1: #051219;
        --bg-2: #0c2731;
        --bg-3: #16424f;
        --card: rgba(255, 255, 255, 0.06);
        --border: rgba(255, 255, 255, 0.12);
        --accent-1: #78f0ff;
        --accent-2: #8dffbf;
        --accent-3: #ffd36f;
        --text: #f5fbff;
        --muted: #bdd7df;
    }

    .stApp {
        background:
            radial-gradient(circle at 15% 20%, rgba(120, 240, 255, 0.14), transparent 30%),
            radial-gradient(circle at 85% 15%, rgba(255, 211, 111, 0.10), transparent 25%),
            radial-gradient(circle at 80% 82%, rgba(141, 255, 191, 0.10), transparent 30%),
            linear-gradient(145deg, var(--bg-1), var(--bg-2), var(--bg-3));
        color: var(--text);
        font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
    }

    h1, h2, h3, h4 { color: var(--text) !important; }

    .hero-title {
        text-align: center;
        font-size: 3rem;
        font-weight: 800;
        background: linear-gradient(90deg, var(--accent-1), var(--accent-2), var(--accent-3));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }

    .hero-sub {
        text-align: center;
        color: var(--muted);
        font-size: 1.05rem;
        max-width: 850px;
        margin: 0 auto 1.2rem;
        line-height: 1.5;
    }

    .disclaimer-banner {
        background: rgba(255, 211, 111, 0.08);
        border: 1px solid rgba(255, 211, 111, 0.28);
        border-radius: 14px;
        padding: 0.75rem 1.1rem;
        font-size: 0.90rem;
        color: #ffebb3;
        margin-bottom: 1.2rem;
        line-height: 1.45;
    }

    .status-banner-warning {
        background: rgba(255, 150, 100, 0.12);
        border: 1px solid rgba(255, 150, 100, 0.35);
        border-radius: 12px;
        padding: 0.65rem 1rem;
        font-size: 0.88rem;
        color: #ffd0b8;
        margin-bottom: 1rem;
    }

    .status-banner-success {
        background: rgba(141, 255, 191, 0.10);
        border: 1px solid rgba(141, 255, 191, 0.28);
        border-radius: 12px;
        padding: 0.65rem 1rem;
        font-size: 0.88rem;
        color: #c9ffdf;
        margin-bottom: 1rem;
    }

    .score-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid var(--border);
        border-radius: 18px;
        padding: 1.1rem 1.25rem;
        margin-bottom: 1rem;
    }

    .score-value {
        font-size: 2.8rem;
        font-weight: 800;
        line-height: 1.05;
        margin: 0.2rem 0;
    }

    .signal-card {
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 1rem;
        margin-bottom: 0.8rem;
        min-height: 160px;
    }

    .coverage-card {
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 0.85rem 1rem;
        margin-bottom: 0.75rem;
    }

    .chip {
        display: inline-flex;
        border-radius: 999px;
        padding: 0.22rem 0.65rem;
        font-size: 0.80rem;
        font-weight: 700;
        margin-right: 0.4rem;
        border: 1px solid rgba(255, 255, 255, 0.12);
    }
    .chip-good { background: rgba(141, 255, 191, 0.16); color: var(--accent-2); }
    .chip-warn { background: rgba(255, 211, 111, 0.16); color: var(--accent-3); }
    .chip-risk { background: rgba(255, 138, 138, 0.16); color: #ff9f9f; }

    .stButton > button {
        background: linear-gradient(90deg, var(--accent-1), var(--accent-2));
        color: #07131a;
        font-weight: 750;
        border: none;
        border-radius: 999px;
        padding: 0.6rem 1.2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Header
st.markdown("<div class='hero-title'>🛡️ VeriLens</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='hero-sub'>Professional-grade credibility screening with SSRF-protected extraction, "
    "linguistic manipulation checks, recognized newsroom directory matching, and live multi-source corroboration.</div>",
    unsafe_allow_html=True,
)

# Explicit, Persistent Disclaimer
st.markdown(
    """
    <div class='disclaimer-banner'>
        <strong>⚠️ Assistive Decision-Support Tool:</strong> VeriLens provides a heuristic credibility estimate
        based on open newsroom indicators, writing quality, and live search corroboration.
        <strong>It is not a final or automated fact-check verdict.</strong> Low scores reflect lack of verified
        evidence or sensationalist framing; always cross-verify high-stakes claims across multiple independent primary sources.
    </div>
    """,
    unsafe_allow_html=True,
)

# Sidebar
with st.sidebar:
    st.subheader("Verification Settings")
    if has_news_api_key():
        st.success("NewsAPI: Active")
    else:
        st.warning("NewsAPI: Unconfigured")

    with st.expander("API Key Configuration"):
        new_key = st.text_input("NewsAPI Key", value=st.session_state.get("news_api_key", ""), type="password")
        if st.button("Save Session Key", use_container_width=True):
            st.session_state["news_api_key"] = new_key.strip()
            set_runtime_news_api_key(new_key.strip())
            st.rerun()

    st.divider()
    st.subheader("Quick Demos")
    st.caption("Inspect standard verification scenarios:")
    for demo in DEMO_CASES:
        if st.button(demo["label"], key=f"btn_{demo['id']}", use_container_width=True):
            load_demo(demo)
            st.rerun()
        st.caption(demo["description"])

    st.divider()
    with st.expander("Directory & Limitations"):
        st.markdown(f"**Recognized Catalog:** {len(RECOGNIZED_OUTLETS)} newsrooms and wire services.")
        st.markdown(f"_{CATALOG_LIMITATIONS_NOTE}_")


# --- UI Reporting Functions ---
def render_analysis_dashboard(result: Dict[str, object], preview_text: str, title: Optional[str] = None) -> None:
    score = float(result["score"])
    verdict = sanitize_html(str(result["verdict"]))
    verdict_note = sanitize_html(str(result["verdict_note"]))

    # Model Mode Banner
    emotion_diag = result.get("emotion_diagnostics", {})
    if emotion_diag.get("is_ml"):
        st.markdown(
            f"<div class='status-banner-success'><strong>Active ML Pipeline:</strong> "
            f"{sanitize_html(str(emotion_diag.get('mode_description')))}</div>",
            unsafe_allow_html=True,
        )
    else:
        fallback_msg = sanitize_html(str(emotion_diag.get("fallback_reason") or "Model not loaded"))
        st.markdown(
            f"<div class='status-banner-warning'><strong>⚠️ ML Emotion Model Inactive:</strong> "
            f"Using keyword heuristic fallback. ({fallback_msg})</div>",
            unsafe_allow_html=True,
        )

    # Credibility Score Card
    st.markdown(
        f"""
        <div class="score-card">
            <div style="font-size:0.85rem; text-transform:uppercase; letter-spacing:0.08em; color:var(--muted);">Credibility Score</div>
            <div class="score-value">{score * 100:.0f}%</div>
            <div><strong>{verdict}</strong> — {verdict_note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.progress(score)

    # Metric Row
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Evidence & Attribution", f"{float(result['evidence_score']) * 100:.0f}%")
    c2.metric("Article Structure", f"{float(result['article_quality_score']) * 100:.0f}%")
    c3.metric("Live Corroboration", f"{float(result['corroboration_score']) * 100:.0f}%")

    # Emotional Intensity Diagnostic (Decoupled from Credibility Score)
    emotion_tone = str(emotion_diag.get("label", "neutral")).title()
    emotion_intensity = str(emotion_diag.get("intensity", "Low"))
    c4.metric(
        "Emotional Framing",
        f"{emotion_tone} ({emotion_intensity})",
        help="Diagnostic signal: emotional intensity is not penalized in the credibility score.",
    )

    if title:
        st.markdown(f"**Title:** {sanitize_html(title)}")
    if result.get("domain"):
        domain_label = "Recognized Publisher" if result["is_recognized"] else "Unlisted Domain"
        st.markdown(f"**Domain:** `{sanitize_html(result['domain'])}` ({domain_label})")

    # Explanation Tabs
    tab_why, tab_coverage, tab_emotion, tab_preview = st.tabs(
        ["Why This Score", "Live Coverage", "Emotional Tone Diagnostic", "Content Preview"]
    )

    with tab_why:
        left, right = st.columns(2)
        with left:
            st.markdown("#### Positive Indicators")
            signals = result.get("supportive_signals", [])
            if signals:
                for s in signals:
                    st.markdown(f"- {sanitize_html(s)}")
            else:
                st.caption("No strong positive indicators detected.")

        with right:
            st.markdown("#### Caution Flags")
            cautions = result.get("caution_flags", [])
            if cautions:
                for c in cautions:
                    st.markdown(f"- {sanitize_html(c)}")
            else:
                st.caption("No significant caution flags detected.")

        st.markdown("---")
        st.markdown("#### Score Component Breakdown")
        for name, value in result.get("breakdown", []):
            sign = "+" if value >= 0 else "-"
            st.markdown(f"- **{sanitize_html(name)}:** `{sign}{abs(value) * 100:.1f}%`")

    with tab_coverage:
        live_items = result.get("live_results", [])
        if not live_items:
            st.info("No live corroboration results found.")
        else:
            for item in live_items:
                m_label = sanitize_html(str(item.get("match_label")))
                chip_cls = (
                    "chip-good" if "Strong" in m_label else ("chip-warn" if "Possible" in m_label else "chip-risk")
                )
                raw_url = sanitize_html(str(item.get("url", "")))
                title_html = (
                    f"<a href='{raw_url}' target='_blank'>{sanitize_html(str(item.get('title')))}</a>"
                    if raw_url
                    else sanitize_html(str(item.get("title")))
                )

                chips = [
                    f"<span class='chip {chip_cls}'>{m_label} ({float(item.get('match_score', 0)) * 100:.0f}%)</span>"
                ]
                if item.get("recognized"):
                    chips.append("<span class='chip chip-good'>Recognized Outlet</span>")
                if item.get("debunk_hit"):
                    chips.append("<span class='chip chip-risk'>Debunk / Contradiction</span>")

                st.markdown(
                    f"""
                    <div class="coverage-card">
                        <div><strong>{title_html}</strong></div>
                        <div style="font-size:0.85rem; color:var(--muted); margin:0.3rem 0;">{sanitize_html(str(item.get('source')))} | {sanitize_html(str(item.get('domain')))}</div>
                        <div style="font-size:0.88rem; margin-bottom:0.4rem;">{sanitize_html(str(item.get('description')))}</div>
                        <div>{"".join(chips)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with tab_emotion:
        st.markdown("#### Emotional Framing & Tone Analysis")
        st.markdown(
            f"**Dominant Tone:** `{emotion_tone}` (Confidence: `{float(emotion_diag.get('score', 0.5)) * 100:.1f}%`)"
        )
        st.markdown(f"**Intensity Level:** `{emotion_intensity}`")
        st.markdown(f"**Analysis Method:** `{sanitize_html(str(emotion_diag.get('mode_description')))}`")
        st.info(sanitize_html(str(emotion_diag.get("diagnostics_note", ""))))

    with tab_preview:
        st.text_area("Extracted Text Preview", value=preview_text[:3000], height=200, disabled=True)


# --- Main Dual-Panel Input Layout ---
st.markdown("---")
col_url, col_text = st.columns(2, gap="large")

with col_url:
    st.subheader("1. URL Verification")
    st.caption("Fetch a published news article with SSRF safeguards, size limits, and live corroboration.")

    url_val = st.text_input("Article URL", key="url_input", placeholder="https://example.com/article...")
    btn_url = st.button("Analyze Article URL", use_container_width=True)

    if btn_url:
        can_proceed, limit_err = check_rate_limit()
        if not can_proceed:
            st.warning(limit_err)
        elif not url_val.strip():
            st.warning("Please enter a valid URL to analyze.")
        else:
            with st.spinner("Safely fetching article and analyzing credibility signals..."):
                title, text, err = cached_extract_article(url_val.strip())

            if err or not text:
                st.error(err or "Failed to extract article content.")
            else:
                # Live search corroboration
                query = clean_headline_title(title) if title else text[:180]
                live_articles, status_msg, used_query = cached_verify_newsapi(query)

                # Emotion inference
                emotion_res = analyze_emotion(text)

                # Credibility analysis
                analysis = analyze_credibility(
                    text=text,
                    source_url=url_val.strip(),
                    title=title,
                    live_results=live_articles,
                    emotion_data=emotion_res,
                )
                render_analysis_dashboard(analysis, text, title=title)

with col_text:
    st.subheader("2. Text & Claim Verification")
    st.caption("Paste a claim, message excerpt, or social forward for linguistic and evidence screening.")

    text_val = st.text_area(
        "Pasted Text / Message", height=150, key="user_text", placeholder="Paste article text or forwarded claim..."
    )
    opt_url = st.text_input("Optional Source URL", key="text_source_url", placeholder="https://...")
    opt_outlet = st.text_input("Optional Outlet Name", key="text_outlet", placeholder="Reuters, BBC, The Hindu...")

    btn_text = st.button("Analyze Pasted Text", use_container_width=True)

    if btn_text:
        can_proceed, limit_err = check_rate_limit()
        if not can_proceed:
            st.warning(limit_err)
        elif not text_val.strip():
            st.warning("Please enter some text to analyze.")
        else:
            with st.spinner("Analyzing text signals and querying corroborating reports..."):
                cleaned_lead = text_val.strip()[:200]
                live_articles, status_msg, used_query = cached_verify_newsapi(cleaned_lead)
                emotion_res = analyze_emotion(text_val.strip())
                analysis = analyze_credibility(
                    text=text_val.strip(),
                    source_url=opt_url.strip() or None,
                    source_hint=opt_outlet.strip() or None,
                    live_results=live_articles,
                    emotion_data=emotion_res,
                )
            render_analysis_dashboard(analysis, text_val.strip())
