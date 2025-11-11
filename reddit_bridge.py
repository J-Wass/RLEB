import asyncio
import prawcore
import praw
import traceback
import random
import re
import threading
from data_bridge import Data
from datetime import datetime, timezone

import global_settings
from global_settings import rleb_log_info
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


class RedditBridge:
    """Class to handle Reddit interactions."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str,
        username: str,
        password: str,
        subreddit_name: str,
    ):
        rleb_log_info("[REDDIT]: RedditBridge initialized.")
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
            username=username,
            password=password,
        )
        self.subreddit = self.reddit.subreddit(subreddit_name)
        self.mod_log = self.subreddit.mod.stream.log(
            pause_after=0,
            skip_existing=False,
        )

        self.submission_stream = self.subreddit.stream.submissions(
            pause_after=0, skip_existing=True
        )
        self.comment_stream = self.subreddit.stream.comments(
            pause_after=0, skip_existing=True
        )
        self.inbox_stream = self.reddit.inbox.stream(pause_after=0, skip_existing=True)
        self.modmail_stream = self.subreddit.modmail.conversations(state="new")

        self.comments = []
        self.submissions = []
        self.mod_logs = []
        self.conversations = []
        self.moderators = []

        thread = threading.Thread(target=self._start_event_loops, daemon=True)
        thread.start()

    def _start_event_loops(self):
        rleb_log_info("[REDDIT]: Setting up loops.")

        self.event_loop = asyncio.new_event_loop()

        self.event_loop.create_task(self.stream_new_submissions())
        self.event_loop.create_task(self.stream_verified_comments())
        self.event_loop.create_task(self.process_inbox())
        self.event_loop.create_task(self.stream_modlog())
        self.event_loop.create_task(self.stream_modmail())

        rleb_log_info("[REDDIT]: Loops done.")

        self.event_loop.run_forever()

        rleb_log_info("[REDDIT]: Done.")

    async def get_comments(self):
        """Async generator that yields verified comments."""
        while True:
            if len(self.comments) > 0:
                print("Yielding something")
                yield self.comments.pop(0)
            else:
                break

    async def get_submissions(self):
        """Async generator that yields new submissions."""
        while True:
            if len(self.submissions) > 0:
                yield self.submissions.pop(0)
            else:
                break

    async def get_mod_logs(self):
        """Async generator that yields modlog entries."""
        while True:
            if len(self.mod_logs) > 0:
                yield self.mod_logs.pop(0)
            else:
                break

    async def get_modmail(self):
        """Async generator that yields modmail conversations."""
        while True:
            if len(self.conversations) > 0:
                yield self.conversations.pop(0)
            else:
                break

    async def get_moderators(self):
        """Populates self.moderators with the latest list of subreddit moderators"""
        self.moderators = self.subreddit.moderators()

    def is_mod(self, username: str) -> bool:
        """Return true if username belongs to a sub moderator.

        Args:
            user (str): Queried subreddit username.
        """
        return username in list(map(lambda x: x.name, self.moderators))

    async def get_modqueue_count(self):
        modqueue_count = 0
        for item in self.subreddit.mod.modqueue():
            modqueue_count += 1
        return modqueue_count

    async def stream_new_submissions(self):
        """Stream subreddit submissions. Will add new submissions to self.submissions list."""
        while True:
            try:
                # This will check for any new submissions and add them to self.submissions
                for submission in self.submission_stream:
                    if submission is None:
                        break
                    self.submissions.append(submission)
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
            await asyncio.sleep(10)

    async def stream_verified_comments(self):
        """Stream verified comments. Updates self.comments when a new verified comment is found."""
        while True:
            print("STREAMING VERIFIED COMMENTS")
            try:
                for comment in self.comment_stream:
                    if comment is None:
                        break

                    for flair in self.subreddit.flair(comment.author):
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
                            self.comments.append(comment)
                            break

            except AssertionError as e:
                if "429" in str(e):
                    await asyncio.sleep(60 * 11)
                    global_settings.rleb_log_error(
                        f"[REDDIT]: stream_verified_comments() -> {str(e)}"
                    )
            except prawcore.exceptions.ServerError as e:
                pass  # Reddit server borked, try again
            except prawcore.exceptions.RequestException as e:
                await asyncio.sleep(60)  # timeout error, just wait awhile and try again
            except Exception as e:
                global_settings.rleb_log_error(
                    "[REDDIT]: Streaming verified comments failed - {0}".format(e)
                )
                global_settings.rleb_log_error(traceback.format_exc())
                global_settings.thread_crashes["asyncio"] += 1
                global_settings.last_datetime_crashed["asyncio"] = datetime.now()
            print("DONE STREAMING VERIFIED COMMENTS")
            await asyncio.sleep(10)

    async def process_inbox(self):
        """Process inbox messages, handling flair requests."""
        while True:
            try:
                for unread_message in self.inbox_stream:
                    if unread_message is None:
                        break

                    body = unread_message.body
                    user = unread_message.author

                    # if message is a flair request
                    subject = unread_message.subject.lower().replace(" ", "")
                    if subject in multiflair_request_keys:
                        self.handle_flair_request(user, body)

                    # Mark message as read now that we have processed it.
                    self.reddit.inbox.mark_read([unread_message])
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
            await asyncio.sleep(10)

    async def stream_modlog(self):
        """Stream mod log entries. Async generator that yields modlog entries."""
        while True:
            try:
                for log in self.mod_log:
                    if log is None:
                        break

                    # only accept logs that have an appropriate mod & action
                    if log.mod != None and (
                        log.mod in global_settings.filtered_mod_log
                    ):
                        continue
                    if log.action != None and (
                        log.action.lower() not in global_settings.allowed_mod_actions
                    ):
                        continue
                    self.mod_logs.append(log)

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
            await asyncio.sleep(10)

    async def stream_modmail(self):
        """Stream modmail conversations. Async generator that yields modmail conversations."""
        while True:
            try:
                # Within-batch deduplication (only for this single batch)
                seen_in_batch: set[str] = set()
                seen_in_batch_ordered: list[str] = []
                for conversation in self.modmail_stream:
                    if not conversation or not isinstance(
                        conversation, ModmailConversation
                    ):
                        continue

                    # only find modmails from 5m ago
                    last_updated = datetime.fromisoformat(conversation.last_updated)
                    if (
                        abs((datetime.now(timezone.utc) - last_updated).total_seconds())
                        > 60 * 5
                    ):
                        continue

                    # Deduplicate within this batch
                    dedupe_id = f"{conversation.id}:{len(conversation.messages)}"
                    if dedupe_id in seen_in_batch:
                        continue
                    seen_in_batch.add(dedupe_id)
                    seen_in_batch_ordered.append(dedupe_id)

                    # Bound cache size: if above 100, dump the first 50 to not have the set grow unbounded
                    if len(seen_in_batch_ordered) >= 100:
                        for convo_to_delete in seen_in_batch_ordered[:50]:
                            seen_in_batch.remove(convo_to_delete)
                        seen_in_batch_ordered = seen_in_batch_ordered[50:]
                        global_settings.rleb_log_info(
                            "[REDDIT]: Modmail - Clearing modmail convo cache within batch"
                        )

                    # mark as read
                    full_convo = self.subreddit.modmail(conversation.id)
                    full_convo.read()
                    conversation.read()

                    global_settings.rleb_log_info(
                        "[REDDIT]: Modmail - {0}".format(dedupe_id)
                    )

                    # Handle multiflairs from subreddit.
                    subject = conversation.subject
                    if subject.lower().replace(" ", "") in multiflair_request_keys:
                        self.handle_flair_request(
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

                    self.conversations.append(conversation)
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
            await asyncio.sleep(10)

    async def get_meme(self, meme_subreddit: str):
        meme_sub = self.reddit.subreddit(meme_subreddit)
        if meme_sub.over18:
            return

        randomizer = random.randint(1, 10)
        count = 0

        tries = 0
        for meme in meme_sub.top("day"):
            if tries > 3:
                return None
            if (
                meme.over_18
                or meme.is_video
                or "gallery" in meme.url
                or "v.reddit" in meme.url
            ):
                tries += 1
                continue

            # Randomly decide whether or not to take a meme. Makes the algo spicey.
            if count <= randomizer or tries > 2:
                count += 1
                continue

            # If meme is suitable and we hit the randomizer, send it.
            link = meme.url
            return link

    async def get_flair_census(
        self,
        amount: int,
        divider=",",
    ) -> str:
        """Takes a census of all user flairs and prints to channel.

        Parameters:
            sub (praw.models.Subreddit): The subreddit to fetch user flairs for.
            amount (int): The top x flairs you want to see.
            channel (discord.TextChannel): The channel to print results to.
            divider (str): Optional, divider to put between each flair and their count in the output.
        """

        # Extend timeouts so asyncio doesn't think that is has crashed.
        global_settings.asyncio_timeout = 60 * 15

        all_flairs = {}
        for flair in self.subreddit.flair(limit=None):
            if flair["flair_text"] != None:
                tokens = flair["flair_text"].split()
                for token in tokens:
                    if token not in all_flairs:
                        all_flairs[token] = 1
                    else:
                        all_flairs[token] += 1
        sorted_census = sorted(all_flairs.items(), key=lambda x: x[1])
        sorted_census.reverse()
        amount = min(amount, len(sorted_census))
        response = ""
        for i in range(amount):
            census_item = sorted_census[i]
            response += "{0}{1} {2}\n".format(
                census_item[0].replace(":", ""), divider, census_item[1]
            )

        # Return timeout to normal.
        global_settings.asyncio_timeout = 60 * 5

        return response

    async def handle_verified_flair_list(self) -> str:
        """Creates a list of all verified users and prints to channel.

        Parameters:
            sub (praw.models.Subreddit): The subreddit to fetch user flairs for.
            channel (discord.TextChannel): The channel to print results to.
        """

        # Extend timeouts so asyncio doesn't think that is has crashed.
        global_settings.asyncio_timeout = 60 * 15

        verified_users = []
        for flair in self.subreddit.flair(limit=None):
            if (not flair) or ("flair_text" not in flair) or (not flair["flair_text"]):
                continue

            if global_settings.verified_needle in flair["flair_text"].strip().lower():
                verified_users.append(flair["user"])

        response = f"There are {len(verified_users)} verified users on the subreddit.\n"
        if len(verified_users) == 0:
            response = "No verified users found :("

        for i in range(len(verified_users)):
            response += f"{verified_users[i].name}\n"

        # Return timeout to normal.
        global_settings.asyncio_timeout = 60 * 5

        return response

    async def get_flair_count(self, flair_text) -> int:
        count = 0
        for flair in self.subreddit.flair(limit=None):
            if flair["flair_text"] == flair_text:
                count += 1
        return count

    async def migrate_flairs(self, from_flair, to_flair):
        for flair in self.subreddit.flair(limit=None):
            if flair["flair_text"] != None and from_flair in flair["flair_text"]:
                user = flair["user"]
                new_flair = flair["flair_text"].replace(from_flair, to_flair)
                global_settings.rleb_log_info(
                    "[DISCORD]: Setting {0} to {1} (was {2})".format(
                        user.name, new_flair, flair["flair_text"]
                    )
                )
                self.subreddit.flair.set(user, text=new_flair, css_class="")

    async def update_submission(self, submission_id, text):
        submission = self.reddit.submission(submission_id)
        if submission == None:
            global_settings.rleb_log_error(
                f"[REDDIT]: Submission {submission_id} not found"
            )
            return False
        if submission.selftext == text:
            global_settings.rleb_log_info(
                f"[REDDIT]: Submission {submission_id} is already up to date"
            )
            return False
        submission.edit(text)
        return True

    def handle_flair_request(
        self, user: praw.reddit.models.Redditor, body: str
    ) -> None:
        """Read, verify, and act of dualflair messages.

        Args:
            sub (praw.models.Subreddit): Subreddit to change user flairs in.
            user (praw.models.Redditor): Redditor requesting flair change.
            body (str): Text of user-sent message.
        """
        # mods can set it to anything so they can add text such as "moderator" to flair
        if user.name in list(map(lambda x: x.name, self.moderators)):
            self.subreddit.flair.set(user, text=body, css_class="")
            rleb_log_info(
                "REDDIT: Set mod flair for {0} to {1}".format(user.name, body)
            )
        else:
            dualflairs = Data.singleton().read_triflairs()
            if dualflairs:
                allowed = list(map(lambda x: x[0], dualflairs))

            # break string into :emoji: tokens
            flairs = re.findall(global_settings.flair_pattern, body)
            seen: set[str] = set()
            flairs = [f for f in flairs if not (f in seen or seen.add(f))]  # type: ignore[func-returns-value]

            # only get allowed emoji tokens
            allowed_flairs = [f for f in flairs if f in allowed]

            # take the first n flairs (n = # of allowed flairs)
            first_n_flairs = allowed_flairs[: global_settings.number_of_allowed_flairs]

            rleb_log_info(
                "\nREDDIT: Flair request for u/{0}: {1}".format(user.name, body)
            )
            rleb_log_info("REDDIT: Requesting: {0}".format(",".join(flairs)))
            rleb_log_info("REDDIT: Allowing: {0}".format(",".join(allowed_flairs)))

            if first_n_flairs != flairs:
                message = f"\"{body}\" wasn't formatted correctly!\n\nMake sure that you are using {global_settings.number_of_allowed_flairs} or less flairs and that your flairs are spelled correctly.\n\nSee all allowed flairs: https://www.reddit.com/r/RocketLeagueEsports/wiki/flairs#wiki_how_do_i_get_2_user_flairs.3F \n\n(I'm a bot. Contact modmail to get in touch with a real person: https://reddit.com/message/compose?to=/r/RocketLeagueEsports)"
                user.message("Error with flair request", message)
            else:
                final_flair_text = " ".join(first_n_flairs)
                self.subreddit.flair.set(user, text=final_flair_text, css_class="")

                rleb_log_info("REDDIT: Taking: {0}".format(",".join(first_n_flairs)))
                rleb_log_info(
                    "REDDIT: Set flair for {0} to {1}".format(
                        user.name, final_flair_text
                    )
                )
