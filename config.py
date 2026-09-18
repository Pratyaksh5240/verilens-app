"""Configuration, constants, lexicons, and recognized publisher catalog for VeriLens.

This module contains:
- Networking and security parameters (SSRF safeguards, timeouts, size caps).
- A structured, defensible recognized publisher directory with clear category metadata.
- Lexicons for evidence cues, sensationalism, conspiracy phrasing, and debunking signals.
- Environment and runtime configuration helpers for NewsAPI.
"""

import os
from typing import Dict, List, Optional, Set

# --- Networking & Security Limits ---
MAX_RESPONSE_BYTES: int = 5 * 1024 * 1024  # 5 MB maximum page size
CONNECT_TIMEOUT_SECONDS: float = 3.0
READ_TIMEOUT_SECONDS: float = 7.0
MAX_REDIRECTS: int = 5

# --- Rate Limiting (per-session anti-abuse) ---
RATE_LIMIT_COOLDOWN_SECONDS: float = 2.0
RATE_LIMIT_MAX_PER_MINUTE: int = 15

DEFAULT_USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 (VeriLens/2.0)"
)

REQUEST_HEADERS: Dict[str, str] = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# --- Runtime NewsAPI Key State ---
_RUNTIME_NEWS_API_KEY: str = ""


def set_runtime_news_api_key(api_key: Optional[str]) -> None:
    """Set an in-memory runtime API key (e.g. entered via session UI)."""
    global _RUNTIME_NEWS_API_KEY
    _RUNTIME_NEWS_API_KEY = (api_key or "").strip()


def get_news_api_key() -> str:
    """Retrieve NewsAPI key, checking runtime session first, then environment."""
    return _RUNTIME_NEWS_API_KEY or os.getenv("NEWS_API_KEY", "").strip()


def has_news_api_key() -> bool:
    """Check whether a non-empty NewsAPI key is configured."""
    return bool(get_news_api_key())


# --- Defensible Recognized Publisher Directory ---
# Transparent catalog of well-documented wire services, public broadcasters,
# IFCN-signatory fact-checkers, and established national/international newsrooms.
# Reframed from an absolute "truth whitelist" to a structured directory of recognized outlets.
CATALOG_LIMITATIONS_NOTE: str = (
    "The recognized outlet catalog is a curated reference list based on international wire services, "
    "IFCN-certified fact-checkers, and established newsrooms. It is non-exhaustive, predominantly English-language, "
    "and presence or absence does not constitute an endorsement or final verdict."
)

RECOGNIZED_OUTLETS: Dict[str, Dict[str, object]] = {
    # Wire Services
    "reuters.com": {
        "name": "Reuters",
        "category": "Wire Service",
        "authority_score": 1.00,
        "description": "Global news agency and financial data provider.",
    },
    "apnews.com": {
        "name": "Associated Press",
        "category": "Wire Service",
        "authority_score": 0.99,
        "description": "Global non-profit news cooperative headquartered in New York.",
    },
    "afp.com": {
        "name": "Agence France-Presse",
        "category": "Wire Service",
        "authority_score": 0.98,
        "description": "International news agency headquartered in Paris.",
    },
    # Fact-Checking Organizations (IFCN Signatories)
    "factcheck.org": {
        "name": "FactCheck.org",
        "category": "Fact-Checker",
        "authority_score": 0.99,
        "description": "Nonpartisan, nonprofit consumer advocate for voters (Annenberg Public Policy Center).",
    },
    "snopes.com": {
        "name": "Snopes",
        "category": "Fact-Checker",
        "authority_score": 0.96,
        "description": "Independent fact-checking and urban legend investigation platform.",
    },
    "politifact.com": {
        "name": "PolitiFact",
        "category": "Fact-Checker",
        "authority_score": 0.97,
        "description": "Pulitzer-winning fact-checking initiative by Poynter Institute.",
    },
    "fullfact.org": {
        "name": "Full Fact",
        "category": "Fact-Checker",
        "authority_score": 0.97,
        "description": "Independent UK fact-checking charity.",
    },
    # Public Broadcasters
    "bbc.com": {
        "name": "BBC News",
        "category": "Public Broadcaster",
        "authority_score": 0.98,
        "description": "British public service broadcaster.",
    },
    "bbc.co.uk": {
        "name": "BBC News (UK)",
        "category": "Public Broadcaster",
        "authority_score": 0.98,
        "description": "British public service broadcaster UK portal.",
    },
    "npr.org": {
        "name": "NPR",
        "category": "Public Broadcaster",
        "authority_score": 0.97,
        "description": "National Public Radio public broadcasting syndicate.",
    },
    "pbs.org": {
        "name": "PBS NewsHour",
        "category": "Public Broadcaster",
        "authority_score": 0.96,
        "description": "Public Broadcasting Service newsroom.",
    },
    "dw.com": {
        "name": "Deutsche Welle",
        "category": "Public Broadcaster",
        "authority_score": 0.95,
        "description": "German international public broadcaster.",
    },
    "cbc.ca": {
        "name": "CBC News",
        "category": "Public Broadcaster",
        "authority_score": 0.95,
        "description": "Canadian Broadcasting Corporation news division.",
    },
    "abc.net.au": {
        "name": "ABC News Australia",
        "category": "Public Broadcaster",
        "authority_score": 0.95,
        "description": "Australian Broadcasting Corporation.",
    },
    # International Health & Scientific Agencies
    "who.int": {
        "name": "World Health Organization",
        "category": "Health Authority",
        "authority_score": 1.00,
        "description": "United Nations specialized agency for international public health.",
    },
    "cdc.gov": {
        "name": "CDC",
        "category": "Health Authority",
        "authority_score": 0.98,
        "description": "US national public health institute.",
    },
    # Established International & National Newsrooms
    "theguardian.com": {
        "name": "The Guardian",
        "category": "Major Daily",
        "authority_score": 0.95,
        "description": "Independent UK news organization owned by the Scott Trust.",
    },
    "nytimes.com": {
        "name": "The New York Times",
        "category": "Major Daily",
        "authority_score": 0.96,
        "description": "US national newspaper of record.",
    },
    "washingtonpost.com": {
        "name": "The Washington Post",
        "category": "Major Daily",
        "authority_score": 0.95,
        "description": "US national daily newspaper.",
    },
    "wsj.com": {
        "name": "The Wall Street Journal",
        "category": "Major Daily",
        "authority_score": 0.96,
        "description": "International business and financial daily newspaper.",
    },
    "ft.com": {
        "name": "Financial Times",
        "category": "Major Daily",
        "authority_score": 0.96,
        "description": "International business and economic daily newspaper.",
    },
    "aljazeera.com": {
        "name": "Al Jazeera English",
        "category": "Major Daily",
        "authority_score": 0.94,
        "description": "International news broadcaster based in Doha, Qatar.",
    },
    "thehindu.com": {
        "name": "The Hindu",
        "category": "Major Daily",
        "authority_score": 0.95,
        "description": "Established Indian English-language national daily newspaper.",
    },
    "indianexpress.com": {
        "name": "The Indian Express",
        "category": "Major Daily",
        "authority_score": 0.94,
        "description": "Major Indian English-language investigative newspaper.",
    },
    "hindustantimes.com": {
        "name": "Hindustan Times",
        "category": "Major Daily",
        "authority_score": 0.92,
        "description": "Indian English-language daily newspaper.",
    },
    "livemint.com": {
        "name": "Mint",
        "category": "Financial News",
        "authority_score": 0.92,
        "description": "Indian business and financial daily publication.",
    },
    "economictimes.indiatimes.com": {
        "name": "The Economic Times",
        "category": "Financial News",
        "authority_score": 0.91,
        "description": "Indian business daily published by the Times Group.",
    },
    "economictimes.com": {
        "name": "The Economic Times",
        "category": "Financial News",
        "authority_score": 0.91,
        "description": "Indian business daily alternative portal.",
    },
    "timesofindia.indiatimes.com": {
        "name": "The Times of India",
        "category": "Major Daily",
        "authority_score": 0.90,
        "description": "Indian English-language daily newspaper.",
    },
    "timesofindia.com": {
        "name": "The Times of India",
        "category": "Major Daily",
        "authority_score": 0.90,
        "description": "Indian English-language daily alternative portal.",
    },
    "ndtv.com": {
        "name": "NDTV",
        "category": "Broadcaster",
        "authority_score": 0.90,
        "description": "Indian television media and online news network.",
    },
    "nature.com": {
        "name": "Nature",
        "category": "Scientific Journal",
        "authority_score": 1.00,
        "description": "Peer-reviewed international scientific journal.",
    },
    "sciencemag.org": {
        "name": "Science",
        "category": "Scientific Journal",
        "authority_score": 1.00,
        "description": "Peer-reviewed academic journal of the AAAS.",
    },
}

OUTLET_ALIASES: Dict[str, str] = {
    "reuters": "reuters.com",
    "ap": "apnews.com",
    "ap news": "apnews.com",
    "associated press": "apnews.com",
    "afp": "afp.com",
    "bbc": "bbc.com",
    "bbc news": "bbc.com",
    "npr": "npr.org",
    "pbs": "pbs.org",
    "pbs news": "pbs.org",
    "pbs newshour": "pbs.org",
    "dw": "dw.com",
    "deutsche welle": "dw.com",
    "cbc": "cbc.ca",
    "cbc news": "cbc.ca",
    "abc australia": "abc.net.au",
    "new york times": "nytimes.com",
    "nyt": "nytimes.com",
    "washington post": "washingtonpost.com",
    "wapo": "washingtonpost.com",
    "wall street journal": "wsj.com",
    "wsj": "wsj.com",
    "financial times": "ft.com",
    "ft": "ft.com",
    "the guardian": "theguardian.com",
    "guardian": "theguardian.com",
    "al jazeera": "aljazeera.com",
    "the hindu": "thehindu.com",
    "indian express": "indianexpress.com",
    "hindustan times": "hindustantimes.com",
    "ht": "hindustantimes.com",
    "mint": "livemint.com",
    "livemint": "livemint.com",
    "ndtv": "ndtv.com",
    "economic times": "economictimes.indiatimes.com",
    "times of india": "timesofindia.indiatimes.com",
    "toi": "timesofindia.indiatimes.com",
    "factcheck": "factcheck.org",
    "factcheck.org": "factcheck.org",
    "snopes": "snopes.com",
    "politifact": "politifact.com",
    "full fact": "fullfact.org",
    "nature": "nature.com",
    "science": "sciencemag.org",
    "who": "who.int",
    "world health organization": "who.int",
    "cdc": "cdc.gov",
}

# --- Lexicons for Text Credibility Signals ---
SENSATIONAL_PATTERNS: List[str] = [
    "shocking",
    "miracle cure",
    "they don't want you to know",
    "hidden truth",
    "exposed",
    "secret plan",
    "share immediately",
    "before it is deleted",
    "before it's deleted",
    "wake up",
    "mainstream media won't tell you",
    "you won't believe",
    "mind-blowing",
    "unbelievable",
    "100% guaranteed",
    "conspiracy",
    "cover-up",
    "censored",
    "banned by",
    "spread this",
    "forward to everyone",
]

CONSPIRACY_PATTERNS: List[str] = [
    "deep state",
    "shadow government",
    "microchip",
    "depopulation",
    "globalist agenda",
    "fake pandemic",
    "plandemic",
    "bioweapon leak covered up",
    "secret cure suppressed",
    "chemtrails",
    "new world order",
]

EVIDENCE_PATTERNS: List[str] = [
    "according to",
    "official statement",
    "spokesperson said",
    "press release",
    "data showed",
    "study published",
    "peer-reviewed",
    "ministry of",
    "department of",
    "reuters reported",
    "ap reported",
    "court filing",
    "police said",
    "investigators found",
    "financial report",
    "census data",
    "regulatory filing",
    "clinical trial",
]

DEBUNK_TERMS: Set[str] = {
    "debunked",
    "debunks",
    "false",
    "hoax",
    "fact check",
    "fact-check",
    "unproven",
    "misleading",
    "fabricated",
    "scam",
    "disproven",
    "unsubstantiated",
}

STOPWORDS: Set[str] = {
    "a",
    "about",
    "above",
    "after",
    "again",
    "against",
    "all",
    "also",
    "am",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "below",
    "between",
    "both",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "doing",
    "down",
    "during",
    "each",
    "few",
    "for",
    "from",
    "further",
    "had",
    "has",
    "have",
    "having",
    "he",
    "her",
    "here",
    "hers",
    "herself",
    "him",
    "himself",
    "his",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "itself",
    "just",
    "me",
    "more",
    "most",
    "my",
    "myself",
    "no",
    "nor",
    "not",
    "now",
    "of",
    "off",
    "on",
    "once",
    "only",
    "or",
    "other",
    "our",
    "ours",
    "out",
    "over",
    "own",
    "same",
    "she",
    "should",
    "so",
    "some",
    "such",
    "than",
    "that",
    "the",
    "their",
    "theirs",
    "them",
    "themselves",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "very",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "while",
    "who",
    "whom",
    "why",
    "with",
    "would",
    "you",
    "your",
    "yours",
    "yourself",
    "yourselves",
}

QUERY_NOISE_TERMS: Set[str] = {
    "breaking",
    "exclusive",
    "watch",
    "live",
    "updates",
    "reported",
    "report",
    "reports",
    "researchers",
    "researcher",
    "scientists",
    "scientist",
    "officials",
    "official",
    "experts",
    "expert",
    "said",
    "says",
    "say",
    "according",
    "continuing",
    "continued",
    "linked",
    "allowing",
    "means",
    "increasing",
    "reduced",
    "lowest",
    "recorded",
    "share",
    "immediately",
    "delete",
    "deleted",
    "reveals",
    "exposed",
    "latest",
    "news",
    "today",
    "yesterday",
}
