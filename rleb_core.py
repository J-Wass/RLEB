import time
import asyncio
from queue import Queue
from threading import Thread
from tornado.platform.asyncio import AnyThreadEventLoopPolicy
from datetime import datetime
import subprocess
import traceback

import rleb_discord
from rleb_reddit import read_new_submissions, monitor_subreddit, monitor_modmail
import rleb_settings
from rleb_settings import rleb_log_error, rleb_log_info
from rleb_trello import read_new_trello_actions


# Monitors health of other threads.
def health_check(threads):
    """Every minute, check if all threads are still running and restart if needed."""
    time.sleep(rleb_settings.health_check_startup_latency)
    chrome_version_mismatch = False
    chrome_settings = rleb_settings.get_chrome_settings(rleb_settings.RUNNING_ENVIRONMENT)
    while True:
        # Monitor Threads
        for t in threads:
            print(t)
            print(t.is_alive())
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
        for asyncio_thread, update_time in rleb_settings.asyncio_threads.items(
        ):
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

        # Monitor Chrome, if a version mismatch was already found, don't alert again.
        if not chrome_version_mismatch and rleb_settings.RUNNING_ENVIRONMENT == "linux":
            try:
                chrome_version = subprocess.check_output(
                    [chrome_settings['path'], '--version']).decode("ASCII")
                chromedriver_version = subprocess.check_output(
                    [chrome_settings['driver'], '--version']).decode("ASCII")
                chrome_major_version = chrome_version.split()[2].split('.')[0]
                chromedriver_major_version = chromedriver_version.split(
                )[1].split('.')[0]
                if chrome_major_version != chromedriver_major_version:
                    rleb_log_error(
                        "HEALTH: The chromedriver version ({0}) does not match chrome version ({1})!"
                        .format(chromedriver_major_version,
                                chrome_major_version))
                    rleb_settings.queues['alerts'].put(
                        "The chromedriver version ({0}) does not match chrome version ({1})!"
                        .format(chromedriver_major_version,
                                chrome_major_version))
                    chrome_version_mismatch = True
            except Exception as e:
                rleb_log_error(
                    "HEALTH: Couldn't get chrome version - {0}".format(e))
                rleb_log_error(traceback.format_exc())

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

    rleb_settings.queues['submissions'] = submissions_queue
    rleb_settings.queues['trello'] = trello_queue
    rleb_settings.queues['modmail'] = modmail_queue
    rleb_settings.queues['alerts'] = alert_queue

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
    threads = [
        modmail_thread, trello_thread, subreddit_thread, submissions_thread,
        health_thread
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

    # Start the discord thread, running on main thread.
    rleb_log_info("Starting discord thread.")
    rleb_discord.start(threads)


if __name__ == "__main__":
    start()
