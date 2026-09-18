"""Unit tests for scoring.py pure functions, decoupled emotion, and publisher directory lookup."""

from scoring import (
    analyze_credibility,
    analyze_writing_signals,
    build_verdict,
    compute_credibility_score,
    lookup_recognized_publisher,
)


def test_recognized_publisher_direct_domain_match():
    is_recognized, score, meta = lookup_recognized_publisher("reuters.com")
    assert is_recognized is True
    assert score == 1.00
    assert meta["category"] == "Wire Service"


def test_recognized_publisher_alias_match():
    is_recognized, score, meta = lookup_recognized_publisher(outlet_name="AP News")
    assert is_recognized is True
    assert score == 0.99
    assert meta["name"] == "Associated Press"


def test_unrecognized_domain():
    is_recognized, score, meta = lookup_recognized_publisher("random-blog-123.xyz")
    assert is_recognized is False
    assert score == 0.0
    assert meta is None


def test_emotion_is_decoupled_from_credibility_score():
    """Verify that emotional tone (e.g. fear during a disaster) does NOT penalize the credibility score."""
    sample_text = (
        "Officials confirmed that a 7.2-magnitude earthquake struck the coastal region on Tuesday, "
        "causing severe structural damage to over 40 buildings according to police reports."
    )

    # Result with fear
    result_fear = analyze_credibility(
        text=sample_text,
        source_url="https://reuters.com/world/earthquake",
        emotion_data={"label": "fear", "score": 0.95, "is_ml": True, "intensity": "High"},
    )

    # Result with neutral
    result_neutral = analyze_credibility(
        text=sample_text,
        source_url="https://reuters.com/world/earthquake",
        emotion_data={"label": "neutral", "score": 0.50, "is_ml": True, "intensity": "Low"},
    )

    # Result with joy
    result_joy = analyze_credibility(
        text=sample_text,
        source_url="https://reuters.com/world/earthquake",
        emotion_data={"label": "joy", "score": 0.88, "is_ml": True, "intensity": "High"},
    )

    # All three must receive the exact same credibility score because emotion is decoupled
    assert result_fear["score"] == result_neutral["score"] == result_joy["score"]
    assert result_fear["score"] >= 0.75  # Retains high credibility despite high fear


def test_debunk_penalty_lowers_score_and_sets_misinformation_verdict():
    score_clean, _ = compute_credibility_score(
        recognized_authority_score=0.0,
        has_live_data=True,
        corroboration_score=0.20,
        article_quality_score=0.30,
        evidence_score=0.10,
        writing_risk=0.10,
        debunk_penalty=0.0,
    )

    score_debunked, _ = compute_credibility_score(
        recognized_authority_score=0.0,
        has_live_data=True,
        corroboration_score=0.20,
        article_quality_score=0.30,
        evidence_score=0.10,
        writing_risk=0.10,
        debunk_penalty=0.30,
    )

    assert score_debunked < score_clean
    assert score_clean - score_debunked >= 0.25

    verdict, note = build_verdict(
        score=score_debunked,
        debunk_penalty=0.30,
        recognized_authority_score=0.0,
        article_quality_score=0.30,
        writing_risk=0.10,
    )
    assert verdict == "High Misinformation Risk"
    assert "debunked" in note.lower()


def test_writing_signals_detect_sensationalism_and_urgency():
    sensational_text = "SHOCKING ALERT!!! Share immediately before it is deleted! The secret plan was exposed!"
    signals = analyze_writing_signals(sensational_text)

    assert signals["risk_score"] > 0.40
    assert any("Sensational" in flag for flag in signals["risk_flags"])
    assert any("exclamation" in flag.lower() for flag in signals["risk_flags"])


def test_writing_signals_detect_journalistic_evidence():
    evidence_text = (
        "According to the official statement released on 14 March, data from the ministry showed "
        "a 15 percent increase across 4 districts as reported by authorities."
    )
    signals = analyze_writing_signals(evidence_text)

    assert signals["evidence_score"] > 0.30
    assert signals["risk_score"] == 0.0
    assert any("attribution" in s.lower() for s in signals["supportive_signals"])
    assert any("numeric" in s.lower() for s in signals["supportive_signals"])
