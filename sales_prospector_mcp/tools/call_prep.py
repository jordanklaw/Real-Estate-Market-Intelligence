"""Tool 3: Call Prep - generates one-page call prep sheets."""

import json

from sales_prospector_mcp.config import (
    DATA_DIR,
    MEETING_TYPES,
    EXCLUDED_STATES,
)
from sales_prospector_mcp.utils.web_scraper import search_duckduckgo, scrape_homepage
from sales_prospector_mcp.utils.formatter import format_call_prep
from sales_prospector_mcp.utils.llm_client import LLMClient

_llm = LLMClient()


def _load_accounts() -> list[dict]:
    with open(DATA_DIR / "accounts.json", "r") as f:
        accounts = json.load(f)
    return [a for a in accounts if a.get("state") not in EXCLUDED_STATES]


def _load_products() -> dict:
    with open(DATA_DIR / "products.json", "r") as f:
        return json.load(f)


def _load_news_cache() -> list[dict]:
    try:
        with open(DATA_DIR / "news_cache.json", "r") as f:
            cache = json.load(f)
        return cache.get("articles", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _load_templates() -> dict:
    with open(DATA_DIR / "templates.json", "r") as f:
        return json.load(f)


def _find_account(company_name: str, accounts: list[dict]) -> dict | None:
    name_lower = company_name.lower()
    for account in accounts:
        if name_lower in account["company_name"].lower():
            return account
    return None


def _find_product(target_product: str, products: dict) -> dict | None:
    target_lower = target_product.lower()
    for key, product in products.items():
        if target_lower in product["name"].lower() or target_lower in key.lower():
            return product
    return None


def _match_news_to_account(account: dict, articles: list[dict]) -> list[dict]:
    """Find news articles relevant to an account's region and portfolio type."""
    state = account.get("state", "")
    matched = []
    for article in articles:
        regions = article.get("regions", [])
        if not regions:
            continue
        for region in regions:
            if region.get("state") == state:
                matched.append(article)
                break
    # Sort by urgency
    urgency_order = {"URGENT": 0, "THIS_WEEK": 1, "FYI": 2}
    matched.sort(key=lambda a: urgency_order.get(a.get("urgency", "FYI"), 2))
    return matched[:5]


async def sales_prep_call(company_name: str, meeting_type: str = "discovery") -> str:
    """Generate a one-page call prep sheet for an account.

    Pulls from accounts.json, live research, news cache, and products.json
    to create a comprehensive prep sheet tailored to the meeting type.

    Args:
        company_name: The company name to prepare for.
        meeting_type: Type of meeting - discovery, demo, follow_up, negotiation, or renewal.

    Returns:
        Formatted call prep sheet.
    """
    if meeting_type not in MEETING_TYPES:
        return f"Invalid meeting type '{meeting_type}'. Must be one of: {', '.join(MEETING_TYPES)}"

    accounts = _load_accounts()
    account = _find_account(company_name, accounts)

    if not account:
        return (
            f"Account '{company_name}' not found in accounts.json. "
            f"Available accounts: {', '.join(a['company_name'] for a in accounts)}"
        )

    # Load supporting data
    products = _load_products()
    product_info = _find_product(account.get("target_product", ""), products)
    news_articles = _load_news_cache()
    matched_news = _match_news_to_account(account, news_articles)
    templates = _load_templates()

    # Live research
    search_results = await search_duckduckgo(
        f"{account['company_name']} property management", max_results=3
    )

    # Try homepage scrape
    research = {}
    for r in search_results:
        url = r.get("url", "")
        if url and account["company_name"].lower().split()[0] in url.lower():
            research = await scrape_homepage(url)
            break

    # Get template sections for this meeting type
    template = templates.get("call_prep_templates", {}).get(meeting_type, {})
    sections = template.get("sections", [])

    # Generate LLM content
    system_prompt = (
        "You are a senior sales strategist preparing a call prep sheet for a "
        "Yardi property management software sales rep. Be specific, actionable, "
        "and concise. Tailor everything to this specific account and meeting type."
    )

    context = (
        f"Account: {account['company_name']}\n"
        f"Location: {account['city']}, {account['state']}\n"
        f"Units: {account['units']}\n"
        f"Portfolio Type: {account['portfolio_type']}\n"
        f"Deal Stage: {account['deal_stage']}\n"
        f"Current Product: {account['current_product']}\n"
        f"Target Product: {account['target_product']}\n"
        f"Last Contact: {account['last_contact']}\n"
        f"Notes: {account.get('notes', 'None')}\n"
        f"\nMeeting Type: {meeting_type}\n"
        f"\nRequired Sections:\n" + "\n".join(f"- {s}" for s in sections)
    )

    if product_info:
        context += f"\n\nTarget Product Info:\n"
        context += f"Name: {product_info['name']}\n"
        context += f"Segment: {product_info['target_segment']}\n"
        context += f"Key Props: {', '.join(product_info.get('key_value_props', [])[:3])}\n"

        # Add relevant objection handling
        objections = product_info.get("common_objections", {})
        if objections:
            context += "\nCommon Objections & Responses:\n"
            for obj, response in list(objections.items())[:3]:
                context += f"- {obj}: {response}\n"

    if matched_news:
        context += "\n\nRelevant Market News:\n"
        for news in matched_news[:3]:
            context += f"- [{news.get('urgency', 'FYI')}] {news['title']}\n"

    if search_results:
        context += "\n\nRecent Search Findings:\n"
        for r in search_results[:3]:
            context += f"- {r['title']}: {r.get('snippet', '')[:100]}\n"

    llm_content = await _llm.generate(
        f"Generate a detailed call prep sheet:\n\n{context}",
        system=system_prompt,
    )

    return format_call_prep(
        account=account,
        research=research,
        news_items=matched_news,
        product_info=product_info or {},
        meeting_type=meeting_type,
        llm_content=llm_content,
    )
