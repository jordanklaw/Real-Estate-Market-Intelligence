"""Tool 4: Email Draft - generates personalized sales emails."""

import json

from sales_prospector_mcp.config import DATA_DIR, EMAIL_TYPES, EXCLUDED_STATES
from sales_prospector_mcp.utils.formatter import format_email
from sales_prospector_mcp.utils.llm_client import LLMClient

_llm = LLMClient()


def _load_accounts() -> list[dict]:
    with open(DATA_DIR / "accounts.json", "r") as f:
        accounts = json.load(f)
    return [a for a in accounts if a.get("state") not in EXCLUDED_STATES]


def _load_products() -> dict:
    with open(DATA_DIR / "products.json", "r") as f:
        return json.load(f)


def _load_templates() -> dict:
    with open(DATA_DIR / "templates.json", "r") as f:
        return json.load(f)


def _load_yardi_resources() -> dict:
    with open(DATA_DIR / "yardi_resources.json", "r") as f:
        return json.load(f)


def _load_news_cache() -> list[dict]:
    try:
        with open(DATA_DIR / "news_cache.json", "r") as f:
            cache = json.load(f)
        return cache.get("articles", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


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
    state = account.get("state", "")
    matched = []
    for article in articles:
        regions = article.get("regions", [])
        if not regions:
            # General/national news is relevant to all
            matched.append(article)
            continue
        for region in regions:
            if region.get("state") == state:
                matched.append(article)
                break
    urgency_order = {"URGENT": 0, "THIS_WEEK": 1, "FYI": 2}
    matched.sort(key=lambda a: urgency_order.get(a.get("urgency", "FYI"), 2))
    return matched[:3]


def _get_relevant_resources(news_items: list[dict], resources: dict) -> list[dict]:
    """Match news items to Yardi resource categories."""
    topic_categories = resources.get("topic_categories", {})
    matched_resources = []

    for article in news_items:
        text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
        for category, data in topic_categories.items():
            desc = data.get("description", "").lower()
            # Simple keyword overlap check
            desc_words = set(desc.split())
            text_words = set(text.split())
            if len(desc_words & text_words) >= 2:
                matched_resources.append({
                    "category": category,
                    "talking_points": data.get("talking_points", []),
                    "resources": data.get("resources", []),
                    "features": data.get("yardi_features", [])[:2],
                })
                break

    return matched_resources


async def sales_email_draft(
    company_name: str,
    email_type: str = "outreach",
    use_news: bool = True,
) -> str:
    """Draft a personalized email for a specific account.

    Email structure: news hook, bridge to their situation, Yardi resource link, soft CTA.

    Args:
        company_name: The company name to draft an email for.
        email_type: Type of email - outreach, follow_up, re_engage, pricing, or value_add.
        use_news: Whether to incorporate recent news into the email. Defaults to True.

    Returns:
        Formatted email draft with subject line and body.
    """
    if email_type not in EMAIL_TYPES:
        return f"Invalid email type '{email_type}'. Must be one of: {', '.join(EMAIL_TYPES)}"

    accounts = _load_accounts()
    account = _find_account(company_name, accounts)

    if not account:
        return (
            f"Account '{company_name}' not found. "
            f"Available: {', '.join(a['company_name'] for a in accounts)}"
        )

    products = _load_products()
    templates = _load_templates()
    yardi_resources = _load_yardi_resources()
    product_info = _find_product(account.get("target_product", ""), products)

    # Get email template
    email_template = templates.get("email_templates", {}).get(email_type, {})

    # News matching
    news_items = []
    resource_matches = []
    if use_news:
        news_articles = _load_news_cache()
        news_items = _match_news_to_account(account, news_articles)
        resource_matches = _get_relevant_resources(news_items, yardi_resources)

    # Build LLM prompt
    system_prompt = (
        "You are a senior sales copywriter for Yardi property management software. "
        "Write concise, personalized sales emails that feel human and consultative. "
        "Never be pushy or generic. Every sentence should demonstrate understanding "
        "of their specific situation. Output ONLY the email subject and body, "
        "formatted as:\nSUBJECT: <subject line>\n\n<email body>"
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
        f"\nEmail Type: {email_type}\n"
        f"Tone: {email_template.get('tone', 'Professional and consultative')}\n"
        f"Max Length: {email_template.get('length', '150 words')}\n"
    )

    structure = email_template.get("structure", [])
    if structure:
        context += "\nRequired Structure:\n"
        for s in structure:
            context += f"- {s}\n"

    if product_info:
        context += f"\nTarget Product: {product_info['name']}\n"
        context += f"Key Value Props: {', '.join(product_info.get('key_value_props', [])[:3])}\n"

    if news_items:
        context += "\nRelevant News (use as hooks):\n"
        for news in news_items[:2]:
            context += f"- [{news.get('urgency', 'FYI')}] {news['title']}"
            if news.get("summary"):
                context += f": {news['summary'][:100]}"
            context += "\n"

    if resource_matches:
        context += "\nYardi Resources to Reference:\n"
        for rm in resource_matches[:2]:
            context += f"- Category: {rm['category']}\n"
            if rm.get("resources"):
                context += f"  Resource: {rm['resources'][0]}\n"
            if rm.get("talking_points"):
                context += f"  Talking Point: {rm['talking_points'][0]}\n"

    llm_response = await _llm.generate(
        f"Draft this sales email:\n\n{context}",
        system=system_prompt,
    )

    # Parse subject and body from LLM response
    subject, body = _parse_email_response(llm_response, account, email_type, email_template)

    return format_email(account, email_type, subject, body)


def _parse_email_response(
    response: str, account: dict, email_type: str, template: dict
) -> tuple[str, str]:
    """Parse LLM response into subject and body."""
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
        # Use template pattern as fallback
        pattern = template.get("subject_pattern", "Quick thought on {company_name}")
        subject = pattern.format(
            company_name=account["company_name"],
            topic=account.get("target_product", "property management"),
            market=f"{account['city']}, {account['state']}",
            product=account.get("target_product", "Yardi"),
            resource_topic="Industry insights",
        )

    body = "\n".join(body_lines).strip() if body_lines else response

    return subject, body
