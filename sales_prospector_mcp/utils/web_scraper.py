"""Web scraping utilities for news sources, homepages, and search."""

import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from sales_prospector_mcp.config import (
    NEWS_SOURCES,
    URGENCY_KEYWORDS,
    EXCLUDED_STATES,
    STATE_TO_REGION,
    TERRITORY_REGIONS,
)

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

# Major cities to state mapping for region detection
CITY_TO_STATE = {
    "new york": "NY", "manhattan": "NY", "brooklyn": "NY", "queens": "NY",
    "newark": "NJ", "jersey city": "NJ", "hoboken": "NJ",
    "baltimore": "MD", "bethesda": "MD", "wilmington": "DE",
    "washington": "DC", "arlington": "VA", "richmond": "VA", "norfolk": "VA",
    "charleston": "WV", "pittsburgh": "PA", "philadelphia": "PA",
    "charlotte": "NC", "raleigh": "NC", "durham": "NC", "greensboro": "NC",
    "charleston": "SC", "columbia": "SC", "greenville": "SC",
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

    # Check state abbreviations (with word boundaries)
    for region, states in TERRITORY_REGIONS.items():
        for state in states:
            if state in EXCLUDED_STATES or state in seen_states:
                continue
            if re.search(rf'\b{state}\b', text):
                found.append({"state": state, "region": region})
                seen_states.add(state)

    # Check city names
    for city, state in CITY_TO_STATE.items():
        if state in EXCLUDED_STATES or state in seen_states:
            continue
        if state not in STATE_TO_REGION:
            continue
        if city in text_lower:
            found.append({"state": state, "region": STATE_TO_REGION[state]})
            seen_states.add(state)

    return found


async def scrape_news_sources() -> list[dict]:
    """Scrape MHN and CPE for news articles."""
    articles = []

    async with httpx.AsyncClient(
        timeout=30.0,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        },
        follow_redirects=True,
    ) as client:
        for source_key, source in NEWS_SOURCES.items():
            try:
                resp = await client.get(source["feed_url"])
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")

                # Try common article selectors
                article_elements = (
                    soup.select("article") or
                    soup.select(".post") or
                    soup.select(".entry") or
                    soup.select("h2 a, h3 a")
                )

                for elem in article_elements[:15]:
                    article = _parse_article_element(elem, source_key, source)
                    if article:
                        # Detect regions and classify urgency
                        text = f"{article['title']} {article.get('summary', '')}"
                        regions = detect_regions(text)
                        urgency = classify_urgency(article["title"], article.get("summary", ""))

                        # Skip articles only about excluded states
                        if regions and all(r["state"] in EXCLUDED_STATES for r in regions):
                            continue

                        # Filter out excluded state regions
                        regions = [r for r in regions if r["state"] not in EXCLUDED_STATES]

                        article["regions"] = regions
                        article["urgency"] = urgency
                        article["scraped_at"] = datetime.now(timezone.utc).isoformat()
                        articles.append(article)

            except (httpx.HTTPError, httpx.TimeoutException) as e:
                articles.append({
                    "source": source_key,
                    "source_name": source["name"],
                    "title": f"[Scrape error: {source['name']}]",
                    "url": source["feed_url"],
                    "summary": f"Could not fetch articles: {str(e)}",
                    "regions": [],
                    "urgency": "FYI",
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                })

    return articles


def _parse_article_element(elem, source_key: str, source: dict) -> Optional[dict]:
    """Parse a single article element from HTML."""
    # Try to find title and link
    title_elem = elem.select_one("h2 a, h3 a, h4 a, a.entry-title") or elem.find("a")
    if not title_elem:
        if elem.name == "a":
            title_elem = elem
        else:
            return None

    title = title_elem.get_text(strip=True)
    if not title or len(title) < 10:
        return None

    url = title_elem.get("href", "")
    if url and not url.startswith("http"):
        url = source["base_url"].rstrip("/") + "/" + url.lstrip("/")

    # Try to find summary
    summary = ""
    summary_elem = elem.select_one("p, .excerpt, .summary, .entry-summary")
    if summary_elem:
        summary = summary_elem.get_text(strip=True)

    # Try to find date
    date_str = ""
    date_elem = elem.select_one("time, .date, .post-date, .entry-date")
    if date_elem:
        date_str = date_elem.get("datetime", "") or date_elem.get_text(strip=True)

    return {
        "source": source_key,
        "source_name": source["name"],
        "title": title,
        "url": url,
        "summary": summary[:500],
        "date": date_str,
    }


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
