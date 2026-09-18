"""Unit tests for config.py constants, limits, and recognized publisher catalog."""

from config import (
    CONNECT_TIMEOUT_SECONDS,
    MAX_REDIRECTS,
    MAX_RESPONSE_BYTES,
    OUTLET_ALIASES,
    READ_TIMEOUT_SECONDS,
    RECOGNIZED_OUTLETS,
    get_news_api_key,
    has_news_api_key,
    set_runtime_news_api_key,
)


def test_security_limits_configured():
    assert MAX_RESPONSE_BYTES == 5 * 1024 * 1024
    assert CONNECT_TIMEOUT_SECONDS <= 5.0
    assert READ_TIMEOUT_SECONDS <= 10.0
    assert MAX_REDIRECTS == 5


def test_recognized_outlets_structure():
    assert len(RECOGNIZED_OUTLETS) >= 20
    for domain, meta in RECOGNIZED_OUTLETS.items():
        assert "name" in meta
        assert "category" in meta
        assert "authority_score" in meta
        assert 0.80 <= meta["authority_score"] <= 1.00


def test_outlet_aliases_map_to_catalog():
    for alias, domain in OUTLET_ALIASES.items():
        assert domain in RECOGNIZED_OUTLETS, f"Alias {alias} points to unknown domain {domain}"


def test_runtime_news_api_key_lifecycle():
    set_runtime_news_api_key("temporary-test-key")
    assert get_news_api_key() == "temporary-test-key"
    assert has_news_api_key() is True

    set_runtime_news_api_key("")
