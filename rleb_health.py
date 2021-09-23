import rleb_settings
from rleb_settings import rleb_log_info, rleb_log_error
import rleb_tasks

import time
from datetime import datetime, timedelta, timezone
import traceback
import math
import pytz

# List of scheduled post ids that weren't misformatted and already warned.
already_warned_scheduled_posts = []

# List of (task_name, timestamp) tuple of tasks that were already warned.
already_warned_late_posts = []


class Event:
    """Encapsulation of an event in time."""
    def __init__(self, event_name, event_creator, event_seconds_since_epoch):
        """Initialize a new task. """

        # Human-readable name of event.
        self.event_name = event_name

        # User who created the event. (may be discord id or reddit username)
        self.event_creator = event_creator

        # When the event is due.
        self.event_seconds_since_epoch = event_seconds_since_epoch

    def __repr__(self):
        return f"{self.event_name} by {self.event_creator} @ {self.event_seconds_since_epoch}"


def get_scheduled_posts() -> list[Event]:
    scheduled_posts = []
    for log in rleb_settings.sub.mod.log(action="create_scheduled_post", limit=20):
        if log.id in already_warned_scheduled_posts:
            continue

        # if post was scheduled >2 days ago, ignore
        if (datetime.now().timestamp() - log.created_utc) > 60 * 60 * 24 * 2:
            continue

        try:
            # https://stackoverflow.com/questions/1703546/parsing-date-time-string-with-timezone-abbreviated-name-in-python
            description = log.description  # description looks like 'scheduled for Tue, 31 Aug 2021 08:30 AM UTC'
            description = description.replace('UTC', '+0000')
            scheduled_datetime = datetime.strptime(description, 'scheduled for %a, %d %b %Y %I:%M %p %z').replace(tzinfo=pytz.UTC)
            scheduled_event = Event(log.details, log.mod, scheduled_datetime.timestamp())
            scheduled_posts.append(scheduled_event)
        except Exception as e:
            rleb_settings.queues["schedule_chat"].put(f"**{log.details}** {log.description} wasn't scheduled in UTC! (internal error = {e})")
            already_warned_scheduled_posts.append(log.id)
    return scheduled_posts


def get_weekly_tasks() -> list[Event]:
    weekly_tasks = []
    tasks = rleb_tasks.get_tasks()
    for t in tasks:
        time_string = t.event_schedule_time.replace('Schedule ', '')
        date_string = t.event_date
        date_time_str = f"{date_string} {time_string} +0000"  # 0 hours and 0 minutes from UTC
        task_datetime = datetime.strptime(date_time_str, '%Y-%m-%d %H:%M %z').replace(tzinfo=pytz.UTC)
        timestamp = task_datetime.timestamp()

        task_event = Event(t.event_name, t.event_creator, timestamp)
        weekly_tasks.append(task_event)
    return weekly_tasks


def task_alert_check():
    while True:
        # List of events from the weekly spreadsheet.
        tasks = get_weekly_tasks()

        # ModAction of schedule post creations on reddit.
        scheduled_posts = get_scheduled_posts()

        # Gather tasks which don't have a scheduled post.
        unscheduled_tasks = []
        for task in tasks:
            # If post is already warned, don't add to list.
            if (task.event_creator, task.event_seconds_since_epoch) in already_warned_late_posts:
                continue

            post_at_same_time = list(filter(lambda s: s.event_seconds_since_epoch == task.event_seconds_since_epoch, scheduled_posts))
            if len(post_at_same_time) == 0:
                unscheduled_tasks.append(task)

        # Warn for each unscheduled task.
        for unscheduled_task in unscheduled_tasks:
            now = datetime.now().timestamp()
            seconds_remaining = unscheduled_task.event_seconds_since_epoch - now

            # Only warn about events that are 2 hours late and due in 8 hours
            if (seconds_remaining < 60 * 60 * 8) and (seconds_remaining > -60 * 60 * 2):
                message = f"WARNING: {unscheduled_task.event_name} was not scheduled correctly!\n\n"
                message += f"Task is due in {math.floor(seconds_remaining / 3600)} hour(s) and {round((seconds_remaining / 60) % 60, 0)} minute(s).\n\nScheduled posts: https://new.reddit.com/r/RocketLeagueEsports/about/scheduledposts"
                rleb_settings.queues["schedule_chat"].put(message)
                already_warned_late_posts.append((unscheduled_task.event_creator, unscheduled_task.event_seconds_since_epoch))

        # Break before waiting for the interval.
        if not rleb_settings.task_alert_check_enabled:
            break
        time.sleep(60 * 10)  # 60 seconds, 10 minutes


# Monitors health of other threads.
def health_check(threads):
    """Every minute, check if all threads are still running and restart if needed."""
    time.sleep(rleb_settings.health_check_startup_latency)

    while True:
        # Monitor Threads
        for t in threads:
            if (not rleb_settings.thread_health_check_enabled):
                break
            if not t.is_alive():
                rleb_log_error(
                    "HEALTH: Thread has died: {0} ({1} crashes)".format(
                        t.name, rleb_settings.thread_crashes['thread']))
                rleb_settings.queues['alerts'].put(
                    "Thread has died: {0} ({1} crashes)".format(
                        t.name, rleb_settings.thread_crashes['thread']))
                threads.remove(t)

        # Monitor Asyncio Threads
        dead_asyncio_threads = []
        for asyncio_thread, update_time in rleb_settings.asyncio_threads.items():
            if (not rleb_settings.asyncio_health_check_enabled):
                break

            # Can't check if an asyncio thread is alive, check heartbeat instead.
            if (datetime.now() - update_time).total_seconds() > 300:
                rleb_log_error(
                    "HEALTH: {0} asyncio thread has stopped responding! ({1} crashes)"
                    .format(asyncio_thread,
                            rleb_settings.thread_crashes['asyncio']))
                rleb_settings.queues['alerts'].put(
                    "{0} asyncio thread has stopped responding! ({1} crashes)".
                    format(asyncio_thread,
                           rleb_settings.thread_crashes['asyncio']))
                dead_asyncio_threads.append(asyncio_thread)

        # Don't warn about this asyncio thread again.
        for dead_asyncio_thread in dead_asyncio_threads:
            del rleb_settings.asyncio_threads[dead_asyncio_thread]

        # Break before waiting for the interval.
        if not rleb_settings.health_enabled:
            break
        time.sleep(30)