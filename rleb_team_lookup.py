from bs4 import BeautifulSoup
import requests
import time
import traceback
import math

import rleb_settings
import rleb_stdout


async def handle_team_lookup(url, channel):
    """Handle team lookup message.

        Args:
            channel (discord.channel.TextChannel): Channel the lookup is being used in.
            url (str): Liquipedia URL string to look for teams.
        """
    # Variable to keep track of how many seconds the lookup took.
    seconds = 0

    start = time.time()
    rleb_settings.rleb_log_info("DISCORD: Creating lookup for {0}".format(url))

    try:
        page = None
        try:
            page = requests.get(url).content
        except Exception as e:
            await channel.send("Couldn't load {0}!\nError: {1}".format(url, e))
            rleb_settings.rleb_log_info(
                "TEAMS: Couldn't load {0}!\nError: {1}".format(url, e))
            rleb_settings.rleb_log_error(traceback.format_exc())
            return

        html = BeautifulSoup(page, "html.parser")

        # The reddit markdown table to return.
        table = '|Team|\n:--:|\n'

        # Iterate each team.
        for team in html.select('div.teamcard'):
            team_element = team.select('b a')[0]
            team_name = team_element.text.replace('(', '').replace(
                ')', '') if team_element else "TBD"
            team_link = 'https://liquipedia.net' + team_element.attrs[
                'href'] if team_element and team_element.attrs['href'] else "#"
            players = []

            # Iterate each player on the team.
            player_list = team.select('.teamcard-inner .list td > a')
            for p in player_list:
                players.append(p.text.replace('_', '-'))
                if (len(players) >= 3):
                    break

            # If 3 players aren't found, leave the team as unknown.
            players = players if len(players) == 3 else ['?', '?', '?']
            table += (
                f'[**{team_name}**]({team_link}) - {players[0]}, {players[1]}, {players[2]}|\n'
            )

        await rleb_stdout.print_to_channel(channel, table, title="Teams")

    except Exception as e:
        await channel.send("Couldn't find teams in {0}. Error: {1}".format(
            url, e))
        rleb_settings.rleb_log_info(
            "LOOKUP: Couldn't find teams in {0}. Error: {1}".format(url, e))
        rleb_settings.rleb_log_error(traceback.format_exc())

    finally:
        seconds = int(time.time() - start)
        return seconds
