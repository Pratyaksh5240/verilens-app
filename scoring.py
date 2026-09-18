"""Pure, testable credibility scoring engine for VeriLens.

Key methodology features:
- Decoupled Emotion: Emotional tone and intensity are treated as an editorial framing diagnostic
  and are NOT penalized in the credibility score, preventing disaster/crisis reporting from being penalized.
- Defensible Source Recognition: Reframes binary domain trust as recognized publisher directory lookup
  with transparent categories (wire service, fact-checker, public broadcaster, major daily).
- Transparent Breakdown: Provides an exact contribution breakdown of recognized authority, corroboration,
  article structure, evidence cues, and writing risk.
- Pure Functions: Zero Streamlit imports, fully deterministic and unit-testable.
"""

import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from config import (
    CATALOG_LIMITATIONS_NOTE,
    CONSPIRACY_PATTERNS,
    EVIDENCE_PATTERNS,
    OUTLET_ALIASES,
    RECOGNIZED_OUTLETS,
    SENSATIONAL_PATTERNS,
)


def split_sentences(text: str) -> List[str]:
    """Split text into sentences using standard punctuation boundaries."""
    raw = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [s.strip() for s in raw if s.strip()]


def extract_domain(url: Optional[str]) -> str:
    """Extract normalized base domain from a URL."""
    if not url:
        return ""
    try:
        domain = urlparse(url.strip()).netloc.lower().strip()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def lookup_recognized_publisher(
    domain: Optional[str] = None,
    outlet_name: Optional[str] = None,
) -> Tuple[bool, float, Optional[Dict[str, object]]]:
    """Check whether a domain or outlet name is in the recognized publisher catalog.

    Returns:
        Tuple[bool, float, Optional[Dict[str, object]]]:
            (is_recognized, authority_score, publisher_metadata_dict)
    """
    clean_domain = (domain or "").lower().strip()
    if clean_domain.startswith("www."):
        clean_domain = clean_domain[4:]

    # Direct domain match
    if clean_domain and clean_domain in RECOGNIZED_OUTLETS:
        entry = RECOGNIZED_OUTLETS[clean_domain]
        return True, float(entry["authority_score"]), entry

    # Subdomain match (e.g. edition.cnn.com -> cnn.com)
    if clean_domain:
        for known_domain, entry in RECOGNIZED_OUTLETS.items():
            if clean_domain.endswith("." + known_domain):
                return True, float(entry["authority_score"]), entry

    # Alias / name match
    if outlet_name:
        clean_alias = outlet_name.lower().strip()
        matched_domain = OUTLET_ALIASES.get(clean_alias)
        if matched_domain and matched_domain in RECOGNIZED_OUTLETS:
            entry = RECOGNIZED_OUTLETS[matched_domain]
            return True, float(entry["authority_score"]), entry

    return False, 0.0, None


def analyze_writing_signals(text: str) -> Dict[str, object]:
    """Analyze linguistic credibility cues, evidence indicators, and manipulation risks."""
    clean_text = (text or "").strip()
    lowered = clean_text.lower()
    words = re.findall(r"\b[\w'-]+\b", clean_text)
    total_words = max(len(words), 1)

    sensational_hits = [p for p in SENSATIONAL_PATTERNS if p in lowered]
    conspiracy_hits = [p for p in CONSPIRACY_PATTERNS if p in lowered]
    evidence_hits = [p for p in EVIDENCE_PATTERNS if p in lowered]

    punctuation_bursts = re.findall(r"[!?]{2,}", clean_text)
    caps_words = [w for w in words if len(w) >= 4 and w.isupper() and not w.isdigit()]

    attribution_matches = re.findall(
        r"\b(according to|said|stated|reported|confirmed|announced|told|data|study|survey|records?)\b",
        lowered,
    )
    numeric_matches = re.findall(r"\b\d[\d,.:/-]*\b", clean_text)
    hedging_matches = re.findall(
        r"\b(alleged|preliminary|unconfirmed|reportedly|may|might|could|appears)\b",
        lowered,
    )

    # Calculate evidence score (0.0 to 1.0)
    evidence_score = 0.0
    if attribution_matches:
        evidence_score += min(0.35, len(attribution_matches) * 0.08)
    if numeric_matches:
        evidence_score += min(0.25, len(numeric_matches) * 0.05)
    if evidence_hits:
        evidence_score += min(0.30, len(evidence_hits) * 0.12)
    if hedging_matches:
        evidence_score += min(0.10, len(hedging_matches) * 0.03)

    evidence_score = min(1.0, evidence_score)

    # Calculate manipulation risk score (0.0 to 1.0)
    risk_score = 0.0
    if sensational_hits:
        risk_score += min(0.45, len(sensational_hits) * 0.22)
    if conspiracy_hits:
        risk_score += min(0.50, len(conspiracy_hits) * 0.30)
    if punctuation_bursts:
        risk_score += min(0.25, len(punctuation_bursts) * 0.10)
    if len(caps_words) >= 2:
        risk_score += min(0.25, len(caps_words) * 0.06)

    risk_score = min(1.0, risk_score)

    # Calculate article structural quality
    quality_score = 0.20
    if len(words) >= 40:
        quality_score += 0.20
    if len(words) >= 120:
        quality_score += 0.25
    if len(split_sentences(clean_text)) >= 3:
        quality_score += 0.15
    if attribution_matches:
        quality_score += 0.10
    if numeric_matches:
        quality_score += 0.10

    article_quality_score = min(1.0, quality_score)

    supportive_signals: List[str] = []
    risk_flags: List[str] = []

    if attribution_matches:
        supportive_signals.append(f"Contains {len(attribution_matches)} direct attribution phrase(s) ('said', 'reported', 'according to').")
    if numeric_matches:
        supportive_signals.append(f"Includes {len(numeric_matches)} concrete numeric references or dates.")
    if evidence_hits:
        supportive_signals.append("Uses formal journalistic evidence patterns (official statements, published data).")

    if sensational_hits:
        risk_flags.append(f"Sensational or urgent forwarding phrasing detected: {', '.join(sensational_hits[:3])}.")
    if conspiracy_hits:
        risk_flags.append(f"Conspiracy framing detected: {', '.join(conspiracy_hits[:2])}.")
    if punctuation_bursts:
        risk_flags.append("Repeated exclamation or question marks indicating emotional pressure.")
    if len(caps_words) >= 2:
        risk_flags.append(f"Multiple all-caps words ({', '.join(caps_words[:3])}) indicating shouting tone.")

    return {
        "evidence_score": round(evidence_score, 3),
        "risk_score": round(risk_score, 3),
        "article_quality_score": round(article_quality_score, 3),
        "attribution_count": len(attribution_matches),
        "numeric_count": len(numeric_matches),
        "sensational_hits": sensational_hits,
        "conspiracy_hits": conspiracy_hits,
        "supportive_signals": supportive_signals,
        "risk_flags": risk_flags,
    }


def compute_credibility_score(
    recognized_authority_score: float,
    has_live_data: bool,
    corroboration_score: float,
    article_quality_score: float,
    evidence_score: float,
    writing_risk: float,
    debunk_penalty: float = 0.0,
) -> Tuple[float, List[Tuple[str, float]]]:
    """Compute overall credibility score (0.0 to 1.0) and detailed itemized breakdown.

    Methodological principle: Emotional tone is decoupled from credibility scoring and is
    NOT penalized, preserving accurate scoring on valid disaster/crisis journalism.
    """
    base_score = 0.15
    breakdown: List[Tuple[str, float]] = []

    # Source authority contribution (up to 38%)
    source_contribution = recognized_authority_score * 0.38
    # Article structure & length quality (up to 18%)
    quality_contribution = article_quality_score * 0.18
    # Live corroboration across outlets (up to 18% if live data available, else 0.08)
    corrob_weight = 0.18 if has_live_data else 0.08
    corroboration_contribution = corroboration_score * corrob_weight
    # Evidence cues (attribution, numbers, data) (up to 18%)
    evidence_contribution = evidence_score * 0.18
    # Writing quality / lack of manipulation signals (up to 20%)
    writing_contribution = (1.0 - writing_risk) * 0.20

    score = (
        base_score
        + source_contribution
        + quality_contribution
        + corroboration_contribution
        + evidence_contribution
        + writing_contribution
    )

    if recognized_authority_score > 0.0:
        breakdown.append(("Recognized publisher authority", source_contribution))

    breakdown.extend([
        ("Article structure quality", quality_contribution),
        ("Cross-source corroboration", corroboration_contribution),
        ("Evidence & attribution cues", evidence_contribution),
        ("Writing quality (low manipulation)", writing_contribution),
    ])

    # Neutral presentation adjustment: distinguishes calm, unverified claims from manipulative forwards
    if recognized_authority_score == 0.0 and writing_risk <= 0.05:
        neutral_boost = 0.12
        score += neutral_boost
        breakdown.append(("Calm unverified phrasing adjustment", neutral_boost))

    # Recognized publisher consistency bonus
    if recognized_authority_score >= 0.90 and article_quality_score >= 0.55 and writing_risk <= 0.25:
        bonus = 0.10 if not has_live_data else 0.05
        score += bonus
        breakdown.append(("Established newsroom bonus", bonus))

    # Structured claim/summary bonus for non-recognized texts that display formal journalism cues
    if recognized_authority_score == 0.0 and article_quality_score >= 0.30 and evidence_score >= 0.12 and writing_risk <= 0.10:
        structured_bonus = 0.12 if not has_live_data else 0.06
        score += structured_bonus
        breakdown.append(("Structured reporting bonus", structured_bonus))

    # Subtract debunking penalty if matching coverage points to a known debunk
    if debunk_penalty > 0.0:
        score -= debunk_penalty
        breakdown.append(("Debunking coverage penalty", -debunk_penalty))

    final_score = max(0.0, min(1.0, score))
    return round(final_score, 3), [(k, round(v, 3)) for k, v in breakdown]


def build_verdict(
    score: float,
    debunk_penalty: float,
    recognized_authority_score: float,
    article_quality_score: float,
    writing_risk: float,
) -> Tuple[str, str]:
    """Generate a high-level verdict label and actionable explanatory note."""
    if debunk_penalty >= 0.20 and score < 0.50:
        return "High Misinformation Risk", "Related news reporting indicates this claim has been debunked or contested."

    if writing_risk >= 0.50:
        return "High Manipulation Risk", "Language displays heavy sensationalism, emotional pressure, or conspiracy framing."

    if recognized_authority_score >= 0.90 and article_quality_score >= 0.60 and score >= 0.85:
        return "Recognized Publisher Article", "Published by an established newsroom or fact-checker with solid reporting structure."

    if score >= 0.65:
        return "Likely Credible Reporting", "Displays characteristic evidence cues and low manipulation risk. Verify source link if unattached."

    if score >= 0.45:
        return "Unverified Claim / Needs Context", "Language is plausible, but independent corroboration or source verification is missing."

    return "Low Credibility / Verify Before Forwarding", "Caution signals outweigh evidence cues. Avoid sharing without cross-checking."


def analyze_credibility(
    text: str,
    source_url: Optional[str] = None,
    source_hint: Optional[str] = None,
    title: Optional[str] = None,
    live_results: Optional[List[Dict[str, object]]] = None,
    emotion_data: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """Run the complete credibility analysis pipeline on an article or text forward.

    Pure function with no UI or Streamlit dependencies.
    """
    domain = extract_domain(source_url)
    is_recognized, authority_score, publisher_meta = lookup_recognized_publisher(
        domain=domain,
        outlet_name=source_hint,
    )

    writing_stats = analyze_writing_signals(text)

    # Process live corroboration results if provided
    has_live = bool(live_results)
    corroboration_score = 0.0
    debunk_penalty = 0.0
    live_items: List[Dict[str, object]] = []
    coverage_support_signals: List[str] = []
    coverage_caution_flags: List[str] = []

    if live_results:
        from verification import assess_live_coverage
        assessment = assess_live_coverage(title or text[:200], live_results)
        corroboration_score = float(assessment["corroboration_score"])
        debunk_penalty = float(assessment["debunk_penalty"])
        live_items = assessment["processed_results"]
        coverage_support_signals = assessment["supportive_signals"]
        coverage_caution_flags = assessment["caution_flags"]

    score, breakdown = compute_credibility_score(
        recognized_authority_score=authority_score,
        has_live_data=has_live,
        corroboration_score=corroboration_score,
        article_quality_score=float(writing_stats["article_quality_score"]),
        evidence_score=float(writing_stats["evidence_score"]),
        writing_risk=float(writing_stats["risk_score"]),
        debunk_penalty=debunk_penalty,
    )

    verdict, verdict_note = build_verdict(
        score=score,
        debunk_penalty=debunk_penalty,
        recognized_authority_score=authority_score,
        article_quality_score=float(writing_stats["article_quality_score"]),
        writing_risk=float(writing_stats["risk_score"]),
    )

    # Aggregate signals
    all_supportive = list(writing_stats["supportive_signals"]) + coverage_support_signals
    all_cautions = list(writing_stats["risk_flags"]) + coverage_caution_flags

    if is_recognized and publisher_meta:
        all_supportive.insert(
            0,
            f"Publisher matched recognized directory: {publisher_meta['name']} ({publisher_meta['category']}).",
        )
    elif domain:
        all_cautions.append(f"Domain '{domain}' is not in our recognized newsroom catalog.")

    # Format emotion diagnostics (decoupled from score)
    emotion_info = emotion_data or {
        "label": "neutral",
        "score": 0.50,
        "is_ml": False,
        "mode_description": "None",
        "fallback_reason": None,
        "intensity": "Low",
        "diagnostics_note": "No emotion data provided.",
    }

    return {
        "score": score,
        "verdict": verdict,
        "verdict_note": verdict_note,
        "breakdown": breakdown,
        "domain": domain,
        "is_recognized": is_recognized,
        "publisher_metadata": publisher_meta,
        "catalog_limitations_note": CATALOG_LIMITATIONS_NOTE,
        "authority_score": authority_score,
        "evidence_score": float(writing_stats["evidence_score"]),
        "article_quality_score": float(writing_stats["article_quality_score"]),
        "writing_risk_score": float(writing_stats["risk_score"]),
        "corroboration_score": corroboration_score,
        "debunk_penalty": debunk_penalty,
        "supportive_signals": all_supportive,
        "caution_flags": all_cautions,
        "live_results": live_items,
        "emotion_diagnostics": emotion_info,
    }
