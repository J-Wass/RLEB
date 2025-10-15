import asyncio
from queue import Queue

import discord_bridge
import global_settings
from global_settings import rleb_log_info


def start():
    # Allows discord bot to use asyncio event loop.
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

    # Create queues that are still needed for alerts, direct messages, and thread creation
    # These are used by various parts of the system to send messages to Discord
    alert_queue = Queue()
    direct_message_queue = Queue()
    thread_creation_queue = Queue()

    # Place queues in global_settings for inter-component communication
    global_settings.queues["alerts"] = alert_queue
    global_settings.queues["direct_messages"] = direct_message_queue
    global_settings.queues["thread_creation"] = thread_creation_queue

    rleb_log_info(
        "Starting RLEB. Running under {0} in {1} mode.".format(
            global_settings.RUNNING_ENVIRONMENT, global_settings.RUNNING_MODE
        )
    )

    # Load remindmes and autoupdates from database
    global_settings.refresh_remindmes()
    global_settings.refresh_autoupdates()

    # Start the discord bot on main thread. All monitoring now happens in asyncio tasks.
    rleb_log_info("Starting discord bot (all monitoring will run in asyncio tasks).")
    discord_bridge.start()


# Here's where it all begins.
if __name__ == "__main__":
    start()
