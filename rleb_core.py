import asyncio
from datetime import datetime
from queue import Queue
from threading import Thread
from tornado.platform.asyncio import AnyThreadEventLoopPolicy

import discord_bridge
from reddit_bridge import (
    read_new_submissions,
    monitor_subreddit,
    monitor_modmail,
    monitor_modlog,
)
import global_settings
from global_settings import rleb_log_info
import health_check
import tasks


def start():
    # Allows discord bot to read from queues while running.
    asyncio.set_event_loop_policy(AnyThreadEventLoopPolicy())

    # Used for passing reddit submissions from reddit to discord.
    submissions_queue = Queue()
    # Used for passing modmail from reddit to discord.
    modmail_queue = Queue()
    # Used for passing modlogs from reddit to discord.
    modlog_queue = Queue()
    # Used for passing alerts from reddit to discord.
    alert_queue = Queue()
    # Used for discord DMs from reddit to discord.
    direct_message_queue = Queue()
     # Used to send messages to #thread_creation on discord.
    thread_creation_queue = Queue()

    # Place all queues in rleb_settings. These queues are used to communicate throughout the bot.
    global_settings.queues["submissions"] = submissions_queue
    global_settings.queues["modmail"] = modmail_queue
    global_settings.queues["modlog"] = modlog_queue
    global_settings.queues["alerts"] = alert_queue
    global_settings.queues["direct_messages"] = direct_message_queue
    global_settings.queues["thread_creation"] = thread_creation_queue

    # Initialize all threads.
    submissions_thread = Thread(target=read_new_submissions, name="Submissions thread")
    submissions_thread.setDaemon(True)
    subreddit_thread = Thread(target=monitor_subreddit, name="Subreddit thread")
    subreddit_thread.setDaemon(True)
    health_thread = Thread(
        target=health_check.health_check, name="Health thread"
    )
    health_thread.setDaemon(True)
    modmail_thread = Thread(target=monitor_modmail, name="ModMail thread")
    modmail_thread.setDaemon(True)
    modlog_thread = Thread(target=monitor_modlog, name="ModLog thread")
    modlog_thread.setDaemon(True)
    task_alert_thread = Thread(
        target=tasks.task_alert_check, name="Task alert thread"
    )
    task_alert_thread.setDaemon(True)

    # Stores all threads used to run the bot.
    threads = [
        modmail_thread,
        subreddit_thread,
        submissions_thread,
        health_thread,
        task_alert_thread,
        modlog_thread,
    ]

    # Setup each thread's heartbeat for future health checks.
    for t in threads:
        global_settings.threads_heartbeats[t.name] = datetime.now()

    rleb_log_info(
        "Starting RLEB. Running under {0} in {1} mode.".format(
            global_settings.RUNNING_ENVIRONMENT, global_settings.RUNNING_MODE
        )
    )

    # Start up first threads for streaming submissions and reading reddit PMs.
    if global_settings.reddit_enabled:
        rleb_log_info("Starting submissions thread.")
        submissions_thread.start()

        rleb_log_info("Starting modmail thread.")
        modmail_thread.start()

        rleb_log_info("Starting modlog thread.")
        modlog_thread.start()

        rleb_log_info("Starting subreddit thread.")
        subreddit_thread.start()

    if global_settings.health_enabled:
        rleb_log_info("Starting health thread.")
        health_thread.start()

    if global_settings.task_alerts_enabled:
        rleb_log_info("Starting task alert thread.")
        task_alert_thread.start()

    global_settings.refresh_remindmes()

    # Start the discord thread, running on main thread.
    rleb_log_info("Starting discord thread.")
    discord_bridge.start()


# Here's where it all begins.
if __name__ == "__main__":
    start()
