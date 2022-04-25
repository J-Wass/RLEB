from bs4 import BeautifulSoup
import requests
import re
import traceback

import rleb_settings
import rleb_stdout
from rleb_liqui import rleb_liqui_utils


async def handle_swiss_lookup(url, channel):
    """Handle swiss table lookup message.

    Args:
        channel (discord.channel.TextChannel): Channel the lookup is being used in.
        url (str): Liquipedia URL string to look for swiss tables.
    """
    rleb_settings.rleb_log_info("DISCORD: Creating lookup for {0}".format(url))

    try:
        content = None
        try:
            content = rleb_liqui_utils.get_page_html_from_url(url)
        except Exception as e:
            await channel.send("Couldn't load {0} !\nError: {1}".format(url, e))
            rleb_settings.rleb_log_info(
                "SWISS: Couldn't load {0}!\nError: {1}".format(url, e)
            )
            rleb_settings.rleb_log_error(traceback.format_exc())
            return

        html = BeautifulSoup(content, "html.parser")

        # The indicator that each cell in the swiss table starts with.
        indicator = {
            "swisstable-bgc-win": "✔️",
            "swisstable-bgc-lose": "❌",
            "swisstable-bgc-": "",
        }

        # Mapping from team name to team acronym.
        acronym_map = {}

        # Find all cells that mention both team name and acronym.
        teams = html.select("div.brkts-matchlist-cell.brkts-matchlist-opponent")
        for t in teams:
            raw_team_name = t.get("aria-label")
            if raw_team_name is None:
                continue

            # Strip years (YYYY) from aria-label.
            team_name = re.sub(r"\s[\d]{4}", "", raw_team_name).lower()
            team_acronym = t.text

            # Add to mapping.
            acronym_map[team_name] = team_acronym

        def name_to_acronym(full_team_name):
            """Takes a team name and returns it's acroynm. If the acronym isn't found, returns the full name."""
            normalized = full_team_name.lower()
            return (
                acronym_map[normalized] if normalized in acronym_map else full_team_name
            )

        tables = []
        for s in html.select("table.swisstable"):
            rows = []
            rows.append(
                "|**#**|**Teams**|**W-L**|**Round 1**|**Round 2**|**Round 3**|**Round 4**|**Round 5**|"
            )
            rows.append("|:-|:-|:-|:-|:-|:-|:-|:-|")
            for t in s.select("tr")[1:]:
                row = []
                row.append(t.select("th")[0].text.replace(".", " "))
                team_name = name_to_acronym(t.select("span.team-template-text")[0].text)
                team_link = t.select("span.team-template-text a")
                if team_link is None or len(team_link) == 0:
                    team_markdown = "**" + team_name + "**"
                else:
                    href = team_link[0]["href"].replace("(", "\(").replace(")", "\)")
                    if "https://liquipedia.net" not in href:
                        href = "https://liquipedia.net" + href
                    team_markdown = "[**" + team_name + "**](" + href + ")"
                row.append(team_markdown)
                row.append("**" + t.select("b")[0].text + "**")
                for m in t.select('td[class^="swisstable-bgc"]'):
                    match = indicator[m["class"][0]]
                    match += " " + m.text.replace(":", "-")
                    other_team = m.select('span[class^="team-template"] a')
                    if len(other_team) > 0:
                        match += " " + name_to_acronym(other_team[0]["title"])
                    row.append(match)
                rows.append("|".join(row))
            rows.insert(int(len(rows) / 2) + 1, "|\-|\- - - - -|\- - -||||||")
            table = "\n".join(rows)
            tables.append(table)
        await rleb_stdout.print_to_channel(
            channel, "\n".join(tables), title="Swiss Bracket"
        )
    except Exception as e:
        await channel.send(
            "Couldn't find swiss group in {0}. Error: {1}.".format(url, e)
        )
        rleb_settings.rleb_log_info(
            "SWISS: Couldn't find swiss group in {0}.\nError: {1}\nTraceback: {2}".format(
                url, e, traceback.format_exc()
            )
        )
        rleb_settings.rleb_log_error(traceback.format_exc())
