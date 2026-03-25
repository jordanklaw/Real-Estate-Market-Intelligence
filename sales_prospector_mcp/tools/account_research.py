"""Tool 2: Account Research - DuckDuckGo search + homepage scrape."""

from sales_prospector_mcp.utils.web_scraper import search_duckduckgo, scrape_homepage
from sales_prospector_mcp.utils.llm_client import LLMClient

_llm = LLMClient()


async def sales_research_account(company_name: str) -> str:
    """Research a company using DuckDuckGo search and homepage scraping.

    Returns a structured research brief with hiring signals, recent news,
    and analysis hooks for sales engagement.

    Args:
        company_name: The company name to research.

    Returns:
        Structured research brief with key findings.
    """
    # Search for the company
    search_results = await search_duckduckgo(
        f"{company_name} property management real estate", max_results=5
    )

    # Try to find and scrape the company homepage
    homepage_data = None
    company_url = None
    for result in search_results:
        url = result.get("url", "")
        if url and company_name.lower().split()[0] in url.lower():
            company_url = url
            break

    if company_url:
        homepage_data = await scrape_homepage(company_url)

    # Search for hiring signals
    hiring_results = await search_duckduckgo(
        f"{company_name} hiring jobs careers property management", max_results=3
    )

    # Search for recent news
    news_results = await search_duckduckgo(
        f"{company_name} news announcement 2026", max_results=3
    )

    # Build research context
    research_context = _build_research_context(
        company_name, search_results, homepage_data, hiring_results, news_results
    )

    # Generate analysis with LLM
    system_prompt = (
        "You are a sales research analyst for Yardi, a property management software company. "
        "Analyze the research data and produce a concise, actionable research brief for a sales rep. "
        "Focus on: 1) Company overview, 2) Hiring signals (growth indicators), "
        "3) Recent news and developments, 4) Technology stack clues, "
        "5) Sales hooks and engagement angles."
    )

    analysis = await _llm.generate(
        f"Research data for {company_name}:\n\n{research_context}\n\n"
        "Produce a structured research brief with the sections listed in your instructions.",
        system=system_prompt,
    )

    # Format output
    output = [
        f"# Account Research: {company_name}",
        "",
    ]

    if company_url:
        output.append(f"**Website:** {company_url}")
    if homepage_data and homepage_data.get("description"):
        output.append(f"**About:** {homepage_data['description']}")
    output.append("")

    output.extend([
        "## Search Results",
    ])
    for r in search_results[:3]:
        output.append(f"- [{r['title']}]({r.get('url', '')})")
        if r.get("snippet"):
            output.append(f"  {r['snippet'][:150]}")
    output.append("")

    if hiring_results:
        output.append("## Hiring Signals")
        for r in hiring_results[:3]:
            output.append(f"- {r['title']}: {r.get('snippet', '')[:100]}")
        output.append("")

    if news_results:
        output.append("## Recent News")
        for r in news_results[:3]:
            output.append(f"- {r['title']}: {r.get('snippet', '')[:100]}")
        output.append("")

    output.extend([
        "## AI Analysis",
        analysis,
    ])

    return "\n".join(output)


def _build_research_context(
    company_name: str,
    search_results: list[dict],
    homepage_data: dict | None,
    hiring_results: list[dict],
    news_results: list[dict],
) -> str:
    """Build context string for LLM analysis."""
    parts = [f"Company: {company_name}\n"]

    if homepage_data and not homepage_data.get("error"):
        parts.append(f"Website Title: {homepage_data.get('title', 'N/A')}")
        parts.append(f"Description: {homepage_data.get('description', 'N/A')}")
        parts.append(f"Content Preview: {homepage_data.get('text_content', '')[:500]}")
        parts.append("")

    parts.append("Search Results:")
    for r in search_results:
        parts.append(f"- {r['title']}: {r.get('snippet', '')}")

    parts.append("\nHiring/Jobs:")
    for r in hiring_results:
        parts.append(f"- {r['title']}: {r.get('snippet', '')}")

    parts.append("\nRecent News:")
    for r in news_results:
        parts.append(f"- {r['title']}: {r.get('snippet', '')}")

    return "\n".join(parts)
