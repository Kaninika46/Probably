"""Hedge word thresholds, segment synonyms, country aliases and intent phrases.

Follows CLAUDE.md section 7.9:
- Hedge words map to published probability scales (IPCC AR5 likelihood scale and
  Sherman Kent's Words of Estimative Probability).
- Segment synonyms map plain-English phrases to the five confirmed S3 segments.
"""

from src import config

# Copy of the hedge lexicon from src/config.py (single source of truth).
# Maps phrase -> (comparison_operator, probability_threshold).
HEDGE_LEXICON: dict[str, tuple[str, float]] = dict(config.HEDGE_THRESHOLDS)

# Longer multi-word hedges must be matched before single-word substrings
# (e.g. "very likely" before "likely", "almost certainly" before "certainly").
ORDERED_HEDGE_PHRASES: list[str] = sorted(
    HEDGE_LEXICON.keys(),
    key=lambda phrase: (-len(phrase.split()), -len(phrase)),
)

# Plain-English synonyms -> canonical segment name in `segments`
SEGMENT_SYNONYMS: dict[str, str] = {
    "champions": "Champions",
    "champion": "Champions",
    "best customers": "Champions",
    "top spenders": "Champions",
    "highest value": "Champions",
    "high-value": "Champions",
    "high value": "Champions",
    "vip": "Champions",
    "loyal": "Loyal",
    "loyal customers": "Loyal",
    "regular": "Loyal",
    "regular customers": "Loyal",
    "repeat buyers": "Loyal",
    "repeat customers": "Loyal",
    "at-risk": "At-Risk",
    "at risk": "At-Risk",
    "slipping": "At-Risk",
    "fading": "At-Risk",
    "cooling off": "At-Risk",
    "new": "New",
    "new customers": "New",
    "newcomers": "New",
    "recent buyers": "New",
    "recent customers": "New",
    "first-time": "New",
    "hibernating": "Hibernating",
    "dormant": "Hibernating",
    "sleeping": "Hibernating",
    "long inactive": "Hibernating",
}

# Common country shorthands -> exact country name in `customers.country`
COUNTRY_ALIASES: dict[str, str] = {
    "uk": "United Kingdom",
    "u.k.": "United Kingdom",
    "britain": "United Kingdom",
    "great britain": "United Kingdom",
    "england": "United Kingdom",
    "ireland": "EIRE",
    "republic of ireland": "EIRE",
    "eire": "EIRE",
    "usa": "USA",
    "united states": "USA",
    "u.s.": "USA",
    "u.s.a.": "USA",
    "rsa": "RSA",
    "south africa": "RSA",
    "uae": "United Arab Emirates",
}

# Phrases that indicate the 90-day lapse predicate
LAPSE_PHRASES: list[str] = [
    "lapse in the next 90 days",
    "lapse in 90 days",
    "no purchase in 90 days",
    "not purchase",
    "stop buying",
    "go quiet",
    "go inactive",
    "lapsing",
    "lapse risk",
    "lapse",
]

# Phrases that indicate Q2 (boundary / uncertain customers)
BOUNDARY_PHRASES: list[str] = [
    "boundary customers",
    "boundary cases",
    "borderline customers",
    "borderline cases",
    "uncertain segment",
    "uncertain membership",
    "uncertain customers",
    "ambiguous customers",
    "between segments",
    "hard to classify",
    "low confidence",
    "boundary",
    "borderline",
]

# Phrases that indicate Q3 (expected segment size / count)
EXPECTED_SIZE_PHRASES: list[str] = [
    "expected segment size",
    "expected segment sizes",
    "expected size",
    "expected sizes",
    "expected number of customers",
    "expected customer count",
    "expected count",
    "how many customers per segment",
    "how many customers in each segment",
    "segment sizes",
    "size of each segment",
    "count per segment",
]

# Phrases that indicate Q4 (expected revenue / spend per segment)
EXPECTED_REVENUE_PHRASES: list[str] = [
    "expected revenue",
    "expected spend",
    "expected sales",
    "expected monetary",
    "revenue per segment",
    "revenue by segment",
    "spend per segment",
    "spend by segment",
    "total expected revenue",
]

# Words that indicate an out-of-scope or unsafe query
OUT_OF_SCOPE_PHRASES: list[str] = [
    "drop table",
    "delete from",
    "insert into",
    "update customers",
    "alter table",
    "truncate",
    "1=1",
    "1 = 1",
    "--",
    "stock code",
    "stock_code",
    "sku",
    "product description",
    "which product",
    "best selling product",
    "postage",
    "weather",
    "stock price",
    "share price",
    "profit margin",
    "employee",
    "salary",
    "password",
]

SUPPORTED_EXAMPLE = (
    "Try a question such as: "
    "'Which customers in Germany are probably Champions?', "
    "'Show the top 10 Loyal customers', "
    "'Which boundary customers have uncertain segment membership?', "
    "'What is the expected revenue per segment?', or "
    "'Which probable At-Risk customers will likely lapse?'"
)


def lookup_hedge(phrase: str) -> tuple[str, float]:
    """Return (operator, threshold) for a hedge phrase (case-insensitive)."""
    key = phrase.strip().lower()
    if key not in HEDGE_LEXICON:
        raise KeyError(f"Unknown hedge phrase: {phrase!r}")
    return HEDGE_LEXICON[key]
