import time
import asyncio
from queue import Queue
from threading import Thread
from tornado.platform.asyncio import AnyThreadEventLoopPolicy
from datetime import datetime, timedelta, timezone
import traceback
import math
import pytz

import rleb_discord
from rleb_reddit import read_new_submissions, monitor_subreddit, monitor_modmail
import rleb_settings
from rleb_settings import rleb_log_error, rleb_log_info
from rleb_trello import read_new_trello_actions
import rleb_tasks


def task_alert_check():
    time.sleep(rleb_settings.task_alerts_startup_latency)

    # Key is (task.event_name, task.event_date), Value is # of times warned.
    task_warns = {}

    # List of a scheduled post ids that aren't in UTC.
    malformed_schedule_posts = []

    # List of schedule tasks in (task.event_name, task.event_date) form.
    scheduled_tasks = []

    while True:
        # Get the last 20 scheduled posts from mod log.
        scheduled_posts = []
        for log in rleb_settings.sub.mod.log(action="create_scheduled_post", limit=20):
            scheduled_posts.append(log)

        # Iterate all tasks from the current week, make sure they are scheduled.
        weekly_tasks = rleb_tasks.get_tasks()
        for task in weekly_tasks:

            # Don't worry about tasks that don't have an assigned creator.
            if task.event_creator == None or len(task.event_creator) == 0:
                continue

            # Created a key for task warnings.
            if (task.event_name, task.event_date) not in task_warns.keys():
                task_warns[(task.event_name, task.event_date)] = 0

            # If we've already warned twice, just ignore.
            if task_warns[(task.event_name, task.event_date)] == 2:
                continue

            # If task is already scheduled, skip.
            if (task.event_name, task.event_date) in scheduled_tasks:
                continue

            timestring = task.event_schedule_time.replace('Schedule ','')
            datestring = task.event_date
            date_time_str = f"{datestring} {timestring} +0000" # 0 hours and 0 minutes from UTC

            task_datetime = datetime.strptime(date_time_str, '%Y-%m-%d %H:%M %z').replace(tzinfo=pytz.UTC)

            now = datetime.utcnow().replace(tzinfo=pytz.UTC)
            seconds_remaining = (task_datetime - now).total_seconds()
            
            # If the post is due in more than 8 hours, don't warn.
            if seconds_remaining > 60*60*8:
                continue

            # If the post was due more than 8 hours ago, don't warn.
            if seconds_remaining < -60*60*8:
                continue

            task_warnings = task_warns[(task.event_name, task.event_date)]
              
            # Don't warn twice.
            if task_warnings > 1:
               continue  
            
            # Check if task is correctly scheduled.
            task_is_scheduled = False
            for scheduled_post in scheduled_posts:
                # if post was schedule >7 days ago, ignore
                if (datetime.now() - datetime.fromtimestamp(scheduled_post.created_utc)).total_seconds() > 60*60*24*7:
                    continue

                try:
                    # If post has the same time as the task, then the task is correctly scheduled.
                    description = scheduled_post.description # description looks like 'scheduled for Tue, 31 Aug 2021 08:30 AM UTC'
                    description.replace('UTC', '+0000')
                    scheduled_datetime = datetime.strptime(description, 'scheduled for %a, %d %b %Y %H:%M %p %z').replace(tzinfo=pytz.UTC)
                    rleb_log_info(f"CORE: Scheduled post: scheduled_post.details} | {scheduled_datetime.timestamp()}")

                    # If the post was previously malformed but worked this time, remove it from the list of malformed posts.
                    if scheduled_post.id in malformed_schedule_posts:
                        malformed_schedule_posts.remove(scheduled_post)

                    if abs((task_datetime - scheduled_datetime).total_seconds()) < 61: #give a minute cushion
                        task_is_scheduled = True
                        break
                except Exception as e:

                    # If the post is already malformed, no reason to warn again.
                    if scheduled_post.id in malformed_schedule_posts:
                        continue

                    message = f"**WARNING:** \"{scheduled_post.details}\" {description} wasn't scheduled correctly! Make sure the event is in UTC!\n\nScheduled posts: https://new.reddit.com/r/RocketLeagueEsports/about/scheduledposts\n\nINTERNAL ERROR: {e} "
                    rleb_settings.queues["schedule_chat"].put(message)
                    rleb_log_info(f"CORE: {message}")
                    malformed_schedule_posts.append(scheduled_post.id)

            # If the post is due in 8 hours, warn the user.
            if not task_is_scheduled:

                rleb_log_info(f"CORE: Task isn't scheduled: {task.event_name} | {task_datetime.timestamp()}")
                
                # If less than an hour remains, ping the schedule chat about the unscheduled post.
                if seconds_remaining < 60*60:
                   task_warns[(task.event_name, task.event_date)] += 1
                   message = f"**WARNING:** \"{task.event_name}\" is due in {math.floor(seconds_remaining / 3600)} hour(s) and {round((seconds_remaining / 60) % 60, 0)} minute(s).\n\nDouble-check that the task is scheduled for **exactly** {timestring} UTC on {datestring}.\n\nScheduled posts: https://new.reddit.com/r/RocketLeagueEsports/about/scheduledposts"
                   rleb_log_info(f"CORE: {message}")
                   rleb_settings.queues["schedule_chat"].put(message)
                   continue

                # If already warned in DMs, don't warn again.
                if task_warns[(task.event_name, task.event_date)] == 1:
                   continue

                # If the task isn't scheduled AND the task is due in > 1hr AND the user hasn't been DMd yet, DM the user.
                task_warns[(task.event_name, task.event_date)] += 1
                message = f"**WARNING:** \"{task.event_name}\" is due in {math.floor(seconds_remaining / 3600)} hour(s) and {round((seconds_remaining / 60) % 60, 0)} minute(s).\n\nDouble-check that the task is scheduled for **exactly** {timestring} UTC on {datestring}.\n\nScheduled posts: https://new.reddit.com/r/RocketLeagueEsports/about/scheduledposts"

                #TODO dont dm until this feature is working fine
                #rleb_settings.queues["direct_messages"].put((task.event_creator, message))
                rleb_settings.queues["schedule_chat"].put(message)
            else:
                task_warns[(task.event_name, task.event_date)] += 0
                scheduled_tasks.append((task.event_name, task.event_date))
                message = f"Post is scheduled: {task.event_name} -> {timestring} UTC on {datestring}"
                rleb_settings.queues["schedule_chat"].put(message)


        # Break before waiting for the interval.
        if not rleb_settings.task_alert_check_enabled:
            break
        time.sleep(60*10) # 60 seconds * 10 minutes


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


def start():
    # Allows discord bot to read from queues while running.
    asyncio.set_event_loop_policy(AnyThreadEventLoopPolicy())

    # Used for passing reddit submissions from reddit to discord.
    submissions_queue = Queue()
    # Used for passing trello actions from reddit to discord.
    trello_queue = Queue()
    # Used for passing modmail from reddit to discord.
    modmail_queue = Queue()
    # Used for passing alerts from reddit to discord.
    alert_queue = Queue()
    # Used for discord DMs from reddit to discord.
    direct_message_queue = Queue()
    # Used to send messages to #schedule_chat on discord.
    schedule_chat_queue = Queue()

    rleb_settings.queues['submissions'] = submissions_queue
    rleb_settings.queues['trello'] = trello_queue
    rleb_settings.queues['modmail'] = modmail_queue
    rleb_settings.queues['alerts'] = alert_queue
    rleb_settings.queues["direct_messages"] = direct_message_queue
    rleb_settings.queues["schedule_chat"] = schedule_chat_queue

    # Stores all threads used to run the bot.
    threads = []

    # Initialize all threads.
    submissions_thread = Thread(target=read_new_submissions,
                                name="Submissions thread")
    submissions_thread.setDaemon(True)
    subreddit_thread = Thread(target=monitor_subreddit,
                              name="Subreddit thread")
    subreddit_thread.setDaemon(True)
    health_thread = Thread(target=health_check,
                           args=(threads, ),
                           name="Health thread")
    health_thread.setDaemon(True)
    trello_thread = Thread(target=read_new_trello_actions,
                           name="Trello thread")
    trello_thread.setDaemon(True)
    modmail_thread = Thread(target=monitor_modmail, name="Modmail thread")
    modmail_thread.setDaemon(True)
    task_alert_thread = Thread(target=task_alert_check, name="`Task alert thread")
    task_alert_thread.setDaemon(True)
    threads = [
        modmail_thread, trello_thread, subreddit_thread, submissions_thread,
        health_thread, task_alert_thread
    ]

    rleb_log_info("Starting RLEB. Running under {0} in {1} mode.".format(
        rleb_settings.RUNNING_ENVIRONMENT, rleb_settings.RUNNING_MODE))

    # Start up first threads for streaming submissions and reading reddit PMs.
    if rleb_settings.reddit_enabled:
        rleb_log_info("Starting submissions thread.")
        submissions_thread.start()

        # Start up the modmail thread.
        rleb_log_info("Starting modmail thread.")
        modmail_thread.start()

        # Start up the subreddit thread.
        rleb_log_info("Starting subreddit thread.")
        subreddit_thread.start()

    # Start up the trello thread.
    if rleb_settings.trello_enabled:
        rleb_log_info("Starting trello thread.")
        trello_thread.start()

    # Start up the health thread.
    if rleb_settings.health_enabled:
        rleb_log_info("Starting health thread.")
        health_thread.start()

    if rleb_settings.task_alerts_enabled:
        rleb_log_info("Starting task alert thread.")
        task_alert_thread.start()

    # Start the discord thread, running on main thread.
    rleb_log_info("Starting discord thread.")
    rleb_discord.start(threads)


if __name__ == "__main__":
    start()
