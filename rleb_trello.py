import time
import json
from datetime import datetime
import requests
import traceback

import rleb_settings


# Create stream to add new posts to submissions queue
def read_new_trello_actions():
    """Read trello actions and put them into the trello queue."""
    time.sleep(30)
    last_check = datetime.utcnow()
    while (True):
        while True:
            try:
                actions = get_trello_actions(last_check)
                for action in actions:
                    human_readable_trello_action(action)
                    rleb_settings.rleb_log_info("TRELLO: Action - {0}".format(
                        action["type"]))
                    rleb_settings.queues['trello'].put(action)
                last_check = datetime.utcnow()
                time.sleep(30)
            except Exception as e:
                if rleb_settings.thread_crashes['thread'] > 5:
                    break
                rleb_settings.rleb_log_error(
                    "REDDIT: Monitoring Trello failed - {0}".format(e))
                rleb_settings.rleb_log_error(traceback.format_exc())
                rleb_settings.thread_crashes['thread'] += 1
                rleb_settings.last_datetime_crashed['thread'] = datetime.now()
            time.sleep(rleb_settings.thread_restart_interval_seconds)


def get_trello_actions(date):
    """Pings the trello board for all actions since the requested date."""
    iso_date = date.replace(microsecond=0).isoformat()
    action_request = "https://api.trello.com/1/boards/{0}/actions/?since={1}Z&key={2}&token={3}".format(
        rleb_settings.TRELLO_BOARD_ID, iso_date, rleb_settings.TRELLO_AUTH_KEY,
        rleb_settings.TRELLO_AUTH_TOKEN)
    response = requests.request("GET", action_request)
    return json.loads(response.text)


def human_readable_trello_action(action):
    """Insert a human readable message into action['message']."""
    if action["type"] == "commentCard":
        action["message"] = "Commented on '{0}'".format(
            action["data"]["card"]["name"])
    elif action["type"] == "createCard":
        action["message"] = "Created card '{0}'".format(
            action["data"]["card"]["name"])
    elif action["type"] == "updateCard":
        if "listAfter" in action["data"]:
            action["message"] = "Moved card '{0}' to list '{1}'".format(
                action["data"]["card"]["name"],
                action["data"]["listAfter"]["name"])
        elif "list" in action["data"]:
            action["message"] = "Moved card '{0}' to list '{1}'".format(
                action["data"]["card"]["name"], action["data"]["list"]["name"])
        else:
            action["message"] = "Updated card '{0}'".format(
                action["data"]["card"]["name"])
    elif action["type"] == "createList":
        action["message"] = "Created list '{0}'".format(
            action["data"]["list"]["name"])
    elif action["type"] == "updateList":
        action["message"] = "Updated list '{0}'".format(
            action["data"]["list"]["name"])
    else:
        action["message"] = "{0}".format(action["type"])
