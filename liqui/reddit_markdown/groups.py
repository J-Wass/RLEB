"""
Build a Reddit group standings table from the Liquipedia DB API.
Replaces the HTML-scraping path in liqui/group_lookup.py.
"""

from liqui.liqui_db_api import client
from liqui.reddit_markdown._utils import opponent_name


def _compute_records(match_ids: list[str], matches_by_id: dict) -> dict:
    """Return {team: {wins, losses, gw, gl}} computed from finished matches."""
    records: dict[str, dict] = {}
    for mid in match_ids:
        match = matches_by_id.get(mid)
        if not match or not match.get("finished"):
            continue
        opponents = match.get("match2opponents", [])
        if len(opponents) < 2:
            continue
        opp1, opp2 = opponents[0], opponents[1]
        name1, name2 = opponent_name(opp1), opponent_name(opp2)
        if name1 == "TBD" or name2 == "TBD":
            continue
        score1 = max(int(opp1.get("score") or 0), 0)
        score2 = max(int(opp2.get("score") or 0), 0)
        winner = str(match.get("winner", ""))

        for name in (name1, name2):
            records.setdefault(name, {"wins": 0, "losses": 0, "gw": 0, "gl": 0})

        if winner == "1":
            records[name1]["wins"] += 1
            records[name2]["losses"] += 1
        elif winner == "2":
            records[name2]["wins"] += 1
            records[name1]["losses"] += 1

        records[name1]["gw"] += score1
        records[name1]["gl"] += score2
        records[name2]["gw"] += score2
        records[name2]["gl"] += score1

    return records


def build_groups_markdown(tournament_page: str) -> str:
    """
    Return a Reddit markdown group standings table.

    Args:
        tournament_page: Liquipedia page name.

    Returns:
        Markdown string (multiple groups separated by spacers),
        empty string if no standings data available.
    """
    tables = client.get_standings(tournament_page)
    if not tables:
        return ""

    matches = client.get_matches(tournament_page, limit=500)
    matches_by_id: dict[str, dict] = {
        m["match2id"]: m for m in matches if "match2id" in m
    }

    spacer = " &#x200B;" * 4
    sections: list[str] = []

    for table in tables:
        group_name = table.get("title", "Group")
        match_ids: list[str] = table.get("matches") or []

        records = _compute_records(match_ids, matches_by_id)
        sorted_teams = sorted(
            records.items(),
            key=lambda x: (x[1]["wins"], x[1]["gw"] - x[1]["gl"]),
            reverse=True,
        )

        lines = [
            "||||",
            "|:-|:-|:-|:-|",
            f"|**#**|**{group_name}**{spacer} |**Matches** |**Game Diff** |",
        ]
        for i, (name, rec) in enumerate(sorted_teams, 1):
            diff = rec["gw"] - rec["gl"]
            diff_str = f"+{diff}" if diff >= 0 else str(diff)
            lines.append(f"|{i}|**{name}**|{rec['wins']}-{rec['losses']}|{diff_str}|")

        sections.append("\n".join(lines))

    return "\n\n&#x200B;\n\n".join(sections)
