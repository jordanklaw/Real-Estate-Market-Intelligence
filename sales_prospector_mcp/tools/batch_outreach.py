"""Tool 6: Batch Outreach - generates multiple personalized emails."""

import json

from sales_prospector_mcp.config import (
    DATA_DIR,
    EXCLUDED_STATES,
    STATE_TO_REGION,
    EMAIL_TYPES,
)
from sales_prospector_mcp.utils.llm_client import LLMClient
from sales_prospector_mcp.utils.formatter import format_email

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


def _load_yardi_resources() -> dict:
    with open(DATA_DIR / "yardi_resources.json", "r") as f:
        return json.load(f)


def _filter_accounts(accounts: list[dict], criteria: dict) -> list[dict]:
    """Filter accounts by criteria dictionary."""
    filtered = accounts.copy()

    if "deal_stage" in criteria:
        stages = criteria["deal_stage"]
        if isinstance(stages, str):
            stages = [stages]
        filtered = [a for a in filtered if a.get("deal_stage") in stages]

    if "portfolio_type" in criteria:
        types = criteria["portfolio_type"]
        if isinstance(types, str):
            types = [types]
        filtered = [a for a in filtered if a.get("portfolio_type") in types]

    if "region" in criteria:
        regions = criteria["region"]
        if isinstance(regions, str):
            regions = [regions]
        filtered = [
            a for a in filtered
            if STATE_TO_REGION.get(a.get("state", "")) in regions
        ]

    if "state" in criteria:
        states = criteria["state"]
        if isinstance(states, str):
            states = [states]
        # Enforce exclusions
        states = [s for s in states if s not in EXCLUDED_STATES]
        filtered = [a for a in filtered if a.get("state") in states]

    if "min_units" in criteria:
        filtered = [a for a in filtered if a.get("units", 0) >= criteria["min_units"]]

    if "max_units" in criteria:
        filtered = [a for a in filtered if a.get("units", 0) <= criteria["max_units"]]

    if "current_product" in criteria:
        products = criteria["current_product"]
        if isinstance(products, str):
            products = [products]
        filtered = [
            a for a in filtered
            if any(p.lower() in a.get("current_product", "").lower() for p in products)
        ]

    return filtered


def _match_article_to_account(account: dict, articles: list[dict], used_articles: set) -> dict | None:
    """Find a distinct article for an account, avoiding reuse."""
    state = account.get("state", "")
    for article in articles:
        article_id = article.get("title", "")
        if article_id in used_articles:
            continue
        regions = article.get("regions", [])
        if not regions:
            used_articles.add(article_id)
            return article
        for region in regions:
            if region.get("state") == state:
                used_articles.add(article_id)
                return article
    # If no region match, use any unused article
    for article in articles:
        article_id = article.get("title", "")
        if article_id not in used_articles:
            used_articles.add(article_id)
            return article
    return None


async def sales_batch_outreach(
    criteria: dict | None = None,
    email_type: str = "outreach",
    news_driven: bool = False,
) -> str:
    """Generate batch personalized emails for filtered accounts.

    Filters accounts by criteria, then generates 1-15 personalized emails.
    When news_driven is True, each email gets matched to a distinct article.

    Args:
        criteria: Filter criteria dict. Keys: deal_stage, portfolio_type, region,
                  state, min_units, max_units, current_product.
        email_type: Type of email to generate. Defaults to "outreach".
        news_driven: When True, each email uses a distinct news article as hook.

    Returns:
        Formatted batch of personalized emails.
    """
    if email_type not in EMAIL_TYPES:
        return f"Invalid email type '{email_type}'. Must be one of: {', '.join(EMAIL_TYPES)}"

    accounts = _load_accounts()
    products = _load_products()
    templates = _load_templates()
    yardi_resources = _load_yardi_resources()

    # Filter accounts
    if criteria:
        accounts = _filter_accounts(accounts, criteria)

    if not accounts:
        return "No accounts match the specified criteria."

    # Limit to 15
    accounts = accounts[:15]

    # Load news if news_driven
    news_articles = []
    if news_driven:
        news_articles = _load_news_cache()
        if not news_articles:
            return (
                "No news articles in cache. Run sales_news_brief first to populate "
                "the news cache, then retry with news_driven=true."
            )

    email_template = templates.get("email_templates", {}).get(email_type, {})
    used_articles: set = set()
    emails = []

    for account in accounts:
        # Find product info
        product_info = None
        target = account.get("target_product", "").lower()
        for key, prod in products.items():
            if target in prod["name"].lower() or target in key.lower():
                product_info = prod
                break

        # Match news article if news_driven
        matched_article = None
        if news_driven:
            matched_article = _match_article_to_account(account, news_articles, used_articles)

        # Build LLM prompt
        system_prompt = (
            "You are a sales copywriter for Yardi. Write a concise, personalized email. "
            "Output format: SUBJECT: <subject>\n\n<body>. Keep under 150 words."
        )

        context = (
            f"Account: {account['company_name']}\n"
            f"Location: {account['city']}, {account['state']}\n"
            f"Units: {account['units']}\n"
            f"Portfolio: {account['portfolio_type']}\n"
            f"Stage: {account['deal_stage']}\n"
            f"Current Product: {account['current_product']}\n"
            f"Target Product: {account['target_product']}\n"
            f"Notes: {account.get('notes', '')}\n"
            f"Email Type: {email_type}\n"
            f"Tone: {email_template.get('tone', 'Professional')}\n"
        )

        if product_info:
            context += f"Product: {product_info['name']}\n"
            context += f"Value Props: {', '.join(product_info.get('key_value_props', [])[:2])}\n"

        if matched_article:
            context += (
                f"\nUse this news article as the email hook:\n"
                f"Title: {matched_article['title']}\n"
                f"Summary: {matched_article.get('summary', '')[:150]}\n"
                f"Urgency: {matched_article.get('urgency', 'FYI')}\n"
            )

        structure = email_template.get("structure", [])
        if structure:
            context += "\nEmail Structure:\n" + "\n".join(f"- {s}" for s in structure) + "\n"

        response = await _llm.generate(
            f"Draft this email:\n\n{context}",
            system=system_prompt,
        )

        # Parse response
        subject, body = _parse_response(response, account, email_template)

        email_output = format_email(account, email_type, subject, body)
        if matched_article:
            email_output += f"\n*News hook: {matched_article['title']}*"
        emails.append(email_output)

    # Combine all emails
    header = (
        f"# Batch Outreach: {len(emails)} Emails\n"
        f"**Type:** {email_type} | **News-driven:** {news_driven}\n"
        f"**Criteria:** {json.dumps(criteria) if criteria else 'All accounts'}\n\n"
        "---\n"
    )

    return header + "\n\n---\n\n".join(emails)


def _parse_response(response: str, account: dict, template: dict) -> tuple[str, str]:
    """Parse LLM email response into subject and body."""
    lines = response.strip().split("\n")
    subject = ""
    body_lines = []
    body_started = False

    for line in lines:
        if line.upper().startswith("SUBJECT:"):
            subject = line[len("SUBJECT:"):].strip()
        elif subject and (line.strip() or body_started):
            body_started = True
            body_lines.append(line)

    if not subject:
        pattern = template.get("subject_pattern", "Quick thought on {company_name}")
        subject = pattern.format(
            company_name=account["company_name"],
            topic=account.get("target_product", ""),
            market=f"{account['city']}, {account['state']}",
            product=account.get("target_product", ""),
            resource_topic="Industry insights",
        )

    body = "\n".join(body_lines).strip() if body_lines else response
    return subject, body
