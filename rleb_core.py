import asyncio
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
from trello_bridge import read_new_trello_actions
import health_check


def start():
    # Allows discord bot to read from queues while running.
    asyncio.set_event_loop_policy(AnyThreadEventLoopPolicy())

    # Used for passing reddit submissions from reddit to discord.
    submissions_queue = Queue()
    # Used for passing trello actions from reddit to discord.
    trello_queue = Queue()
    # Used for passing modmail from reddit to discord.
    modmail_queue = Queue()
    # Used for passing modlogs from reddit to discord.
    modlog_queue = Queue()
    # Used for passing alerts from reddit to discord.
    alert_queue = Queue()
    # Used for discord DMs from reddit to discord.
    direct_message_queue = Queue()
    # Used to send messages to #schedule_chat on discord.
    schedule_chat_queue = Queue()

    # Place all queues in rleb_settings. These queues are used to communicate throughout the bot.
    global_settings.queues["submissions"] = submissions_queue
    global_settings.queues["trello"] = trello_queue
    global_settings.queues["modmail"] = modmail_queue
    global_settings.queues["modlog"] = modlog_queue
    global_settings.queues["alerts"] = alert_queue
    global_settings.queues["direct_messages"] = direct_message_queue
    global_settings.queues["schedule_chat"] = schedule_chat_queue

    # Stores all threads used to run the bot.
    threads = []

    # Initialize all threads.
    submissions_thread = Thread(target=read_new_submissions, name="Submissions thread")
    submissions_thread.setDaemon(True)
    subreddit_thread = Thread(target=monitor_subreddit, name="Subreddit thread")
    subreddit_thread.setDaemon(True)
    health_thread = Thread(
        target=health_check.health_check, args=(threads,), name="Health thread"
    )
    health_thread.setDaemon(True)
    trello_thread = Thread(target=read_new_trello_actions, name="Trello thread")
    trello_thread.setDaemon(True)
    modmail_thread = Thread(target=monitor_modmail, name="ModMail thread")
    modmail_thread.setDaemon(True)
    modlog_thread = Thread(target=monitor_modlog, name="ModLog thread")
    modlog_thread.setDaemon(True)
    task_alert_thread = Thread(
        target=health_check.task_alert_check, name="Task alert thread"
    )
    task_alert_thread.setDaemon(True)
    threads = [
        modmail_thread,
        trello_thread,
        subreddit_thread,
        submissions_thread,
        health_thread,
        task_alert_thread,
        modlog_thread,
    ]

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

    if global_settings.trello_enabled:
        rleb_log_info("Starting trello thread.")
        trello_thread.start()

    if global_settings.health_enabled:
        rleb_log_info("Starting health thread.")
        health_thread.start()

    if global_settings.task_alerts_enabled:
        rleb_log_info("Starting task alert thread.")
        task_alert_thread.start()

    global_settings.refresh_remindmes()

    # Start the discord thread, running on main thread.
    rleb_log_info("Starting discord thread.")
    discord_bridge.start(threads)


# Here's where it all begins.
if __name__ == "__main__":
    start()
