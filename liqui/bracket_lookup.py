from typing import NamedTuple
from bs4 import BeautifulSoup
from datetime import datetime
import traceback

import global_settings
import stdout
from liqui import liqui_utils
from . import diesel

import discord

BRACKET_MARKDOWN_TEMPLATE = """
|**Double Elimination**|**UTC**|[**Liquipedia Bracket**]({LIQUI_URL}#Results)|
|:-|:-|:-|"""

BRACKET_ROUND_TEMPLATE = "|`▼ {ROUND_NAME}`||`(Bo?)`|"
BRACKET_NEW_MATCH_TEMPLATE = (
    "|{TEAM1}|[**{TIMESTRING}**](https://www.google.com/search?q={TIMESTRING})|{TEAM2}|"
)
BRACKET_FINISHED_MATCH_TEMPLATE = "|{TEAM1}|**{TEAM1_SCORE} - {TEAM2_SCORE}**|{TEAM2}|"


def bracket_names(round):
    correct_names = {
        "Upper Bracket Quarter-Finals": "Upper Quarters",
        "Upper Bracket Semi-Finals": "Upper Semis",
        "Upper Bracket Final": "Upper Final",
        "Lower Bracket Quarter-Finals": "Lower Quarters",
        "Lower Bracket Semi-Finals": "Lower Semis",
        "Lower Bracket Final": "Lower Final",
    }  # Can add to this list to change round names when needed
    if round in correct_names:
        output = correct_names[round]
    else:
        output = round

    return output


async def handle_bracket_lookup(url: str, channel: discord.channel.TextChannel, day_number: int) -> None:
    """Handle bracket lookup message.

    Args:
        channel (discord.channel.TextChannel): Channel the lookup is being used in.
        url (str): Liquipedia URL string to look for elimination brackets.
        day_number (int): The day (usually 1, 2, or 3) of the event to generate a bracket for.
    """
    global_settings.rleb_log_info(
        "DISCORD: Creating bracket lookup for {0}".format(url)
    )

    # Attempt to load markdown from Diesel.
    await channel.send("Building bracket table from Diesel...")
    markdown = await diesel.get_bracket_markdown(url, day_number)
    if markdown:
        await stdout.print_to_channel(channel, markdown, title="Bracket")
        return

    # If Diesel fails, fallback to RLEB, python parsing.
    await channel.send("Failed to build bracket table from Diesel. Trying RLEB...")
    try:
        content = None
        try:
            content = liqui_utils.get_page_html_from_url(url)
        except Exception as e:
            await channel.send("Couldn't load {0} !\nError: {1}".format(url, e))
            global_settings.rleb_log_info(
                "BRACKET: Couldn't load {0}!\nError: {1}".format(url, e)
            )
            global_settings.rleb_log_error(traceback.format_exc())
            return

        html = BeautifulSoup(content, "html.parser")

        class Match(NamedTuple):
            team1: str
            team2: str
            team1_score: int
            team2_score: int
            game_start_time: datetime
            is_finished: bool

        matches: list[Match] = []
        rounds: list[str] = []

        def datetime_from_liqui_timestring(
            liqui_timestring: str, timezone: str
        ) -> datetime:
            """Returns a datetime off of the time string from liquipedia."""
            # Make sure the hour is 0-padded.
            tz_tokens = timezone.split(":")
            if len(tz_tokens[0]) == 2:
                tz_tokens[0] = tz_tokens[0].replace("-", "-0").replace("+", "+0")
            tz = ":".join(tz_tokens)

            # Liqui format example: March 26, 2022 - 13:15
            return datetime.strptime(liqui_timestring + tz, "%B %d, %Y - %H:%M%z")

        def time_of_day_from_datetime(dt: datetime) -> str:
            """Returns 'hh:mm UTC' from a datetime."""
            return datetime.strftime(dt, "%H:%M UTC")

        match_elements = html.select(".brkts-round-center")
        for match in match_elements:
            timer = match.select(".timer-object")[0]
            try:
                is_finished = timer.attrs["data-finished"] != None
            except:
                is_finished = False

            # Strip out timezone info from timer, use data-tz instead (more standard).
            liqui_timestring = timer.text
            timezone = timer.select("abbr")[0].attrs["data-tz"]
            timezone_str = timer.select("abbr")[0].text
            liqui_timestring = liqui_timestring.replace(timezone_str, "").strip()
            start_datetime = datetime_from_liqui_timestring(liqui_timestring, timezone)

            # Fetch team names and scores.
            teams = match.select(".brkts-opponent-entry")
            team1_name = "TBD"
            team1_score = ""
            team2_name = "TBD"
            team2_score = ""
            try:
                team1_name = teams[0].select(".name")[0].text
                team1_score = teams[0].select(".brkts-opponent-score-inner")[0].text
            except:
                pass
            try:
                team2_name = teams[1].select(".name")[0].text
                team2_score = teams[1].select(".brkts-opponent-score-inner")[0].text
            except:
                pass

            new_match = Match(
                team1_name,
                team2_name,
                team1_score,
                team2_score,
                start_datetime,
                is_finished,
            )
            matches.append(new_match)

        round_elements = html.select(".brkts-header.brkts-header-div")
        rounds = [r.select(".brkts-header-option")[0].text for r in round_elements]

        # changes liquipedia grab to our preferred round names
        correct_rounds = list(map(bracket_names, rounds))

        matches.sort(key=lambda x: x.game_start_time)

        final_markdown = BRACKET_MARKDOWN_TEMPLATE.replace("{LIQUI_URL}", url)
        for r in correct_rounds:
            new_round = BRACKET_ROUND_TEMPLATE.replace("{ROUND_NAME}", r)
            final_markdown += f"\n{new_round}"

        for m in matches:
            team1_name = m.team1
            team2_name = m.team2
            match_template = BRACKET_NEW_MATCH_TEMPLATE
            if m.is_finished:
                match_template = BRACKET_FINISHED_MATCH_TEMPLATE
                # Bold the winning team.
                if m.team1_score > m.team2_score:
                    team1_name = f"**{m.team1}**"
                else:
                    team2_name = f"**{m.team2}**"

            match_row = match_template.replace("{TEAM1}", team1_name)
            match_row = match_row.replace("{TEAM2}", team2_name)
            match_row = match_row.replace(
                "{TIMESTRING}", time_of_day_from_datetime(m.game_start_time)
            )
            match_row = match_row.replace("{TEAM1_SCORE}", m.team1_score)
            match_row = match_row.replace("{TEAM2_SCORE}", m.team2_score)

            final_markdown += f"\n{match_row}"

        await stdout.print_to_channel(
            channel, final_markdown, title="Elimination Bracket", force_pastebin=True
        )
    except Exception as e:
        await channel.send("Couldn't find brackets in {0}. Error: {1}.".format(url, e))
        global_settings.rleb_log_info(
            "BRACKET: Couldn't find brackets in {0}.\nError: {1}\nTraceback: {2}".format(
                url, e, traceback.format_exc()
            )
        )
        global_settings.rleb_log_error(traceback.format_exc())
