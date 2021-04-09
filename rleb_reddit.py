import time
import prawcore
import traceback
from datetime import datetime

from rleb_dualflairs import handle_dualflair
import rleb_settings
from rleb_settings import sub, r, moderators, rleb_log_info


# Create stream to add new posts to submissions queue
def read_new_submissions():
    """Stream subreddit submissions into the submissions queue."""
    while True:
        started = datetime.now()
        try:
            for submission in sub.stream.submissions():
                if (datetime.now() - started).total_seconds() < 60:
                    continue
                rleb_settings.rleb_log_info(
                    "REDDIT: Submission - {0}".format(submission))
                rleb_settings.queues["submissions"].put(submission)
        except prawcore.exceptions.ServerError as e:
            pass  # Reddit server borked, wait an interval and try again
        except Exception as e:
            if rleb_settings.thread_crashes['thread'] > 5:
                break
            rleb_settings.rleb_log_error(
                "REDDIT: Monitoring new submissions failed - {0}".format(e))
            rleb_settings.rleb_log_error(traceback.format_exc())
            rleb_settings.thread_crashes['thread'] += 1
            rleb_settings.last_datetime_crashed['thread'] = datetime.now()
        time.sleep(rleb_settings.thread_restart_interval_seconds)


# Monitor inbox for PMs
def monitor_subreddit():
    """Loop over RLMatchThreads inbox, looking for key messages."""
    while True:
        try:
            for item in r.inbox.stream():
                # unbox message
                unread_message = item
                r.inbox.mark_read([unread_message])
                subject = unread_message.subject.lower().replace(' ', '')
                body = unread_message.body
                user = unread_message.author
                # if message is a flair request
                if subject == "flair" or subject == "flairrequest" or subject == "flairs" or subject == "dualflairs" or subject == "dualflair":
                    handle_dualflair(sub, user, body, moderators)
        except Exception as e:
            if rleb_settings.thread_crashes['thread'] > 5:
                break
            rleb_settings.rleb_log_error(
                "REDDIT: Monitoring RLMatchThreads inbox failed - {0}".format(
                    e))
            rleb_settings.rleb_log_error(traceback.format_exc())
            rleb_settings.thread_crashes['thread'] += 1
            rleb_settings.last_datetime_crashed['thread'] = datetime.now()
        time.sleep(rleb_settings.thread_restart_interval_seconds)


# Monitor modmail
def monitor_modmail():
    """Loop over ModMail, looking for new mail."""
    while True:
        try:
            for item in sub.mod.unread():
                item.mark_read()
                rleb_settings.rleb_log_info("REDDIT: Modmail - {0}".format(
                    item.id))
                rleb_settings.queues['modmail'].put(item)
            time.sleep(rleb_settings.modmail_polling_interval_seconds)
        except Exception as e:
            if rleb_settings.thread_crashes['thread'] > 5:
                break
            rleb_settings.rleb_log_error(
                "REDDIT: Monitoring subreddit modmail failed - {0}".format(e))
            rleb_settings.rleb_log_error(traceback.format_exc())
            rleb_settings.thread_crashes['thread'] += 1
            rleb_settings.last_datetime_crashed['thread'] = datetime.now()
        time.sleep(rleb_settings.thread_restart_interval_seconds)
