# Real Estate Market Intelligence (MCP)

A local-first sales intelligence system built on the Model Context Protocol (MCP), designed for commercial and multifamily real estate software sales. The system aggregates RE industry news, matches signals to accounts by territory and urgency, and exposes six tools through MCP for use with any compatible AI client.

All LLM inference runs locally via Ollama. No external API keys are required for core functionality.

## What It Does

The MCP server gives a sales rep six tools that turn raw market data into actionable outreach. A RE news feed monitors Multi-Housing News and Commercial Property Executive, categorizes articles by region and urgency tier, and cross-references them against a territory-filtered account list. The pipeline ranker scores accounts by deal stage, recency, and portfolio size. The email drafter and call prep tools generate personalized outreach grounded in real news events, not generic templates.

A standalone daily brief script runs on a cron schedule, delivering a prioritized HTML briefing to your inbox each morning with the top five accounts to contact and why.

## MCP Compatibility

This server implements the [Model Context Protocol](https://modelcontextprotocol.io/), an open standard introduced by Anthropic in 2024 and since adopted across the industry. MCP is now maintained by the Agentic AI Foundation under the Linux Foundation, co-founded by Anthropic, Block, and OpenAI.

Any MCP-compatible client can connect to this server, including:

- **Claude Desktop** (Anthropic)
- **ChatGPT Desktop** (OpenAI)
- **Gemini** (Google DeepMind)
- **Microsoft Copilot / VS Code** (Microsoft)
- **Cursor** and **Windsurf** (AI-native IDEs)
- **Goose CLI** (Block, open source)
- **Custom clients** built with the official Python, TypeScript, Go, C#, or Java SDKs

The protocol is model-agnostic. You build the server once, and it works everywhere. Configuration details for Claude Desktop are provided below as a reference example, but the setup pattern is similar across clients.

## Architecture

The system is structured in five layers, each depending only on the layers beneath it.

**Foundation** contains all configuration constants (territory regions, excluded states, urgency-tier keywords, LLM settings) and the five JSON data files that define accounts, products, email templates, product-marketing resource mappings, and the news cache.

**Utilities** provide the LLM client (Ollama primary, with a multi-provider pattern that supports remote fallback if explicitly configured), web scraping functions for news sources and company research, and output formatters for all tool responses.

**Tools** implement the six MCP-exposed capabilities. Every tool enforces territory exclusions (IL, MN, MI, WI are filtered out at the data layer) and handles errors gracefully.

**Server** registers all six tools with FastMCP and provides the `python -m sales_prospector_mcp` entry point.

**Daily Brief** is a standalone script at the project root that orchestrates the full pipeline (scrape, match, rank, generate, send) and delivers a formatted email via the Gmail API.

## Tools

`sales_news_brief` scrapes and caches territory-filtered real estate news, grouped by urgency tier (urgent, this week, FYI) and region.

`sales_research_account` runs a DuckDuckGo search and homepage scrape for a given company, surfacing hiring signals, recent news, and analysis hooks.

`sales_prep_call` generates a complete call preparation sheet for discovery, demo, follow-up, negotiation, or renewal meetings, pulling from account data, live research, cached news, and product information.

`sales_email_draft` produces a personalized email using a news hook, bridge to the prospect's situation, relevant Yardi feature, and soft CTA. Supports outreach, follow-up, re-engage, pricing, and value-add types.

`sales_pipeline_rank` scores and ranks accounts by deal stage, last contact recency, portfolio size, and territory priority.

`sales_batch_outreach` filters accounts by criteria (region, portfolio type, deal stage, unit count) and generates up to 15 personalized emails, optionally matching each to a distinct news article.

## Prerequisites

Python 3.11 or higher and Ollama must be installed on the host machine. The default model is Qwen3 14B, which requires approximately 10GB of RAM at Q4 quantization. A machine with 16GB RAM runs this comfortably.

Install Ollama from [ollama.com](https://ollama.com) and pull the model:

```bash
ollama pull qwen3:14b
```

## Installation

```bash
git clone https://github.com/jordanklaw/Real-Estate-Market-Intelligence.git
cd Real-Estate-Market-Intelligence
bash install.sh
```

The install script creates a virtual environment, installs dependencies, creates the `briefs/` directory, and prints a Claude Desktop configuration block with absolute paths for your machine. The same server binary works with any MCP client.

## Configuration

Copy `.env.example` to `.env` and set your values:

```bash
cp .env.example .env
```

The only required variable for the daily brief email delivery is `DAILY_BRIEF_RECIPIENT`. All other functionality works without any environment variables as long as Ollama is running.

To use the optional remote LLM fallback, set `LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY` in `.env`. This is not required and not recommended for default operation.

## Connecting to an MCP Client

The server runs as a local process that any MCP client can connect to. Below are setup instructions for the most common clients.

### Claude Desktop

Config file location:
- Linux: `~/.config/Claude/claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "sales_prospector": {
      "command": "/absolute/path/to/venv/bin/python",
      "args": ["-m", "sales_prospector_mcp"],
      "cwd": "/absolute/path/to/Real-Estate-Market-Intelligence"
    }
  }
}
```

`install.sh` prints this block with the correct absolute paths for your machine. Restart Claude Desktop after saving.

### ChatGPT Desktop

OpenAI adopted MCP in March 2025. In ChatGPT Desktop, navigate to Settings and add an MCP server with the same command and args shown above. Consult [OpenAI's MCP documentation](https://platform.openai.com/docs) for the latest configuration format.

### Cursor / Windsurf / VS Code

These IDEs support MCP through their settings or extension configuration. Point the MCP server config to the same Python binary and module entry point. Each IDE's documentation covers the specific JSON structure.

### Custom Clients

The official MCP SDKs (Python, TypeScript, Go, C#, Java) allow you to build your own client. The server exposes standard MCP tool definitions with typed parameters and docstrings. Any client implementing the MCP spec can discover and call all six tools.

## Daily Brief Setup

The daily brief requires Gmail API credentials for email delivery. The HTML brief is always saved locally to `briefs/` regardless of email configuration.

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable the Gmail API
3. Create an OAuth 2.0 Client ID (Desktop application type)
4. Download the credentials file and save it as `credentials.json` in the project root
5. Run `python daily_brief.py` once manually to complete the browser-based OAuth flow and generate `token.json`
6. Schedule with cron for automated delivery:

```bash
crontab -e
# Add this line (runs at 5:30 AM PST daily):
30 5 * * * cd /path/to/Real-Estate-Market-Intelligence && venv/bin/python daily_brief.py
```

## Territory Coverage

The system covers five regions across 24 states. Illinois, Minnesota, Michigan, and Wisconsin are excluded at the configuration level and filtered from all tool outputs.

Northeast: NY, NJ. Mid-Atlantic: MD, DE, DC, VA, WV, PA. Southeast: NC, SC, GA, FL. South Central: TX, OK, AR, LA, MS, AL, TN, KY. Midwest (covered): OH, IN, MO, IA, NE, KS.

## Project Structure

```
Real-Estate-Market-Intelligence/
├── sales_prospector_mcp/
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py
│   ├── server.py
│   ├── data/
│   │   ├── accounts.json
│   │   ├── products.json
│   │   ├── templates.json
│   │   ├── yardi_resources.json
│   │   └── news_cache.json
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── llm_client.py
│   │   ├── web_scraper.py
│   │   └── formatter.py
│   └── tools/
│       ├── __init__.py
│       ├── news_brief.py
│       ├── account_research.py
│       ├── call_prep.py
│       ├── email_draft.py
│       ├── pipeline_rank.py
│       └── batch_outreach.py
├── daily_brief.py
├── briefs/
├── requirements.txt
├── install.sh
├── .env.example
└── .gitignore
```

## Stack

Python 3.11, FastMCP, Model Context Protocol, Ollama, Qwen3 14B, Ubuntu 24.04 LTS, Gmail API, BeautifulSoup4, httpx, cron.

## License

MIT
