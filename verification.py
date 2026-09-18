"""NewsAPI cross-verification client and query extraction engine.

Features:
- Title Cleaning: Unescapes HTML entities and strips site-name suffixes/prefixes and separators (| - — ::).
- Keyphrase Extraction: Extracts named entities, proper nouns, and substantive terms, filtering stopwords and news boilerplate.
- Robust Edge-Case Handling: Supports empty text, non-English scripts, pure punctuation, and short text without exceptions.
- NewsAPI Client: Queries the NewsAPI /everything endpoint with timeout and audit logging.
- Cross-Source Assessment: Computes match relevance, source domain diversity, and debunking cues.
"""

import html
import logging
import re
from difflib import SequenceMatcher
from typing import Dict, List, Set, Tuple
from urllib.parse import urlparse

import requests

from config import (
    CONNECT_TIMEOUT_SECONDS,
    DEBUNK_TERMS,
    OUTLET_ALIASES,
    QUERY_NOISE_TERMS,
    READ_TIMEOUT_SECONDS,
    RECOGNIZED_OUTLETS,
    REQUEST_HEADERS,
    STOPWORDS,
    get_news_api_key,
)

logger = logging.getLogger("verilens.verification")

# Regex to split on common headline/outlet separators: " - ", " | ", " — ", " – ", " :: ", " -- ", " » "
SEPARATOR_REGEX = re.compile(r"\s+(?:[:]{2}|[-|—–»•]|\/\/\/|--)\s+")


def clean_headline_title(raw_title: str) -> str:
    """Strip site-name boilerplate, HTML entities, and separator artifacts from headlines.

    Examples:
        'Arctic Ice Hits Historic Low | Reuters' -> 'Arctic Ice Hits Historic Low'
        'BBC News - Prime Minister Announces Budget' -> 'Prime Minister Announces Budget'
        'Secret Plan &quot;Exposed&quot; -- Breaking' -> 'Secret Plan "Exposed"'
    """
    if not raw_title or not isinstance(raw_title, str):
        return ""

    # Decode HTML entities (e.g., &quot;, &amp;, &#39;)
    cleaned = html.unescape(raw_title.strip())

    # Split on standard title separators
    parts = SEPARATOR_REGEX.split(cleaned)
    if len(parts) > 1:
        # Check if the first or last part is a recognized outlet name
        first_clean = parts[0].strip().lower()
        last_clean = parts[-1].strip().lower()

        if last_clean in OUTLET_ALIASES or any(alias in last_clean for alias in OUTLET_ALIASES):
            cleaned = " ".join(parts[:-1]).strip()
        elif first_clean in OUTLET_ALIASES or any(alias in first_clean for alias in OUTLET_ALIASES):
            cleaned = " ".join(parts[1:]).strip()
        else:
            # Fall back to picking the longest substantive part (the actual headline)
            cleaned = max(parts, key=lambda p: len(p.strip())).strip()

    # Strip any trailing or leading isolated separator characters
    cleaned = re.sub(r"^[\s\-|—–:»•]+|[\s\-|—–:»•]+$", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def extract_keywords_and_entities(text: str) -> List[str]:
    """Extract substantive keywords, proper noun sequences, and entities for search queries.

    Filters out stopwords and common journalism noise terms.
    """
    if not text or not isinstance(text, str):
        return []

    decoded = html.unescape(text)

    # 1. Look for capitalized multi-word sequences (Named Entities e.g., 'Arctic Sea Ice', 'Supreme Court')
    capitalized_sequences = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", decoded)

    # 2. Extract alphanumeric words
    tokens = re.findall(r"\b[A-Za-z0-9\u00C0-\u024F\u0400-\u04FF\u0900-\u097F'-]+\b", decoded)

    substantive_tokens: List[str] = []
    seen: Set[str] = set()

    for token in tokens:
        lower_token = token.lower().strip("'")
        if (
            len(lower_token) >= 3
            and lower_token not in STOPWORDS
            and lower_token not in QUERY_NOISE_TERMS
            and not lower_token.isdigit()
        ):
            if lower_token not in seen:
                seen.add(lower_token)
                substantive_tokens.append(token)

    # Prioritize capitalized multi-word phrases if present
    results: List[str] = []
    for seq in capitalized_sequences:
        seq_clean = seq.strip()
        if len(seq_clean.split()) <= 4 and seq_clean.lower() not in seen:
            results.append(seq_clean)

    results.extend(substantive_tokens)
    return results


def build_search_query(text: str, max_terms: int = 6) -> str:
    """Construct an optimized NewsAPI query from article title or text snippet.

    Strips boilerplate separators, extracts high-signal keyphrases, and falls back
    gracefully for edge cases (empty text, pure punctuation, non-English).
    """
    if not text or not text.strip():
        return ""

    cleaned_title = clean_headline_title(text)
    keywords = extract_keywords_and_entities(cleaned_title if cleaned_title else text)

    if not keywords:
        # Fall back to first non-empty word tokens if keyword filter was too strict
        raw_words = re.findall(r"\b\w+\b", text)
        return " ".join(raw_words[:max_terms])

    selected = keywords[:max_terms]
    return " ".join(selected)


def normalize_domain_name(url: str) -> str:
    """Extract normalized base domain from a URL string."""
    try:
        domain = urlparse(url).netloc.lower().strip()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def calculate_relevance_score(reference_text: str, candidate_text: str) -> float:
    """Calculate topical relevance between reference text and candidate news headline/snippet."""
    if not reference_text or not candidate_text:
        return 0.0

    ref_words = set(re.findall(r"\b\w+\b", reference_text.lower())) - STOPWORDS - QUERY_NOISE_TERMS
    cand_words = set(re.findall(r"\b\w+\b", candidate_text.lower())) - STOPWORDS - QUERY_NOISE_TERMS

    if not ref_words or not cand_words:
        return 0.0

    # Jaccard overlap on informative words
    intersection = ref_words & cand_words
    union = ref_words | cand_words
    jaccard = len(intersection) / max(len(union), 1)

    # String similarity on raw content
    seq_ratio = SequenceMatcher(None, reference_text.lower(), candidate_text.lower()).ratio()

    # Weighted combination
    combined = (jaccard * 0.70) + (seq_ratio * 0.30)
    return max(0.0, min(1.0, combined))


def assess_live_coverage(
    query_text: str,
    raw_articles: List[Dict[str, object]],
) -> Dict[str, object]:
    """Score matching news coverage for topical alignment, domain diversity, and debunking indicators."""
    processed_results: List[Dict[str, object]] = []
    seen_domains: Set[str] = set()
    recognized_domains_count = 0
    debunk_hits = 0

    total_match_score = 0.0

    for article in raw_articles:
        title = str(article.get("title") or "")
        desc = str(article.get("description") or "")
        url = str(article.get("url") or "")
        source_name = str(
            (article.get("source") or {}).get("name")
            if isinstance(article.get("source"), dict)
            else article.get("source", "Unknown")
        )
        domain = normalize_domain_name(url)

        combined_text = f"{title} {desc}".lower()
        match_score = calculate_relevance_score(query_text, f"{title} {desc}")

        # Check for debunking signals in this article
        is_debunk = any(term in combined_text for term in DEBUNK_TERMS)
        if is_debunk:
            debunk_hits += 1

        is_recognized = domain in RECOGNIZED_OUTLETS or any(alias in source_name.lower() for alias in OUTLET_ALIASES)
        if is_recognized and domain not in seen_domains:
            recognized_domains_count += 1

        if domain:
            seen_domains.add(domain)

        # Classify match quality
        if match_score >= 0.40:
            match_label = "Strong match"
        elif match_score >= 0.20:
            match_label = "Possible match"
        else:
            match_label = "Related topic"

        processed_results.append(
            {
                "title": title,
                "description": desc,
                "url": url,
                "source": source_name,
                "domain": domain,
                "match_score": round(match_score, 3),
                "match_label": match_label,
                "debunk_hit": is_debunk,
                "recognized": is_recognized,
            }
        )

        total_match_score += match_score

    n_results = len(raw_articles)
    avg_relevance = (total_match_score / n_results) if n_results > 0 else 0.0

    # Corroboration score incorporates relevance and source diversity
    corroboration_score = min(1.0, avg_relevance * 1.5)
    if recognized_domains_count >= 2:
        corroboration_score = min(1.0, corroboration_score + 0.15)
    elif recognized_domains_count == 1:
        corroboration_score = min(1.0, corroboration_score + 0.08)

    # Debunking penalty
    debunk_penalty = min(0.40, debunk_hits * 0.18)

    supportive_signals: List[str] = []
    caution_flags: List[str] = []

    if recognized_domains_count >= 2:
        supportive_signals.append(
            f"Corroborating coverage found across {len(seen_domains)} distinct domains including recognized newsrooms."
        )
    elif len(seen_domains) >= 2:
        supportive_signals.append(f"Related news reporting detected across {len(seen_domains)} distinct publishers.")

    if debunk_hits > 0:
        caution_flags.append(
            f"Debunking/fact-check terminology ('false', 'debunked', 'fact-check') appeared in {debunk_hits} matching news article(s)."
        )

    return {
        "corroboration_score": round(corroboration_score, 3),
        "debunk_penalty": round(debunk_penalty, 3),
        "distinct_domains_count": len(seen_domains),
        "recognized_domains_count": recognized_domains_count,
        "debunk_hits": debunk_hits,
        "processed_results": processed_results,
        "supportive_signals": supportive_signals,
        "caution_flags": caution_flags,
    }


def verify_with_newsapi(
    query_hint: str,
    page_size: int = 5,
) -> Tuple[List[Dict[str, object]], str, str]:
    """Query NewsAPI /v2/everything for matching coverage using clean query extraction.

    Returns:
        Tuple[List[Dict[str, object]], str, str]:
            (article_list, status_message, constructed_query)
    """
    api_key = get_news_api_key()
    if not api_key:
        logger.info("NewsAPI key not configured; skipping live cross-verification.")
        return [], "NewsAPI key is not configured.", ""

    active_query = build_search_query(query_hint)
    if not active_query:
        return [], "Could not generate a search query from the provided text.", ""

    endpoint = "https://newsapi.org/v2/everything"
    params = {
        "q": active_query,
        "pageSize": page_size,
        "sortBy": "relevancy",
        "language": "en",
        "apiKey": api_key,
    }

    try:
        logger.info("Querying NewsAPI with: '%s'", active_query)
        response = requests.get(
            endpoint,
            params=params,
            headers=REQUEST_HEADERS,
            timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
        )
        data = response.json()
    except requests.exceptions.Timeout as exc:
        logger.warning("NewsAPI request timed out: %s", exc)
        return [], "Live NewsAPI verification timed out.", active_query
    except requests.exceptions.RequestException as exc:
        logger.warning("NewsAPI request error: %s", exc)
        return [], f"NewsAPI connection error: {exc}", active_query
    except Exception as exc:
        logger.error("Unexpected error parsing NewsAPI response: %s", exc, exc_info=True)
        return [], "Failed to parse NewsAPI response.", active_query

    if response.status_code != 200 or data.get("status") != "ok":
        error_code = data.get("code", "unknown")
        error_message = data.get("message", "NewsAPI query failed.")
        logger.warning("NewsAPI responded with code %s: %s", error_code, error_message)
        return [], f"NewsAPI notice: {error_message}", active_query

    articles = data.get("articles", [])
    if not articles:
        return [], "No matching articles found on NewsAPI.", active_query

    logger.info("NewsAPI returned %d matching articles for '%s'", len(articles), active_query)
    return articles, "Live verification succeeded.", active_query
