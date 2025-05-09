﻿from __future__ import print_function
import datetime
import traceback
from typing import List
import pytz
import json

from google.oauth2 import service_account
from googleapiclient.discovery import build
import discord

import global_settings
import stdout

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

ABOUT_SECTION = """
# About

 You can post anything here that might not have been allowed as its own post. Whether that's quick questions, recently/frequently/over discussed content or "light" content that you don't deem worthy of its own thread.

 The table below features upcoming streams of S-Tier, A-Tier and the bigger B-Tier events including their streamed qualifiers[.](https://reddit-stream.com/comments/b6vu2e/) For a full list of all upcoming RLEsports events check [**Liquipedia**](https://liquipedia.net/rocketleague/Main_Page) or [**blast.tv**](https://blast.tv/rl/tournaments)."""

# todo: use pytz to get the timezone abbreviations (EST vs EDT, AEST vs AEDT) dynamically
TABLE_HEADER = """
# {day-name}, {month-name} {day-number}
|Scroll to view times / links >>|**ET**|**CET**|**AET**|**Streams**|**Matches**|
|:-|:-|:-|:-|:-|:-|"""

TABLE_ROW = """|⚪ [**{title}**]({link}) |[**{ET}**](https://www.google.com/search?q={ET}+ET) |{CET} |{AET} | {STREAM} |[**Bracket**]({BRACKET})|"""

BOTTOM_SECTION = """

# Event Threads

Events prefixed with ⚽ will have an **Event Thread** posted by mods.  Anyone can [**create an Event Thread**](https://www.reddit.com/r/RocketLeagueEsports/wiki/event_threads) or **Match Threads** for unmarked events. Follow the link to learn more.

# Sidebar Schedule

If you are on the official **Reddit App**, you will find the schedule under the "**About**" tab. If you are browsing the **Desktop** version,  you can find the schedule on the sidebar of the [**sh.reddit**](https://sh.reddit.com/r/RocketLeagueEsports/) version of this subreddit. Alternatively you can use our [**Google Calendar**](https://www.reddit.com/r/RocketLeagueEsports/wiki/calendar) which is used to feed the schedule.
"""


class CalendarEvent:
    def __init__(
        self, rawtext: str, start_timestamp: str, stream: str, description: str
    ):
        self.rawtext = rawtext
        self.start_timestamp = start_timestamp
        self.stream = stream
        self.description = description

        # Handle both markup and not-markup in calendar event title
        if "[**" in self.rawtext:
            self.title = self.rawtext.split("**")[1].replace("|", "-")
            self.link = self.rawtext.split("(")[1].split(")")[0]
        else:
            self.title = self.rawtext
            if "<a" in self.description:
                if "<span" in self.description:
                    self.link = self.description.split("<span>")[1].split("</span>")[0]
                else:
                    self.link = self.description.split(">")[1].split("<")[0]
            else:
                self.link = self.description

        self.bracket_link = self.link + "#Results"

        self.start_datetime = datetime.datetime.fromisoformat(self.start_timestamp)
        self.utc_datetime = self.start_datetime.astimezone(pytz.timezone("Etc/UTC"))
        self.et_datetime = self.start_datetime.astimezone(
            pytz.timezone("America/New_York")
        )
        self.cet_datetime = self.start_datetime.astimezone(
            pytz.timezone("Europe/Paris")
        )
        self.aet_datetime = self.start_datetime.astimezone(
            pytz.timezone("Australia/Melbourne")
        )

        self.day_number = self.et_datetime.day
        self.day_name = global_settings.DAYS[self.et_datetime.weekday()]
        self.month_number = self.et_datetime.month
        self.month_name = global_settings.MONTHS[self.et_datetime.month - 1]

    def __repr__(self):
        return f" {self.title} {self.link} {self.bracket_link} {self.et_datetime} {self.cet_datetime} {self.aet_datetime} {self.day_name} {self.month_name} {self.day_number}"


def timestring(datetime, relative_datetime, offset_hours=0):
    """Human readable time string from datetime. Will italicize the string if the datetime is on a different day from relative_datetime."""
    hour = str(datetime.hour - offset_hours)
    minute = datetime.minute
    # Adding leading 0 to single-digit minute
    if minute < 10:
        minute = f"0{minute}"
    if datetime.day != relative_datetime.day:
        return f"*{hour}:{minute}*"
    return f"{hour}:{minute}"


def formatted_calendar_events(
    calendar_events: List[CalendarEvent], formatter: str
) -> str:
    if formatter == "reddit":
        return reddit_formatted_calendar_events(calendar_events)
    elif formatter == "sheets":
        return sheets_formatted_calendar_events(calendar_events)
    else:
        return "I didn't understand formatter '{0}', I can only recognize 'reddit' and 'sheets' as a formatter. Try '!events reddit 7'.".format(
            formatter
        )


def sheets_formatted_calendar_events(calendar_events: list[CalendarEvent]) -> str:
    """Returns tab separated calendar events for google sheets (or other spreadsheet software)."""

    lines = ["" for x in range(3)]
    # Start to build each line in the sheet, indexed by item.
    # 0 - Title
    # 1 - Date & Day of the Week
    # 2 - Schedule Time & Update Time
    for event in sorted(calendar_events, key=lambda e: e.utc_datetime):
        lines[0] += event.title.strip() + ",,"
        lines[1] += (
            event.utc_datetime.strftime("%x")
            + ","
            + global_settings.DAYS[event.utc_datetime.weekday()]
            + ","
        )
        lines[2] += (
            "Schedule "
            + timestring(event.utc_datetime, event.utc_datetime, offset_hours=1)
            + ",Update "
            + timestring(event.utc_datetime, event.utc_datetime)
            + ","
        )

    # idk why but if I use tabs above, the formatting get's wrecked, convert from csv to tsv here
    return ("\n".join(lines)).replace(",", "\t")


def reddit_formatted_calendar_events(calendar_events: list[CalendarEvent]) -> str:
    """Returns a reddit markdown post featuring all events in calendar_events."""

    reddit_submission = ABOUT_SECTION
    day_buckets: dict[int, list[CalendarEvent]] = {}

    # Group all events that occur on a similar day into the same bucket
    for calendar_event in calendar_events:
        day_value = calendar_event.day_number + calendar_event.month_number * 31
        if day_value not in day_buckets:
            day_buckets[day_value] = []
        day_buckets[day_value].append(calendar_event)

    # Start listing out each day, one by one.
    for day, events in sorted(day_buckets.items(), key=lambda x: x[0]):
        sample_event = events[0]  # snag a random event and use it to build the header
        header = (
            TABLE_HEADER.replace("{day-name}", sample_event.day_name)
            .replace("{day-number}", str(sample_event.day_number))
            .replace("{month-name}", sample_event.month_name)
        )
        rows = []
        # Make a new row for each event within the day
        event_list = events
        event_list.sort(key=lambda x: x.utc_datetime)
        for event in event_list:
            tr = TABLE_ROW.replace("{title}", event.title.strip())
            tr = tr.replace("{link}", event.link)
            tr = tr.replace("{BRACKET}", event.bracket_link)
            tr = tr.replace("{ET}", timestring(event.et_datetime, event.et_datetime))
            tr = tr.replace("{CET}", timestring(event.cet_datetime, event.et_datetime))
            tr = tr.replace("{AET}", timestring(event.aet_datetime, event.et_datetime))

            # Make sure that all http links start with https://www
            if "." in event.stream:
                stream = event.stream
                if "https://www." not in stream:
                    stream = "https://www." + stream
                tr = tr.replace("{STREAM}", "[**Stream**]({0})".format(stream))
            else:
                tr = tr.replace("{STREAM}", event.stream)

            rows.append(tr)
        table = [header]
        table.extend(rows)
        reddit_submission += "\n".join(table)

    reddit_submission += "\n\n" + BOTTOM_SECTION
    return reddit_submission


async def handle_calendar_lookup(
    channel: discord.channel.TextChannel,
    formatter: str = "reddit",
    start: int = 0,
    end: int = 7,
) -> None:
    """Retrieves calendar events, formats them, and then sends them to the discord channel with the supplied formatter."""

    try:
        credential_info = json.loads(global_settings.GOOGLE_CREDENTIALS_JSON)
        credentials = service_account.Credentials.from_service_account_info(
            credential_info, scopes=SCOPES
        )

        service = build("calendar", "v3", credentials=credentials)

        start_date = datetime.datetime.now() + datetime.timedelta(days=start)
        end_date = datetime.datetime.now() + datetime.timedelta(days=end)
        upcoming_events = (
            service.events()
            .list(
                calendarId=global_settings.GOOGLE_CALENDAR_ID,
                timeMin=start_date.astimezone().isoformat(),
                timeMax=end_date.astimezone().isoformat(),
                orderBy="updated",
            )
            .execute()
        )

        # Store processed calendar events from the Google calendar API.
        calendar_events = []

        event_items = upcoming_events["items"]
        for event_item in event_items:
            rawtext = event_item["summary"] if "summary" in event_item else ""
            is_start_time_available = ("start" in event_item) and (
                "dateTime" in event_item["start"]
            )
            start_timestamp = (
                event_item["start"]["dateTime"] if (is_start_time_available) else ""
            )
            stream = "None"
            if "location" in event_item:
                stream = event_item["location"]
            else:
                await channel.send(
                    'Warning: No location for "{0}" was put in the calendar, using "None" instead.'.format(
                        rawtext
                    )
                )
            description = event_item.get(
                "description", "https://www.reddit.com/r/RocketLeagueEsports"
            )
            calendar_event = CalendarEvent(
                rawtext, start_timestamp, stream, description
            )
            calendar_events.append(calendar_event)

        formatted_text = formatted_calendar_events(calendar_events, formatter)

        await stdout.print_to_channel(
            channel,
            formatted_text,
            title="Calendar",
            force_pastebin=True,
        )
    except Exception as e:
        global_settings.rleb_log_error(traceback.format_exc())
        await channel.send("Couldn't build event post :(")
        await channel.send(e)
        await channel.send(traceback.format_exc())
