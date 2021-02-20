﻿from __future__ import print_function
import datetime
import pickle
import os.path
import re as reee
import traceback
import pytz
import json

from google.oauth2 import service_account
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

import rleb_settings
import rleb_stdout

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

ABOUT_SECTION = """
# About

 You can post anything here that might not have been allowed as its own post. Whether that's quick questions, recently/frequently/over discussed content or "light" content that you don't deem worthy of its own thread.

 The table below features upcoming streams of S-Tier, A-Tier and the bigger B-Tier events including their streamed qualifiers[.](https://reddit-stream.com/comments/b6vu2e/) For a full list of all upcoming RLEsports events check [**Liquipedia**](https://liquipedia.net/rocketleague/Main_Page)."""

 # todo: you pytz to get the timezone abbreviations (EST, CET, etc) dynamically
TABLE_HEADER = """
# {day-name}, {month-name} {day-number}
|Scroll to view start times / links >>|**EST**|**CET**|**AEDT**|**Streams**|**Matches**|
|:-|:-|:-|:-|:-|:-|"""
TABLE_ROW = """|[**{title}**]({link}) |[**{EST}**](https://www.google.com/search?q={EST}+EST) |{CET} |{AEDT} |**Stream** |**Bracket**|"""

BOTTOM_SECTION = """
# Sidebar Schedule

If you are on the official **Reddit App**, you will find the schedule under the "**About**" tab. If you are browsing the **Desktop** version,  you can find the schedule on the sidebar of the [**new.reddit**](https://new.reddit.com/r/RocketLeagueEsports/) version of this subreddit. Alternatively you can use our [**Google Calendar**](https://www.reddit.com/r/RocketLeagueEsports/wiki/calendar) which is used to feed the schedule.

# Guides / FAQs

* [**Intro to RL Esports**](https://www.reddit.com/r/RocketLeagueEsports/wiki/guide)
* [**What is RLCS X? A Guide**](https://www.reddit.com/r/RocketLeagueEsports/comments/ic6mq3/what_is_rlcs_x_a_guide/)
* [**RLCS X Winter - Beginner's Guide**](https://esports.rocketleague.com/news/rlcs-x-winter-split-beginners-guide/)
* [**Fan Rewards FAQ**](https://www.reddit.com/r/RocketLeagueEsports/wiki/rewards)

&nbsp;
&nbsp;

# Community Spotlight

Every Monday we will pin 1 quality piece of Original Content from the previous week or earlier.

# Subreddit Content

* [**Community Spotlights**](https://www.reddit.com/r/RocketLeagueEsports/wiki/community_spotlight)"""

class CalendarEvent:
    def __init__(self, rawtext, start_timestamp):
        self.rawtext = rawtext
        self.start_timestamp = start_timestamp

    def __repr__(self):
        return f" {self.title} {self.link} {self.est_datetime} {self.cet_datetime} {self.aedt_datetime} {self.day_name} {self.month_name} {self.day_number}"

def timestring(datetime, relative_datetime, offset_hours = 0):
    """Human readable time string from datetime. Will italicize the string if the datetime is on a different day from relative_datetime."""
    hour = str(datetime.hour - offset_hours)
    minute = datetime.minute
    # Adding leading 0 to single-digit minute
    if minute < 10:
        minute = f"0{minute}"
    if datetime.day != relative_datetime.day:
            return f"*{hour}:{minute}*"
    return f"{hour}:{minute}"

def process_calendar_events(calendar_event):
    """Builds the list of calendar event objects from the google calendar api response."""
    calendar_event.title = calendar_event.rawtext.split("**")[1].replace("|", "-")
    calendar_event.link = calendar_event.rawtext.split("(")[1].split(")")[0]

    calendar_event.start_datetime = datetime.datetime.fromisoformat(calendar_event.start_timestamp)
    calendar_event.utc_datetime = calendar_event.start_datetime.astimezone(pytz.timezone("Etc/UTC"))
    calendar_event.est_datetime = calendar_event.start_datetime.astimezone(pytz.timezone("America/New_York"))
    calendar_event.cet_datetime = calendar_event.start_datetime.astimezone(pytz.timezone("Europe/Paris"))
    calendar_event.aedt_datetime = calendar_event.start_datetime.astimezone(pytz.timezone("Australia/Melbourne"))

   
    calendar_event.day_number = calendar_event.est_datetime.day
    calendar_event.day_name =  rleb_settings.DAYS[calendar_event.est_datetime.weekday()]
    calendar_event.month_number = calendar_event.est_datetime.month
    calendar_event.month_name = rleb_settings.MONTHS[calendar_event.est_datetime.month - 1]

def formatted_calendar_events(calendar_events, formatter):
    if formatter == 'reddit':
        return reddit_formatted_calendar_events(calendar_events)
    elif formatter == 'sheets':
        return sheets_formatted_calendar_events(calendar_events)
    else:
        return "I didn't understand formatter '{0}', I can only recognize 'reddit' and 'sheets' as a formatter. Try '!events reddit 7'.".format(renderer)

def sheets_formatted_calendar_events(calendar_events):
    """Returns tab separated calendar events for google sheets (or other spreadsheet software)."""
    
    lines = ['' for x in range(3)]
    # Start to build each line in the sheet, indexed by item.
    # 0 - Title
    # 1 - Date & Day of the Week
    # 2 - Schedule Time & Update Time
    for event in sorted(calendar_events, key=lambda e: e.start_datetime):
        lines[0] += event.title + ',,'
        lines[1] += event.start_datetime.strftime("%x") + ',' + event.day_name + ','
        lines[2] += 'Schedule ' + timestring(event.utc_datetime, event.utc_datetime, offset_hours=1) + ',Update ' + timestring(event.utc_datetime, event.utc_datetime) + ','
    
    # idk why but if I use tabs above, the formatting get's wrecked, convert from csv to tsv here
    return ('\n'.join(lines)).replace(',', '\t')

def reddit_formatted_calendar_events(calendar_events):
    """Returns a reddit markdown post featuring all events in calendar_events."""

    reddit_submission = ABOUT_SECTION
    day_buckets = {}

    # Group all events that occur on a similar day into the same bucket
    for calendar_event in calendar_events:
        day_value = calendar_event.day_number + calendar_event.month_number * 31
        if day_value not in day_buckets:
            day_buckets[day_value] = []
        day_buckets[day_value].append(calendar_event)

    # Start listing out each day, one by one.
    for day, events in sorted(day_buckets.items(), key=lambda x: x[0]):
        sample_event = events[0] # snag a random event and use it to build the header
        header = TABLE_HEADER.replace("{day-name}", sample_event.day_name).replace("{day-number}", str(sample_event.day_number)).replace("{month-name}", sample_event.month_name)
        rows = []
        # Make a new row for each event within the day
        event_list = events
        event_list.sort(key=lambda x: x.utc_datetime)
        for event in event_list:
            rows.append(TABLE_ROW.replace("{title}", event.title).replace("{link}", event.link).replace("{EST}", timestring(event.est_datetime, event.est_datetime)).replace("{CET}", timestring(event.cet_datetime, event.est_datetime)).replace("{AEDT}", timestring(event.aedt_datetime, event.est_datetime)))
        table = [header]
        table.extend(rows)
        reddit_submission += "\n".join(table)

    reddit_submission += "\n\n" + BOTTOM_SECTION
    return reddit_submission

async def handle_calendar_lookup(channel, formatter='reddit', days_in_advance = 7):
    """Retrieves calendar events, formats them, and then sends them to the discord channel with the supplied formatter."""

    try:
        credential_info = json.loads(rleb_settings.GOOGLE_CREDENTIALS_JSON)
        credentials = service_account.Credentials.from_service_account_info(credential_info, scopes=SCOPES)
       
        service = build('calendar', 'v3', credentials=credentials)

        later = datetime.datetime.now() + datetime.timedelta(days=days_in_advance)
        upcoming_events = service.events().list(calendarId=rleb_settings.GOOGLE_CALENDAR_ID, timeMin=datetime.datetime.now().astimezone().isoformat(), timeMax=later.astimezone().isoformat(), orderBy='updated').execute()

        # Store processed calendar events from the Google calendar API.
        calendar_events = []

        event_items = upcoming_events['items']
        for event_item in event_items:
            rawtext = event_item['summary'] if 'summary' in event_item else ''
            start_timestamp = event_item['start']['dateTime'] if ('start' in event_item and 'dateTime' in event_item['start'])  else ''
            calendar_event = CalendarEvent(rawtext, start_timestamp)
            process_calendar_events(calendar_event)
            calendar_events.append(calendar_event)

        formatted_text = formatted_calendar_events(calendar_events, formatter)
        
        await rleb_stdout.print_to_channel(channel, formatted_text, title='{0} calender for next {1} days'.format(formatter, days_in_advance))
    except Exception as e:
        rleb_settings.rleb_log_error(traceback.format_exc())
        await channel.send("Couldn't build event post :(")
        await channel.send(e)
        await channel.send(traceback.format_exc())


