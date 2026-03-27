"""Utility modules for Sales Prospector MCP."""

from .llm_client import LLMClient
from .web_scraper import (
    scrape_all_sources,
    format_scrape_summary,
    scrape_homepage,
    search_duckduckgo,
    classify_urgency,
    detect_regions,
)
from .formatter import (
    format_call_prep,
    format_email,
    format_pipeline_table,
    format_news_brief,
    format_daily_brief_html,
)

__all__ = [
    "LLMClient",
    "scrape_all_sources",
    "format_scrape_summary",
    "scrape_homepage",
    "search_duckduckgo",
    "classify_urgency",
    "detect_regions",
    "format_call_prep",
    "format_email",
    "format_pipeline_table",
    "format_news_brief",
    "format_daily_brief_html",
]
