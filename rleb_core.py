import asyncio

import discord_bridge
import global_settings
from global_settings import rleb_log_info


def start() -> None:
    # Allows discord bot to use asyncio event loop.
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

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
