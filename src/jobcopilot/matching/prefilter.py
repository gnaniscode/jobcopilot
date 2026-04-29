"""Cheap pre-scoring filter: only score jobs that look genuinely relevant.

Strategy: instead of trying to enumerate every BAD role to exclude, we
list the roles a Python/AI backend engineer should consider. If the title
doesn't match anything in the inclusion list, we skip without paying for
LLM scoring. Saves ~70% of API cost.
"""
from jobcopilot.sources.schemas import Job


USER_COUNTRY = "United States"

# Title keywords that suggest a potentially relevant role.
# Lowercase, substring match. Be generous here — false positives just cost
# pennies; false negatives mean missing a great job.
RELEVANT_TITLE_KEYWORDS = (
    # Core engineering
    "python", "backend", "back-end", "back end",
    "fullstack", "full-stack", "full stack",
    "software engineer", "software developer",
    "platform engineer", "infrastructure engineer",
    "api engineer", "services engineer",
    # AI / ML
    "ai engineer", "ml engineer", "machine learning",
    "applied ai", "applied scientist", "applied ml",
    "genai", "gen ai", "llm",
    "ai/ml", "ml/ai", "ai platform", "ml platform",
    "ai infrastructure", "ml infrastructure",
    # Data
    "data engineer", "data platform",
    # Adjacent
    "developer experience", "devx",
    "site reliability", "sre",
    "cloud engineer", "devops",
)


def _looks_relevant(title: str) -> bool:
    title_lower = title.lower()
    return any(kw in title_lower for kw in RELEVANT_TITLE_KEYWORDS)


import re

# US state codes (the "CA" problem: Canada also contains 'CA' as substring)
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
}

# Match ", XX" where XX is exactly two letters at a word boundary
_STATE_PATTERN = re.compile(r",\s*([A-Z]{2})\b")

# Country names that should be excluded even if a US-like substring matches
NON_US_COUNTRIES = (
    "canada", "uk", "united kingdom", "ireland", "germany", "france",
    "india", "japan", "korea", "singapore", "australia", "brazil",
    "mexico", "spain", "italy", "netherlands", "poland", "china",
    "remote - emea", "remote - apac", "remote - latam", "remote - europe",
)


def _location_ok(job: Job) -> bool:
    """User is US-based. Accept US locations or remote-US, exclude others."""
    location_raw = job.location.raw or ""
    location_lower = location_raw.lower()

    # Hard-exclude obvious non-US countries even if other patterns match
    if any(country in location_lower for country in NON_US_COUNTRIES):
        return False

    # Remote roles: only accept if explicitly US-friendly
    if job.location.remote or "remote" in location_lower:
        # Generic "Remote" with no other info → assume US-friendly
        if location_lower.strip() in ("remote", "remote - global", ""):
            return True
        # If the string says "Remote - USA" or "Remote, US" → ok
        us_remote_signals = ("remote - usa", "remote, usa", "remote us", "remote, united states")
        if any(sig in location_lower for sig in us_remote_signals):
            return True
        # Otherwise (e.g. "Remote - Canada", "Remote - EMEA") → not ok
        # already filtered above, but defensive
        return "united states" in location_lower or "usa" in location_lower

    # Non-remote: look for explicit US signals
    if "united states" in location_lower or "usa" in location_lower or "u.s." in location_lower:
        return True

    # Look for ", XX" pattern where XX is a US state code (case-sensitive on the original)
    matches = _STATE_PATTERN.findall(location_raw)
    if any(m in US_STATES for m in matches):
        return True

    # Fall back to known US cities (handles cases where state isn't included)
    us_cities = (
        "san francisco", "new york", "seattle", "austin", "boston",
        "los angeles", "chicago", "denver", "atlanta", "miami",
        "san jose", "palo alto", "mountain view", "menlo park",
        "redmond", "bellevue", "raleigh", "durham", "philadelphia",
        "washington, d.c.", "washington dc",
    )
    return any(city in location_lower for city in us_cities)
    """User is US-based. Accept US locations or remote."""
    if job.location.remote:
        return True
    location_lower = (job.location.raw or "").lower()
    us_signals = (
        "united states", "usa", "u.s.", "us-", " us ",
        "remote - usa", "remote, usa", "remote us",
        ", tx", ", ca", ", ny", ", wa", ", il", ", ma", ", co", ", ga",
        "san francisco", "new york", "seattle", "austin", "boston",
        "los angeles", "chicago", "denver", "atlanta", "remote",
    )
    return any(sig in location_lower for sig in us_signals)


def should_skip(job: Job) -> tuple[bool, str]:
    """Return (skip, reason). Reason is empty if not skipped."""
    if not _looks_relevant(job.title):
        return True, f"title not relevant: '{job.title}'"

    if not _location_ok(job):
        return True, f"location not US-based or remote: '{job.location.raw}'"

    return False, ""