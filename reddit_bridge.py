import asyncio
import prawcore
import praw
import traceback
from datetime import datetime, timezone

from triflairs import handle_flair_request
import global_settings
from global_settings import sub, r, rleb_log_info
from praw.models import ModmailConversation

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


async def stream_new_submissions():
    """Stream subreddit submissions. Async generator that yields new submissions."""
    try:
        # Use asyncio.to_thread to run blocking PRAW operations
        def get_submissions():
            submissions = []
            try:
                for submission in sub.stream.submissions(pause_after=0):
                    if submission is None:
                        break
                    # Sometimes, submission stream gives us old posts. Only accept posts that are within 2m of now.
                    submission_datetime = datetime.fromtimestamp(submission.created_utc)
                    if abs((datetime.now() - submission_datetime).total_seconds()) > 60 * 2:
                        continue
                    submissions.append(submission)
            except Exception:
                pass
            return submissions

        submissions = await asyncio.to_thread(get_submissions)
        for submission in submissions:
            global_settings.rleb_log_info(
                "[REDDIT]: Submission - {0}".format(submission)
            )
            yield submission

    except AssertionError as e:
        if "429" in str(e):
            await asyncio.sleep(60 * 11)
            global_settings.rleb_log_error(
                f"[REDDIT]: stream_new_submissions() -> {str(e)}"
            )
    except prawcore.exceptions.ServerError as e:
        pass  # Reddit server borked, try again
    except prawcore.exceptions.RequestException as e:
        await asyncio.sleep(60)  # timeout error, just wait awhile and try again
    except Exception as e:
        global_settings.rleb_log_error(
            "[REDDIT]: Streaming new submissions failed - {0}".format(e)
        )
        global_settings.rleb_log_error(traceback.format_exc())
        global_settings.thread_crashes["asyncio"] += 1
        global_settings.last_datetime_crashed["asyncio"] = datetime.now()


async def stream_verified_comments():
    """Stream verified comments. Async generator that yields verified comments."""
    try:
        def get_comments():
            comments = []
            try:
                for comment in sub.stream.comments(skip_existing=True, pause_after=0):
                    if comment is None:
                        break
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
                            comments.append(comment)
                            break
            except Exception:
                pass
            return comments

        comments = await asyncio.to_thread(get_comments)
        for comment in comments:
            global_settings.rleb_log_info(
                "[REDDIT]: Comment - {0}".format(comment)
            )
            yield comment

    except AssertionError as e:
        if "429" in str(e):
            await asyncio.sleep(60 * 11)
            global_settings.rleb_log_error(
                f"[REDDIT]: stream_verified_comments() -> {str(e)}"
            )
    except prawcore.exceptions.ServerError as e:
        pass  # Reddit server yorked, try again
    except prawcore.exceptions.RequestException as e:
        await asyncio.sleep(60)  # timeout error, just wait awhile and try again
    except Exception as e:
        global_settings.rleb_log_error(
            "[REDDIT]: Streaming verified comments failed - {0}".format(e)
        )
        global_settings.rleb_log_error(traceback.format_exc())
        global_settings.thread_crashes["asyncio"] += 1
        global_settings.last_datetime_crashed["asyncio"] = datetime.now()


async def process_inbox():
    """Process inbox messages, handling flair requests."""
    try:
        def check_inbox():
            processed = []
            try:
                for item in r.inbox.stream(pause_after=0):
                    if item is None:
                        break
                    # unbox message
                    unread_message = item
                    r.inbox.mark_read([unread_message])

                    body = unread_message.body
                    user = unread_message.author

                    # if message is a flair request
                    subject = unread_message.subject.lower().replace(" ", "")
                    if subject in multiflair_request_keys:
                        handle_flair_request(sub, user, body)
                        processed.append(unread_message)
            except Exception:
                pass
            return processed

        await asyncio.to_thread(check_inbox)

    except AssertionError as e:
        if "429" in str(e):
            await asyncio.sleep(60 * 11)
            global_settings.rleb_log_error(
                f"[REDDIT]: process_inbox() -> {str(e)}"
            )
    except prawcore.exceptions.ServerError as e:
        pass  # Reddit server borked, wait an interval and try again
    except prawcore.exceptions.RequestException as e:
        await asyncio.sleep(60)  # timeout error, just wait awhile and try again
    except Exception as e:
        global_settings.rleb_log_error(
            "[REDDIT]: Processing inbox failed - {0}".format(e)
        )
        global_settings.rleb_log_error(traceback.format_exc())
        global_settings.thread_crashes["asyncio"] += 1
        global_settings.last_datetime_crashed["asyncio"] = datetime.now()


async def stream_modlog():
    """Stream mod log entries. Async generator that yields modlog entries."""
    try:
        def get_modlog():
            logs_to_yield = []
            try:
                logs = praw.models.util.stream_generator(
                    global_settings.sub.mod.log,
                    pause_after=0,
                    skip_existing=True,
                    attribute_name="id",
                )
                for log in logs:
                    if log is None:
                        break

                    # only accept logs that have an appropriate mod & action
                    if log.mod != None and (log.mod in global_settings.filtered_mod_log):
                        continue
                    if log.action != None and (
                        log.action.lower() not in global_settings.allowed_mod_actions
                    ):
                        continue
                    logs_to_yield.append(log)
            except Exception:
                pass
            return logs_to_yield

        logs = await asyncio.to_thread(get_modlog)
        for log in logs:
            yield log

    except AssertionError as e:
        if "429" in str(e):
            await asyncio.sleep(60 * 11)
            global_settings.rleb_log_error(
                f"[REDDIT]: stream_modlog() -> {str(e)}"
            )
    except prawcore.exceptions.ServerError as e:
        pass  # Reddit server borked, wait an interval and try again
    except prawcore.exceptions.RequestException as e:
        await asyncio.sleep(60)  # timeout error, just wait awhile and try again
    except Exception as e:
        global_settings.rleb_log_error(
            "[REDDIT]: Streaming modlog failed - {0}".format(e)
        )
        global_settings.rleb_log_error(traceback.format_exc())
        global_settings.thread_crashes["asyncio"] += 1
        global_settings.last_datetime_crashed["asyncio"] = datetime.now()


async def stream_modmail():
    """Stream modmail conversations. Async generator that yields modmail conversations."""
    already_printed_convos: set[str] = set()
    already_printed_convos_ordered: list[str] = []

    try:
        def get_modmail():
            conversations_to_yield = []
            try:
                for conversation in sub.modmail.conversations(state="new"):
                    if not conversation or not isinstance(
                        conversation, ModmailConversation
                    ):
                        continue

                    # only find modmails from 2m ago
                    last_updated = datetime.fromisoformat(conversation.last_updated)
                    if (
                        abs((datetime.now(timezone.utc) - last_updated).total_seconds())
                        > 60 * 2
                    ):
                        continue

                    dedupe_id = f"{conversation.id}:{len(conversation.messages)}"
                    if dedupe_id in already_printed_convos:
                        continue
                    already_printed_convos.add(dedupe_id)
                    already_printed_convos_ordered.append(dedupe_id)

                    # if above 100, dump the first 50 to not have the set grow unbounded
                    if len(already_printed_convos_ordered) >= 100:
                        for convo_to_delete in already_printed_convos_ordered[:50]:
                            already_printed_convos.remove(convo_to_delete)
                        already_printed_convos_ordered = already_printed_convos_ordered[50:]
                        global_settings.rleb_log_info(
                            "[REDDIT]: Modmail - Clearing modmail convo cache"
                        )

                    # mark as read
                    full_convo = sub.modmail(conversation.id)
                    full_convo.read()
                    conversation.read()

                    global_settings.rleb_log_info(
                        "[REDDIT]: Modmail - {0}".format(dedupe_id)
                    )

                    # Handle multiflairs from subreddit.
                    subject = conversation.subject
                    if subject.lower().replace(" ", "") in multiflair_request_keys:
                        handle_flair_request(
                            sub,
                            conversation.authors[0],
                            conversation.messages[-1].body_markdown,
                        )
                        if getattr(full_convo, "state", None) != "archived":
                            full_convo.archive()
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
                        and len(conversation.messages) == 1
                    ):
                        continue

                    conversations_to_yield.append(conversation)
            except Exception:
                pass
            return conversations_to_yield

        conversations = await asyncio.to_thread(get_modmail)
        for conversation in conversations:
            yield conversation

    except AssertionError as e:  # rate limit
        if "429" in str(e):
            await asyncio.sleep(60 * 11)
            global_settings.rleb_log_error(
                f"[REDDIT]: stream_modmail() -> {str(e)}"
            )
    except prawcore.exceptions.ServerError as e:
        pass  # Reddit server borked, wait an interval and try again
    except prawcore.exceptions.RequestException as e:
        await asyncio.sleep(60)  # timeout error, just wait awhile and try again
    except Exception as e:
        global_settings.rleb_log_error(
            "[REDDIT]: Streaming modmail failed - {0}".format(e)
        )
        global_settings.rleb_log_error(traceback.format_exc())
        global_settings.thread_crashes["asyncio"] += 1
        global_settings.last_datetime_crashed["asyncio"] = datetime.now()
