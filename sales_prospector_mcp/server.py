"""Sales Prospector MCP Server - FastMCP-based sales intelligence for Yardi."""

import sys
from pathlib import Path

# Ensure package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastmcp import FastMCP

from sales_prospector_mcp.tools.news_brief import sales_news_brief
from sales_prospector_mcp.tools.account_research import sales_research_account
from sales_prospector_mcp.tools.call_prep import sales_prep_call
from sales_prospector_mcp.tools.email_draft import sales_email_draft
from sales_prospector_mcp.tools.pipeline_rank import sales_pipeline_rank
from sales_prospector_mcp.tools.batch_outreach import sales_batch_outreach

# Create the MCP server
mcp = FastMCP("sales_prospector")


# Register all 6 tools
@mcp.tool()
async def tool_sales_news_brief(refresh: bool = False) -> str:
    """Scrape multihousingnews.com and cpexecutive.com for real estate news.
    Categorizes articles by territory region and urgency tier (URGENT, THIS_WEEK, FYI).
    Uses cache if under 24 hours old unless refresh is True."""
    return await sales_news_brief(refresh=refresh)


@mcp.tool()
async def tool_sales_research_account(company_name: str) -> str:
    """Research a company using DuckDuckGo search and homepage scraping.
    Returns structured research brief with hiring signals, recent news, and analysis hooks."""
    return await sales_research_account(company_name=company_name)


@mcp.tool()
async def tool_sales_prep_call(company_name: str, meeting_type: str = "discovery") -> str:
    """Generate a one-page call prep sheet for an account.
    Meeting types: discovery, demo, follow_up, negotiation, renewal.
    Pulls from accounts.json, live research, news cache, and products.json."""
    return await sales_prep_call(company_name=company_name, meeting_type=meeting_type)


@mcp.tool()
async def tool_sales_email_draft(
    company_name: str,
    email_type: str = "outreach",
    use_news: bool = True,
) -> str:
    """Draft a personalized email for an account.
    Structure: news hook, bridge to situation, Yardi resource link, soft CTA.
    Types: outreach, follow_up, re_engage, pricing, value_add."""
    return await sales_email_draft(
        company_name=company_name,
        email_type=email_type,
        use_news=use_news,
    )


@mcp.tool()
async def tool_sales_pipeline_rank(top_n: int = 10) -> str:
    """Score and rank all accounts by deal stage, recency, unit count, and territory.
    Returns ranked list with recommended next actions."""
    return await sales_pipeline_rank(top_n=top_n)


@mcp.tool()
async def tool_sales_batch_outreach(
    criteria: dict | None = None,
    email_type: str = "outreach",
    news_driven: bool = False,
) -> str:
    """Generate batch personalized emails for filtered accounts (1-15 per call).
    When news_driven is True, each email uses a distinct news article as hook.
    Criteria keys: deal_stage, portfolio_type, region, state, min_units, max_units, current_product."""
    return await sales_batch_outreach(
        criteria=criteria,
        email_type=email_type,
        news_driven=news_driven,
    )


if __name__ == "__main__":
    mcp.run()
