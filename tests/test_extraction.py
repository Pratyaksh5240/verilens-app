"""Unit tests for extraction.py covering SSRF defense, streaming size cap, and article extraction."""

from unittest.mock import MagicMock, patch

import pytest

from extraction import (
    extract_article_content,
    fetch_url_content_safely,
    validate_url_for_ssrf,
)


@pytest.mark.parametrize(
    "unsafe_url",
    [
        "http://127.0.0.1:8000/internal",
        "http://127.0.0.2:80/secret",
        "http://10.0.0.1/status",
        "http://192.168.1.1/admin",
        "http://172.16.0.10/api",
        "http://169.254.169.254/latest/meta-data",  # Cloud metadata service
        "http://0.0.0.0:8000",
        "http://100.64.0.1",  # CGNAT
        "http://localhost:3000",
    ],
)
def test_ssrf_rejects_private_and_loopback_ips(unsafe_url):
    is_safe, error_msg = validate_url_for_ssrf(unsafe_url)
    assert is_safe is False
    assert error_msg is not None
    assert any(term in error_msg.lower() for term in ["blocked", "restricted", "private", "ssrf", "local", "loopback"])


@pytest.mark.parametrize(
    "disallowed_scheme_url",
    [
        "file:///etc/passwd",
        "ftp://ftp.example.com/files",
        "gopher://127.0.0.1:6379",
        "data:text/html,<h1>Hello</h1>",
        "javascript:alert(1)",
    ],
)
def test_ssrf_rejects_non_http_schemes(disallowed_scheme_url):
    is_safe, error_msg = validate_url_for_ssrf(disallowed_scheme_url)
    assert is_safe is False
    assert "only http and https" in error_msg.lower() or "unsupported scheme" in error_msg.lower()


def test_ssrf_rejects_embedded_credentials():
    is_safe, error_msg = validate_url_for_ssrf("http://admin:secret@example.com/dashboard")
    assert is_safe is False
    assert "credentials" in error_msg.lower()


def test_streaming_size_cap_aborts_oversized_download():
    """Verify that downloads exceeding MAX_RESPONSE_BYTES (5MB) are aborted."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.is_redirect = False
    mock_response.headers = {"Content-Length": "10000000"}  # 10MB header

    with patch("extraction.validate_url_for_ssrf", return_value=(True, None)):
        with patch("requests.Session.get", return_value=mock_response):
            html, err = fetch_url_content_safely("https://example.com/huge-file.html")
            assert html is None
            assert err is not None
            assert "exceeds maximum allowed limit" in err.lower()


def test_streaming_chunk_accumulator_aborts_past_limit():
    """Verify stream abortion when Content-Length is missing but streamed bytes exceed 5MB."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.is_redirect = False
    mock_response.headers = {}
    # Yield 6MB in chunks of 1MB
    mock_response.iter_content.return_value = [b"A" * (1024 * 1024) for _ in range(6)]

    with patch("extraction.validate_url_for_ssrf", return_value=(True, None)):
        with patch("requests.Session.get", return_value=mock_response):
            html, err = fetch_url_content_safely("https://example.com/chunked-stream")
            assert html is None
            assert "exceeded maximum allowed download size" in err.lower()


def test_article_extraction_parses_semantic_body_and_strips_scripts():
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Major Scientific Discovery Announced - News Outlet</title>
        <meta property="og:title" content="Major Scientific Discovery Announced" />
        <script>var tracking = "malicious or noisy";</script>
        <style>body { font-size: 14px; }</style>
    </head>
    <body>
        <nav><a href="/">Home</a><a href="/news">News</a></nav>
        <article class="article-body">
            <h1>Major Scientific Discovery Announced</h1>
            <p>Researchers at the international consortium published findings today confirming a breakthrough.</p>
            <p>The study spanned five years and included observations from twelve global astronomical observatories.</p>
            <p>Officials stated that the new data will be made publicly available for peer review starting next week.</p>
        </article>
        <footer>Copyright 2026. All rights reserved.</footer>
    </body>
    </html>
    """

    with patch("extraction.fetch_url_content_safely", return_value=(sample_html, None)):
        title, text, error = extract_article_content("https://example.com/news/breakthrough")

        assert error is None
        assert title == "Major Scientific Discovery Announced"
        assert "breakthrough" in text.lower()
        assert "tracking" not in text  # script content stripped
        assert "copyright" not in text  # footer stripped
