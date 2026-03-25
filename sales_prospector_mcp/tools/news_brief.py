"""Tool 1: Sales News Brief - scrapes MHN and CPE, categorizes articles."""

import json
from datetime import datetime, timezone
from pathlib import Path

from sales_prospector_mcp.config import DATA_DIR, NEWS_CACHE_MAX_AGE_HOURS, EXCLUDED_STATES
from sales_prospector_mcp.utils.web_scraper import scrape_news_sources
from sales_prospector_mcp.utils.formatter import format_news_brief

CACHE_FILE = DATA_DIR / "news_cache.json"


def _load_cache() -> dict:
    """Load news cache from disk."""
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"articles": [], "last_updated": None}


def _save_cache(cache: dict) -> None:
    """Save news cache to disk."""
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def _cache_is_fresh(cache: dict) -> bool:
    """Check if cache is under 24 hours old."""
    if not cache.get("last_updated"):
        return False
    try:
        last_updated = datetime.fromisoformat(cache["last_updated"])
        age = datetime.now(timezone.utc) - last_updated
        return age.total_seconds() < NEWS_CACHE_MAX_AGE_HOURS * 3600
    except (ValueError, TypeError):
        return False


def _filter_excluded_states(articles: list[dict]) -> list[dict]:
    """Remove articles that only reference excluded states."""
    filtered = []
    for article in articles:
        regions = article.get("regions", [])
        if regions:
            # Keep if any region is NOT in excluded states
            valid_regions = [r for r in regions if r.get("state") not in EXCLUDED_STATES]
            if valid_regions:
                article["regions"] = valid_regions
                filtered.append(article)
        else:
            # No region detected - keep it (national/general news)
            filtered.append(article)
    return filtered


async def sales_news_brief(refresh: bool = False) -> str:
    """Scrape multihousingnews.com and cpexecutive.com for real estate news.

    Categorizes articles by territory region and urgency tier (URGENT, THIS_WEEK, FYI).
    Caches results to avoid redundant scraping.

    Args:
        refresh: Force refresh even if cache is under 24 hours old.

    Returns:
        Formatted news brief with articles grouped by urgency tier.
    """
    cache = _load_cache()

    # Use cache if fresh and not forcing refresh
    if not refresh and _cache_is_fresh(cache):
        articles = _filter_excluded_states(cache.get("articles", []))
        brief = format_news_brief(articles)
        return brief + "\n\n*Using cached data. Set refresh=true to force update.*"

    # Scrape fresh articles
    articles = await scrape_news_sources()
    articles = _filter_excluded_states(articles)

    # Update cache
    cache = {
        "articles": articles,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
    _save_cache(cache)

    return format_news_brief(articles)
