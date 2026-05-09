"""
Build a Reddit team roster table from the Liquipedia DB API.
Replaces the HTML-scraping path in liqui/team_lookup.py.
"""

from liqui.liqui_db_api import client


def build_teams_markdown(tournament_page: str) -> str:
    """
    Return a Reddit markdown table of teams and their players.

    Args:
        tournament_page: Liquipedia page name, e.g. "RLCS/2025/World_Championship"

    Returns:
        Markdown string, empty string if no player data available.
    """
    players = client.get_players(tournament_page)
    if not players:
        return ""

    # Group player handles by team, preserving insertion order.
    teams: dict[str, list[str]] = {}
    for p in players:
        team = p.get("team") or p.get("faction") or "Unknown"
        handle = p.get("id") or p.get("name") or "?"
        teams.setdefault(team, []).append(handle)

    lines = ["|Team|Players|", "|:-|:-|"]
    for team_name, handles in teams.items():
        lines.append(f"|**{team_name}**|{', '.join(handles)}|")

    return "\n".join(lines)
