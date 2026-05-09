"""
Build a Reddit prize pool table from the Liquipedia DB API.
Replaces the HTML-scraping path in liqui/prizepool_lookup.py.
"""

from liqui.liqui_db_api import client
from liqui.reddit_markdown._utils import format_money


def build_prizepool_markdown(tournament_page: str) -> str:
    """
    Return a Reddit markdown prize pool table.

    Args:
        tournament_page: Liquipedia page name.

    Returns:
        Markdown string, empty string if no placement data available.

    Note: RLCS points are not available via the DB API placement endpoint.
    """
    entries = client.get_prizepool(tournament_page)
    real = [
        e for e in entries
        if e.get("placement") and e.get("opponentname") not in ("TBD", "", None)
    ]
    if not real:
        return ""

    lines = ["|**Place**|**Prize**|**Team**|", "|:-|:-|:-|"]
    for e in real:
        placement = e.get("placement", "?")
        prize = format_money(e.get("prizemoney", 0))
        team = e.get("opponentname") or e.get("opponenttemplate") or "TBD"
        lines.append(f"|**{placement}**|{prize}|{team}|")

    return "\n".join(lines)
