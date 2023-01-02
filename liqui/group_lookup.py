from bs4 import BeautifulSoup
import time
import traceback

import global_settings
import stdout
from liqui import liqui_utils
from . import diesel


async def handle_group_lookup(url, channel):
    """Handle group lookup message.

    Args:
        channel (discord.Channel): Channel the lookup is being used in.
        url (str): Liquipedia URL string to look for groups.
    """

    start = time.time()
    global_settings.rleb_log_info("DISCORD: Creating group lookup for {0}".format(url))

    # Attempt to load markdown from Diesel.
    await channel.send("Building group table from Diesel...")
    markdown = await diesel.get_group_markdown(url)
    if markdown:
        await stdout.print_to_channel(channel, markdown, title="Groups")
        return

    # If Diesel fails, fallback to RLEB, python parsing.
    await channel.send("Failed to build group table from Diesel. Trying RLEB...")
    try:
        page = None
        try:
            page = liqui_utils.get_page_html_from_url(url)
        except Exception as e:
            await channel.send("Couldn't load {0}!\nError: {1}".format(url, e))
            global_settings.rleb_log_info(
                "TEAMS: Couldn't load {0}!\nError: {1}".format(url, e)
            )
            global_settings.rleb_log_error(traceback.format_exc())
            return

        html = BeautifulSoup(page, "html.parser")

        GROUP_TEMPLATE_HEADER = "|||||\n|:-|:-|:-|:-|\n|**#**|**{GROUP_NAME}** &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; |**Matches** |**Game Diff** |"
        GROUP_TEMPLATE_ROW = (
            "|{PLACEMENT}|[**{NAME}**]({LINK})|{MATCH_RECORD}|{PLUS_MINUS}|"
        )

        class Team:
            def __init__(self, teamName, teamLink, matchRecord, plusMinus):
                self.teamName = teamName
                self.teamLink = teamLink
                self.matchRecord = matchRecord
                self.plusMinus = plusMinus

        class Group:
            def __init__(self, groupName, teams):
                self.groupName = groupName
                self.teams = teams

        # Holds all groups in the liquipedia page.
        groups = []

        # Iterate each table.
        tables = html.select("table.grouptable")
        for t in tables:
            groupName = t.select("tr:nth-child(1) th span")[0].text

            # Hold all of the teams for the group object.
            teams = []

            # Iterate each row.
            rows = t.select("tr:nth-child(n+2)")
            for r in rows:
                name = r.select("td")[0].text.strip()
                link = (
                    "https://liquipedia.net"
                    + r.select("td")[0].select(".team-template-text a")[0].attrs["href"]
                )
                matchRecord = r.select("td")[1].text
                plusMinus = r.select("td")[3].text

                newTeam = Team(name, link, matchRecord, plusMinus)
                teams.append(newTeam)

            newGroup = Group(groupName, teams)
            groups.append(newGroup)

        finalMarkdown = ""
        for g in groups:
            groupMarkdown = GROUP_TEMPLATE_HEADER
            groupMarkdown = groupMarkdown.replace(
                "{GROUP_NAME}", g.groupName if g.groupName else "Group"
            )
            placement = 1
            for t in g.teams:
                row = GROUP_TEMPLATE_ROW
                row = row.replace("{PLACEMENT}", str(placement))
                row = row.replace("{NAME}", t.teamName)
                row = row.replace("{LINK}", t.teamLink)
                row = row.replace("{MATCH_RECORD}", t.matchRecord)
                row = row.replace("{PLUS_MINUS}", t.plusMinus)
                groupMarkdown += "\n" + row
                placement += 1

            finalMarkdown += groupMarkdown + "\n\n&#x200B;\n\n"

        await stdout.print_to_channel(channel, finalMarkdown, title="Groups")

    except Exception as e:
        await channel.send("Couldn't find groups in {0}.".format(url))
        global_settings.rleb_log_info(
            "LOOKUP: Couldn't find groups in {0}. Error: {1}".format(url, e)
        )
        global_settings.rleb_log_error(traceback.format_exc())

    finally:
        return int(time.time() - start)
