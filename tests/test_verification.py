"""Unit tests for verification.py covering headline cleaning, keyphrase extraction, and NewsAPI client."""

import logging
from unittest.mock import MagicMock, patch

import pytest
import requests

from verification import (
    assess_live_coverage,
    build_search_query,
    calculate_relevance_score,
    clean_headline_title,
    extract_keywords_and_entities,
    verify_with_newsapi,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        (
            "Arctic Sea Ice Hits Historic Low | Reuters",
            "Arctic Sea Ice Hits Historic Low",
        ),
        (
            "BBC News - Prime Minister Announces Fiscal Plan",
            "Prime Minister Announces Fiscal Plan",
        ),
        (
            "Secret Plot &quot;Exposed&quot; — Breaking",
            'Secret Plot "Exposed"',
        ),
        (
            "Major Election Reform Bill Passed :: AP News",
            "Major Election Reform Bill Passed",
        ),
        (
            "Global Climate Summit Concludes • The Guardian",
            "Global Climate Summit Concludes",
        ),
        (
            "Headline With No Separator",
            "Headline With No Separator",
        ),
        (
            "",
            "",
        ),
    ],
)
def test_clean_headline_title(raw, expected):
    assert clean_headline_title(raw) == expected


def test_extract_keywords_filters_stopwords_and_noise():
    text = "The officials reported that the scientists said latest updates show breaking news in Geneva."
    keywords = extract_keywords_and_entities(text)
    # Noise words (reported, scientists, said, latest, updates, breaking, news) and stopwords must be filtered
    assert "Geneva" in keywords
    assert "reported" not in [k.lower() for k in keywords]
    assert "breaking" not in [k.lower() for k in keywords]


def test_extract_keywords_handles_edge_cases():
    # Empty string
    assert extract_keywords_and_entities("") == []
    # Pure punctuation
    assert extract_keywords_and_entities("??? !!! --- ... ///") == []
    # Non-English script (Hindi / Devanagari)
    hindi_text = "भारत मौसम विज्ञान विभाग ने चक्रवात की चेतावनी जारी की"
    extracted_hindi = extract_keywords_and_entities(hindi_text)
    assert len(extracted_hindi) > 0  # Extracted without encoding exception
    # Accented European text
    french_text = "L'Assemblée nationale a voté la nouvelle loi énergétique hier à Paris."
    extracted_french = extract_keywords_and_entities(french_text)
    assert len(extracted_french) > 0


def test_build_search_query_with_title_and_noise():
    title = "Historic Arctic Sea Ice Decline Linked to Global Warming | AP News"
    query = build_search_query(title, max_terms=5)
    assert "Arctic Sea Ice" in query or "Arctic" in query
    assert len(query.split()) <= 6


def test_calculate_relevance_score_between_topical_texts():
    score_high = calculate_relevance_score(
        "Taiwan earthquake eastern county rescue efforts",
        "Taiwan earthquake rescue teams search collapsed buildings in eastern county",
    )
    score_low = calculate_relevance_score(
        "Taiwan earthquake eastern county rescue efforts",
        "Celebrity red carpet fashion show opens in Los Angeles",
    )
    assert score_high > 0.40
    assert score_low < 0.10


def test_assess_live_coverage_detects_debunking_and_applies_penalty():
    mock_articles = [
        {
            "title": "Fact check: Viral claim that lemon water cures cancer is debunked",
            "description": "Medical experts confirm this viral health claim is false and unsupported.",
            "url": "https://factcheck.org/claims/lemon-cure",
            "source": {"name": "FactCheck.org"},
        },
        {
            "title": "Snopes investigates miracle lemon water cancer cure rumors",
            "description": "We found this claim to be completely unproven and misleading.",
            "url": "https://snopes.com/fact-check/lemon-water",
            "source": {"name": "Snopes"},
        },
    ]

    assessment = assess_live_coverage("lemon water cures cancer", mock_articles)

    assert assessment["debunk_hits"] >= 2
    assert assessment["debunk_penalty"] > 0.20
    assert any("debunk" in flag.lower() for flag in assessment["caution_flags"])


def test_verify_with_newsapi_missing_key_returns_graceful_notice():
    with patch("verification.get_news_api_key", return_value=""):
        articles, status, query = verify_with_newsapi("sample headline")
        assert articles == []
        assert "not configured" in status.lower()


def test_verify_with_newsapi_network_timeout_logs_and_returns_message(caplog):
    with patch("verification.get_news_api_key", return_value="test-api-key"):
        with patch("requests.get", side_effect=requests.exceptions.Timeout("Connection timed out")):
            with caplog.at_level(logging.WARNING, logger="verilens.verification"):
                articles, status, query = verify_with_newsapi("Arctic ice melt")
                assert articles == []
                assert "timed out" in status.lower()
                assert any("timed out" in rec.message.lower() for rec in caplog.records)
