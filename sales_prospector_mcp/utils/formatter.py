"""Output formatting utilities for all tools."""

from datetime import datetime


def format_news_brief(articles: list[dict]) -> str:
    """Format news articles into a readable brief."""
    if not articles:
        return "No articles found."

    # Group by urgency
    grouped = {"URGENT": [], "THIS_WEEK": [], "FYI": []}
    for article in articles:
        tier = article.get("urgency", "FYI")
        if tier not in grouped:
            tier = "FYI"
        grouped[tier].append(article)

    lines = ["# Sales News Brief", f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*", ""]

    tier_labels = {
        "URGENT": "🔴 URGENT — Action Required",
        "THIS_WEEK": "🟡 THIS WEEK — Monitor Closely",
        "FYI": "🔵 FYI — Background Intel",
    }

    for tier in ["URGENT", "THIS_WEEK", "FYI"]:
        tier_articles = grouped[tier]
        if not tier_articles:
            continue

        lines.append(f"## {tier_labels[tier]}")
        lines.append("")

        for article in tier_articles:
            regions_str = ""
            if article.get("regions"):
                region_names = list(set(r["region"] for r in article["regions"]))
                regions_str = f" [{', '.join(region_names)}]"

            lines.append(f"### {article['title']}{regions_str}")
            lines.append(f"*Source: {article.get('source_name', article.get('source', 'Unknown'))}*")
            if article.get("url"):
                lines.append(f"[Read more]({article['url']})")
            if article.get("summary"):
                lines.append(f"\n{article['summary']}")
            lines.append("")

    return "\n".join(lines)


def format_call_prep(
    account: dict,
    research: dict,
    news_items: list[dict],
    product_info: dict,
    meeting_type: str,
    llm_content: str,
) -> str:
    """Format a call prep sheet."""
    lines = [
        f"# Call Prep: {account['company_name']}",
        f"**Meeting Type:** {meeting_type.replace('_', ' ').title()}",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d')}",
        "",
        "## Account Overview",
        f"- **Company:** {account['company_name']}",
        f"- **Location:** {account['city']}, {account['state']}",
        f"- **Units:** {account['units']:,}",
        f"- **Portfolio Type:** {account['portfolio_type']}",
        f"- **Deal Stage:** {account['deal_stage']}",
        f"- **Last Contact:** {account['last_contact']}",
        f"- **Current Product:** {account['current_product']}",
        f"- **Target Product:** {account['target_product']}",
        "",
    ]

    if account.get("notes"):
        lines.extend([
            "## Internal Notes",
            account["notes"],
            "",
        ])

    if product_info:
        product_name = product_info.get("name", account["target_product"])
        lines.extend([
            f"## Product Focus: {product_name}",
            f"**Target Segment:** {product_info.get('target_segment', 'N/A')}",
            "",
            "**Key Value Props:**",
        ])
        for prop in product_info.get("key_value_props", [])[:4]:
            lines.append(f"- {prop}")
        lines.append("")

    if news_items:
        lines.append("## Relevant News")
        for item in news_items[:3]:
            lines.append(f"- **[{item.get('urgency', 'FYI')}]** {item['title']}")
        lines.append("")

    if research and not research.get("error"):
        lines.append("## Live Research")
        if research.get("title"):
            lines.append(f"**Website:** {research['title']}")
        if research.get("description"):
            lines.append(f"**About:** {research['description']}")
        lines.append("")

    if llm_content:
        lines.extend([
            "## AI-Generated Prep Notes",
            llm_content,
            "",
        ])

    return "\n".join(lines)


def format_email(
    account: dict,
    email_type: str,
    subject: str,
    body: str,
) -> str:
    """Format a drafted email."""
    lines = [
        f"# Email Draft: {email_type.replace('_', ' ').title()}",
        f"**To:** {account['company_name']}",
        f"**Subject:** {subject}",
        "",
        "---",
        "",
        body,
        "",
        "---",
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
        f"Account: {account['company_name']} ({account['deal_stage']})*",
    ]
    return "\n".join(lines)


def format_pipeline_table(ranked_accounts: list[dict]) -> str:
    """Format ranked accounts into a pipeline table."""
    if not ranked_accounts:
        return "No accounts to display."

    lines = [
        "# Pipeline Rankings",
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
        "| Rank | Company | State | Units | Stage | Score | Last Contact | Recommended Action |",
        "|------|---------|-------|-------|-------|-------|--------------|--------------------|",
    ]

    for i, acct in enumerate(ranked_accounts, 1):
        lines.append(
            f"| {i} | {acct['company_name']} | {acct['state']} | "
            f"{acct['units']:,} | {acct['deal_stage']} | "
            f"{acct.get('score', 0):.1f} | {acct['last_contact']} | "
            f"{acct.get('recommended_action', 'N/A')} |"
        )

    lines.append("")
    lines.append(f"*{len(ranked_accounts)} accounts ranked*")
    return "\n".join(lines)


def format_daily_brief_html(
    date: str,
    news_articles: list[dict],
    top_accounts: list[dict],
    account_briefs: list[dict],
) -> str:
    """Format the daily brief as HTML email."""
    html = f"""<!DOCTYPE html>
<html>
<head>
<style>
  body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; color: #333; }}
  h1 {{ color: #1a5276; border-bottom: 3px solid #1a5276; padding-bottom: 10px; }}
  h2 {{ color: #2c3e50; margin-top: 30px; }}
  h3 {{ color: #34495e; }}
  .urgent {{ border-left: 4px solid #e74c3c; padding-left: 12px; margin: 10px 0; }}
  .this-week {{ border-left: 4px solid #f39c12; padding-left: 12px; margin: 10px 0; }}
  .fyi {{ border-left: 4px solid #3498db; padding-left: 12px; margin: 10px 0; }}
  .account-card {{ background: #f8f9fa; border-radius: 8px; padding: 16px; margin: 12px 0; border: 1px solid #dee2e6; }}
  .account-card h3 {{ margin-top: 0; color: #1a5276; }}
  .score {{ display: inline-block; background: #1a5276; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.9em; }}
  .tag {{ display: inline-block; background: #e8f4f8; color: #1a5276; padding: 2px 8px; border-radius: 4px; font-size: 0.85em; margin: 2px; }}
  .talking-point {{ margin: 6px 0; padding: 4px 0; }}
  .product-angle {{ background: #eafaf1; padding: 10px; border-radius: 4px; margin-top: 8px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
  th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #ddd; }}
  th {{ background: #1a5276; color: white; }}
  tr:nth-child(even) {{ background: #f2f2f2; }}
  .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; color: #888; font-size: 0.85em; }}
  a {{ color: #2980b9; }}
</style>
</head>
<body>
<h1>Daily Sales Intelligence Brief</h1>
<p><strong>Date:</strong> {date} | <strong>Prepared for:</strong> Jordan Law</p>

<h2>Market News</h2>
"""

    # News section grouped by urgency
    tier_config = {
        "URGENT": ("urgent", "URGENT — Action Required"),
        "THIS_WEEK": ("this-week", "THIS WEEK — Monitor Closely"),
        "FYI": ("fyi", "FYI — Background Intel"),
    }

    grouped_news = {"URGENT": [], "THIS_WEEK": [], "FYI": []}
    for article in news_articles:
        tier = article.get("urgency", "FYI")
        if tier not in grouped_news:
            tier = "FYI"
        grouped_news[tier].append(article)

    for tier in ["URGENT", "THIS_WEEK", "FYI"]:
        articles = grouped_news[tier]
        if not articles:
            continue
        css_class, label = tier_config[tier]
        html += f'<h3>{label}</h3>\n'
        for article in articles:
            regions_str = ""
            if article.get("regions"):
                region_names = list(set(r["region"] for r in article["regions"]))
                regions_str = " — " + ", ".join(r.replace("_", " ").title() for r in region_names)
            html += f'<div class="{css_class}">\n'
            html += f'<strong>{article["title"]}</strong>{regions_str}<br>\n'
            if article.get("summary"):
                html += f'<em>{article["summary"][:200]}</em><br>\n'
            if article.get("url"):
                html += f'<a href="{article["url"]}">Read more</a>\n'
            html += '</div>\n'

    # Top accounts section
    html += '<h2>Top 5 Priority Accounts</h2>\n'
    html += '<table>\n<tr><th>#</th><th>Company</th><th>Location</th><th>Stage</th><th>Units</th><th>Priority Score</th></tr>\n'

    for i, acct in enumerate(top_accounts[:5], 1):
        html += f'<tr><td>{i}</td><td>{acct["company_name"]}</td><td>{acct.get("city", "")}, {acct["state"]}</td>'
        html += f'<td>{acct["deal_stage"]}</td><td>{acct["units"]:,}</td>'
        html += f'<td>{acct.get("score", 0):.1f}</td></tr>\n'

    html += '</table>\n'

    # Account briefs
    html += '<h2>Account Intelligence</h2>\n'
    for brief in account_briefs:
        html += '<div class="account-card">\n'
        html += f'<h3>{brief["company_name"]} <span class="score">{brief.get("score", 0):.1f}</span></h3>\n'
        html += f'<p><span class="tag">{brief.get("deal_stage", "")}</span> '
        html += f'<span class="tag">{brief.get("portfolio_type", "")}</span> '
        html += f'<span class="tag">{brief.get("city", "")}, {brief.get("state", "")}</span></p>\n'

        if brief.get("matched_news"):
            html += '<p><strong>Relevant News:</strong></p>\n<ul>\n'
            for news in brief["matched_news"][:2]:
                html += f'<li><strong>[{news.get("urgency", "FYI")}]</strong> {news.get("title", "")}</li>\n'
            html += '</ul>\n'

        if brief.get("talking_points"):
            html += '<p><strong>Talking Points:</strong></p>\n<ul>\n'
            for point in brief["talking_points"]:
                html += f'<li class="talking-point">{point}</li>\n'
            html += '</ul>\n'

        if brief.get("yardi_angle"):
            html += f'<div class="product-angle"><strong>Yardi Product Angle:</strong> {brief["yardi_angle"]}</div>\n'

        html += '</div>\n'

    html += f"""
<div class="footer">
<p>This brief was auto-generated by Sales Prospector MCP.<br>
Data sources: Multi-Housing News, Commercial Property Executive<br>
Generated: {date}</p>
</div>
</body>
</html>"""

    return html
