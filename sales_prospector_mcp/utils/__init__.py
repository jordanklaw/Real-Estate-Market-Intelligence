"""Utility modules for Sales Prospector MCP."""

from .llm_client import LLMClient
from .web_scraper import scrape_news_sources, scrape_homepage, search_duckduckgo
from .formatter import (
    format_call_prep,
    format_email,
    format_pipeline_table,
    format_news_brief,
    format_daily_brief_html,
)

__all__ = [
    "LLMClient",
    "scrape_news_sources",
    "scrape_homepage",
    "search_duckduckgo",
    "format_call_prep",
    "format_email",
    "format_pipeline_table",
    "format_news_brief",
    "format_daily_brief_html",
]
