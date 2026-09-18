"""URL fetching and article text extraction with SSRF protection, size caps, and logging.

Security features:
- SSRF Defense: Resolves hostnames and validates all resolved IPs against private,
  loopback, link-local, multicast, and CGNAT IP ranges.
- Safe Redirect Handling: Manually tracks HTTP redirects, re-validating the resolved IP
  of each target URL prior to opening any new connection.
- Size Cap: Streams content and aborts downloads exceeding MAX_RESPONSE_BYTES (5 MB).
- Strict Timeouts: Enforces connect (3s) and read (7s) timeouts.
- Explicit Logging: Logs every rejection, network failure, and parser fallback with Python logging.
"""

import ipaddress
import logging
import re
import socket
from typing import List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from config import (
    CONNECT_TIMEOUT_SECONDS,
    MAX_REDIRECTS,
    MAX_RESPONSE_BYTES,
    READ_TIMEOUT_SECONDS,
    REQUEST_HEADERS,
)

logger = logging.getLogger("verilens.extraction")

# Additional private/special IPv4 networks not caught by is_private in all Python versions
CARRIER_GRADE_NAT = ipaddress.ip_network("100.64.0.0/10")
CURRENT_NETWORK_V4 = ipaddress.ip_network("0.0.0.0/8")


def is_ip_restricted(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check whether an IP address belongs to any private, loopback, link-local, or reserved range."""
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        return True

    if isinstance(ip, ipaddress.IPv4Address):
        if ip in CARRIER_GRADE_NAT or ip in CURRENT_NETWORK_V4:
            return True

    return False


def validate_url_for_ssrf(url: str) -> Tuple[bool, Optional[str]]:
    """Validate a URL against SSRF threats by inspecting scheme and resolving hostnames.

    Returns:
        Tuple[bool, Optional[str]]: (True, None) if safe, or (False, reason_message) if unsafe.
    """
    if not url or not isinstance(url, str):
        return False, "Empty or invalid URL provided."

    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower()

    if scheme not in ("http", "https"):
        return False, f"Unsupported scheme '{scheme}'. Only HTTP and HTTPS are permitted."

    hostname = parsed.hostname
    if not hostname:
        return False, "URL does not specify a valid hostname."

    # Reject embedded userinfo (e.g., http://user:pass@host)
    if parsed.username or parsed.password:
        return False, "URLs with embedded credentials are not permitted."

    port = parsed.port or (443 if scheme == "https" else 80)

    # Check if the hostname is a direct IP literal
    try:
        ip_obj = ipaddress.ip_address(hostname)
        if is_ip_restricted(ip_obj):
            logger.warning("SSRF check blocked direct IP literal: %s", hostname)
            return False, f"Access to restricted or private IP address '{hostname}' is blocked."
        return True, None
    except ValueError:
        # Not a direct IP literal, proceed to DNS resolution
        pass

    try:
        addr_info = socket.getaddrinfo(
            hostname,
            port,
            socket.AF_UNSPEC,
            socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        logger.warning("DNS resolution failed for %s: %s", hostname, exc)
        return False, f"Could not resolve domain name '{hostname}': {exc}"
    except Exception as exc:
        logger.error("Unexpected error during DNS resolution for %s: %s", hostname, exc)
        return False, f"DNS resolution error: {exc}"

    if not addr_info:
        return False, f"No IP addresses resolved for domain '{hostname}'."

    # Validate every resolved IP
    for family, _, _, _, sockaddr in addr_info:
        ip_str = sockaddr[0]
        try:
            resolved_ip = ipaddress.ip_address(ip_str)
            if is_ip_restricted(resolved_ip):
                logger.warning(
                    "SSRF check blocked resolved IP %s for hostname %s", ip_str, hostname
                )
                return False, f"Access to restricted IP range '{ip_str}' is blocked (SSRF safeguard)."
        except ValueError:
            return False, f"Resolved address '{ip_str}' is malformed."

    return True, None


def fetch_url_content_safely(url: str) -> Tuple[Optional[str], Optional[str]]:
    """Fetch URL body text with SSRF validation on every redirect hop and a streaming size cap.

    Returns:
        Tuple[Optional[str], Optional[str]]: (response_html, None) on success, or (None, error_message).
    """
    current_url = url.strip()
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)

    for hop in range(MAX_REDIRECTS + 1):
        is_safe, error_msg = validate_url_for_ssrf(current_url)
        if not is_safe:
            logger.warning("Aborting request at hop %d due to SSRF validation failure: %s", hop, error_msg)
            return None, error_msg

        try:
            response = session.get(
                current_url,
                stream=True,
                allow_redirects=False,
                timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
            )
        except requests.exceptions.Timeout as exc:
            logger.warning("Timeout while fetching %s: %s", current_url, exc)
            return None, "Connection timed out while contacting the server."
        except requests.exceptions.SSLError as exc:
            logger.warning("SSL verification failed for %s: %s", current_url, exc)
            return None, f"SSL verification failed: {exc}"
        except requests.exceptions.RequestException as exc:
            logger.warning("Network request failed for %s: %s", current_url, exc)
            return None, f"Could not connect to the remote server: {exc}"

        # Handle redirects manually to validate each target IP against SSRF
        if response.is_redirect or response.status_code in (301, 302, 303, 307, 308):
            redirect_target = response.headers.get("Location")
            if not redirect_target:
                return None, f"Server responded with redirect ({response.status_code}) but missing Location header."

            next_url = urljoin(current_url, redirect_target)
            logger.info("Following redirect (%d/%d): %s -> %s", hop + 1, MAX_REDIRECTS, current_url, next_url)
            current_url = next_url

            if hop >= MAX_REDIRECTS:
                logger.warning("Exceeded maximum redirect limit (%d hops) for %s", MAX_REDIRECTS, url)
                return None, f"Too many redirects (exceeded limit of {MAX_REDIRECTS})."
            continue

        if response.status_code != 200:
            logger.info("Server returned non-200 status code: %d for %s", response.status_code, current_url)
            return None, f"Server returned HTTP error status {response.status_code}."

        # Verify Content-Length header if present
        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) > MAX_RESPONSE_BYTES:
                    logger.warning(
                        "Aborting download: Content-Length %s exceeds limit %d bytes",
                        content_length,
                        MAX_RESPONSE_BYTES,
                    )
                    return None, f"Page size exceeds maximum allowed limit of {MAX_RESPONSE_BYTES // (1024 * 1024)}MB."
            except ValueError:
                pass

        # Stream response chunks up to MAX_RESPONSE_BYTES
        chunks: List[bytes] = []
        total_bytes = 0
        try:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    total_bytes += len(chunk)
                    if total_bytes > MAX_RESPONSE_BYTES:
                        logger.warning(
                            "Aborting download: stream exceeded %d bytes for %s",
                            MAX_RESPONSE_BYTES,
                            current_url,
                        )
                        return None, f"Page exceeded maximum allowed download size ({MAX_RESPONSE_BYTES // (1024 * 1024)}MB)."
                    chunks.append(chunk)
        except requests.exceptions.RequestException as exc:
            logger.warning("Stream read failed for %s: %s", current_url, exc)
            return None, f"Failed reading response stream: {exc}"

        raw_bytes = b"".join(chunks)
        encoding = response.encoding or response.apparent_encoding or "utf-8"
        try:
            return raw_bytes.decode(encoding, errors="replace"), None
        except Exception as exc:
            logger.error("Encoding decode error: %s", exc)
            return raw_bytes.decode("utf-8", errors="replace"), None

    return None, "Exceeded maximum redirect hops."


def normalize_whitespace(text: str) -> str:
    """Normalize internal whitespace and strip leading/trailing spaces."""
    return re.sub(r"\s+", " ", text or "").strip()


def find_meta_content(soup: BeautifulSoup, attribute_name: str, attribute_value: str) -> Optional[str]:
    """Extract content string from an HTML meta tag."""
    tag = soup.find("meta", attrs={attribute_name: attribute_value})
    if tag and tag.get("content"):
        return normalize_whitespace(str(tag["content"]))
    return None


def collect_paragraph_text(container: BeautifulSoup) -> str:
    """Extract text from paragraph tags inside a container."""
    paragraphs: List[str] = []
    for paragraph in container.find_all(["p", "h2", "h3"]):
        text = normalize_whitespace(paragraph.get_text(" ", strip=True))
        if len(text) >= 30:
            paragraphs.append(text)
    return " ".join(paragraphs)


def extract_article_content(url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Fetch an article URL safely and extract title, clean text content, and error message.

    Returns:
        Tuple[Optional[str], Optional[str], Optional[str]]: (title, article_text, error_message).
    """
    html_content, error_msg = fetch_url_content_safely(url)
    if error_msg or not html_content:
        return None, None, error_msg or "Failed to retrieve page content."

    try:
        soup = BeautifulSoup(html_content, "lxml")
    except Exception as exc:
        logger.info("lxml parser unavailable or failed, falling back to html.parser: %s", exc)
        soup = BeautifulSoup(html_content, "html.parser")

    # Strip script, styles, interactive and non-content tags
    for tag_name in ["script", "style", "noscript", "svg", "footer", "nav", "form", "aside", "header"]:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    title_candidates: List[Optional[str]] = [
        find_meta_content(soup, "property", "og:title"),
        find_meta_content(soup, "name", "twitter:title"),
    ]
    if soup.title and soup.title.text:
        title_candidates.append(normalize_whitespace(soup.title.text))
    if soup.find("h1"):
        title_candidates.append(normalize_whitespace(soup.find("h1").get_text(" ", strip=True)))

    title = next((c for c in title_candidates if c), "Untitled Article")

    # Select common semantic containers for news articles
    blocks: List[str] = []
    selectors = [
        "article",
        "main",
        "[itemprop='articleBody']",
        ".article-body",
        ".story-body",
        ".entry-content",
        ".post-content",
        ".main-content",
        "#article-body",
    ]
    for selector in selectors:
        for block in soup.select(selector):
            block_text = collect_paragraph_text(block)
            if len(block_text) > 180:
                blocks.append(block_text)

    article_text = max(blocks, key=len) if blocks else collect_paragraph_text(soup)

    if len(article_text) < 180:
        description = find_meta_content(soup, "name", "description") or find_meta_content(
            soup, "property", "og:description"
        )
        if description:
            article_text = normalize_whitespace(f"{title}. {description}")

    if len(article_text) < 80:
        logger.warning("Article text extraction yielded fewer than 80 characters for %s", url)
        return title, None, "Could not extract sufficient article text from the webpage."

    logger.info("Successfully extracted article (%d chars) from %s", len(article_text), url)
    return title, article_text, None
