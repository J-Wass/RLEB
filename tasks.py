from datetime import datetime
import json
import random
import threading
import time
from google.oauth2 import service_account
from googleapiclient.discovery import build
import discord
import traceback
import math
import pytz

import const_wasteland
import global_settings
import stdout
from data_bridge import Data, Remindme


class Task:
    """Encapsulation of a task from the google sheet."""

    def __init__(
        self,
        event_name,
        event_creator,
        event_updater1,
        event_updater2,
        event_day,
        event_date,
        event_schedule_time,
        event_sticky=None,
    ):
        """Initialize a new task."""
        self.event_name = event_name
        self.event_creator = event_creator
        self.event_updater1 = event_updater1
        self.event_updater2 = event_updater2
        self.event_day = event_day
        self.event_date = event_date
        self.event_schedule_time = event_schedule_time
        self.event_sticky = event_sticky

    def pretty_print(self):
        """Returns a human-readable string which represents this task."""
        output = f"**{self.event_name}** ({self.event_day} {self.event_date})\n"
        if self.event_sticky:
            output += f"📌 Sticky: **{self.event_sticky}**\n"
        output += f"✏️ Creator/Scheduler ({self.event_schedule_time} UTC): **{self.event_creator}**\n"
        output += f"🚔 Updaters/Monitors: **{self.event_updater1}**, **{self.event_updater2}**\n"
        output += f"\n-----------------------------------------------------------\n\n"
        return output

    def contains_user(self, user):
        """Returns true if user is involved in this task."""
        return (
            user.lower() == self.event_creator.lower()
            or user.lower() == self.event_updater1.lower()
            or user.lower() == self.event_updater2.lower()
        )


async def tasks_for_user(tasks: list[Task], user: str) -> list[Task]:
    """Returns a list of tasks for the given username."""
    return list(filter(lambda x: x.contains_user(user.lower()), tasks))


async def send_tasks(
    user: str,
    tasks: list[Task],
    client: discord.ClientUser,
    channel: discord.TextChannel,
) -> None:
    """DMs a user (discord name) all of their tasks."""
    # Fetch the user id from mappings, and their tasks.
    user_tasks = await tasks_for_user(tasks, user)
    user_mapping = global_settings.user_names_to_ids
    discord_user = (
        None if user not in user_mapping else client.get_user(user_mapping[user])
    )
    if not discord_user:
        await stdout.print_to_channel(
            channel,
            f"Couldn't dm {user}! Is their name spelled correctly in the sheet?",
        )
        return

    message = f"{random.choice(global_settings.greetings)}\n\n"
    for t in user_tasks:
        message += t.pretty_print()
    # Discord messages must be less than 2000 to avoid rejection.
    if len(message) > 1990:
        message = await stdout.create_paste(message, title=f"{u}'s tasks")
    try:

        await discord_user.send(message)
    except Exception as e:
        await stdout.print_to_channel(
            channel,
            f"**Couldn't dm {user}! Do they have DMs unblocked for the bot?**\n\n Underlying error: {e}",
        )


async def broadcast_tasks(
    tasks: list[Task], client: discord.ClientUser, channel: discord.TextChannel
) -> None:
    """Broadcasts the tasks to each user."""

    # Get the list of all unique users in the list.
    users = set()
    for t in tasks:
        users.add(t.event_creator)
        users.add(t.event_updater1)
        users.add(t.event_updater2)

    # Remove nulls from the weekly sheet.
    users.discard("")
    users.discard("No one needed")
    users.discard("****")
    users.discard("**")

    # Iterate each user, and pm them their tasks.
    for u in users:
        await send_tasks(u, tasks, client, channel)


def get_tasks() -> list[Task]:
    """Gets all tasks from the Spreadsheet tab named "Current Week"."""
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    credential_info = json.loads(global_settings.GOOGLE_CREDENTIALS_JSON)
    credentials = service_account.Credentials.from_service_account_info(
        credential_info, scopes=SCOPES
    )
    service = build("sheets", "v4", credentials=credentials)
    sheet = service.spreadsheets()

    # Shnag the range from 5-11, which includes event time and updaters/creators
    sheet_json = (
        sheet.values()
        .get(
            spreadsheetId=global_settings.SHEETS_ID,
            range=global_settings.weekly_schedule_sheets_range,
        )
        .execute()
    )
    values = sheet_json["values"]

    # Break sheet_json into useful lists.
    tasks = []
    event_names = values[0]
    event_dates = values[1]
    event_times = values[2]
    creators = values[3]
    thread_options = values[4]
    updaters = values[6]

    # Iterate each event, build a new task for each.
    for i in range(1, len(event_names), 2):
        try:
            event_name = event_names[i]
            event_creator = creators[i]
            event_updater1 = updaters[i]
            event_updater2 = updaters[
                i + 1
            ]  # updaters and date tab take up 2 spaces on spreadsheet
            event_day = event_dates[i + 1]
            event_date = event_dates[i]
            event_schedule_time = event_times[i]
            event_sticky = thread_options[i + 1]
            new_task = Task(
                event_name,
                event_creator,
                event_updater1,
                event_updater2,
                event_day,
                event_date,
                event_schedule_time,
                event_sticky,
            )
            tasks.append(new_task)
        except:
            bad_task = event_names[i] if i >= len(event_names) else i
            global_settings.queues["thread_creation"].put(
                f"Weekly tasks were fetched, but bot was unable to read task `{event_names[i]}`. Was the creator or updater filled out?"
            )
            pass

    return tasks


async def handle_task_lookup(
    channel: discord.TextChannel,
    client: discord.ClientUser,
    user: str = "all",
    extra: str = None,
) -> None:
    """
    Looks up tasks in the google calendar for the provided user.
    Not providing a user argument returns tasks for the requester.

    Args:
        channel (discord.TextChannel): The channel requesting !tasks.
        client (discord.ClientUser): The discord client of the bot.
        user (str): The optional username, defined in the google sheet, to return weekly tasks for.
        extra (str): Optional extra message argument, used for some !tasks options.
    """
    try:
        tasks = get_tasks()

        # Determine which tasks should be returned.
        relevant_tasks = []
        if user == "broadcast":
            await broadcast_tasks(tasks, client, channel)
            return
        elif user == "all":
            relevant_tasks = tasks
        elif user == "send":
            target_user = extra
            await send_tasks(target_user, tasks, client, channel)
            return
        else:
            relevant_tasks = await tasks_for_user(tasks, user)

        # Send the response to discord.
        if len(relevant_tasks) == 0:
            await channel.send(f"{user} has no tasks this week.")
            return

        for task in relevant_tasks:
            response = task.pretty_print()
            await channel.send(response)

    except Exception as e:
        global_settings.rleb_log_info("Couldn't find tasks :(")
        global_settings.rleb_log_info(e)
        global_settings.rleb_log_error(traceback.format_exc())
        await channel.send("Couldn't find tasks :(")
        await channel.send(e)
        await channel.send(traceback.format_exc())


# todo, replace this with just task? Or combine them?
class Event:
    """Encapsulation of an event in time."""

    def __init__(
        self,
        event_name,
        event_creator,
        event_updater,
        event_seconds_since_epoch,
        id=None,
    ):
        """Initialize a new task."""

        # Human-readable name of event.
        self.event_name = event_name

        # User who created the event. (may be discord id or reddit username)
        self.event_creator = event_creator

        # User who created the event. (may be discord id or reddit username)
        self.event_updater = event_updater

        # When the event is due.
        self.event_seconds_since_epoch = event_seconds_since_epoch

        # Id of the event, if any exists.
        self.id = id

    def __repr__(self):
        return f"{self.event_name} ({self.event_creator}) @ {self.event_seconds_since_epoch}"


def get_scheduled_posts(
    already_warned_scheduled_posts: list[int] = None, days_ago: int = 5
) -> list[Event]:
    """ Returns a list of scheduled posts from the sub starting `days_ago`, ignoring posts already in already_warned_scheduled_posts."""
    scheduled_posts = []
    for log in global_settings.sub.mod.log(action="create_scheduled_post", limit=20):
        if already_warned_scheduled_posts and log.id in already_warned_scheduled_posts:
            continue

        # only take posts that have been made x days ago
        if (datetime.now().timestamp() - log.created_utc) > 60 * 60 * 24 * days_ago:
            continue

        try:
            description = (
                log.description
            )  # description looks like 'scheduled for Tue, 31 Aug 2021 08:30 AM UTC'


            # Replace timezone with offset.
            for timezone_code, utc_offset in const_wasteland.timezone_offsets.items():
                description = description.replace(timezone_code, utc_offset)

            # Turn into utc and add to list of scheduled posts.
            scheduled_datetime = datetime.strptime(
                description, "scheduled for %a, %d %b %Y %I:%M %p %z"
            )
            scheduled_event = Event(
                log.details, log.mod, "", scheduled_datetime.timestamp(), log.id
            )
            scheduled_posts.append(scheduled_event)
        except Exception as e:
            # only send warnings of the caller provided a list to be filled out (already_warned_scheduled_posts)
            if already_warned_scheduled_posts is not None:
                global_settings.queues["thread_creation"].put(
                    f"Failed to parse scheduled post **{log.details}** {log.description}. Use `!logs db 10` to debug further."
                )
                already_warned_scheduled_posts.append(log.id)
                Data.singleton().write_already_warned_scheduled_post(
                    log.id, datetime.now().timestamp()
                )
            global_settings.rleb_log_error(
                f"Failed to handle get_scheduled_posts: {str(e)}"
            )
    return scheduled_posts


def get_weekly_events() -> list[Event]:
    """Fetches events from google sheets."""
    weekly_events = []
    new_tasks = get_tasks()
    for t in new_tasks:
        try:
            # Post instead of Schedule means the post will be done manually. Don't return in weekly tasks.
            if "Post" in t.event_schedule_time:
                continue
            time_string = t.event_schedule_time.replace("Schedule ", "")
            date_string = t.event_date
            date_time_str = (
                f"{date_string} {time_string} +0000"  # 0 hours and 0 minutes from UTC
            )
            task_datetime = datetime.strptime(
                date_time_str, "%Y-%m-%d %H:%M %z"
            ).replace(tzinfo=pytz.UTC)
            timestamp = task_datetime.timestamp()

            task_event = Event(
                t.event_name, t.event_creator, t.event_updater1, timestamp
            )
            weekly_events.append(task_event)
        except Exception as e:
            global_settings.rleb_log_info(f"TASK CHECK: Skipping weekly task: {(e)}")
            continue
    return weekly_events


def task_alert_check():

    # List of scheduled post ids that weren't misformatted and already warned.
    one_week_ago_seconds_since_epoch = datetime.now().timestamp() - 7 * 86400
    already_warned_scheduled_posts = (
        Data.singleton().read_already_warned_scheduled_posts(
            one_week_ago_seconds_since_epoch
        )
    )

    # List of scheduled post ids have already been confirmed to be scheduled.
    already_confirmed_scheduled_posts = (
        Data.singleton().read_already_confirmed_scheduled_posts(
            one_week_ago_seconds_since_epoch
        )
    )

    # List of (task_creator, timestamp) tuple of tasks that were already warned.
    already_warned_late_posts = []
    last_emptied_already_late_posts = datetime.now().timestamp()

    # Every 10 cycles of loop, use the counter to enable enhanced logging.
    counter = 0

    while True:
        global_settings.threads_heartbeats["Task alert thread"] = datetime.now()

        use_enhanced_logging = counter % 10 == 0
        if use_enhanced_logging:
            global_settings.rleb_log_info(
                f"TASK CHECK: At {counter} cycles: enabled enhanced logging."
            )
        counter += 1

        # Every 3 hours, empty the already warned posts list and rewarn the world.
        if (datetime.now().timestamp() - last_emptied_already_late_posts) > 60 * 60 * 3:
            global_settings.rleb_log_info(
                f"TASK CHECK: Emptying already_late_posts of size {len(already_warned_late_posts)}"
            )
            last_emptied_already_late_posts = datetime.now().timestamp()
            already_warned_late_posts = []

        # Use threading events here to make sure we don't hang on fetching posts.
        new_scheduled_posts = None
        tasks = None
        get_weekly_events_ready = threading.Event()
        get_scheduled_posts_ready = threading.Event()

        def get_weekly_events_wrapper():
            global get_weekly_events_result
            get_weekly_events_result = get_weekly_events()
            get_weekly_events_ready.set()

        def get_scheduled_posts_wrapper():
            global get_scheduled_posts_result
            get_scheduled_posts_result = get_scheduled_posts(
                already_warned_scheduled_posts
            )
            get_scheduled_posts_ready.set()

        weekly_events_thread = threading.Thread(target=get_weekly_events_wrapper)
        weekly_events_thread.start()
        scheduled_posts_thread = threading.Thread(target=get_scheduled_posts_wrapper)
        scheduled_posts_thread.start()
        get_weekly_events_ready.wait(20)
        get_scheduled_posts_ready.wait(20)

        # After the threads are done, check if the data is available.
        if get_weekly_events_ready.is_set():
            tasks = get_weekly_events_result
        if get_scheduled_posts_ready.is_set():
            new_scheduled_posts = get_scheduled_posts_result

        if use_enhanced_logging:
            tasks_num = len(tasks) if tasks else "0"
            post_num = len(new_scheduled_posts) if new_scheduled_posts else "0"
            global_settings.rleb_log_info(
                f"TASK CHECK: Found {tasks_num} weekly tasks & {post_num} posts already scheduled."
            )

        # If the data was unobtainable, wait 5m and try again.
        if tasks == None or new_scheduled_posts == None:
            global_settings.rleb_log_info(
                f"TASK CHECK: Skipping null posts. tasks={tasks}, schedule posts={new_scheduled_posts}. tasks is set={get_weekly_events_ready.is_set()}, scheduled posts is set={get_scheduled_posts_ready.is_set()}"
            )
            time.sleep(60 * 5)
            continue

        # Gather tasks which don't have a scheduled post.
        unscheduled_tasks: list[Event] = []
        for task in tasks:

            # Find if any posts are scheduled at the right time. If they are, assume post is scheduled.
            post_at_same_time = list(
                filter(
                    lambda s: s.event_seconds_since_epoch
                    == task.event_seconds_since_epoch,
                    new_scheduled_posts,
                )
            )
            if use_enhanced_logging:
                global_settings.rleb_log_info(
                    f"TASK CHECK: Found {len(post_at_same_time)} tasks at the same time as {task.event_name}."
                )

            if len(post_at_same_time) == 0:
                # todo, also try to compare task.event_name and posts that share a similar name
                unscheduled_tasks.append(task)

            # Task is scheduled.
            else:
                scheduled_post = post_at_same_time[0]
                if scheduled_post.id not in already_confirmed_scheduled_posts:
                    global_settings.rleb_log_info(
                        f"TASK CHECK: Found new scheduled post: {task.event_name}."
                    )

                    # If thread has an updater, remind them 1hr after thread post.
                    updater = task.event_updater
                    time_until_alert = (
                        task.event_seconds_since_epoch - time.time() + 60 * 60
                    )

                    # Uncomment this once confident that the timing is correct.
                    if updater != "" and updater != "No one needed":
                        update_reminder = Data.singleton().write_remindme(
                            user=updater,
                            message=f"**{task.event_name}** is starting now.",
                            elapsed_time=time_until_alert,
                            channel_id=global_settings.SCHEDULE_CHAT_CHANNEL_ID,
                        )
                        global_settings.schedule_remindme(update_reminder)

                    message = random.choice(global_settings.success_emojis)
                    message += f" Task is scheduled: **{task.event_name}** by {task.event_creator}.\nhttps://new.reddit.com/r/RocketLeagueEsports/about/scheduledposts"
                    global_settings.queues["thread_creation"].put(message)
                    already_confirmed_scheduled_posts.append(scheduled_post.id)
                    Data.singleton().write_already_warned_confirmed_post(
                        scheduled_post.id, datetime.now().timestamp()
                    )

        # Warn for each unscheduled task.
        if use_enhanced_logging:
            global_settings.rleb_log_info(
                f"TASK CHECK: Found {len(unscheduled_tasks)} unscheduled posts."
            )

        for unscheduled_task in unscheduled_tasks:
            now = datetime.now().timestamp()
            seconds_remaining = unscheduled_task.event_seconds_since_epoch - now

            # Don't warn about task again.
            if (
                unscheduled_task.event_creator,
                unscheduled_task.event_seconds_since_epoch,
            ) in already_warned_late_posts:
                continue

            if use_enhanced_logging:
                global_settings.rleb_log_info(
                    f"TASK CHECK: Check if needs warning for unscheduled post: {unscheduled_task.event_name}."
                )

            # Only warn about events that are 2 hours late or are due in 8 hours
            if (seconds_remaining < 60 * 60 * 8) and (seconds_remaining > -60 * 60 * 2):
                message = f"WARNING: {unscheduled_task.event_name} was not scheduled correctly!\n\n"
                message += f"Task is due in {math.floor(seconds_remaining / 3600)} hour(s) and {round((seconds_remaining / 60) % 60, 0)} minute(s).\n\nScheduled posts: https://new.reddit.com/r/RocketLeagueEsports/about/scheduledposts"
                global_settings.rleb_log_info(
                    f"TASK CHECK: Thread is due in {seconds_remaining}s: {message}"
                )

                # Warn on the #thread-creation channel if the thread is due in less than 4 hours.
                if seconds_remaining < 60 * 60 * 4:
                    global_settings.rleb_log_info(
                        f"TASK CHECK: Creating #thread-creation late thread warning: {message}"
                    )
                    global_settings.queues["thread_creation"].put(message)

                # Warn in DMs everytime.
                message += (
                    f"\nAccording to the weekly sheet, **you** are the thread creator."
                )
                global_settings.queues["direct_messages"].put(
                    (unscheduled_task.event_creator, message)
                )
                already_warned_late_posts.append(
                    (
                        unscheduled_task.event_creator,
                        unscheduled_task.event_seconds_since_epoch,
                    )
                )

        # Break before waiting for the interval.
        if not global_settings.task_alert_check_enabled:
            break
        time.sleep(60 * 10)  # 60 seconds, 10 minutes
    global_settings.rleb_log_info(f"TASK CHECK: Exiting task_check loop.")
