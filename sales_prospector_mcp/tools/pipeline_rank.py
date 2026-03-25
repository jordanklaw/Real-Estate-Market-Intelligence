"""Tool 5: Pipeline Rank - scores and ranks accounts."""

import json
from datetime import datetime

from sales_prospector_mcp.config import (
    DATA_DIR,
    EXCLUDED_STATES,
    DEAL_STAGE_WEIGHTS,
    STATE_TO_REGION,
)
from sales_prospector_mcp.utils.formatter import format_pipeline_table


def _load_accounts() -> list[dict]:
    with open(DATA_DIR / "accounts.json", "r") as f:
        accounts = json.load(f)
    return [a for a in accounts if a.get("state") not in EXCLUDED_STATES]


def _days_since_contact(last_contact: str) -> int:
    """Calculate days since last contact."""
    try:
        contact_date = datetime.strptime(last_contact, "%Y-%m-%d")
        return (datetime.now() - contact_date).days
    except (ValueError, TypeError):
        return 999  # Very stale = high urgency


def _score_account(account: dict) -> float:
    """Score an account based on deal stage, recency, unit count, and territory."""
    score = 0.0

    # Deal stage weight (0-9)
    stage = account.get("deal_stage", "prospect")
    score += DEAL_STAGE_WEIGHTS.get(stage, 0) * 3

    # Recency score - more days since contact = higher urgency
    days = _days_since_contact(account.get("last_contact", ""))
    if days <= 7:
        score += 5  # Recently contacted, still warm
    elif days <= 14:
        score += 10  # Due for follow-up
    elif days <= 30:
        score += 15  # Getting stale
    elif days <= 60:
        score += 12  # At risk
    else:
        score += 8  # May be cold

    # Unit count score (larger portfolios = higher value)
    units = account.get("units", 0)
    if units >= 5000:
        score += 15
    elif units >= 2000:
        score += 12
    elif units >= 1000:
        score += 8
    elif units >= 500:
        score += 5
    else:
        score += 3

    # Territory bonus - covered states get a boost
    state = account.get("state", "")
    if state in STATE_TO_REGION:
        score += 5

    # Legacy upgrade bonus
    current = account.get("current_product", "").lower()
    if any(legacy in current for legacy in ["genesis", "professional", "dos"]):
        score += 8  # Easy upgrade path

    # Competitor switch bonus
    if any(comp in current for comp in ["appfolio", "realpage", "buildium", "mri", "propertyware"]):
        score += 5

    return score


def _recommend_action(account: dict) -> str:
    """Generate recommended next action based on account state."""
    stage = account.get("deal_stage", "prospect")
    days = _days_since_contact(account.get("last_contact", ""))

    if stage == "closed":
        return "Account closed - monitor for expansion"
    elif stage == "negotiation":
        if days > 7:
            return "URGENT: Follow up on negotiation - risk of going cold"
        return "Continue negotiation - prepare counter/concession"
    elif stage == "proposal":
        if days > 14:
            return "Re-engage on proposal - send new value-add content"
        return "Check in on proposal review status"
    elif stage == "demo":
        if days > 7:
            return "Follow up on demo - address remaining questions"
        return "Prepare post-demo proposal with tailored pricing"
    elif stage == "discovery":
        if days > 14:
            return "Re-engage with relevant market news or case study"
        return "Schedule demo - confirm pain points and priorities"
    elif stage == "prospect":
        if days > 30:
            return "Re-engage with fresh outreach - new hook needed"
        return "Initial outreach - personalized email with news hook"
    elif stage == "follow_up":
        if days > 14:
            return "URGENT: Risk of losing momentum - call or value-add email"
        return "Send follow-up with new information or resource"

    return "Review account and determine next step"


async def sales_pipeline_rank(top_n: int = 10) -> str:
    """Score and rank all accounts by priority.

    Scores each account based on deal stage, days since last contact,
    unit count, and territory coverage. Returns ranked list with
    recommended next actions.

    Args:
        top_n: Number of top accounts to return. Defaults to 10.

    Returns:
        Formatted pipeline ranking table with scores and recommended actions.
    """
    accounts = _load_accounts()

    if not accounts:
        return "No accounts found in accounts.json."

    # Score all accounts
    for account in accounts:
        account["score"] = _score_account(account)
        account["recommended_action"] = _recommend_action(account)

    # Sort by score descending
    accounts.sort(key=lambda a: a["score"], reverse=True)

    # Limit to top N
    top_accounts = accounts[:top_n]

    result = format_pipeline_table(top_accounts)

    # Add detailed breakdown
    result += "\n\n## Detailed Breakdown\n"
    for i, acct in enumerate(top_accounts, 1):
        days = _days_since_contact(acct.get("last_contact", ""))
        result += (
            f"\n### {i}. {acct['company_name']} (Score: {acct['score']:.1f})\n"
            f"- **Stage:** {acct['deal_stage']} | **Days since contact:** {days}\n"
            f"- **Current:** {acct['current_product']} → **Target:** {acct['target_product']}\n"
            f"- **Action:** {acct['recommended_action']}\n"
        )

    return result
