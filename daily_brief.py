#!/usr/bin/env python3
"""Daily Sales Intelligence Brief - Standalone scheduled task.

Runs the full pipeline:
1. Scrape MHN and CPE for fresh headlines
2. Categorize by territory region and urgency tier
3. Read accounts.json
4. Match news to accounts by region, portfolio type, and competitive situation
5. Rank and select top 5 accounts (weighted: news urgency + deal stage + days since contact)
6. Generate talking points and Yardi product angle for each
7. Send as HTML email via Gmail API to the configured recipient
8. Save brief as dated file in briefs/ folder

Cron schedule: 5:30 AM Pacific, Monday-Friday
  30 12 * * 1-5 cd /path/to/project && venv/bin/python daily_brief.py
"""

import asyncio
import json
import os
import sys
import base64
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from sales_prospector_mcp.config import (
    DATA_DIR,
    BRIEFS_DIR,
    EXCLUDED_STATES,
    DEAL_STAGE_WEIGHTS,
    STATE_TO_REGION,
    DAILY_BRIEF_RECIPIENT,
    DAILY_BRIEF_TOP_N,
)
from sales_prospector_mcp.utils.web_scraper import scrape_news_sources
from sales_prospector_mcp.utils.llm_client import LLMClient
from sales_prospector_mcp.utils.formatter import format_daily_brief_html


def load_accounts() -> list[dict]:
    """Load and filter accounts."""
    with open(DATA_DIR / "accounts.json", "r") as f:
        accounts = json.load(f)
    return [a for a in accounts if a.get("state") not in EXCLUDED_STATES]


def load_yardi_resources() -> dict:
    """Load Yardi resources."""
    with open(DATA_DIR / "yardi_resources.json", "r") as f:
        return json.load(f)


def load_products() -> dict:
    """Load products."""
    with open(DATA_DIR / "products.json", "r") as f:
        return json.load(f)


def match_news_to_account(account: dict, articles: list[dict]) -> list[dict]:
    """Match news articles to an account by region and portfolio type."""
    state = account.get("state", "")
    portfolio = account.get("portfolio_type", "").lower()
    matched = []

    for article in articles:
        score = 0
        regions = article.get("regions", [])

        # Region match
        for region in regions:
            if region.get("state") == state:
                score += 3
                break

        # Portfolio type relevance
        title_summary = f"{article.get('title', '')} {article.get('summary', '')}".lower()
        if portfolio in title_summary:
            score += 2
        if "multifamily" in title_summary or "apartment" in title_summary:
            if portfolio in ("multifamily", "mixed"):
                score += 1
        if "commercial" in title_summary:
            if portfolio in ("commercial", "mixed"):
                score += 1

        # Competitive situation
        current = account.get("current_product", "").lower()
        if current and current in title_summary:
            score += 2

        if score > 0:
            matched.append({**article, "_match_score": score})

    matched.sort(key=lambda a: a.get("_match_score", 0), reverse=True)
    return matched[:3]


def days_since_contact(last_contact: str) -> int:
    """Calculate days since last contact."""
    try:
        contact_date = datetime.strptime(last_contact, "%Y-%m-%d")
        return (datetime.now() - contact_date).days
    except (ValueError, TypeError):
        return 999


def score_account(account: dict, matched_news: list[dict]) -> float:
    """Score an account for daily brief ranking.

    Weighted by: news urgency + deal stage + days since last contact.
    """
    score = 0.0

    # News urgency component
    urgency_weights = {"URGENT": 15, "THIS_WEEK": 8, "FYI": 3}
    for news in matched_news:
        score += urgency_weights.get(news.get("urgency", "FYI"), 3)

    # Deal stage component
    stage = account.get("deal_stage", "prospect")
    score += DEAL_STAGE_WEIGHTS.get(stage, 0) * 2

    # Days since contact component (higher = more urgent)
    days = days_since_contact(account.get("last_contact", ""))
    if days <= 3:
        score += 2
    elif days <= 7:
        score += 5
    elif days <= 14:
        score += 10
    elif days <= 30:
        score += 12
    else:
        score += 8

    # Unit count bonus
    units = account.get("units", 0)
    if units >= 3000:
        score += 5
    elif units >= 1000:
        score += 3

    return score


def get_yardi_product_angle(account: dict, resources: dict, products: dict) -> str:
    """Determine the best Yardi product angle for an account."""
    target = account.get("target_product", "").lower()
    current = account.get("current_product", "").lower()

    # Find the target product info
    product_info = None
    for key, prod in products.items():
        if target in prod["name"].lower() or target in key.lower():
            product_info = prod
            break

    if not product_info:
        return "Explore Yardi solutions that match their portfolio needs."

    # Build angle based on current product
    angle_parts = [f"Target: {product_info['name']}"]

    # Check for upgrade path
    upgrade_paths = product_info.get("upgrade_path", {})
    for path_key, path_desc in upgrade_paths.items():
        if any(word in current for word in path_key.replace("_", " ").split()):
            angle_parts.append(f"Upgrade path: {path_desc[:150]}")
            break

    # Add top value prop
    value_props = product_info.get("key_value_props", [])
    if value_props:
        angle_parts.append(f"Lead with: {value_props[0]}")

    return " | ".join(angle_parts)


async def generate_talking_points(
    account: dict, matched_news: list[dict], llm: LLMClient
) -> list[str]:
    """Generate talking points for an account using LLM."""
    system = (
        "You are a sales strategist for Yardi property management software. "
        "Generate 3 concise, actionable talking points for a sales rep. "
        "Each point should be 1-2 sentences. Output as a numbered list."
    )

    context = (
        f"Account: {account['company_name']} ({account['city']}, {account['state']})\n"
        f"Units: {account['units']} | Portfolio: {account['portfolio_type']}\n"
        f"Stage: {account['deal_stage']} | Current: {account['current_product']}\n"
        f"Target: {account['target_product']}\n"
        f"Notes: {account.get('notes', 'None')}\n"
    )

    if matched_news:
        context += "\nRelevant news:\n"
        for news in matched_news[:2]:
            context += f"- [{news.get('urgency', 'FYI')}] {news['title']}\n"

    response = await llm.generate(
        f"Generate 3 talking points:\n\n{context}",
        system=system,
    )

    # Parse numbered list
    points = []
    for line in response.strip().split("\n"):
        line = line.strip()
        if line and (line[0].isdigit() or line.startswith("-")):
            # Strip number prefix
            clean = line.lstrip("0123456789.-) ").strip()
            if clean:
                points.append(clean)

    return points[:3] if points else [response.strip()[:200]]


def send_gmail(html_content: str, subject: str, recipient: str) -> bool:
    """Send HTML email via Gmail API."""
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
        creds = None
        token_path = Path(__file__).parent / "token.json"
        creds_path = Path(__file__).parent / "credentials.json"

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            elif creds_path.exists():
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
                creds = flow.run_local_server(port=0)
            else:
                print("WARNING: No Gmail credentials found. Email not sent.")
                print(f"  Place credentials.json at: {creds_path}")
                return False

            with open(token_path, "w") as token:
                token.write(creds.to_json())

        service = build("gmail", "v1", credentials=creds)

        message = MIMEText(html_content, "html")
        message["to"] = recipient
        message["subject"] = subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        body = {"raw": raw}

        service.users().messages().send(userId="me", body=body).execute()
        print(f"Email sent to {recipient}")
        return True

    except Exception as e:
        print(f"WARNING: Could not send email: {e}")
        print("Brief saved to file. Configure Gmail API credentials to enable sending.")
        return False


def save_brief(html_content: str, date_str: str) -> Path:
    """Save brief as dated HTML file."""
    BRIEFS_DIR.mkdir(exist_ok=True)
    filepath = BRIEFS_DIR / f"daily_brief_{date_str}.html"
    with open(filepath, "w") as f:
        f.write(html_content)
    print(f"Brief saved to: {filepath}")
    return filepath


async def run_daily_brief():
    """Execute the full daily brief pipeline."""
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\n{'='*50}")
    print(f"  Daily Sales Intelligence Brief - {today}")
    print(f"{'='*50}\n")

    # Step 1: Scrape news
    print("[1/7] Scraping news sources...")
    articles = await scrape_news_sources()
    # Filter excluded states
    filtered_articles = []
    for article in articles:
        regions = article.get("regions", [])
        if regions:
            valid = [r for r in regions if r.get("state") not in EXCLUDED_STATES]
            if valid:
                article["regions"] = valid
                filtered_articles.append(article)
        else:
            filtered_articles.append(article)
    articles = filtered_articles
    print(f"  Found {len(articles)} articles")

    # Step 2: Categorize (already done during scraping)
    print("[2/7] Articles categorized by region and urgency")
    for tier in ["URGENT", "THIS_WEEK", "FYI"]:
        count = sum(1 for a in articles if a.get("urgency") == tier)
        if count:
            print(f"  {tier}: {count} articles")

    # Save to cache
    cache = {
        "articles": articles,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
    with open(DATA_DIR / "news_cache.json", "w") as f:
        json.dump(cache, f, indent=2)

    # Step 3: Load accounts
    print("[3/7] Loading accounts...")
    accounts = load_accounts()
    print(f"  {len(accounts)} accounts loaded")

    # Step 4: Match news to accounts
    print("[4/7] Matching news to accounts...")
    account_matches = []
    for account in accounts:
        matched = match_news_to_account(account, articles)
        account_matches.append((account, matched))

    # Step 5: Score and rank, select top 5
    print("[5/7] Scoring and ranking accounts...")
    scored = []
    for account, matched in account_matches:
        s = score_account(account, matched)
        scored.append((account, matched, s))
    scored.sort(key=lambda x: x[2], reverse=True)
    top_5 = scored[:DAILY_BRIEF_TOP_N]

    for i, (acct, _, s) in enumerate(top_5, 1):
        print(f"  #{i} {acct['company_name']} (score: {s:.1f})")

    # Step 6: Generate talking points and Yardi angle
    print("[6/7] Generating talking points and product angles...")
    llm = LLMClient()
    resources = load_yardi_resources()
    products = load_products()

    account_briefs = []
    for account, matched_news, s in top_5:
        talking_points = await generate_talking_points(account, matched_news, llm)
        yardi_angle = get_yardi_product_angle(account, resources, products)

        account_briefs.append({
            "company_name": account["company_name"],
            "city": account.get("city", ""),
            "state": account.get("state", ""),
            "units": account.get("units", 0),
            "deal_stage": account.get("deal_stage", ""),
            "portfolio_type": account.get("portfolio_type", ""),
            "score": s,
            "matched_news": matched_news[:2],
            "talking_points": talking_points,
            "yardi_angle": yardi_angle,
        })

    # Build top accounts list for the HTML
    top_accounts = []
    for account, _, s in top_5:
        top_accounts.append({**account, "score": s})

    # Generate HTML
    html = format_daily_brief_html(today, articles, top_accounts, account_briefs)

    # Step 7a: Save brief
    print("[7/7] Saving and sending brief...")
    save_brief(html, today)

    # Step 7b: Send email
    subject = f"Daily Sales Intelligence Brief - {today}"
    if DAILY_BRIEF_RECIPIENT:
        send_gmail(html, subject, DAILY_BRIEF_RECIPIENT)
    else:
        print("Set DAILY_BRIEF_RECIPIENT in .env to enable email delivery.")

    print(f"\nDaily brief complete!")


if __name__ == "__main__":
    asyncio.run(run_daily_brief())
