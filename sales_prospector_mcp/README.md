# Sales Prospector MCP

A FastMCP-based sales intelligence server for Yardi property management software sales. Provides 6 tools for prospecting, research, call prep, email drafting, pipeline management, and batch outreach.

## Quick Start

```bash
cd sales_prospector_mcp
bash install.sh
source venv/bin/activate
python server.py
```

## Tools

| Tool | Description |
|------|-------------|
| `sales_news_brief` | Scrapes MHN and CPE for real estate news, categorizes by region and urgency |
| `sales_research_account` | DuckDuckGo search + homepage scrape for company research |
| `sales_prep_call` | One-page call prep sheet for any meeting type |
| `sales_email_draft` | Personalized email drafts with news hooks and Yardi angles |
| `sales_pipeline_rank` | Score and rank accounts by priority with next actions |
| `sales_batch_outreach` | Generate 1-15 personalized emails in a single call |

## Territory Coverage

- **Northeast:** NY, NJ
- **Mid-Atlantic:** MD, DE, DC, VA, WV, PA
- **Southeast:** NC, SC, GA, FL
- **South Central:** TX, OK, AR, LA, MS, AL, TN, KY
- **Midwest (covered):** OH, IN, MO, IA, NE, KS
- **Excluded:** IL, MN, MI, WI

## LLM Configuration

The server tries Ollama (localhost:11434, qwen2.5:7b) first, then falls back to Anthropic API.

Set `LLM_PROVIDER` env var to override: `ollama` or `anthropic`.

## Daily Brief

A standalone `daily_brief.py` script runs the full pipeline and sends an HTML email via Gmail API.

```bash
# Manual run
python daily_brief.py

# Cron (5:30 AM Pacific, Mon-Fri)
30 12 * * 1-5 cd /path/to/project && venv/bin/python daily_brief.py
```

Requires `credentials.json` from Google Cloud Console for Gmail API access.
