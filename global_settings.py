# Utilities file. Houses methods that are used throughout rleb.
import threading
import time
from typing import Dict
import praw
import datetime
import requests
import json
from datetime import datetime
from threading import Lock, Timer
import os
from sys import platform
import discord

from data_bridge import AutoUpdate, Data, Remindme

# This is bad code, don't tell anyone I wrote this.
try:
    import rleb_secrets
except Exception as e:
    rleb_secrets = {}
    print("rleb_secrets.py not found, using keys in environment settings.")

# OS
ENVIRONMENT_DICT = {
    "aix": "aix",
    "linux": "linux",
    "win32": "windows",
    "cygwin": "cygwin",
    "darwin": "mac",
}

RUNNING_ENVIRONMENT = ENVIRONMENT_DICT[platform]

RUNNING_MODE = os.environ.get("RUNNING_MODE") or rleb_secrets.RUNNING_MODE

# CORE
health_enabled = True
task_alerts_enabled = True
health_check_startup_latency = 10  # seconds to wait before health thread starts
task_alerts_startup_latency = 10  # seconds to wait before task alert thread starts
queues = {}  # Global queue dictionary for various things in RLEB.
asyncio_health_check_enabled = True
thread_health_check_enabled = True
task_alert_check_enabled = True

# Mapping of each asyncio thread to the last time it sent a heartbeat out. Used to determine if an asnycio thread has crashed.
asyncio_threads_heartbeats = {
    "submissions": datetime.now(),
    "alerts": datetime.now(),
    "modmail": datetime.now(),
    "direct_messages": datetime.now(),
    "thread_creation": datetime.now(),
}

# List of threads to check for heartbeat in health check.
threads_to_check = {"Task alert thread"}

# Mapping of each thread to the last time it sent a heartbeat out. Used to determine if a thread has crashed.
threads_heartbeats = {}

# seconds until an asyncio_thread is considered timed-out.
asyncio_timeout = 60 * 5
thread_timeout = 60 * 15

# The number of times a thread or asyncio thread crashed and had to be restarted.
thread_crashes = {"asyncio": 0, "thread": 0}

# The last time a thread or asyncio thread crashed and had to be restarted. Used for logging.
last_datetime_crashed = {"asyncio": None, "thread": None}

# Mapping of reminder_ids to Timers
remindme_timers = {}

# Mapping of auto_update_ids to autoupdates.
auto_updates: Dict[int, AutoUpdate] = {}

# The number of times the auto update thread didn't find anything to autoupdate.
auto_update_empties = 0
auto_update_enabled = threading.Event()


def _trigger_remindme(remindme: Remindme) -> None:
    """Executes a remindme and removes it from the db."""
    user_id = user_names_to_ids[remindme.discord_username]
    msg = f"**Reminder for <@{user_id}>:** {remindme.message}"
    queues["alerts"].put((msg, remindme.channel_id))
    Data.singleton().delete_remindme(remindme.remindme_id)
    del remindme_timers[remindme.remindme_id]

    rleb_log_info(f"REMINDME: Triggered remindme {remindme.remindme_id}")


def schedule_remindme(remindme: Remindme) -> None:
    """Starts a new timer for the readme and adds it to the readme_timers."""

    seconds_remaining = remindme.trigger_timestamp - time.time()
    delay = max(60, seconds_remaining)

    timer = Timer(delay, _trigger_remindme, args=(remindme,))
    remindme_timers[remindme.remindme_id] = timer
    timer.start()

    rleb_log_info(f"REMINDME: Created remindme {remindme.remindme_id} due in {delay}s.")


def refresh_remindmes() -> None:
    """Loads !remindme schedulers from db."""
    # Delete old timers.
    for timer in remindme_timers.values():
        timer.cancel()
    remindme_timers.clear()

    # Create fresh timers from db.
    remindmes = Data.singleton().read_remindmes()
    for remindme in remindmes:
        schedule_remindme(remindme)


def refresh_autoupdates() -> bool:
    """
    Loads !autoupdate tasks from db.

    Returns True if any autoupdates were found.
    """
    # Delete old auto updates.
    auto_updates.clear()

    # Create fresh auto updates from db.
    autoupdates = Data.singleton().read_all_auto_updates()
    for autoupdate in autoupdates:
        auto_updates[autoupdate.auto_update_id] = autoupdate
    if len(autoupdates):
        auto_update_enabled.set()


# REDDIT
reddit_enabled = True
target_sub = "rocketleagueesports" if RUNNING_MODE == "production" else "rlcsnewstest"
r = praw.Reddit(
    client_id=os.environ.get("REDDIT_CLIENT_ID") or rleb_secrets.REDDIT_CLIENT_ID,
    client_secret=os.environ.get("REDDIT_CLIENT_SECRET")
    or rleb_secrets.REDDIT_CLIENT_SECRET,
    user_agent=os.environ.get("REDDIT_USER_AGENT") or rleb_secrets.REDDIT_USER_AGENT,
    username=os.environ.get("REDDIT_USERNAME") or rleb_secrets.REDDIT_USERNAME,
    password=os.environ.get("REDDIT_PASSWORD") or rleb_secrets.REDDIT_PASSWORD,
)
sub = r.subreddit(target_sub)
moderators = sub.moderator()
read_new_submissions_enabled = True
monitor_subreddit_enabled = True
monitor_modmail_enabled = True
monitor_modlog_enabled = True
filtered_mod_log = [
    "tweet_widget"
]  # list of mods who shouldn't show up in discord #mod-log channel
allowed_mod_actions = [
    "approvecomment",
    "removecomment",
    "approvelink",
    "removelink",
    "create_scheduled_post",
    "edit_scheduled_post",
]  # list of mod actions which should show up in discord #mod-log channgel


def is_mod(username):
    """Return true if username belongs to a sub moderator.

    Args:
        user (str): Queried subreddit username.
    """
    return username in list(map(lambda x: x.name, moderators))


flair_pattern = "\:\w+\:"
number_of_allowed_flairs = 3  # the number of allowed user flairs on the sub

modmail_polling_interval_seconds = 10
thread_restart_interval_seconds = 30

# GOOGLE
GOOGLE_CALENDAR_ID = os.environ.get("CALENDAR_ID") or rleb_secrets.CALENDAR_ID
GOOGLE_CREDENTIALS_JSON = (
    os.environ.get("GOOGLE_CREDENTIALS_JSON") or rleb_secrets.GOOGLE_CREDENTIALS_JSON
).replace("\\\\n", "\\n")
SHEETS_ID = os.environ.get("SHEETS_ID") or rleb_secrets.SHEETS_ID

weekly_schedule_sheets_range = (
    "Current Week!5:11" if RUNNING_MODE == "production" else "Bot Development!5:11"
)

# DISCORD
discord_enabled = True
discord_check_new_submission_enabled = True
discord_check_new_modmail_enabled = True
discord_check_new_alerts_enabled = True
discord_check_direct_messages_enabled = True
discord_check_new_thread_creation_enabled = True

TOKEN = os.environ.get("DISCORD_TOKEN") or rleb_secrets.DISCORD_TOKEN
NEW_POSTS_CHANNEL_ID = int(
    os.environ.get("NEW_POSTS_CHANNEL_ID") or rleb_secrets.NEW_POSTS_CHANNEL_ID
)
MODMAIL_CHANNEL_ID = int(
    os.environ.get("MODMAIL_CHANNEL_ID") or rleb_secrets.MODMAIL_CHANNEL_ID
)
BOT_COMMANDS_CHANNEL_ID = int(
    os.environ.get("BOT_COMMANDS_CHANNEL_ID") or rleb_secrets.BOT_COMMANDS_CHANNEL_ID
)
SCHEDULE_CHAT_CHANNEL_ID = int(
    os.environ.get("SCHEDULE_CHAT_CHANNEL_ID") or rleb_secrets.SCHEDULE_CHAT_CHANNEL_ID
)
ROSTER_NEWS_CHANNEL_ID = int(
    os.environ.get("ROSTER_NEWS_CHANNEL_ID") or rleb_secrets.ROSTER_NEWS_CHANNEL_ID
)
MODLOG_CHANNEL_ID = int(
    os.environ.get("MODLOG_CHANNEL_ID") or rleb_secrets.MODLOG_CHANNEL_ID
)
THREAD_CREATION_CHANNEL_ID = int(
    os.environ.get("THREAD_CREATION_CHANNEL_ID")
    or rleb_secrets.THREAD_CREATION_CHANNEL_ID
)

# reroute testing pings to bot_commands
if RUNNING_MODE == "local":
    SCHEDULE_CHAT_CHANNEL_ID = BOT_COMMANDS_CHANNEL_ID
    THREAD_CREATION_CHANNEL_ID = BOT_COMMANDS_CHANNEL_ID
    MODMAIL_CHANNEL_ID = BOT_COMMANDS_CHANNEL_ID
    NEW_POSTS_CHANNEL_ID = BOT_COMMANDS_CHANNEL_ID
    MODLOG_CHANNEL_ID = BOT_COMMANDS_CHANNEL_ID

colors = [
    0x2644CE,
    0x000000,
    0xDC143C,
    0xFFFFFF,
    0x6FFF79,
    0xFF8C69,
    0xFE59C2,
    0x32CD32,
]
developer_name = "Voices"
developer_discriminator = "6380"
hooks = [
    "Hot and ready",
    "Fresh outa the oven",
    "This one was made with love",
    "Enjoy",
    "Congrats, you won a prize",
    "This is my greatest work yet",
    "I promise this isn't a virus",
    "This message will self distruct in 2 minutes",
    "I made this one without even trying",
]
greetings = ["Incoming!", "Why hello there.", "Hola, amigo", "Bonjour, mon ami"]
success_emojis = ["🥳", "💪", "✅", "🔥", "🚀", "💯", "🌟", "🏆", "🆒"]
verified_moderators = json.loads(
    os.environ.get("VERIFIED_MODERATORS") or rleb_secrets.VERIFIED_MODERATORS
)
moderator_emails = json.loads(
    os.environ.get("MODERATOR_EMAILS") or rleb_secrets.MODERATOR_EMAILS
)

# Mapping of discord staff usernames to their ids
user_names_to_ids = {}


def refresh_discord_username_id_mapping(channel: discord.TextChannel) -> None:
    """Refreshes user_names_to_ids mapping.

    Args:
        channel (discord.channel.TextChannel): Discord channel to make mapping from.
    """
    user_mappings = {}
    for m in channel.members:
        user_mappings[m.name.lower() + "#" + m.discriminator] = m.id
    user_names_to_ids = user_mappings


def is_discord_mod(user: discord.Member):
    """Returns true if the discord user is a verified moderator."""
    if user.discriminator == "0":
        username = user.name.lower()
    else:
        username = user.name.lower() + "#" + user.discriminator
    return username in verified_moderators


discord_async_interval_seconds = 20

# MONITORING

enable_direct_channel_messages = (
    True  # whether rleb_stdout should send messages directly to channels
)

logging_enabled = True


def _flush_memory_log():
    """Write all logs from memory to db. MUST HAVE LOG_LOCK."""
    if RUNNING_MODE == "local":
        return
    Data.singleton().write_to_logs(memory_log)
    memory_log.clear()


memory_log = []
log_lock = Lock()  # Used when writing to the memory_log


def _rleb_log(message, should_flush=False) -> None:
    """Log a message to memory (thread safe). If `should_flush` is True or memory is too full, the logs will be sent to db."""
    print("{0} UTC {1}".format(datetime.utcnow(), message))
    if not logging_enabled:
        return
    with log_lock:
        memory_log.append("{0} UTC {1}".format(datetime.utcnow(), message))
        if len(memory_log) > 100 or should_flush:
            _flush_memory_log()


def rleb_log_info(message: str, should_flush: bool = False) -> None:
    """Log an informative message. If `should_flush` is True or memory is too full, the logs will be sent to db."""
    _rleb_log("INFO - {0}".format(message), should_flush=should_flush)


def rleb_log_error(message: str) -> None:
    """Log an error message."""
    _rleb_log("ERROR - {0}".format(message), should_flush=True)


# DATES
MONTHS = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sept",
    "Oct",
    "Nov",
    "Dec",
]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# PASTEBIN
PASTEBIN_API_KEY = os.environ.get("PASTEBIN_API_KEY") or rleb_secrets.PASTEBIN_API_KEY
PASTEBIN_API_USER_KEY = (
    os.environ.get("PASTEBIN_API_USER_KEY") or rleb_secrets.PASTEBIN_API_USER_KEY
)
PASTEBIN_USER_NAME = (
    os.environ.get("PASTEBIN_USER_NAME") or rleb_secrets.PASTEBIN_USER_NAME
)
PASTEBIN_USER_PASS = (
    os.environ.get("PASTEBIN_USER_PASS") or rleb_secrets.PASTEBIN_USER_PASS
)
PASTEEE_APP_KEY = os.environ.get("PASTEEE_APP_KEY") or rleb_secrets.PASTEEE_APP_KEY
