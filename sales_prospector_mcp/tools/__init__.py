"""Sales Prospector MCP tools."""

from .news_brief import sales_news_brief
from .account_research import sales_research_account
from .call_prep import sales_prep_call
from .email_draft import sales_email_draft
from .pipeline_rank import sales_pipeline_rank
from .batch_outreach import sales_batch_outreach

__all__ = [
    "sales_news_brief",
    "sales_research_account",
    "sales_prep_call",
    "sales_email_draft",
    "sales_pipeline_rank",
    "sales_batch_outreach",
]
