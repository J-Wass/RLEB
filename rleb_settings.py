# Utilities file. Houses methods that are used throughout rleb.

import praw
from pymongo import MongoClient
import psycopg2
from psycopg2.extras import execute_values
import datetime
import requests
import json
from datetime import datetime
from threading import Lock
from queue import Queue
import os

try:
    import secrets
except Exception as e:
    secrets = {}
    print("secrets.py not found, usings keys in environment settings.")

# Global queue dictionary for various things in RLEB.
queues = {}

# OS (Either windows or linux)
# TODO: Automatically get the running environment
RUNNING_ENVIRONMENT = "windows"

RUNNING_MODE = os.environ.get('RUNNING_MODE') or secrets.RUNNING_MODE

# REDDIT
reddit_enabled = True
target_sub = 'rocketleagueesports'
r = praw.Reddit(client_id=os.environ.get('REDDIT_CLIENT_ID') or secrets.REDDIT_CLIENT_ID,
                client_secret=os.environ.get('REDDIT_CLIENT_SECRET') or secrets.REDDIT_CLIENT_SECRET,
                user_agent=os.environ.get('REDDIT_USER_AGENT') or secrets.REDDIT_USER_AGENT,
                username=os.environ.get('REDDIT_USERNAME') or secrets.REDDIT_USERNAME,
                password=os.environ.get('REDDIT_PASSWORD') or secrets.REDDIT_PASSWORD)
sub = r.subreddit(target_sub)
moderators = sub.moderator();
def is_mod(username):
    """Return true if username belongs to a sub moderator.

    Args:
        user (str): Queried subreddit username.
    """
    return username in list(map(lambda x: x.name, moderators))
flair_pattern = "\:\w+\:"

modmail_polling_interval_seconds = 10
thread_restart_interval_seconds = 30

# CALENDAR
GOOGLE_CALENDAR_ID = os.environ.get('CALENDAR_ID') or secrets.CALENDAR_ID
GOOGLE_CREDENTIALS_JSON = os.environ.get('GOOGLE_CREDENTIALS_JSON') or secrets.GOOGLE_CREDENTIALS_JSON
#= {
#  "type": "service_account",
#  "project_id": os.environ.get('GOOGLE_PROJECT_ID') or secrets.GOOGLE_PROJECT_ID,
#  "private_key_id": os.environ.get('GOOGLE_PRIVATE_KEY_ID') or secrets.GOOGLE_PRIVATE_KEY_ID,
#  "private_key": os.environ.get('GOOGLE_PRIVATE_KEY') or secrets.GOOGLE_PRIVATE_KEY,
#  "client_email": os.environ.get('GOOGLE_CLIENT_EMAIL') or secrets.GOOGLE_CLIENT_EMAIL,
#  "client_id": os.environ.get('GOOGLE_CLIENT_ID') or secrets.GOOGLE_CLIENT_ID,
#  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
#  "token_uri": "https://oauth2.googleapis.com/token",
#  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
#  "client_x509_cert_url": os.environ.get('GOOGLE_CERT_URL') or secrets.GOOGLE_CERT_URL
#}

# DISCORD
discord_enabled = True
TOKEN = os.environ.get('DISCORD_TOKEN') or secrets.DISCORD_TOKEN
NEW_POSTS_CHANNEL_ID = int(os.environ.get('NEW_POSTS_CHANNEL_ID') or secrets.NEW_POSTS_CHANNEL_ID)
TRELLO_CHANNEL_ID = int(os.environ.get('TRELLO_CHANNEL_ID') or secrets.TRELLO_CHANNEL_ID)
MODMAIL_CHANNEL_ID = int(os.environ.get('MODMAIL_CHANNEL_ID') or secrets.MODMAIL_CHANNEL_ID)
BOT_COMMANDS_CHANNEL_ID = int(os.environ.get('BOT_COMMANDS_CHANNEL_ID') or secrets.BOT_COMMANDS_CHANNEL_ID)
colors = [
0x2644ce,
0x000000,
0xDC143C,
0xffffff,
0x6FFF79,
0xFF8C69,
0xFE59C2,
0x32cd32,
]
developer_name = 'Voices'
developer_discriminator = '6380'

# THREADING
# Mapping of each asyncio thread to the last time it sent a heartbeat out. Used to determine if an asnycio thread has crashed.
asyncio_threads = {
    'submissions': datetime.now(),
    'alerts': datetime.now(),
    'modmail': datetime.now(),
    'trello': datetime.now()
}

# The number of times a thread or asyncio thread crashed and had to be restarted.
thread_crashes = {
    'asyncio': 0,
    'thread': 0
}

# The last time a thread or asyncio thread crashed and had to be restarted. Used for logging.
last_datetime_crashed = {
    'asyncio': None,
    'thread': None
}

# DATABASE
def postgresConnection():
    """Returns a new postgresSQL connection."""
    return psycopg2.connect(dbname=os.environ.get('DB_NAME') or secrets.DB_NAME, 
                            host=os.environ.get('DB_HOST') or secrets.DB_HOST, 
                            user=os.environ.get('DB_USER') or secrets.DB_USER,  
                            port=os.environ.get('DB_PORT') or secrets.DB_PORT,  
                            password=os.environ.get('DB_PASSWORD') or secrets.DB_PASSWORD, )

memory_log = []
log_lock = Lock() # Used when writing to the memory_log

def flush_memory_log():
    """Write all logs from memory to db. MUST HAVE LOG_LOCK."""
    db = postgresConnection()
    cursor = db.cursor()
    memory_logs_tuples = list(map(lambda x: (x,), memory_log))
    psycopg2.extras.execute_values(cursor, "INSERT INTO logs VALUES %s", memory_logs_tuples)
    db.commit()
    memory_log.clear()

# TRELLO
trello_enabled = True
TRELLO_AUTH_KEY = os.environ.get('TRELLO_AUTH_KEY') or secrets.TRELLO_AUTH_KEY
TRELLO_AUTH_TOKEN = os.environ.get('TRELLO_AUTH_TOKEN') or secrets.TRELLO_AUTH_TOKEN
TRELLO_BOARD_ID  = os.environ.get('TRELLO_BOARD_ID') or secrets.TRELLO_BOARD_ID
def get_trello_actions(date):
    """Pings the trello board for all actions since the requested date."""
    iso_date = date.replace(microsecond=0).isoformat()
    action_request = "https://api.trello.com/1/boards/{0}/actions/?since={1}Z&key={2}&token={3}".format(TRELLO_BOARD_ID, iso_date, TRELLO_AUTH_KEY, TRELLO_AUTH_TOKEN)
    response = requests.request("GET", action_request)
    return json.loads(response.text)

# MONITORING
def rleb_log(message, should_flush=False):
    """Log a message to memory (thread safe)."""
    with log_lock:
        print("{0}UTC {1}".format(datetime.utcnow(), message))
        memory_log.append("{0}UTC {1}".format(datetime.utcnow(), message))
        if len(memory_log) > 100 or should_flush:
            flush_memory_log()

def rleb_log_info(message):
    """Log an informative message to either memory."""
    rleb_log("INFO - {0}".format(message), should_flush=False)

def rleb_log_error(message):
    """Log an error message to either memory."""
    rleb_log("ERROR - {0}".format(message), should_flush=True)

# DATES
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# PASTEBIN
PASTEBIN_API_KEY = os.environ.get('PASTEBIN_API_KEY') or secrets.PASTEBIN_API_KEY