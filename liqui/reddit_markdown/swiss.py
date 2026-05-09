"""
Build a Reddit Swiss-bracket standings table from the Liquipedia DB API.
Replaces the HTML-scraping path in liqui/swiss_lookup.py.
"""

import re

from liqui.liqui_db_api import client
from liqui.reddit_markdown._utils import opponent_name

WIN = "✔️"
LOSS = "❌"


def _round_number(match: dict) -> int:
    """Extract round number from match2bracketdata.inheritedheader."""
    header = (match.get("match2bracketdata") or {}).get("inheritedheader", "")
    m = re.search(r"\d+", header)
    return int(m.group()) if m else 0


def build_swiss_markdown(tournament_page: str) -> str:
    """
    Return a Reddit markdown Swiss-bracket standings table.

    Args:
        tournament_page: Liquipedia page name.

    Returns:
        Markdown string, empty string if no Swiss standings available.
    """
    tables = client.get_standings(tournament_page, standings_type="swiss")
    if not tables:
        return ""

    matches = client.get_matches(tournament_page, limit=500)

    # Per-team per-round result: {team: {round: {won: bool, opponent: str}}}
    round_results: dict[str, dict[int, dict]] = {}
    win_loss: dict[str, dict] = {}

    for match in matches:
        if not match.get("finished"):
            continue
        opponents = match.get("match2opponents", [])
        if len(opponents) < 2:
            continue
        opp1, opp2 = opponents[0], opponents[1]
        name1, name2 = opponent_name(opp1), opponent_name(opp2)
        if name1 == "TBD" or name2 == "TBD":
            continue

        winner = str(match.get("winner", ""))
        rnd = _round_number(match)

        for name in (name1, name2):
            round_results.setdefault(name, {})
            win_loss.setdefault(name, {"wins": 0, "losses": 0})

        round_results[name1][rnd] = {"won": winner == "1", "opponent": name2}
        round_results[name2][rnd] = {"won": winner == "2", "opponent": name1}

        if winner == "1":
            win_loss[name1]["wins"] += 1
            win_loss[name2]["losses"] += 1
        elif winner == "2":
            win_loss[name2]["wins"] += 1
            win_loss[name1]["losses"] += 1

    if not round_results:
        return ""

    max_round = max(
        (r for team_rounds in round_results.values() for r in team_rounds),
        default=5,
    )
    num_rounds = max(max_round, 5)

    round_headers = "|".join(f"**Round {r}**" for r in range(1, num_rounds + 1))
    header = f"|**#**|**Teams**|**W-L**|{round_headers}|"
    sep = "|:-|:-|:-|" + ":-|" * num_rounds

    sorted_teams = sorted(
        round_results.keys(),
        key=lambda t: (-win_loss[t]["wins"], win_loss[t]["losses"]),
    )

    lines = [header, sep]
    mid = len(sorted_teams) // 2
    for i, name in enumerate(sorted_teams, 1):
        if i == mid + 1:
            lines.append(r"|\-|\- - - - -|\- - -|" + "|" * num_rounds)
        wl = win_loss[name]
        record = f"{wl['wins']}-{wl['losses']}"
        rounds_str = ""
        for r in range(1, num_rounds + 1):
            result = round_results[name].get(r)
            if result:
                icon = WIN if result["won"] else LOSS
                rounds_str += f"|{icon} {result['opponent']}"
            else:
                rounds_str += "|"
        lines.append(f"|{i}|**{name}**|{record}{rounds_str}|")

    return "\n".join(lines)
