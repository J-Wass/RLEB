import asyncio
import asyncprawcore as prawcore
import asyncpraw
import traceback
import random
import re
from data_bridge import Data
from datetime import datetime, timezone

import global_settings
from global_settings import rleb_log_info
from asyncpraw.models import ModmailConversation
from pprint import pprint

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
        # Create new async Praw instance
        self.reddit = asyncpraw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
            username=username,
            password=password,
        )
        # Store our subreddit name
        self.subreddit_name = subreddit_name

    # When called, it will create all async streaming tasks and add them to the event loop.
    async def start(self):
        # We are required to await the subreddit before using it in future calls.
        self.subreddit = await self.reddit.subreddit(self.subreddit_name)

        await self.subreddit.load()

        # Streams all new mod log entries
        self.mod_log = self.subreddit.mod.stream.log(
            pause_after=0,
            skip_existing=True,
        )
        # Streams all new submissions from the subreddit.
        self.submission_stream = self.subreddit.stream.submissions(
            pause_after=0, skip_existing=True
        )
        # Streams all new comments from the subreddit
        self.comment_stream = self.subreddit.stream.comments(
            pause_after=0, skip_existing=True
        )
        # Streams all new inbox messages
        self.inbox_stream = self.reddit.inbox.stream(pause_after=0, skip_existing=True)
        # Streams all new modmail entries
        self.modmail_stream = self.subreddit.mod.stream.modmail_conversations(
            pause_after=0, skip_existing=True
        )

        self.comments = []
        self.submissions = []
        self.mod_logs = []
        self.conversations = []
        self.moderators = []

        await self.get_moderators()

        self.event_loop = asyncio.get_event_loop()

        self.event_loop.create_task(self.stream_new_submissions())
        self.event_loop.create_task(self.stream_verified_comments())
        self.event_loop.create_task(self.process_inbox())
        self.event_loop.create_task(self.stream_modlog())
        self.event_loop.create_task(self.stream_modmail())

    async def get_comments(self):
        """Async generator that yields verified comments."""
        while True:
            if len(self.comments) > 0:
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
        self.moderators = []
        async for moderator in self.subreddit.moderator:
            self.moderators.append(moderator)

    def is_mod(self, username: str) -> bool:
        """Return true if username belongs to a sub moderator.

        Args:
            user (str): Queried subreddit username.
        """
        return username in list(map(lambda x: x.name, self.moderators))

    async def get_modqueue_count(self):
        """Returns the number of items currently in the modqueue"""
        modqueue_count = 0
        try:
            async for item in self.subreddit.mod.modqueue():
                modqueue_count += 1
        except prawcore.exceptions.TooManyRequests as e:
            global_settings.rleb_log_error(
                f"[REDDIT]: get_modqueue_count() -> {str(e)}"
            )
            await asyncio.sleep(60 * 11)
        except prawcore.exceptions.ServerError as e:
            global_settings.rleb_log_error(
                f"[REDDIT]: get_modqueue_count() -> {str(e)}"
            )
            await asyncio.sleep(10)  # Reddit server borked, try again
            pass
        except prawcore.exceptions.RequestException as e:
            global_settings.rleb_log_error(
                f"[REDDIT]: get_modqueue_count() -> {str(e)}"
            )
            await asyncio.sleep(60)  # timeout error, just wait awhile and try again
        except Exception as e:
            global_settings.rleb_log_error(f"[REDDIT]: get_modqueue_count - {str(e)}")
            global_settings.rleb_log_error(traceback.format_exc())
            global_settings.thread_crashes["asyncio"] += 1
            global_settings.last_datetime_crashed["asyncio"] = datetime.now()
        return modqueue_count

    async def stream_new_submissions(self):
        """Stream subreddit submissions. Will add new submissions to self.submissions list."""
        while True:
            try:
                # This will check for any new submissions and add them to self.submissions
                async for submission in self.submission_stream:
                    if submission is None:
                        break
                    self.submissions.append(submission)

            except prawcore.exceptions.TooManyRequests as e:
                global_settings.rleb_log_error(
                    f"[REDDIT]: stream_new_submissions() -> {str(e)}"
                )
                await asyncio.sleep(60 * 11)
            except prawcore.exceptions.ServerError as e:
                self.submission_stream = self.subreddit.stream.submissions(
                    pause_after=0, skip_existing=True
                )
                global_settings.rleb_log_error(
                    f"[REDDIT]: stream_new_submissions() -> {str(e)}"
                )
                await asyncio.sleep(10)  # Reddit server borked, try again
                pass
            except prawcore.exceptions.RequestException as e:
                global_settings.rleb_log_error(
                    f"[REDDIT]: stream_new_submissions() -> {str(e)}"
                )
                await asyncio.sleep(60)  # timeout error, just wait awhile and try again
            except Exception as e:
                self.submission_stream = self.subreddit.stream.submissions(
                    pause_after=0, skip_existing=True
                )
                global_settings.rleb_log_error(
                    f"[REDDIT]: Streaming new submissions failed - {str(e)}"
                )
                global_settings.rleb_log_error(traceback.format_exc())
                global_settings.thread_crashes["asyncio"] += 1
                global_settings.last_datetime_crashed["asyncio"] = datetime.now()
            await asyncio.sleep(10)

    async def stream_verified_comments(self):
        """Stream verified comments. Updates self.comments when a new verified comment is found."""
        while True:
            try:
                async for comment in self.comment_stream:
                    if comment is None:
                        break

                    async for flair in self.subreddit.flair(comment.author):
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

            except prawcore.exceptions.TooManyRequests as e:
                global_settings.rleb_log_error(
                    f"[REDDIT]: stream_verified_comments() -> {str(e)}"
                )
                await asyncio.sleep(60 * 11)
            except prawcore.exceptions.ServerError as e:
                self.comment_stream = self.subreddit.stream.comments(
                    pause_after=0, skip_existing=True
                )
                global_settings.rleb_log_error(
                    f"[REDDIT]: stream_verified_comments() -> {str(e)}"
                )
                await asyncio.sleep(10)  # Reddit server borked, try again
                pass
            except prawcore.exceptions.RequestException as e:
                global_settings.rleb_log_error(
                    f"[REDDIT]: stream_verified_comments() -> {str(e)}"
                )
                await asyncio.sleep(60)  # timeout error, just wait awhile and try again
            except Exception as e:
                self.comment_stream = self.subreddit.stream.comments(
                    pause_after=0, skip_existing=True
                )
                global_settings.rleb_log_error(
                    f"[REDDIT]: Streaming new verified comments failed - {str(e)}"
                )
                global_settings.rleb_log_error(traceback.format_exc())
                global_settings.thread_crashes["asyncio"] += 1
                global_settings.last_datetime_crashed["asyncio"] = datetime.now()
            await asyncio.sleep(10)

    # TODO refactor
    async def process_inbox(self):
        """Process inbox messages, handling flair requests."""
        while True:
            try:
                async for unread_message in self.inbox_stream:
                    if unread_message is None:
                        break

                    body = unread_message.body
                    user = unread_message.author

                    # if message is a flair request
                    subject = unread_message.subject.lower().replace(" ", "")
                    if subject in multiflair_request_keys:
                        await self.handle_flair_request(user, body)

                    # Mark message as read now that we have processed it.
                    await self.reddit.inbox.mark_read([unread_message])
            except prawcore.exceptions.TooManyRequests as e:
                global_settings.rleb_log_error(f"[REDDIT]: process_inbox() -> {str(e)}")
                await asyncio.sleep(60 * 11)
            except prawcore.exceptions.ServerError as e:
                self.inbox_stream = self.reddit.inbox.stream(
                    pause_after=0, skip_existing=True
                )
                global_settings.rleb_log_error(f"[REDDIT]: process_inbox() -> {str(e)}")
                await asyncio.sleep(10)  # Reddit server borked, try again
                pass
            except prawcore.exceptions.RequestException as e:
                global_settings.rleb_log_error(f"[REDDIT]: process_inbox() -> {str(e)}")
                await asyncio.sleep(60)  # timeout error, just wait awhile and try again
            except Exception as e:
                self.inbox_stream = self.reddit.inbox.stream(
                    pause_after=0, skip_existing=True
                )
                global_settings.rleb_log_error(
                    f"[REDDIT]: Streaming Inbox failed - {str(e)}"
                )
                global_settings.rleb_log_error(traceback.format_exc())
                global_settings.thread_crashes["asyncio"] += 1
                global_settings.last_datetime_crashed["asyncio"] = datetime.now()
            await asyncio.sleep(10)

    async def stream_modlog(self):
        """Stream mod log entries. Async generator that yields modlog entries."""
        while True:
            try:
                async for log in self.mod_log:
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

            except prawcore.exceptions.TooManyRequests as e:
                global_settings.rleb_log_error(f"[REDDIT]: stream_modlog() -> {str(e)}")
                await asyncio.sleep(60 * 11)
            except prawcore.exceptions.ServerError as e:
                self.mod_log = self.subreddit.mod.stream.log(
                    pause_after=0,
                    skip_existing=True,
                )
                global_settings.rleb_log_error(f"[REDDIT]: stream_modlog() -> {str(e)}")
                await asyncio.sleep(10)  # Reddit server borked, try again
                pass
            except prawcore.exceptions.RequestException as e:
                global_settings.rleb_log_error(f"[REDDIT]: stream_modlog() -> {str(e)}")
                await asyncio.sleep(60)  # timeout error, just wait awhile and try again
            except Exception as e:
                self.mod_log = self.subreddit.mod.stream.log(
                    pause_after=0,
                    skip_existing=True,
                )
                global_settings.rleb_log_error(
                    f"[REDDIT]: Streaming Mod Log failed - {str(e)}"
                )
                global_settings.rleb_log_error(traceback.format_exc())
                global_settings.thread_crashes["asyncio"] += 1
                global_settings.last_datetime_crashed["asyncio"] = datetime.now()
            await asyncio.sleep(10)

    # TODO refactor
    async def stream_modmail(self):
        """Stream modmail conversations. Async generator that yields modmail conversations."""
        while True:
            try:
                # Within-batch deduplication (only for this single batch)
                async for conversation in self.modmail_stream:
                    if conversation == None:
                        break

                    global_settings.rleb_log_info(
                        f"[REDDIT]: Modmail - {conversation.id}"
                    )

                    # Handle multiflairs from subreddit.
                    subject = conversation.subject
                    if subject.lower().replace(" ", "") in multiflair_request_keys:
                        # Fetch full information from server
                        await conversation.load()

                        shouldSkip = False
                        # Check to see if we have already responded to this message.
                        for message in conversation.messages:
                            # Check if we have responded to this message.
                            if message.author == "RLMatchThreads":
                                # Archive the message since the bot won't try to do anything with it.
                                await conversation.archive()
                                global_settings.rleb_log_info(
                                    f"[REDDIT] Skipping triflair conversation - {conversation.id}"
                                )
                                shouldSkip = True
                                break
                        if shouldSkip:
                            continue
                        result = await self.handle_flair_request(
                            conversation.authors[0],
                            conversation.messages[-1].body_markdown,
                        )
                        # If we got an error, leave it alone so it can be tried again later.
                        if result["Message"] == "Reddit Error":
                            continue
                        await conversation.reply(result["Message"])
                        await conversation.archive()
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
            except prawcore.exceptions.TooManyRequests as e:
                global_settings.rleb_log_error(
                    f"[REDDIT]: stream_modmail() -> {str(e)}"
                )
                await asyncio.sleep(60 * 11)
            except prawcore.exceptions.ServerError as e:
                self.modmail_stream = self.subreddit.modmail.conversations(state="new")
                global_settings.rleb_log_error(
                    f"[REDDIT]: stream_modmail() -> {str(e)}"
                )
                await asyncio.sleep(10)  # Reddit server borked, try again
                pass
            except prawcore.exceptions.RequestException as e:
                global_settings.rleb_log_error(
                    f"[REDDIT]: stream_modmail() -> {str(e)}"
                )
                await asyncio.sleep(60)  # timeout error, just wait awhile and try again
            except Exception as e:
                self.modmail_stream = self.subreddit.modmail.conversations(state="new")
                global_settings.rleb_log_error(
                    f"[REDDIT]: Streaming modmail failed - {str(e)}"
                )
                global_settings.rleb_log_error(traceback.format_exc())
                global_settings.thread_crashes["asyncio"] += 1
                global_settings.last_datetime_crashed["asyncio"] = datetime.now()
            await asyncio.sleep(10)

    async def get_meme(self, meme_subreddit: str):
        meme_sub = await self.reddit.subreddit(meme_subreddit)
        if meme_sub.over18:
            return

        randomizer = random.randint(1, 10)
        count = 0

        tries = 0
        async for meme in meme_sub.top(time_filter="day"):
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
        async for flair in self.subreddit.flair(limit=None):
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
        async for flair in self.subreddit.flair(limit=None):
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
        """Returns a count of users with specified flair text"""
        count = 0
        async for flair in self.subreddit.flair(limit=None):
            if flair["flair_text"] == flair_text:
                count += 1
        return count

    async def migrate_flairs(self, from_flair, to_flair):
        """Will change all users whose flair is from_flair to to_flair"""
        count = 0
        async for flair in self.subreddit.flair(limit=None):
            if flair["flair_text"] != None and from_flair in flair["flair_text"]:
                user = flair["user"]
                new_flair = flair["flair_text"].replace(from_flair, to_flair)
                global_settings.rleb_log_info(
                    f"[DISCORD]: Setting {user.name} to {new_flair} (was {flair['flair_text']})"
                )

                await self.subreddit.flair.set(user, text=new_flair, css_class="")
                count += 1
        return count

    async def update_submission(self, submission_id, text):
        """Updates a submission with new text"""
        try:
            submission = await self.reddit.submission(submission_id)
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
            await submission.edit(text)
            return True
        except prawcore.exceptions.TooManyRequests as e:
            global_settings.rleb_log_error(f"[REDDIT]: update_submission() -> {str(e)}")
            await asyncio.sleep(60 * 11)
        except prawcore.exceptions.ServerError as e:
            global_settings.rleb_log_error(f"[REDDIT]: update_submission() -> {str(e)}")
            await asyncio.sleep(10)  # Reddit server borked, try again
            pass
        except prawcore.exceptions.RequestException as e:
            global_settings.rleb_log_error(f"[REDDIT]: update_submission) -> {str(e)}")
            await asyncio.sleep(60)  # timeout error, just wait awhile and try again
        except Exception as e:
            global_settings.rleb_log_error(f"[REDDIT]: update_submission - {str(e)}")
            global_settings.rleb_log_error(traceback.format_exc())
            global_settings.thread_crashes["asyncio"] += 1
            global_settings.last_datetime_crashed["asyncio"] = datetime.now()

    async def handle_flair_request(
        self, user: asyncpraw.reddit.models.Redditor, body: str
    ):
        """Read, verify, and act of triflair messages.

        Args:
            user (praw.models.Redditor): Redditor requesting flair change.
            body (str): Text of user-sent message.
        """
        # mods can set it to anything so they can add text such as "moderator" to flair
        if user.name in list(map(lambda x: x.name, self.moderators)):
            await self.subreddit.flair.set(user, text=body, css_class="")
            rleb_log_info(
                "REDDIT: Set mod flair for {0} to {1}".format(user.name, body)
            )
            result = {
                "Succeeded": True,
                "Message": f"I have successfully set your flairs to {body}",
            }
            return result
        else:
            triflairs = Data.singleton().read_triflairs()
            if triflairs:
                allowed = list(map(lambda x: x[0], triflairs))
            else:
                allowed = []

            # Creates a set based upon regex pattern matching.
            requested_flairs = set(re.findall(global_settings.flair_pattern, body))
            # Creates a set for allowed flairs
            request_allowed = {f for f in requested_flairs if f in allowed}
            # Crease a set for flairs that are not allowed.
            request_not_allowed = {f for f in requested_flairs if f not in allowed}

            rleb_log_info(f"REDDIT: Flair request for u/{user.name}: {body}")
            rleb_log_info(f"REDDIT: Requested Flairs: {','.join(requested_flairs)}")
            rleb_log_info(f"REDDIT: Allowed Flairs: {','.join(request_allowed)}")
            rleb_log_info(
                f"REDDIT: Not allowed Flairs: {','.join(request_not_allowed)}"
            )

            result = {"Succeeded": True, "Message": ""}

            if len(requested_flairs) == 0:
                result["Succeeded"] = False
                result["Message"] = (
                    f'"{body}" wasn\'t formatted correctly!\n\nMake sure that you are using the correct format from the wiki: https://www.reddit.com/r/RocketLeagueEsports/wiki/flairs\n\nPlease send a new message after fixing the error.'
                )
            elif len(requested_flairs) > global_settings.number_of_allowed_flairs:
                result["Succeeded"] = False
                result["Message"] = (
                    f"I detected {len(requested_flairs)} flairs in this request, the current limit is {global_settings.number_of_allowed_flairs}!\n\nPlease send a new message after fixing the error."
                )
            elif len(request_not_allowed) > 0:
                result["Succeeded"] = False
                result["Message"] = (
                    f"The following flairs are not allowed: {','.join(request_not_allowed)}\n\nPlease send a new message after fixing the error."
                )
            else:
                rleb_log_info(
                    f"REDDIT: Setting flair for {user.name} to {' '.join(request_allowed)}"
                )
                try:
                    await self.subreddit.flair.set(
                        redditor=user, text=" ".join(request_allowed), css_class=""
                    )
                except prawcore.exceptions.TooManyRequests as e:
                    global_settings.rleb_log_error(
                        f"[REDDIT]: get_from_modlog() -> {str(e)}"
                    )
                    await asyncio.sleep(60 * 11)
                    result["Succeeded"] = False
                    result["Message"] = "Reddit Error"
                except prawcore.exceptions.ServerError as e:
                    global_settings.rleb_log_error(
                        f"[REDDIT]: get_from_modlog() -> {str(e)}"
                    )
                    await asyncio.sleep(10)
                    result["Succeeded"] = False
                    result["Message"] = "Reddit Error"
                except prawcore.exceptions.RequestException as e:
                    global_settings.rleb_log_error(
                        f"[REDDIT]: get_from_modlog()) -> {str(e)}"
                    )
                    await asyncio.sleep(
                        60
                    )  # timeout error, just wait awhile and try again
                    result["Succeeded"] = False
                    result["Message"] = "Reddit Error"
                except Exception as e:
                    global_settings.rleb_log_error(
                        f"[REDDIT]: epdate_submission - {str(e)}"
                    )
                    global_settings.rleb_log_error(traceback.format_exc())
                    global_settings.thread_crashes["asyncio"] += 1
                    global_settings.last_datetime_crashed["asyncio"] = datetime.now()
                    result["Succeeded"] = False
                    result["Message"] = "Reddit Error"
                else:
                    result["Message"] = (
                        f"I have successfully set your flairs to {','.join(request_allowed)}"
                    )

            if result["Message"] != "Reddit Error":
                result["Message"] += (
                    "\n\n(I'm a bot. Contact modmail to get in touch with a real person: https://reddit.com/message/compose?to=/r/RocketLeagueEsports"
                )

            return result

    async def get_from_modlog(self, action: str, limit: int):
        try:
            logs = []
            async for log in self.subreddit.mod.log(action=action, limit=limit):
                logs.append(log)
            return logs
        except prawcore.exceptions.TooManyRequests as e:
            global_settings.rleb_log_error(f"[REDDIT]: get_from_modlog() -> {str(e)}")
            await asyncio.sleep(60 * 11)
        except prawcore.exceptions.ServerError as e:
            global_settings.rleb_log_error(f"[REDDIT]: get_from_modlog() -> {str(e)}")
            await asyncio.sleep(10)  # Reddit server borked, try again
            pass
        except prawcore.exceptions.RequestException as e:
            global_settings.rleb_log_error(f"[REDDIT]: get_from_modlog()) -> {str(e)}")
            await asyncio.sleep(60)  # timeout error, just wait awhile and try again
        except Exception as e:
            global_settings.rleb_log_error(f"[REDDIT]: epdate_submission - {str(e)}")
            global_settings.rleb_log_error(traceback.format_exc())
            global_settings.thread_crashes["asyncio"] += 1
            global_settings.last_datetime_crashed["asyncio"] = datetime.now()
        finally:
            return logs
