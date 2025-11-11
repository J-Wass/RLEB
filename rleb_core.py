import asyncio
import os
import discord_bridge
import global_settings
from global_settings import rleb_log_info
from reddit_bridge import RedditBridge


def start() -> None:
    # Allows discord bot to use asyncio event loop.
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

    rleb_log_info(
        "Starting RLEB. Running under {0} in {1} mode.".format(
            global_settings.RUNNING_ENVIRONMENT, global_settings.RUNNING_MODE
        )
    )

    # Initialize RedditBridge and store it in global_settings
    global_settings.reddit_bridge = RedditBridge(
        client_id=os.environ.get("REDDIT_CLIENT_ID")
        or global_settings.config["Reddit"]["REDDIT_CLIENT_ID"],
        client_secret=os.environ.get("REDDIT_CLIENT_SECRET")
        or global_settings.config["Reddit"]["REDDIT_CLIENT_SECRET"],
        user_agent=os.environ.get("REDDIT_USER_AGENT")
        or global_settings.config["Reddit"]["REDDIT_USER_AGENT"],
        username=os.environ.get("REDDIT_USERNAME")
        or global_settings.config["Reddit"]["REDDIT_USERNAME"],
        password=os.environ.get("REDDIT_PASSWORD")
        or global_settings.config["Reddit"]["REDDIT_PASSWORD"],
        subreddit_name=global_settings.target_sub,
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
