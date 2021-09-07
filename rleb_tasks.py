import json

from google.oauth2 import service_account
from googleapiclient.discovery import build
import discord
import traceback

import rleb_settings


class Task:
    """Encapsulation of a task from the google sheet."""
    def __init__(self, event_name, event_creator, event_updater1,
                 event_updater2, event_day, event_date, event_schedule_time):
        """Initialize a new task. """
        self.event_name = event_name
        self.event_creator = event_creator
        self.event_updater1 = event_updater1
        self.event_updater2 = event_updater2
        self.event_day = event_day
        self.event_date = event_date
        self.event_schedule_time = event_schedule_time

    def pretty_print(self):
        """Returns a human-readable string which represents this task."""
        output = f'**{self.event_name}** ({self.event_day} {self.event_date})\n'
        output += f'Creator/Scheduler ({self.event_schedule_time} UTC): **{self.event_creator}**\n'
        output += f'Updaters/Monitors: **{self.event_updater1}**, **{self.event_updater2}**\n'
        output += f'\n-----------------------------------------------------------\n\n'
        return output

    def contains_user(self, user):
        """Returns true if user is involved in this task."""
        return user.lower() == self.event_creator.lower() or user.lower(
        ) == self.event_updater1.lower() or user.lower(
        ) == self.event_updater2.lower()


def user_names_to_ids(channel: discord.TextChannel) -> dict[str, int]:
    """Returns a mapping of discord staff usernames to their ids.
    
       Args:
           channel (discord.channel.TextChannel): Discord channel to make mapping from.

       Returns:
           dict[str,int]: Mapping from discord username (user#tag) to their discord ids.
    """
    user_mappings = {}
    for m in channel.members:
        user_mappings[m.name.lower() + '#' + m.discriminator] = m.id
    return user_mappings

async def tasks_for_user(tasks: list[Task], user: str) -> list[Task]:
    """Returns a list of tasks for the given username."""
    return list(filter(lambda x: x.contains_user(user.lower()), tasks))


async def broadcast_tasks(tasks: list[Task], client: discord.ClientUser,
                          channel: discord.TextChannel) -> None:
    """Broadcasts the tasks to each user."""

    # Get the list of all unique users in the list.
    users = set()
    for t in tasks:
        users.add(t.event_creator)
        users.add(t.event_updater1)
        users.add(t.event_updater2)

    users.discard('')
    users.discard('No one needed')

    # Iterate each user, and pm them their tasks.
    user_mapping = user_names_to_ids(channel)
    for u in users:
        # Fetch the user id from mappings, and their tasks.
        user_tasks = await tasks_for_user(tasks, u)
        discord_user = None if u not in user_mapping else client.get_user(
            user_mapping[u])
        if not discord_user:
            await channel.send(
                f'Couldn\'t dm {u}! Is their name spelled correctly in the sheet?'
            )
            continue
        await discord_user.send("Incoming!\n\n")
        for t in user_tasks:
            await discord_user.send(t.pretty_print())

def get_tasks() -> list[Task]:
    """Gets all tasks from the Spreadsheet tab named "Current Week". """
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
    credential_info = json.loads(rleb_settings.GOOGLE_CREDENTIALS_JSON)
    credentials = service_account.Credentials.from_service_account_info(
        credential_info, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=credentials)
    sheet = service.spreadsheets()

    # Shnag the range from 5-11, which includes event time and updaters/creators
    sheet_json = sheet.values().get(spreadsheetId=rleb_settings.SHEETS_ID,
                                    range=rleb_settings.weekly_schedule_sheets_range).execute()
    values = sheet_json['values']

    # Break sheet_json into useful lists.
    tasks = []
    event_names = values[0]
    event_dates = values[1]
    event_times = values[2]
    creators = values[3]
    updaters = values[6]

    # Iterate each event, build a new task for each.
    for i in range(1, len(event_names), 2):
        event_name = event_names[i]
        event_creator = creators[i]
        event_updater1 = updaters[i]
        event_updater2 = updaters[i + 1] #updaters and date tab take up 2 spaces on spreadsheet
        event_day = event_dates[i + 1]
        event_date = event_dates[i]
        event_schedule_time = event_times[i]
        new_task = Task(event_name, event_creator, event_updater1,
                        event_updater2, event_day, event_date,
                        event_schedule_time)
        tasks.append(new_task)

    return tasks


async def handle_task_lookup(channel: discord.TextChannel,
                             client: discord.ClientUser,
                             user: str = 'all'):
    """
    Looks up tasks in the google calendar for the provided user. 
    Not providing a user argument returns tasks for the requester.
    
    Args:
        channel (discord.TextChannel): The channel requesting !tasks.
        client ( discord.ClientUser): The discord client of the bot.
        user (str): The optional username, defined in the google sheet, to return weekly tasks for.
    """
    try:
        tasks = get_tasks()

        # Determine which tasks should be returned.
        relevant_tasks = []
        if user == 'broadcast':
            await broadcast_tasks(tasks, client, channel)
            return
        elif user == 'all':
            relevant_tasks = tasks
        else:
            relevant_tasks = await tasks_for_user(tasks, user)

        # Send the response to discord.
        if len(relevant_tasks) == 0:
            await channel.send(f'{user} has no tasks this week.')
            return

        for task in relevant_tasks:
            response = task.pretty_print()
            await channel.send(response)

    except Exception as e:
        rleb_settings.rleb_log_info("Couldn't find tasks :(")
        rleb_settings.rleb_log_info(e)
        rleb_settings.rleb_log_error(traceback.format_exc())
        await channel.send("Couldn't find tasks :(")
        await channel.send(e)
        await channel.send(traceback.format_exc())
