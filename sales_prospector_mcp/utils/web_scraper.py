"""
Web scraper for real estate news sources.

Escalation strategy:
  1. httpx with realistic headers + session cookies
  2. curl_cffi TLS fingerprint impersonation (if httpx fails)
  3. Graceful degradation with structured error reporting

Note on curl_cffi: It impersonates a real browser's TLS fingerprint to bypass
bot detection. This is standard practice for personal automation tools, but be
aware it sits in a gray area with some sites' ToS. For a once-daily cron job
pulling headlines, this is reasonable. If open-sourcing, document the tradeoff.
"""

import asyncio
import logging
import random
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from sales_prospector_mcp.config import (
    URGENCY_KEYWORDS,
    EXCLUDED_STATES,
    STATE_TO_REGION,
    TERRITORY_REGIONS,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Rotate through a small pool so the same UA isn't hitting every source
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Source URLs -- CPE moved to commercialsearch.com in 2025
NEWS_SOURCES = {
    "mhn": {
        "name": "Multi-Housing News",
        "url": "https://www.multihousingnews.com/",
        "article_selector": ".post",
        "title_selector": "h3 a, h2 a",
        "link_selector": "h3 a, h2 a",
    },
    "cpe": {
        "name": "Commercial Property Executive",
        "url": "https://www.commercialsearch.com/news/",  # was cpexecutive.com
        "article_selector": ".post",
        "title_selector": "h3 a, h2 a",
        "link_selector": "h3 a, h2 a",
    },
}

# Request spacing: random delay between source fetches to avoid
# pattern-based blocking (same IP, same time, rapid succession)
MIN_DELAY_SECONDS = 2
MAX_DELAY_SECONDS = 8

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ScrapedArticle:
    title: str
    url: str
    source: str
    snippet: str = ""
    scraped_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class ScrapeResult:
    """Structured result so the caller always knows what happened."""
    source_name: str
    source_url: str
    articles: list[ScrapedArticle] = field(default_factory=list)
    success: bool = False
    method: str = ""        # "httpx" | "curl_cffi" | "none"
    error: str = ""
    status_code: Optional[int] = None


# ---------------------------------------------------------------------------
# Fetch strategies (escalation ladder)
# ---------------------------------------------------------------------------

def _random_headers() -> dict:
    """Headers with a randomly selected User-Agent."""
    headers = HEADERS.copy()
    headers["User-Agent"] = random.choice(_USER_AGENTS)
    return headers


def _fetch_httpx(url: str, timeout: int = 30) -> Optional[str]:
    """
    Strategy 1: httpx with realistic headers and session cookies.

    Some sites (MHN) set cookies on the first request and only serve
    real content on subsequent requests. A session preserves those cookies
    across the retry.
    """
    headers = _random_headers()
    try:
        with httpx.Client(
            headers=headers,
            follow_redirects=True,
            timeout=timeout,
        ) as client:
            response = client.get(url)

            if response.status_code == 403:
                logger.info(
                    f"httpx got 403 on first request to {url}, "
                    f"retrying with session cookies..."
                )
                time.sleep(random.uniform(1.5, 3.0))
                response = client.get(url)

            response.raise_for_status()
            return response.text

    except httpx.HTTPStatusError as e:
        logger.warning(f"httpx failed for {url}: HTTP {e.response.status_code}")
        return None
    except httpx.RequestError as e:
        logger.warning(f"httpx request error for {url}: {e}")
        return None


def _fetch_curl_cffi(url: str) -> Optional[str]:
    """
    Strategy 2: curl_cffi with browser TLS fingerprint impersonation.

    Falls back here when httpx fails, typically because the site uses
    Cloudflare or similar TLS fingerprint checks. Much lighter than
    a headless browser -- safe for the IdeaPad's RAM constraints.
    """
    try:
        from curl_cffi import requests as curl_requests
    except ImportError:
        logger.warning(
            "curl_cffi not installed. Run: pip install curl_cffi "
            "--break-system-packages (or in your venv)"
        )
        return None

    try:
        response = curl_requests.get(
            url,
            impersonate="chrome",
            timeout=30,
            headers=_random_headers(),
        )
        response.raise_for_status()
        return response.text

    except Exception as e:
        logger.warning(f"curl_cffi failed for {url}: {e}")
        return None


def fetch_page(url: str) -> tuple[Optional[str], str]:
    """
    Try httpx first, then curl_cffi. Returns (html, method_used).
    method_used is "httpx", "curl_cffi", or "none".
    """
    html = _fetch_httpx(url)
    if html:
        return html, "httpx"

    logger.info(f"Escalating to curl_cffi for {url}")
    html = _fetch_curl_cffi(url)
    if html:
        return html, "curl_cffi"

    return None, "none"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_articles(
    html: str,
    source_key: str,
    source_config: dict,
) -> list[ScrapedArticle]:
    """
    Parse article titles and URLs from a news source page.
    Validates each article before including it.
    """
    soup = BeautifulSoup(html, "html.parser")
    articles: list[ScrapedArticle] = []
    seen_urls: set[str] = set()

    # Try configured selector first, then fallback chain
    article_elements = soup.select(source_config["article_selector"])
    if not article_elements:
        for fallback in [".post", ".entry", ".story", ".news-item"]:
            article_elements = soup.select(fallback)
            if article_elements:
                break

    for element in article_elements:
        # Extract title: try configured selector, then common patterns
        title_el = element.select_one(source_config["title_selector"])
        if not title_el:
            title_el = element.select_one("h2 a, h3 a, h4 a, a.entry-title")
        if not title_el:
            # Last resort: first anchor with text
            title_el = element.find("a")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)

        # Extract link
        link_el = element.select_one(source_config["link_selector"])
        if not link_el:
            link_el = title_el  # title element is usually the link
        url = link_el.get("href", "")

        # Make relative URLs absolute
        if url and not url.startswith("http"):
            base = source_config["url"].rstrip("/")
            url = f"{base}/{url.lstrip('/')}"

        # --- Validation checks ---
        if not title or len(title) < 5:
            continue
        if not url or not url.startswith("http"):
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Extract snippet if available
        snippet = ""
        snippet_el = element.select_one("p, .excerpt, .summary, .description")
        if snippet_el:
            snippet = snippet_el.get_text(strip=True)[:300]

        articles.append(
            ScrapedArticle(
                title=title,
                url=url,
                source=source_config["name"],
                snippet=snippet,
            )
        )

    return articles


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def scrape_all_sources() -> list[ScrapeResult]:
    """
    Scrape all configured news sources with escalation and spacing.

    Returns a list of ScrapeResult objects -- one per source -- so the
    caller always has structured data about what worked, what failed,
    and why. No exceptions bubble up from here.
    """
    results: list[ScrapeResult] = []

    source_keys = list(NEWS_SOURCES.keys())
    random.shuffle(source_keys)  # Don't always hit the same source first

    for i, key in enumerate(source_keys):
        config = NEWS_SOURCES[key]
        result = ScrapeResult(
            source_name=config["name"],
            source_url=config["url"],
        )

        # Spacing between requests (skip delay before the first one)
        if i > 0:
            delay = random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
            logger.info(f"Waiting {delay:.1f}s before next source...")
            time.sleep(delay)

        try:
            html, method = fetch_page(config["url"])

            if html is None:
                result.error = (
                    f"All fetch strategies failed for {config['name']}. "
                    f"Site may be blocking automated requests."
                )
                logger.warning(result.error)
                results.append(result)
                continue

            result.method = method
            result.articles = parse_articles(html, key, config)
            result.success = True

            logger.info(
                f"Scraped {len(result.articles)} articles from "
                f"{config['name']} via {method}"
            )

            # Validation: warn if we got HTML but zero articles
            if not result.articles:
                logger.warning(
                    f"Got HTML from {config['name']} but parsed 0 articles. "
                    f"Page structure may have changed -- check selectors."
                )

        except Exception as e:
            result.error = f"Unexpected error scraping {config['name']}: {e}"
            logger.error(result.error, exc_info=True)

        results.append(result)

    return results


def format_scrape_summary(results: list[ScrapeResult]) -> str:
    """
    Human-readable summary for the daily brief email.
    Shows what worked, what failed, and why -- so a 5:30 AM failure
    tells you something actionable instead of just being empty.
    """
    lines: list[str] = []

    total_articles = sum(len(r.articles) for r in results)
    failed = [r for r in results if not r.success]

    lines.append(f"Scraped {total_articles} articles from {len(results)} sources.")

    if failed:
        lines.append("")
        lines.append("Failed sources:")
        for r in failed:
            lines.append(f"  - {r.source_name} ({r.source_url}): {r.error}")

    for r in results:
        if r.success and not r.articles:
            lines.append(
                f"  - {r.source_name}: HTML fetched via {r.method} "
                f"but 0 articles parsed (selector mismatch?)"
            )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Preserved utility functions (used by daily_brief, news_brief, tools, tests)
# ---------------------------------------------------------------------------

# US state names to abbreviations
STATE_NAMES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "district of columbia": "DC", "florida": "FL", "georgia": "GA", "hawaii": "HI",
    "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY",
}

# Major cities to state mapping for region detection.
CITY_TO_STATE = {
    "new york": "NY", "manhattan": "NY", "brooklyn": "NY", "queens": "NY",
    "newark": "NJ", "jersey city": "NJ", "hoboken": "NJ",
    "baltimore": "MD", "bethesda": "MD", "wilmington": "DE",
    "washington": "DC", "arlington": "VA", "richmond": "VA", "norfolk": "VA",
    "pittsburgh": "PA", "philadelphia": "PA",
    "charlotte": "NC", "raleigh": "NC", "durham": "NC", "greensboro": "NC",
    "columbia": "SC", "greenville": "SC",
    "atlanta": "GA", "savannah": "GA", "augusta": "GA",
    "miami": "FL", "orlando": "FL", "tampa": "FL", "jacksonville": "FL",
    "fort lauderdale": "FL", "west palm beach": "FL",
    "dallas": "TX", "houston": "TX", "austin": "TX", "san antonio": "TX",
    "fort worth": "TX", "oklahoma city": "OK", "tulsa": "OK",
    "little rock": "AR", "new orleans": "LA", "baton rouge": "LA",
    "jackson": "MS", "memphis": "TN", "nashville": "TN", "knoxville": "TN",
    "birmingham": "AL", "huntsville": "AL", "mobile": "AL",
    "louisville": "KY", "lexington": "KY",
    "columbus": "OH", "cleveland": "OH", "cincinnati": "OH",
    "indianapolis": "IN", "fort wayne": "IN",
    "kansas city": "MO", "st. louis": "MO", "st louis": "MO",
    "des moines": "IA", "omaha": "NE", "wichita": "KS",
}

# Explicit city/state disambiguation patterns for ambiguous city names.
CITY_STATE_PATTERNS = [
    (r"\bcharleston\b.{0,40}\b(wv|west virginia)\b", "WV"),
    (r"\bcharleston\b.{0,40}\b(sc|south carolina)\b", "SC"),
]


def classify_urgency(title: str, summary: str) -> str:
    """Classify an article's urgency tier based on keywords."""
    text = f"{title} {summary}".lower()
    for keyword in URGENCY_KEYWORDS["URGENT"]:
        if keyword in text:
            return "URGENT"
    for keyword in URGENCY_KEYWORDS["THIS_WEEK"]:
        if keyword in text:
            return "THIS_WEEK"
    return "FYI"


def detect_regions(text: str) -> list[dict]:
    """Detect territory regions mentioned in text. Returns list of {state, region}."""
    text_lower = text.lower()
    found = []
    seen_states = set()

    # Check state names
    for name, abbr in STATE_NAMES.items():
        if abbr in EXCLUDED_STATES:
            continue
        if abbr not in STATE_TO_REGION:
            continue
        if name in text_lower and abbr not in seen_states:
            found.append({"state": abbr, "region": STATE_TO_REGION[abbr]})
            seen_states.add(abbr)

    # Check state abbreviations (with word boundaries), case-insensitive.
    for region, states in TERRITORY_REGIONS.items():
        for state in states:
            if state in EXCLUDED_STATES or state in seen_states:
                continue
            if re.search(rf"\b{re.escape(state)}\b", text, flags=re.IGNORECASE):
                found.append({"state": state, "region": region})
                seen_states.add(state)

    # Check explicit disambiguation patterns first (e.g., "Charleston, WV")
    for pattern, state in CITY_STATE_PATTERNS:
        if state in EXCLUDED_STATES or state in seen_states:
            continue
        if state not in STATE_TO_REGION:
            continue
        if re.search(pattern, text_lower):
            found.append({"state": state, "region": STATE_TO_REGION[state]})
            seen_states.add(state)

    # Check city names using unique city->state mapping
    for city, state in CITY_TO_STATE.items():
        if state in EXCLUDED_STATES or state in seen_states:
            continue
        if state not in STATE_TO_REGION:
            continue
        if city in text_lower:
            found.append({"state": state, "region": STATE_TO_REGION[state]})
            seen_states.add(state)

    return found


async def scrape_homepage(url: str) -> dict:
    """Scrape a company homepage for key information."""
    result = {
        "url": url,
        "title": "",
        "description": "",
        "text_content": "",
        "links": [],
        "error": None,
    }

    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            # Title
            title_tag = soup.find("title")
            result["title"] = title_tag.get_text(strip=True) if title_tag else ""

            # Meta description
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc:
                result["description"] = meta_desc.get("content", "")

            # Main text content (first 2000 chars)
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator=" ", strip=True)
            result["text_content"] = text[:2000]

            # Important links
            for a in soup.find_all("a", href=True)[:20]:
                href = a.get("href", "")
                text = a.get_text(strip=True)
                if text and href and not href.startswith("#"):
                    result["links"].append({"text": text, "href": href})

    except Exception as e:
        result["error"] = str(e)

    return result


async def search_duckduckgo(query: str, max_results: int = 5) -> list[dict]:
    """Search DuckDuckGo for information about a company."""
    results = []

    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            follow_redirects=True,
        ) as client:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            for result_div in soup.select(".result")[:max_results]:
                title_elem = result_div.select_one(".result__title a, .result__a")
                snippet_elem = result_div.select_one(".result__snippet")

                if title_elem:
                    title = title_elem.get_text(strip=True)
                    url = title_elem.get("href", "")
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": snippet,
                    })

    except Exception as e:
        results.append({
            "title": "Search error",
            "url": "",
            "snippet": f"Could not complete search: {str(e)}",
        })

    return results


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    print("Testing scraper...\n")
    results = scrape_all_sources()

    print(format_scrape_summary(results))
    print()

    for r in results:
        if r.articles:
            print(f"\n--- {r.source_name} ({r.method}) ---")
            for a in r.articles[:5]:
                print(f"  {a.title}")
                print(f"    {a.url}")
                if a.snippet:
                    print(f"    {a.snippet[:100]}...")
