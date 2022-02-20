import time
import prawcore
import praw
import traceback
from datetime import datetime

from rleb_dualflairs import handle_dualflair
import rleb_settings
from rleb_settings import sub, r, rleb_log_info


# Create stream to add new posts to submissions queue
def read_new_submissions():
    """Stream subreddit submissions into the submissions queue."""
    while True:
        try:
            # webhook for reddit submissions
            for submission in sub.stream.submissions():
                # Sometimes, submission stream gives us old posts. Only accept posts that are within 2m of now.
                submission_datetime = datetime.fromtimestamp(submission.created_utc)
                if abs((datetime.now() - submission_datetime).total_seconds()) > 60*2:
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
        if (not rleb_settings.read_new_submissions_enabled):
            break
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
                    handle_dualflair(sub, user, body)
        except prawcore.exceptions.ServerError as e:
            pass  # Reddit server borked, wait an interval and try again
        except Exception as e:
            if rleb_settings.thread_crashes['thread'] > 5:
                break
            rleb_settings.rleb_log_error(
                "REDDIT: Monitoring RLMatchThreads inbox failed - {0}".format(
                    e))
            rleb_settings.rleb_log_error(traceback.format_exc())
            rleb_settings.thread_crashes['thread'] += 1
            rleb_settings.last_datetime_crashed['thread'] = datetime.now()
        if (not rleb_settings.monitor_subreddit_enabled):
            break
        time.sleep(rleb_settings.thread_restart_interval_seconds)

# Monitor moderator feeds.
def monitor_modlog():
    """Listen to new ModLogs."""
    while True:
        try:
            logs = praw.models.util.stream_generator(rleb_settings.sub.mod.log, pause_after=0, skip_existing=True, attribute_name='id')
            for log in logs:
                if log is None:
                    continue
                if (log.mod or '') in rleb_settings.filtered_mod_log:
                    continue
                if (log.action.lower() or '') in rleb_settings.filtered_mod_actions:
                    continue
                rleb_settings.queues['modlog'].put(log)
                time.sleep(rleb_settings.modmail_polling_interval_seconds)
        except prawcore.exceptions.ServerError as e:
            pass  # Reddit server borked, wait an interval and try again            
        except Exception as e:
            if rleb_settings.thread_crashes['thread'] > 5:
                break
            rleb_settings.rleb_log_error(
                "REDDIT: Monitoring subreddit modlogs failed - {0}".format(e))
            rleb_settings.rleb_log_error(traceback.format_exc())
            rleb_settings.thread_crashes['thread'] += 1
            rleb_settings.last_datetime_crashed['thread'] = datetime.now()
        if (not rleb_settings.monitor_modlog_enabled):
            break
        time.sleep(rleb_settings.thread_restart_interval_seconds)

# Monitor moderator feeds.
def monitor_modmail():
    """Listen to new ModMail."""
    while True:
        try:
            for item in sub.mod.unread():
                item.mark_read()
                rleb_settings.rleb_log_info("REDDIT: Modmail - {0}".format(
                    item.id))
                rleb_settings.queues['modmail'].put(item)
            time.sleep(rleb_settings.modmail_polling_interval_seconds)
        except prawcore.exceptions.ServerError as e:
            pass  # Reddit server borked, wait an interval and try again            
        except Exception as e:
            if rleb_settings.thread_crashes['thread'] > 5:
                break
            rleb_settings.rleb_log_error(
                "REDDIT: Monitoring subreddit modmail failed - {0}".format(e))
            rleb_settings.rleb_log_error(traceback.format_exc())
            rleb_settings.thread_crashes['thread'] += 1
            rleb_settings.last_datetime_crashed['thread'] = datetime.now()
        if (not rleb_settings.monitor_modmail_enabled):
            break
        time.sleep(rleb_settings.thread_restart_interval_seconds)
