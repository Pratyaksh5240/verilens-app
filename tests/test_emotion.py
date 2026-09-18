"""Unit tests for emotion.py covering model inference, top_k=None compatibility, fallback, and logging."""

import logging
from unittest.mock import MagicMock, patch

import pytest
from emotion import (
    analyze_emotion,
    detect_emotion_fallback,
    get_emotion_intensity,
)


def test_analyze_emotion_empty_text():
    res = analyze_emotion("")
    assert res["label"] == "neutral"
    assert res["intensity"] == "Low"
    assert res["is_ml"] is False


def test_fallback_detects_fear_keywords():
    label, score = detect_emotion_fallback("A deadly crisis and terrifying danger threatens the region with severe panic.")
    assert label == "fear"
    assert score >= 0.70


def test_fallback_detects_anger_keywords():
    label, score = detect_emotion_fallback("Shocking corrupt fraud and outrage exposed in shameless scandal!")
    assert label == "anger"
    assert score >= 0.70


def test_fallback_returns_neutral_for_objective_text():
    label, score = detect_emotion_fallback("The committee reviewed the three proposals submitted by the engineering team.")
    assert label == "neutral"
    assert score == 0.50


def test_emotion_intensity_levels():
    assert get_emotion_intensity("neutral", 0.90) == "Low"
    assert get_emotion_intensity("fear", 0.85) == "High"
    assert get_emotion_intensity("anger", 0.60) == "Moderate"
    assert get_emotion_intensity("joy", 0.40) == "Low"


def test_analyze_emotion_with_mocked_transformer_pipeline():
    """Verify that predictions from pipeline(..., top_k=None) are parsed correctly."""
    mock_pipeline = MagicMock()
    mock_pipeline.return_value = [
        [
            {"label": "fear", "score": 0.88},
            {"label": "anger", "score": 0.05},
            {"label": "neutral", "score": 0.07},
        ]
    ]

    with patch("emotion.load_emotion_pipeline", return_value=mock_pipeline):
        res = analyze_emotion("Trapped residents were evacuated amid continuing aftershocks.")

        assert res["is_ml"] is True
        assert res["label"] == "fear"
        assert res["score"] == 0.88
        assert res["intensity"] == "High"
        assert "DistilRoBERTa" in res["mode_description"]
        assert res["fallback_reason"] is None


def test_analyze_emotion_logs_and_falls_back_on_inference_error(caplog):
    """Verify that exceptions during inference are logged with error level and fall back cleanly."""
    mock_pipeline = MagicMock()
    mock_pipeline.side_effect = RuntimeError("CUDA out of memory or tensor dimension mismatch")

    with patch("emotion.load_emotion_pipeline", return_value=mock_pipeline):
        with caplog.at_level(logging.ERROR, logger="verilens.emotion"):
            res = analyze_emotion("Terrible panic and danger in the area.")

            # Exception must not propagate to user
            assert res["is_ml"] is False
            assert "Keyword Heuristic Fallback" in res["mode_description"]
            assert "Inference failure" in res["fallback_reason"]
            assert res["label"] == "fear"  # Caught by heuristic

            # Confirm logging occurred
            assert any("Transformer inference failed" in record.message for record in caplog.records)
