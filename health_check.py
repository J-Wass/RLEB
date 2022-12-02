import global_settings
from global_settings import rleb_log_error
from data_bridge import Data
import tasks

import time
from datetime import datetime
import math
import pytz
import random


class Event:
    """Encapsulation of an event in time."""

    def __init__(self, event_name, event_creator, event_seconds_since_epoch, id=None):
        """Initialize a new task."""

        # Human-readable name of event.
        self.event_name = event_name

        # User who created the event. (may be discord id or reddit username)
        self.event_creator = event_creator

        # When the event is due.
        self.event_seconds_since_epoch = event_seconds_since_epoch

        # Id of the event, if any exists.
        self.id = id

    def __repr__(self):
        return f"{self.event_name} ({self.event_creator}) @ {self.event_seconds_since_epoch}"


def get_scheduled_posts(
    already_warned_scheduled_posts: list[int] = None,
    days_ago: int = 5
) -> list[Event]:
    """ "Returns a list of scheduled posts from the sub starting `days_ago`, ignoring posts already in already_warned_scheduled_posts."""
    scheduled_posts = []
    for log in global_settings.sub.mod.log(action="create_scheduled_post", limit=20):
        if already_warned_scheduled_posts and log.id in already_warned_scheduled_posts:
            continue

        # only take posts that have been made x days ago
        if (datetime.now().timestamp() - log.created_utc) > 60 * 60 * 24 * days_ago:
            continue

        try:
            # todo https://stackoverflow.com/questions/1703546/parsing-date-time-string-with-timezone-abbreviated-name-in-python
            description = (
                log.description
            )  # description looks like 'scheduled for Tue, 31 Aug 2021 08:30 AM UTC'
            description = description.replace("UTC", "+0000")
            scheduled_datetime = datetime.strptime(
                description, "scheduled for %a, %d %b %Y %I:%M %p %z"
            ).replace(tzinfo=pytz.UTC)
            scheduled_event = Event(
                log.details, log.mod, scheduled_datetime.timestamp(), log.id
            )
            scheduled_posts.append(scheduled_event)
        except Exception as e:
            # only send warnings of the caller provided a list to be filled out (already_warned_scheduled_posts)
            if already_warned_scheduled_posts:
                global_settings.queues["thread_creation"].put(
                    f"**{log.details}** {log.description} wasn't scheduled in UTC! Please recreate this thread and schedule it in UTC.\n\n(internal error = {e})"
                )
                already_warned_scheduled_posts.append(log.id)
                Data.singleton().write_already_warned_scheduled_post(
                    log.id, datetime.now().timestamp()
                )
    return scheduled_posts


def get_weekly_tasks() -> list[Event]:
    """Fetches tasks from google sheets and returns them as a list of events."""
    weekly_tasks = []
    new_tasks = tasks.get_tasks()
    for t in new_tasks:
        try:
            time_string = t.event_schedule_time.replace("Schedule ", "")
            date_string = t.event_date
            date_time_str = (
                f"{date_string} {time_string} +0000"  # 0 hours and 0 minutes from UTC
            )
            task_datetime = datetime.strptime(
                date_time_str, "%Y-%m-%d %H:%M %z"
            ).replace(tzinfo=pytz.UTC)
            timestamp = task_datetime.timestamp()

            task_event = Event(t.event_name, t.event_creator, timestamp)
            weekly_tasks.append(task_event)
        except Exception as e:
            global_settings.rleb_log_info(f"THREAD CHECK: Skipping weekly task: {(e)}")
            continue
    return weekly_tasks


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

    counter = 0

    while True:
        use_enhanced_logging = counter % 100 == 0
        if use_enhanced_logging:
            global_settings.rleb_log_info(f"THREAD CHECK: At {counter} cycles: enabled enhanced logging.")

        # Every 3 hours, empty the already warned posts list and rewarn the world.
        if (datetime.now().timestamp() - last_emptied_already_late_posts) > 60 * 60 * 3:
            global_settings.rleb_log_info(f"THREAD CHECK: Emptying already_late_posts of size {len(already_warned_late_posts)}")
            last_emptied_already_late_posts = datetime.now().timestamp()
            already_warned_late_posts = []

        # List of events from the weekly spreadsheet.
        tasks = get_weekly_tasks()

        # List of scheduled posts recently made.
        new_scheduled_posts = get_scheduled_posts(already_warned_scheduled_posts)

        if use_enhanced_logging:
            global_settings.rleb_log_info(f"THREAD CHECK: Found {len(tasks)} weekly tasks & {(len(new_scheduled_posts))} posts already scheduled.")

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
                global_settings.rleb_log_info(f"THREAD CHECK: Found {len(post_at_same_time)} tasks at the same time as {task.event_name}.")

            if len(post_at_same_time) == 0:
                # todo, also try to compare task.event_name and posts that share a similar name
                unscheduled_tasks.append(task)

            # Task is scheduled.
            else:
                scheduled_post = post_at_same_time[0]
                if scheduled_post.id not in already_confirmed_scheduled_posts:
                    global_settings.rleb_log_info(f"THREAD CHECK: Found new scheduled post: {task.event_name}.")

                    message = random.choice(global_settings.success_emojis)
                    message += f" Task is scheduled: **{task.event_name}** by {task.event_creator}.\nhttps://new.reddit.com/r/RocketLeagueEsports/about/scheduledposts"
                    global_settings.queues["thread_creation"].put(message)
                    already_confirmed_scheduled_posts.append(scheduled_post.id)
                    Data.singleton().write_already_warned_confirmed_post(
                        scheduled_post.id, datetime.now().timestamp()
                    )

        # Warn for each unscheduled task.
        if use_enhanced_logging:
                global_settings.rleb_log_info(f"THREAD CHECK: Found {len(unscheduled_tasks)} unscheduled posts.")

        for unscheduled_task in unscheduled_tasks:
            now = datetime.now().timestamp()
            seconds_remaining = unscheduled_task.event_seconds_since_epoch - now

            # Don't warn about task again.
            if (
                unscheduled_task.event_creator,
                unscheduled_task.event_seconds_since_epoch,
            ) in already_warned_late_posts:
                continue

            global_settings.rleb_log_info(f"THREAD CHECK: Warning for unscheduled post: {unscheduled_task.event_name}.")

            # Only warn about events that are 2 hours late or are due in 8 hours
            if (seconds_remaining < 60 * 60 * 8) and (seconds_remaining > -60 * 60 * 2):
                message = f"WARNING: {unscheduled_task.event_name} was not scheduled correctly!\n\n"
                message += f"Task is due in {math.floor(seconds_remaining / 3600)} hour(s) and {round((seconds_remaining / 60) % 60, 0)} minute(s).\n\nScheduled posts: https://new.reddit.com/r/RocketLeagueEsports/about/scheduledposts"
                global_settings.rleb_log_info(f"THREAD CHECK: Thread is due in {seconds_remaining}s: {message}")

                
                # Warn on the #thread-creation channel if the thread is due in less than 4 hours.
                if seconds_remaining < 60 * 60 * 4:
                    global_settings.rleb_log_info(f"THREAD CHECK: Creating #thread-creation late thread warning: {message}")
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
        counter += 1
        time.sleep(60 * 10)  # 60 seconds, 10 minutes
    global_settings.rleb_log_info(f"THREAD CHECK: Existing task_check loop.")


# Monitors health of other threads.
def health_check(threads):
    """Every minute, check if all threads are still running and restart if needed."""
    time.sleep(global_settings.health_check_startup_latency)

    while True:
        # Monitor Threads
        for t in threads:
            if not global_settings.thread_health_check_enabled:
                break
            if global_settings.thread_crashes["thread"] >= 5:
                global_settings.thread_health_check_enabled = False
                global_settings.health_enabled = False
                rleb_log_error("HEALTH: More than 5 thread crashes.")
                global_settings.queues["alerts"].put("More than 5 thread crashes detected.")
                break
            if global_settings.thread_crashes["asyncio"] >= 5:
                global_settings.thread_health_check_enabled = False
                global_settings.health_enabled = False
                rleb_log_error("HEALTH: More than 5 asyncio crashes.")
                global_settings.queues["alerts"].put("More than 5 asyncio crashes detected.")
                break
            if not t.is_alive():
                rleb_log_error(
                    "HEALTH: Thread has died: {0} ({1} crashes)".format(
                        t.name, global_settings.thread_crashes["thread"]
                    )
                )
                global_settings.queues["alerts"].put(
                    (
                        "Thread has died: {0} ({1} crashes)".format(
                            t.name, global_settings.thread_crashes["thread"]
                        ),
                        global_settings.BOT_COMMANDS_CHANNEL_ID,
                    )
                )
                threads.remove(t)

        # Monitor Asyncio Threads
        dead_asyncio_threads = []
        for asyncio_thread, update_time in global_settings.asyncio_threads.items():
            if not global_settings.asyncio_health_check_enabled:
                break

            # Can't check if an asyncio thread is alive, check heartbeat instead.
            if (datetime.now() - update_time).total_seconds() > 300:
                rleb_log_error(
                    "HEALTH: {0} asyncio thread has stopped responding! ({1} crashes)".format(
                        asyncio_thread, global_settings.thread_crashes["asyncio"]
                    )
                )
                global_settings.queues["alerts"].put(
                    (
                        "{0} asyncio thread has stopped responding! ({1} crashes)".format(
                            asyncio_thread, global_settings.thread_crashes["asyncio"]
                        ),
                        global_settings.BOT_COMMANDS_CHANNEL_ID,
                    )
                )
                dead_asyncio_threads.append(asyncio_thread)

        # Don't warn about this asyncio thread again.
        for dead_asyncio_thread in dead_asyncio_threads:
            del global_settings.asyncio_threads[dead_asyncio_thread]

        # Break before waiting for the interval.
        if not global_settings.health_enabled:
            break
        time.sleep(30)
