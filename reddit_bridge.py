import time
import prawcore
import praw
import traceback
from datetime import datetime

from triflairs import handle_flair_request
import global_settings
from global_settings import sub, r, rleb_log_info

# keys that trigger multiflair request, from modmail or u/RLMatchThreads's inbox. The keys should be lowercase and stripped of whitespace.
multiflair_request_keys = [
    "flair",
    "flairs",
    "flairrequest",
    "dualflair",
    "dualflairs",
    "dualflairrequest",
    "triflair",
    "triflairs",
    "triflairrequest",
    "multiflair",
    "multiflairs",
    "multiflairrequest",
]


# Create stream to add new posts to submissions queue
def read_new_submissions():
    """Stream subreddit submissions into the submissions queue."""
    while True:
        try:
            # webhook for reddit submissions
            for submission in sub.stream.submissions():
                # Sometimes, submission stream gives us old posts. Only accept posts that are within 2m of now.
                submission_datetime = datetime.fromtimestamp(submission.created_utc)
                if abs((datetime.now() - submission_datetime).total_seconds()) > 60 * 2:
                    continue

                global_settings.rleb_log_info(
                    "[REDDIT]: Submission - {0}".format(submission)
                )
                global_settings.queues["submissions"].put(submission)
                global_settings.threads_heartbeats["Submissions thread"] = (
                    datetime.now()
                )
        except AssertionError as e:
            if "429" in str(e):
                time.sleep(60 * 11)
                global_settings.rleb_log_error(
                    f"[REDDIT]: read_new_submissions() -> {str(e)}"
                )
        except prawcore.exceptions.ServerError as e:
            pass  # Reddit server borked, try again
        except prawcore.exceptions.RequestException as e:
            time.sleep(60)  # timeout error, just wait awhile and try again
        except Exception as e:
            if global_settings.thread_crashes["thread"] > 5:
                break
            global_settings.rleb_log_error(
                "[REDDIT]: Monitoring new submissions failed - {0}".format(e)
            )
            global_settings.rleb_log_error(traceback.format_exc())
            global_settings.thread_crashes["thread"] += 1
            global_settings.last_datetime_crashed["thread"] = datetime.now()
        if not global_settings.read_new_submissions_enabled:
            break
        time.sleep(global_settings.thread_restart_interval_seconds)


# Create stream to add new comments to verified comments queue
def read_new_verfied_comments():
    while True:
        try:
            for comment in sub.stream.comments(skip_existing=True):
                # check if it arrived in the last 2 mins.
                submission_datetime = datetime.fromtimestamp(comment.created_utc)
                if abs((datetime.now() - submission_datetime).total_seconds()) > 60 * 2:
                    continue

                for flair in sub.flair(comment.author):
                    if (
                        (not flair)
                        or ("flair_text" not in flair)
                        or (not flair["flair_text"])
                    ):
                        continue
                    if (
                        global_settings.verified_needle
                        in flair["flair_text"].strip().lower()
                    ):
                        global_settings.rleb_log_info(
                            "[REDDIT]: Comment - {0}".format(comment)
                        )
                        global_settings.queues["verified_comments"].put(comment)
                        global_settings.threads_heartbeats[
                            "Verified Comments thread"
                        ] = datetime.now()

        except AssertionError as e:
            if "429" in str(e):
                time.sleep(60 * 11)
                global_settings.rleb_log_error(
                    f"[REDDIT]: read_new_verified_comments() -> {str(e)}"
                )
        except prawcore.exceptions.ServerError as e:
            pass  # Reddit server yorked, try again
        except prawcore.exceptions.RequestException as e:
            time.sleep(60)  # bimeout berror, just wait awhile and try again
        except Exception as e:
            if global_settings.thread_crashes["thread"] > 5:
                break
            global_settings.rleb_log_error(
                "[REDDIT]: Monitoring new verified comments failed - {0}".format(e)
            )
            global_settings.rleb_log_error(traceback.format_exc())
            global_settings.thread_crashes["thread"] += 1
            global_settings.last_datetime_crashed["thread"] = datetime.now()
        if not global_settings.read_new_verified_comments_enabled:
            break
        time.sleep(global_settings.thread_restart_interval_seconds)


# Monitor inbox for PMs
def monitor_subreddit():
    """Loop over RLMatchThreads inbox, looking for key messages."""
    while True:
        try:
            for item in r.inbox.stream():
                # unbox message
                unread_message = item
                r.inbox.mark_read([unread_message])

                body = unread_message.body
                user = unread_message.author

                # if message is a flair request
                subject = unread_message.subject.lower().replace(" ", "")
                if subject in multiflair_request_keys:
                    handle_flair_request(sub, user, body)
                global_settings.threads_heartbeats["Subreddit thread"] = datetime.now()
        except AssertionError as e:
            if "429" in str(e):
                time.sleep(60 * 11)
                global_settings.rleb_log_error(
                    f"[REDDIT]: monitor_subreddit() -> {str(e)}"
                )
        except prawcore.exceptions.ServerError as e:
            pass  # Reddit server borked, wait an interval and try again
        except prawcore.exceptions.RequestException as e:
            time.sleep(60)  # timeout error, just wait awhile and try again
        except Exception as e:
            if global_settings.thread_crashes["thread"] > 5:
                break
            global_settings.rleb_log_error(
                "[REDDIT]: Monitoring RLMatchThreads inbox failed - {0}".format(e)
            )
            global_settings.rleb_log_error(traceback.format_exc())
            global_settings.thread_crashes["thread"] += 1
            global_settings.last_datetime_crashed["thread"] = datetime.now()
        if not global_settings.monitor_subreddit_enabled:
            break
        time.sleep(global_settings.thread_restart_interval_seconds)


# Monitor moderator feeds.
def monitor_modlog():
    """Listen to new ModLogs."""
    while True:
        try:
            logs = praw.models.util.stream_generator(
                global_settings.sub.mod.log,
                pause_after=0,
                skip_existing=True,
                attribute_name="id",
            )
            for log in logs:
                if log is None:
                    continue

                # only accept logs that have an appropriate mod & action
                if log.mod != None and (log.mod in global_settings.filtered_mod_log):
                    continue
                if log.action != None and (
                    log.action.lower() not in global_settings.allowed_mod_actions
                ):
                    continue
                global_settings.queues["modlog"].put(log)
                global_settings.threads_heartbeats["ModLog thread"] = datetime.now()
                time.sleep(global_settings.modmail_polling_interval_seconds)
        except AssertionError as e:
            if "429" in str(e):
                time.sleep(60 * 11)
                global_settings.rleb_log_error(
                    f"[REDDIT]: monitor_modlog() -> {str(e)}"
                )
        except prawcore.exceptions.ServerError as e:
            pass  # Reddit server borked, wait an interval and try again
        except prawcore.exceptions.RequestException as e:
            time.sleep(60)  # timeout error, just wait awhile and try again
        except Exception as e:
            if global_settings.thread_crashes["thread"] > 5:
                break
            global_settings.rleb_log_error(
                "[REDDIT]: Monitoring subreddit modlogs failed - {0}".format(e)
            )
            global_settings.rleb_log_error(traceback.format_exc())
            global_settings.thread_crashes["thread"] += 1
            global_settings.last_datetime_crashed["thread"] = datetime.now()
        if not global_settings.monitor_modlog_enabled:
            break
        time.sleep(global_settings.thread_restart_interval_seconds)


# Monitor moderator feeds.
def monitor_modmail():
    """Listen to new ModMail."""
    while True:
        try:
            for item in sub.mod.unread():
                item.mark_read()
                global_settings.rleb_log_info("[REDDIT]: Modmail - {0}".format(item.id))

                # Handle multiflairs from subreddit.
                subject = item.subject
                if subject.lower().replace(" ", "") in multiflair_request_keys:
                    handle_flair_request(sub, item.author, item.body)
                    continue

                # Filter modmail from removal reasons.
                # Make sure replies to removal reasons aren't filtered (check if they have a parent).
                if (
                    subject
                    in {
                        "Your comment was removed from /r/RocketLeagueEsports",
                        "Your comment from RocketLeagueEsports was removed",
                        "Your submission was removed from /r/RocketLeagueEsports",
                        "Your post from RocketLeagueEsports was removed",
                    }
                    and not item.parent_id
                ):
                    continue

                # Send modmail to discord.
                global_settings.queues["modmail"].put(item)
                global_settings.threads_heartbeats["ModMail thread"] = datetime.now()
            time.sleep(global_settings.modmail_polling_interval_seconds)
        except AssertionError as e:  # rate limit
            if "429" in str(e):
                time.sleep(60 * 11)
                global_settings.rleb_log_error(
                    f"[REDDIT]: monitor_modmail() -> {str(e)}"
                )
        except prawcore.exceptions.ServerError as e:
            pass  # Reddit server borked, wait an interval and try again
        except prawcore.exceptions.RequestException as e:
            time.sleep(60)  # timeout error, just wait awhile and try again
        except Exception as e:
            if global_settings.thread_crashes["thread"] > 5:
                break
            global_settings.rleb_log_error(
                "[REDDIT]: Monitoring subreddit modmail failed - {0}".format(e)
            )
            global_settings.rleb_log_error(traceback.format_exc())
            global_settings.thread_crashes["thread"] += 1
            global_settings.last_datetime_crashed["thread"] = datetime.now()
        if not global_settings.monitor_modmail_enabled:
            break
        time.sleep(global_settings.thread_restart_interval_seconds)
