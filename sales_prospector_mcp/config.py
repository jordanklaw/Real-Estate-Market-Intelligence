"""Configuration for Sales Prospector MCP server."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Base paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
BRIEFS_DIR = BASE_DIR.parent / "briefs"

# Ensure directories exist
BRIEFS_DIR.mkdir(exist_ok=True)

# Territory regions
TERRITORY_REGIONS = {
    "northeast": ["NY", "NJ"],
    "mid_atlantic": ["MD", "DE", "DC", "VA", "WV", "PA"],
    "southeast": ["NC", "SC", "GA", "FL"],
    "south_central": ["TX", "OK", "AR", "LA", "MS", "AL", "TN", "KY"],
    "midwest_covered": ["OH", "IN", "MO", "IA", "NE", "KS"],
}

# Hard exclusions - never surface these states in any tool
EXCLUDED_STATES = {"IL", "MN", "MI", "WI"}

# All covered states (flat set for quick lookup)
COVERED_STATES = set()
for states in TERRITORY_REGIONS.values():
    COVERED_STATES.update(states)

# State to region mapping
STATE_TO_REGION = {}
for region, states in TERRITORY_REGIONS.items():
    for state in states:
        STATE_TO_REGION[state] = region

# News sources
NEWS_SOURCES = {
    "mhn": {
        "name": "Multi-Housing News",
        "base_url": "https://www.multihousingnews.com",
        "feed_url": "https://www.multihousingnews.com/news/",
    },
    "cpe": {
        "name": "Commercial Property Executive",
        "base_url": "https://www.commercialsearch.com",
        "feed_url": "https://www.commercialsearch.com/news/",
    },
}

# Urgency tier keywords
URGENCY_KEYWORDS = {
    "URGENT": [
        "eviction", "rent control", "rate announcement", "acquisition",
        "merger", "legislation", "ban", "moratorium", "regulation",
        "ordinance", "mandate", "emergency", "crisis",
    ],
    "THIS_WEEK": [
        "vacancy", "market shift", "policy proposal", "trend",
        "construction", "development", "pipeline", "investment",
        "occupancy", "rent growth", "supply",
    ],
    "FYI": [],  # Default tier - anything not matching above
}

# LLM configuration
# No Anthropic fallback by default. See llm_client.py for remote provider pattern.
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:14b")

# News cache settings
NEWS_CACHE_MAX_AGE_HOURS = 24

# Daily brief settings
DAILY_BRIEF_RECIPIENT = os.environ.get("DAILY_BRIEF_RECIPIENT", "")
DAILY_BRIEF_TOP_N = 5

# Deal stage weights for scoring
DEAL_STAGE_WEIGHTS = {
    "prospect": 1,
    "discovery": 3,
    "demo": 5,
    "proposal": 7,
    "negotiation": 9,
    "closed": 0,
}

# Meeting types
MEETING_TYPES = ["discovery", "demo", "follow_up", "negotiation", "renewal"]

# Email types
EMAIL_TYPES = ["outreach", "follow_up", "re_engage", "pricing", "value_add"]
