import os
import pathlib
import signal
import discord
import random
from datetime import datetime
import time
import asyncio
from threading import Lock, Thread
import traceback
import math

import health_check
import global_settings
from reddit_bridge import RedditBridge
from liqui import diesel
import stdout
from data_bridge import AutoUpdate, Data, Remindme
from global_settings import user_names_to_ids
from liqui.team_lookup import handle_team_lookup
from liqui.group_lookup import handle_group_lookup
from calendar_event import handle_calendar_lookup
from tasks import handle_task_lookup, get_scheduled_posts, get_weekly_events
from liqui.swiss_lookup import handle_swiss_lookup
from liqui.bracket_lookup import handle_bracket_lookup
from liqui.mvp_lookup import (
    handle_mvp_form_creation,
    handle_mvp_results_lookup,
)
from liqui.diesel import (
    handle_makethread_lookup,
    handle_stream_lookup,
    handle_broadcast_lookup,
    healthcheck,
    handle_coverage_lookup,
    handle_schedule_lookup,
)
from liqui.prizepool_lookup import handle_prizepool_lookup

responses_lock = Lock()


def is_staff(user: discord.Member) -> bool:
    """Return true if discord user has the Subreddit Moderators role."""
    return "Subreddit Moderators" in map(lambda x: x.name, user.roles)


class RLEsportsBot(discord.Client):
    new_post_channel: discord.TextChannel
    modmail_channel: discord.TextChannel
    bot_command_channel: discord.TextChannel
    schedule_chat_channel: discord.TextChannel
    roster_news_channel: discord.TextChannel
    verified_comments_channel: discord.TextChannel
    modlog_channel: discord.TextChannel
    thread_creation_channel: discord.TextChannel
    moderation_channel: discord.TextChannel

    def __init__(self):
        """Initialize a new instance of RLEsportsBot."""
        super().__init__(intents=discord.Intents.all())

        # The datetime the bot started.
        self.start_datetime = datetime.now()

        # Stores map of username->datetime of users who have recently pinged.
        self.responses = {}

        # The subreddit of memes or images to flood into #bot-commands.
        self.meme_subreddit = "minimalistphotography"

        # The last time the modqueue alert was sent (for 12-hour cooldown)
        self.last_modqueue_alert_time = None

        # Track if we've sent the congrats message for empty modqueue
        # Initialize to True so we don't send congrats on bot startup if queue is already empty
        self.modqueue_congrats_sent = True

    async def setup_hook(self):
        """Setup hook to store global reference."""
        # Store reference to Discord client globally for direct communication
        global_settings.discord_client = self

    async def on_ready(self):
        """Indicate bot has joined the discord and start background tasks."""
        global_settings.rleb_log_info("[DISCORD]: Logged on as {0}".format(self.user))

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

        # start background tasts for reddit bridge
        await global_settings.reddit_bridge.start()

        global_settings.rleb_log_info(
            f"[REDDIT]: Finished Reddit Startup for {global_settings.reddit_bridge.subreddit_name}"
        )

        # Initialize all channels first
        self.new_post_channel = self.get_channel(global_settings.NEW_POSTS_CHANNEL_ID)  # type: ignore

        assert isinstance(self.new_post_channel, discord.abc.Messageable), (
            "New Post channel is not messageable or not found!"
        )

        self.modmail_channel = self.get_channel(global_settings.MODMAIL_CHANNEL_ID)  # type: ignore

        assert isinstance(self.modmail_channel, discord.abc.Messageable), (
            "Modmail channel is not messageable or not found!"
        )

        self.bot_command_channel = self.get_channel(
            global_settings.BOT_COMMANDS_CHANNEL_ID
        )  # type: ignore

        assert isinstance(self.bot_command_channel, discord.abc.Messageable), (
            "Bot command channel is not messageable or not found!"
        )

        self.schedule_chat_channel = self.get_channel(
            global_settings.SCHEDULE_CHAT_CHANNEL_ID
        )  # type: ignore

        assert isinstance(self.schedule_chat_channel, discord.abc.Messageable), (
            "Modmail channel is not messageable or not found!"
        )

        self.roster_news_channel = self.get_channel(
            global_settings.ROSTER_NEWS_CHANNEL_ID
        )  # type: ignore

        assert isinstance(self.roster_news_channel, discord.abc.Messageable), (
            "Modmail channel is not messageable or not found!"
        )

        self.verified_comments_channel = self.get_channel(
            global_settings.VERIFIED_COMMENTS_CHANNEL_ID
        )  # type: ignore

        assert isinstance(self.verified_comments_channel, discord.abc.Messageable), (
            "Modmail channel is not messageable or not found!"
        )

        self.modlog_channel = self.get_channel(global_settings.MODLOG_CHANNEL_ID)  # type: ignore

        assert isinstance(self.modlog_channel, discord.abc.Messageable), (
            "Modmail channel is not messageable or not found!"
        )

        self.thread_creation_channel = self.get_channel(
            global_settings.THREAD_CREATION_CHANNEL_ID
        )  # type: ignore

        assert isinstance(self.thread_creation_channel, discord.abc.Messageable), (
            "Modmail channel is not messageable or not found!"
        )

        self.moderation_channel = self.get_channel(
            global_settings.MODERATION_CHANNEL_ID
        )  # type: ignore

        assert isinstance(self.moderation_channel, discord.abc.Messageable), (
            "Modmail channel is not messageable or not found!"
        )

        # Now that channels are initialized, create background tasks
        self.loop.create_task(self.check_new_submissions())
        self.loop.create_task(self.check_new_modfeed())
        self.loop.create_task(self.check_new_verified_comments())
        self.loop.create_task(self.check_modqueue_length())
        self.loop.create_task(self.process_reddit_inbox())
        self.loop.create_task(self.auto_update_threads())
        self.loop.create_task(self.check_remindmes())

        # Create asyncio tasks for health monitoring and task alerts
        if global_settings.health_enabled:
            self.loop.create_task(self.run_health_check())
        if global_settings.task_alerts_enabled:
            self.loop.create_task(self.run_task_alerts())

        # Create a mapping of discord usernames to discord ids for future use.
        for m in self.new_post_channel.members:  # type: ignore
            if m.discriminator == "0":  # type: ignore
                global_settings.user_names_to_ids[m.name.lower()] = m.id  # type: ignore
            else:
                global_settings.user_names_to_ids[
                    m.name.lower() + "#" + m.discriminator  # type: ignore
                ] = m.id

        # If testing, ping the discord channel.
        if global_settings.RUNNING_MODE != "production":
            await self.bot_command_channel.send(  # type: ignore
                "Bot is online, running in {0} under {1} mode.".format(
                    global_settings.RUNNING_ENVIRONMENT, global_settings.RUNNING_MODE
                )
            )
        else:
            await self.send_meme(self.bot_command_channel)

    async def send_meme(self, channel):
        if not global_settings.reddit_bridge:
            return False

        meme_link = await global_settings.reddit_bridge.get_meme(
            meme_subreddit=self.meme_subreddit
        )

        if meme_link == None:
            await channel.send("Couldn't find a suitable meme :(")
            return False
        else:
            await channel.send("{0}".format(meme_link))
            return True

    async def check_new_submissions(self):
        """Check Reddit submissions directly and post in 'new posts' discord channel."""
        # Track already posted submissions to avoid duplicates
        already_posted_submissions: set[str] = set()
        already_posted_submissions_ordered: list[str] = []

        await asyncio.sleep(10)
        while True:
            try:
                if (
                    not global_settings.discord_check_new_submission_enabled
                    or not global_settings.reddit_bridge
                ):
                    break

                async for submission in global_settings.reddit_bridge.get_comments():
                    # Skip if we've already posted this submission
                    submission_id = submission.id
                    if submission_id in already_posted_submissions:
                        continue

                    # Track this submission as posted
                    already_posted_submissions.add(submission_id)
                    already_posted_submissions_ordered.append(submission_id)

                    # Keep cache size reasonable (clear oldest 50 when we hit 100)
                    if len(already_posted_submissions_ordered) >= 100:
                        for sub_to_delete in already_posted_submissions_ordered[:50]:
                            already_posted_submissions.remove(sub_to_delete)
                        already_posted_submissions_ordered = (
                            already_posted_submissions_ordered[50:]
                        )

                    global_settings.rleb_log_info(
                        "[DISCORD]: Received submission id {0}: {1}".format(
                            submission, submission.title
                        )
                    )
                    embed = discord.Embed(
                        title=submission.title,
                        url="https://www.reddit.com{0}".format(submission.permalink),
                        color=random.choice(global_settings.colors),
                    )
                    embed.set_author(name=submission.author.name)

                    if not submission.link_flair_text:
                        continue

                    if "roster news" in submission.link_flair_text.strip().lower():
                        await self.roster_news_channel.send(embed=embed)  # type: ignore

                    await self.new_post_channel.send(embed=embed)  # type: ignore

                global_settings.asyncio_threads_heartbeats["submissions"] = (
                    datetime.now()
                )
            except Exception as e:
                global_settings.rleb_log_error(
                    "[DISCORD]: Submissions asyncio thread failed - {0}".format(e)
                )
                await self.bot_command_channel.send(  # type: ignore
                    "New Submissions asyncio thread encountered error"
                )
                global_settings.rleb_log_error(traceback.format_exc())
                global_settings.thread_crashes["asyncio"] += 1
                global_settings.last_datetime_crashed["asyncio"] = datetime.now()
            await asyncio.sleep(global_settings.discord_async_interval_seconds)

    async def check_new_verified_comments(self):
        """Check Reddit verified comments directly and post in discord channel."""

        # Track already posted verified comments to avoid duplicates
        already_posted_verified_comments: set[str] = set()
        already_posted_verified_comments_ordered: list[str] = []

        await asyncio.sleep(10)
        while True:
            try:
                if (
                    not global_settings.discord_check_new_verified_comments_enabled
                    or not global_settings.reddit_bridge
                ):
                    break

                async for (
                    verified_comments
                ) in global_settings.reddit_bridge.get_comments():
                    # Skip if we've already posted this comment
                    comment_id = verified_comments.id
                    if comment_id in already_posted_verified_comments:
                        continue

                    # Track this comment as posted
                    already_posted_verified_comments.add(comment_id)
                    already_posted_verified_comments_ordered.append(comment_id)

                    # keep already_posted_verified_comments capped so it doesnt grow forever
                    if len(already_posted_verified_comments_ordered) >= 100:
                        for (
                            comment_to_delete
                        ) in already_posted_verified_comments_ordered[:50]:
                            already_posted_verified_comments.remove(comment_to_delete)
                        already_posted_verified_comments_ordered = (
                            already_posted_verified_comments_ordered[50:]
                        )

                    global_settings.rleb_log_info(
                        "[DISCORD]: Received comment id {0}: {1}, {2}".format(
                            verified_comments,
                            verified_comments.body,
                            verified_comments.author.name,
                        )
                    )

                    # ensure we stay under the 256 limit for title length
                    text = verified_comments.body if verified_comments.body else ""
                    text = text[:250]
                    if len(text) == 250:
                        text += "..."
                    embed = discord.Embed(
                        title=text,
                        url="https://www.reddit.com{0}".format(
                            verified_comments.permalink
                        ),
                        color=random.choice(global_settings.colors),
                    )
                    embed.set_author(name=verified_comments.author.name)

                    await self.verified_comments_channel.send(embed=embed)  # type: ignore

                global_settings.asyncio_threads_heartbeats["verified_comments"] = (
                    datetime.now()
                )
            except Exception as e:
                global_settings.rleb_log_error(
                    "[DISCORD]: Verified comments asyncio thread failed - {0}".format(e)
                )
                await self.bot_command_channel.send(  # type: ignore
                    "Verified Comments asyncio thread encountered error"
                )
                global_settings.rleb_log_error(traceback.format_exc())
                global_settings.thread_crashes["asyncio"] += 1
                global_settings.last_datetime_crashed["asyncio"] = datetime.now()
            await asyncio.sleep(global_settings.discord_async_interval_seconds)

    async def check_new_modfeed(self):
        """Check Reddit modmail/modlog directly and post in discord."""

        # Track already posted modlog entries to avoid duplicates
        already_posted_modlog: set[str] = set()
        already_posted_modlog_ordered: list[str] = []

        # Track already posted modmail conversations to avoid duplicates
        already_posted_modmail: set[str] = set()
        already_posted_modmail_ordered: list[str] = []

        await asyncio.sleep(10)
        while True:
            try:
                if (
                    not global_settings.discord_check_new_modmail_enabled
                    or not global_settings.reddit_bridge
                ):
                    break

                # Mod Log
                async for item in global_settings.reddit_bridge.get_mod_logs():
                    # Skip if we've already posted this modlog entry
                    modlog_id = item.id

                    if modlog_id in already_posted_modlog:
                        continue

                    # Track this modlog entry as posted
                    already_posted_modlog.add(modlog_id)
                    already_posted_modlog_ordered.append(modlog_id)

                    # Keep cache size reasonable (clear oldest 50 when we hit 100)
                    if len(already_posted_modlog_ordered) >= 100:
                        for log_to_delete in already_posted_modlog_ordered[:50]:
                            already_posted_modlog.remove(log_to_delete)
                        already_posted_modlog_ordered = already_posted_modlog_ordered[
                            50:
                        ]

                    await asyncio.sleep(1)

                    # Create an embed to post for each mod log.
                    embed = discord.Embed(
                        title=item.action.replace("_", " ").title(),
                        url="https://www.reddit.com/r/RocketLeagueEsports/about/log/",
                        color=random.choice(global_settings.colors),
                    )
                    embed.set_author(name=item.mod)

                    # The text that will follow the embed.
                    content_array = []
                    if len(item.target_title or "") > 0:
                        content_array.append(f"**Title**: {item.target_title}")
                    if (
                        len(item.target_author or "") > 0
                        and item.target_author != item.mod
                    ):
                        content_array.append(f"**User**: {item.target_author}")
                    if len(item.description or "") > 0:
                        content_array.append(f"**Description**: {item.description}")
                    if len(item.details or "") > 0:
                        content_array.append(f"**Extra Details**: {item.details}")
                    content_array.append(
                        "--------------------------------------------------------"
                    )
                    contents = "\n".join(content_array)

                    embed.description = contents

                    # Send everything.
                    try:
                        await self.modlog_channel.send(embed=embed)
                    except discord.HTTPException as e:
                        # Message has invalid formatting. Just send basic msg.
                        await self.modlog_channel.send(item.description)

                # Mod Mail
                async for conversation in global_settings.reddit_bridge.get_modmail():
                    # Skip if we've already posted this modmail conversation
                    # Use same dedupe logic as in stream_modmail (id + message count)
                    dedupe_id = f"{conversation.id}:{len(conversation.messages)}"
                    if dedupe_id in already_posted_modmail:
                        continue

                    # Track this modmail as posted
                    already_posted_modmail.add(dedupe_id)
                    already_posted_modmail_ordered.append(dedupe_id)

                    # Keep cache size reasonable (clear oldest 50 when we hit 100)
                    if len(already_posted_modmail_ordered) >= 100:
                        for mail_to_delete in already_posted_modmail_ordered[:50]:
                            already_posted_modmail.remove(mail_to_delete)
                        already_posted_modmail_ordered = already_posted_modmail_ordered[
                            50:
                        ]
                    global_settings.rleb_log_info(
                        "[DISCORD]: Received modmail id {0}: {1}".format(
                            conversation.id, conversation.messages[-1].body_markdown
                        )
                    )
                    embed = None

                    # On-going conversation.
                    if len(conversation.messages) > 1:
                        embed = discord.Embed(
                            title="Commented on '{0}'".format(conversation.subject),
                            url="https://mod.reddit.com/mail/all",
                            color=random.choice(global_settings.colors),
                        )
                        embed.set_author(name=conversation.authors[0].name)
                    # New modmail
                    else:
                        embed = discord.Embed(
                            title="Created: '{0}'".format(conversation.subject),
                            url="https://mod.reddit.com/mail/all",
                            color=random.choice(global_settings.colors),
                        )
                        embed.set_author(name=conversation.authors[0].name)

                    embed.description = f"{conversation.messages[-1].body_markdown}\n--------------------------------------------------------"

                    # Send everything.
                    try:
                        await self.modmail_channel.send(embed=embed)
                    except discord.HTTPException as e:
                        # Message has invalid formatting. Just send basic msg.
                        await self.modmail_channel.send(
                            f"**{conversation.subject}** by {conversation.authors[0].name}"
                        )

                global_settings.asyncio_threads_heartbeats["modmail"] = datetime.now()
            except Exception as e:
                global_settings.rleb_log_error(
                    "[DISCORD]: Modfeed asyncio thread failed - {0}".format(e)
                )
                await self.bot_command_channel.send(
                    "Modfeed asyncio thread encountered error"
                )
                global_settings.rleb_log_error(traceback.format_exc())
                global_settings.thread_crashes["asyncio"] += 1
                global_settings.last_datetime_crashed["asyncio"] = datetime.now()

            await asyncio.sleep(global_settings.discord_async_interval_seconds)

    async def check_modqueue_length(self):
        """Check modqueue length every 10 minutes and alert if too long."""
        global_settings.asyncio_threads_heartbeats["modqueue"] = datetime.now()
        await asyncio.sleep(10)
        while True:
            try:
                if not global_settings.reddit_bridge:
                    break

                # Count items in modqueue
                modqueue_count = (
                    await global_settings.reddit_bridge.get_modqueue_count()
                )

                global_settings.rleb_log_info(
                    f"[DISCORD]: Modqueue check - {modqueue_count} items in queue"
                )

                # Check if we should alert
                should_alert = False
                if modqueue_count >= global_settings.MODQUEUE_ALERT_THRESHOLD:
                    if self.last_modqueue_alert_time is None:
                        # Never alerted before
                        should_alert = True
                    else:
                        # Check if cooldown period has passed
                        time_since_last_alert = (
                            datetime.now() - self.last_modqueue_alert_time
                        ).total_seconds()
                        if (
                            time_since_last_alert
                            >= global_settings.MODQUEUE_ALERT_COOLDOWN
                        ):
                            should_alert = True

                if should_alert:
                    alert_message = f"⚠️ **Modqueue Alert**: The modqueue is getting large! ({modqueue_count} items waiting in queue). Please review https://www.reddit.com/mod/queue"
                    await self.moderation_channel.send(alert_message)
                    self.last_modqueue_alert_time = datetime.now()
                    # Reset congrats flag so we can congratulate when it gets cleared
                    self.modqueue_congrats_sent = False
                    global_settings.rleb_log_info(
                        f"[DISCORD]: Modqueue alert sent - {modqueue_count} items"
                    )

                # Send congrats message when queue returns to 0
                if modqueue_count == 0 and not self.modqueue_congrats_sent:
                    emoji = random.choice(global_settings.success_emojis)
                    congrats_message = (
                        f"{emoji}{emoji}{emoji} The modqueue has been cleared!"
                    )
                    await self.moderation_channel.send(congrats_message)
                    self.modqueue_congrats_sent = True
                    global_settings.rleb_log_info(
                        "[DISCORD]: Modqueue congrats message sent - queue is empty"
                    )

                global_settings.asyncio_threads_heartbeats["modqueue"] = datetime.now()

            except Exception as e:
                global_settings.rleb_log_error(
                    "[DISCORD]: Modqueue check asyncio thread failed - {0}".format(e)
                )
                await self.bot_command_channel.send(
                    "Modqueue check asyncio thread died"
                )
                global_settings.rleb_log_error(traceback.format_exc())
                global_settings.thread_crashes["asyncio"] += 1
                global_settings.last_datetime_crashed["asyncio"] = datetime.now()

            await asyncio.sleep(global_settings.MODQUEUE_CHECK_INTERVAL)

    async def process_reddit_inbox(self):
        """Process Reddit inbox for flair requests."""

        await asyncio.sleep(10)
        while True:
            try:
                # Needs to be fixed still.
                # if global_settings.monitor_subreddit_enabled:
                #     continue

                global_settings.asyncio_threads_heartbeats["inbox"] = datetime.now()
            except Exception as e:
                global_settings.rleb_log_error(
                    "[DISCORD]: Inbox processing failed - {0}".format(e)
                )
                global_settings.rleb_log_error(traceback.format_exc())
                global_settings.thread_crashes["asyncio"] += 1
                global_settings.last_datetime_crashed["asyncio"] = datetime.now()

            await asyncio.sleep(global_settings.discord_async_interval_seconds)

    async def check_remindmes(self):
        """Check for due reminders and send them."""
        await asyncio.sleep(10)
        while True:
            try:
                remindmes = Data.singleton().read_remindmes()
                current_time = time.time()

                for remindme in remindmes:
                    # Check if reminder is due
                    if remindme.trigger_timestamp <= current_time:
                        global_settings.rleb_log_info(
                            f"[REMINDME]: Triggering reminder {remindme.remindme_id}"
                        )

                        # Build the message
                        user_id = global_settings.user_names_to_ids.get(
                            remindme.discord_username
                        )
                        if user_id:
                            msg = f"**Reminder for <@{user_id}>:** {remindme.message}"
                        else:
                            msg = f"**Reminder for {remindme.discord_username}:** {remindme.message}"

                        # Send to channel
                        try:
                            channel = self.get_channel(remindme.channel_id)  # type: ignore
                            if not channel:
                                global_settings.rleb_log_info(
                                    f"[REMINDME]: Channel {remindme.channel_id} not found for reminder {remindme.remindme_id}, using fallback channel"
                                )
                                channel = self.bot_command_channel

                            if channel:
                                await channel.send(msg)  # type: ignore
                            else:
                                global_settings.rleb_log_error(
                                    f"[REMINDME]: Could not find channel {remindme.channel_id} for reminder {remindme.remindme_id}"
                                )
                        except Exception as e:
                            global_settings.rleb_log_error(
                                f"[REMINDME]: Failed to send reminder {remindme.remindme_id}: {e}"
                            )

                        # Delete from database
                        Data.singleton().delete_remindme(remindme.remindme_id)

                global_settings.asyncio_threads_heartbeats["remindme"] = datetime.now()
            except Exception as e:
                global_settings.rleb_log_error(
                    "[DISCORD]: Remindme check failed - {0}".format(e)
                )
                global_settings.rleb_log_error(traceback.format_exc())
                global_settings.thread_crashes["asyncio"] += 1
                global_settings.last_datetime_crashed["asyncio"] = datetime.now()

            await asyncio.sleep(60)  # Check every 60 seconds

    async def auto_update_threads(self):
        """Auto-update Reddit threads with fresh Liquipedia data."""
        await asyncio.sleep(10)
        while True:
            try:
                if not global_settings.reddit_bridge:
                    break

                auto_updates = global_settings.auto_updates.values()
                if auto_updates:
                    global_settings.rleb_log_info(
                        "[AUTO UPDATER]: Starting auto update check."
                    )

                for auto_update in auto_updates:
                    try:
                        day_number = auto_update.day_number
                        liquipedia_url = auto_update.liquipedia_url

                        options = auto_update.thread_options
                        tourney_system = auto_update.thread_type
                        stringified_options = "-".join(
                            sorted(options.lower().split(","))
                        )
                        if stringified_options == "none":
                            template = tourney_system
                        else:
                            template = f"{tourney_system}-{stringified_options}"

                        # Run blocking diesel call in thread pool
                        fresh_markdown = await asyncio.to_thread(
                            diesel.get_make_thread_markdown,
                            liquipedia_url,
                            template,
                            day_number,
                        )

                        # If markdown is the same as last time, don't write to reddit
                        if (
                            liquipedia_url in global_settings.auto_update_markdown
                            and global_settings.auto_update_markdown[liquipedia_url]
                            == fresh_markdown
                        ):
                            continue

                        reddit_url = auto_update.reddit_url

                        # https://www.reddit.com/r/RLCSnewsTest/comments/17oh7u8/auto_update_test/
                        # becomes
                        # 17oh7u8
                        submission_id = reddit_url.split("/comments/")[1].split("/")[0]

                        # Update the thread with new results
                        result = await global_settings.reddit_bridge.update_submission(
                            submission_id=submission_id, text=fresh_markdown
                        )
                        # TODO is this logic correct?
                        if result is False:
                            del global_settings.auto_updates[auto_update.auto_update_id]
                            Data.singleton().delete_auto_update(auto_update)
                        elif result is True:
                            global_settings.rleb_log_info(
                                f"[AUTO UPDATER]: Updated {auto_update.reddit_url}"
                            )
                            global_settings.auto_update_markdown[liquipedia_url] = (
                                fresh_markdown
                            )

                    except Exception as e:
                        global_settings.rleb_log_error(
                            f"[AUTO UPDATER]: Failed to auto update reddit thread {auto_update.reddit_url}. {str(e)}"
                        )

                global_settings.asyncio_threads_heartbeats["auto_update"] = (
                    datetime.now()
                )

            except Exception as e:
                global_settings.rleb_log_error(
                    "[DISCORD]: Auto updater failed - {0}".format(e)
                )
                global_settings.rleb_log_error(traceback.format_exc())
                global_settings.thread_crashes["asyncio"] += 1
                global_settings.last_datetime_crashed["asyncio"] = datetime.now()

            await asyncio.sleep(60)  # Check every 60 seconds

    async def run_health_check(self):
        """Run the health check monitor."""
        from health_check import health_check

        try:
            await health_check(self.bot_command_channel)
        except Exception as e:
            global_settings.rleb_log_error(
                "[DISCORD]: Health check failed - {0}".format(e)
            )
            global_settings.rleb_log_error(traceback.format_exc())

    async def run_task_alerts(self):
        """Run the task alert checker."""
        from tasks import task_alert_check

        try:
            await task_alert_check(self.thread_creation_channel, self)
        except Exception as e:
            global_settings.rleb_log_error(
                "[DISCORD]: Task alerts failed - {0}".format(e)
            )
            global_settings.rleb_log_error(traceback.format_exc())

    # Record that a user was responded to. Useful for responding "thanks".
    async def add_response(self, message):
        Data.singleton().increment_user_statistics_commands_used(str(message.author))
        with responses_lock:
            self.responses[str(message.author)] = datetime.now()

    # Remove old records that a user was responded to.
    async def remove_old_responses(self):
        with responses_lock:
            responses = self.responses.copy()
            for k, v in responses.items():
                if (datetime.now() - v).total_seconds() > 20:
                    del self.responses[k]

    # TODO: refactor this bad boy
    async def on_message(self, message):
        """Handle messages that occur in discord.

        Args:
            message (discord.Message): Discord message being handled.
        """
        # Don't respond to messages from yourself, lol.
        if "RLesports" in str(message.author):
            return

        await self.remove_old_responses()

        # force local builds to use !debug command before any commands
        discord_message = message.content

        if global_settings.RUNNING_MODE == "local":
            if "!debug" not in discord_message:
                return
            discord_message = discord_message.replace("!debug ", "")

        if str(message.channel) == "voting":
            global_settings.rleb_log_info(
                "[DISCORD]: New voting message: {0}".format(discord_message)
            )
            await message.add_reaction("👍")
            await message.add_reaction("👎")
            await message.add_reaction("🤷")
            return

        if str(message.channel) == "ban-review":
            global_settings.rleb_log_info(
                "[DISCORD]: New ban-review message: {0}".format(discord_message)
            )
            await message.add_reaction("⚠️")
            await message.add_reaction("1️⃣")
            await message.add_reaction("2️⃣")
            await message.add_reaction("3️⃣")
            await message.add_reaction("💀")
            await message.add_reaction("👥")
            await message.add_reaction("🤷")
            return

        elif (
            discord_message == "thanks"
            or discord_message == "thank you"
            or discord_message == "ty"
            or discord_message == "thx"
        ):
            if str(message.author) in self.responses:
                thanks_responses = ["np", "no problem", "no worries", "you're welcome"]
                await message.channel.send(random.choice(thanks_responses))
                Data.singleton().increment_user_statistics_thanks_given(
                    str(message.author)
                )
                del self.responses[str(message.author)]

        elif discord_message.startswith("!ty") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            tokens = discord_message.split()
            if len(tokens) == 1:
                user_statistics = [
                    Data.singleton().read_user_statistics(str(message.author))
                ]
            elif len(tokens) == 2:
                if tokens[1] == "help":
                    await message.channel.send(
                        f"Usage is `!ty`, `!ty all` or `!ty discord_username`"
                    )
                    return
                if tokens[1] == "all":
                    user_statistics = Data.singleton().read_all_user_statistics()
                else:
                    user_stat = Data.singleton().read_user_statistics(tokens[1])
                    if not user_stat:
                        await message.channel.send(
                            f"{tokens[1]} has never used the bot!"
                        )
                        return
                    user_statistics = [user_stat]
            else:
                await message.channel.send(
                    f"Usage is `!ty`, `!ty all` or `!ty discord_username`"
                )
                return

            msg_to_send = ""
            for us in user_statistics:
                if us != None:
                    thankfulness = round(us.thanks_given / us.commands_used * 100, 0)
                    msg_to_send += f"{us.discord_username} has used the bot {us.commands_used} times and was only thankful {thankfulness}% of the time\n"
            if msg_to_send == "":
                await message.channel.send("daz broken :/")
            else:
                await stdout.print_to_channel(
                    message.channel,
                    msg_to_send,
                    title="User Statistics",
                    use_hook=False,
                )

        elif discord_message.startswith("!census") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            if not global_settings.reddit_bridge:
                return

            global_settings.rleb_log_info("[DISCORD]: Starting flair census.")
            await message.channel.send(
                "Starting flair census, this may take a minute..."
            )
            tokens = discord_message.split()
            amount = 10
            try:
                amount = abs(int(tokens[1]))
            except Exception:
                await message.channel.send(
                    "Couldn't understand that. Expected '!census [amount] [optional divider like ',' or '|']'."
                )
                return
            divider = ","
            try:
                divider = tokens[2][0]
                if divider == " ":
                    divider = ","
            except Exception:
                divider = ","
            census_data = await global_settings.reddit_bridge.get_flair_census(
                amount, divider
            )
            await stdout.print_to_channel(message.channel, census_data, "Census")
            await self.add_response(message)

        elif discord_message == "!verified" and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            if not global_settings.reddit_bridge:
                return

            global_settings.rleb_log_info(
                "[DISCORD]: Starting verified flair list creation."
            )
            await message.channel.send(
                "Retrieving all verified flairs, this may take a minute..."
            )
            flair_data = (
                await global_settings.reddit_bridge.handle_verified_flair_list()
            )
            await stdout.print_to_channel(message.channel, flair_data, "Verified Users")
            await self.add_response(message)

        elif discord_message.startswith("!migrate") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            if not global_settings.reddit_bridge:
                return

            # increase asyncio timeout so it doesn't seem like a crash
            global_settings.asyncio_timeout = 60 * 15

            global_settings.rleb_log_info("[DISCORD]: Starting migration")
            tokens = discord_message.split()
            from_flair = None
            to_flair = None
            try:
                from_flair = tokens[1]
                to_flair = tokens[2]
            except IndexError:
                await message.channel.send(
                    "Couldn't understand that. Expected '!migrate :from_flair: :to_flair:'."
                )
                global_settings.asyncio_timeout = 60 * 5
                return

            await message.channel.send("Checking flairs...")
            count = await global_settings.reddit_bridge.get_flair_count(from_flair)

            if from_flair != None and to_flair != None:
                await message.channel.send(
                    f"Type '!confirm migrate' to migrate '{from_flair}' -> '{to_flair}' in the next 2 minutes. This will affect {count} users."
                )
                self.to_flair = to_flair
                self.from_flair = from_flair
                self.migrate_request_time = datetime.now()
                await self.add_response(message)

                # reset asyncio timeout
                global_settings.asyncio_timeout = 60 * 5

        elif discord_message == "!confirm migrate" and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            if not global_settings.reddit_bridge:
                return

            # increase asyncio timeout so it doesn't seem like a crash
            global_settings.asyncio_timeout = 60 * 15

            if (datetime.now() - self.migrate_request_time).total_seconds() > 120:
                await message.channel.send(
                    "Migration timed out. You must confirm within 2 minutes to migrate flairs."
                )
                global_settings.asyncio_timeout = 60 * 5
                return
            await message.channel.send(
                f"Starting migration {self.from_flair} -> {self.to_flair}."
            )
            count = await global_settings.reddit_bridge.migrate_flairs(
                self.from_flair, self.to_flair
            )
            await message.channel.send(f"Migrated {count} users.")
            await self.add_response(message)

            # reset asyncio timeout
            global_settings.asyncio_timeout = 60 * 5

        elif discord_message == "!triflairs list" and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            all_flairs = ""
            flairs = Data.singleton().read_triflairs()
            flair_list = list(map(lambda x: x[0], flairs))
            flair_list.sort()
            for flair in flair_list:
                all_flairs += flair
                all_flairs += "\n"
            if all_flairs == "":
                await message.channel.send("No flairs found.")
                await self.add_response(message)
            else:
                await message.channel.send(all_flairs)
                await self.add_response(message)

        elif discord_message.startswith("!triflairs remove") and is_staff(
            message.author
        ):
            if not global_settings.is_discord_mod(message.author):
                return

            tokens = discord_message.split()
            flair_to_remove = None
            try:
                flair_to_remove = tokens[2]
            except IndexError:
                await message.channel.send(
                    "Couldn't understand that. Expected '!triflairs remove :flair:'."
                )
                return

            flairs = Data.singleton().read_triflairs()
            flair_list = list(map(lambda x: x[0], flairs))
            if not (flair_to_remove in flair_list):
                await message.channel.send(
                    "Couldn't find {0}! Type '!triflairs list' to view all flairs.".format(
                        flair_to_remove
                    )
                )
                return
            else:
                Data.singleton().yeet_triflair(flair_to_remove)
                await message.channel.send("Removed {0}.".format(flair_to_remove))
                await self.add_response(message)

        elif discord_message.startswith("!triflairs add") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            tokens = discord_message.split()

            try:
                flair_to_add = tokens[2]
            except IndexError:
                await message.channel.send(
                    "Couldn't understand that. Expected '!triflairs add :flair:'."
                )
                return
            if not flair_to_add or not flair_to_add.startswith(":"):
                await message.channel.send(
                    "Couldn't understand that. Make sure you are passing a :flair_code: and not an emoji 😭. You may have to disable Discord Nitro or auto emoji."
                )
                return

            flairs = Data.singleton().read_triflairs()
            flair_list = list(map(lambda x: x[0], flairs))
            if flair_to_add in flair_list:
                await message.channel.send(
                    "{0} is already in the flair list! Type '!triflairs list' to view all flairs.".format(
                        flair_to_add
                    )
                )
                return
            else:
                Data.singleton().add_triflair(flair_to_add)
                await message.channel.send("Added {0}.".format(flair_to_add))
                await self.add_response(message)

        elif discord_message.startswith("!flush") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            global_settings.flush_memory_log()
            await message.channel.send(":toilet:")

        elif discord_message.startswith("!weekly") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            scheduled_posts = await get_scheduled_posts()
            weekly_events = get_weekly_events()

            output = "**Found the following scheduled posts on reddit:**\n"
            if scheduled_posts:
                output += "\n".join(scheduled_posts)
            else:
                output += "No scheduled posts found."

            output += "\n\n**Found the following events on the weekly sheet:**\n"
            if weekly_events:
                output += "\n".join(weekly_events)
            else:
                output += "No weekly events found."

            await stdout.print_to_channel(
                message.channel, output, title="Weekly Schedule", use_hook=False
            )
            await self.add_response(message)

        elif discord_message.startswith("!sql") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            sql = " ".join(discord_message.split()[1:])
            try:
                response = Data.singleton().yolo_query(sql)
                await stdout.print_to_channel(
                    message.channel, response, title="SQL Query Results", use_hook=False
                )
            except ValueError as e:
                global_settings.rleb_log_info(
                    f"SQL query failed: {sql}", str(e), should_flush=True
                )
                await stdout.print_to_channel(
                    message.channel,
                    f"SQL query failed:\n{str(e)}",
                    title="SQL Query Error",
                    use_hook=False,
                )
                return

        elif discord_message.startswith("!logs") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            tokens = discord_message.split()
            datasource = "memory"
            count = 10
            try:
                datasource = str(tokens[1])
                count = abs(int(tokens[2]))
            except Exception:
                await message.channel.send(
                    "The first argument should be 'memory' or 'db', and the second argument should be the number of logs to see."
                )
                return

            logs = None
            if datasource == "memory":
                logs = global_settings.memory_log[(-1 * count) :]
            elif datasource == "db":
                logs = Data.singleton().read_logs(count)
            else:
                await message.channel.send(
                    "The first argument should be either 'memory' or 'db'."
                )
                return
            try:
                if logs == None or len(logs) == 0:
                    await message.channel.send("No logs to show.")
                    return
                msg = "\n".join([f"{log[0]} - {log[1]}" for log in logs])
                await stdout.print_to_channel(message.channel, msg, title="logs")
            except discord.HTTPException:
                global_settings.rleb_log_error(traceback.format_exc())
                await message.channel.send(
                    "Couldn't send logs over! (tip: there's a limit to the number of characters that can be sent. Make sure you aren't requesting too many logs. Use '!logs [db/memory] [n]', where n is a small number to avoid the character limit.)"
                )
            await self.add_response(message)

        elif discord_message.startswith("!deploy") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            await message.channel.send("Deploying… see ya in 210 seconds")
            global_settings.rleb_log_info("Deploying.", should_flush=True)
            await asyncio.sleep(0.5)

            flag = pathlib.Path("/app/data/deploy.flag")
            try:
                flag.write_text(f"ts={time.time()}\n")
            except Exception as e:
                await message.channel.send(f"Deploy trigger failed: {e}")
                return

        elif discord_message.startswith("!restart") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            await message.channel.send("brb")
            global_settings.rleb_log_info("Restarting.", should_flush=True)

            # Give Discord a moment to send the message & flush logs
            await asyncio.sleep(1.0)

            try:
                # Close Discord connection cleanly so sockets/files are released
                await self.close()
            except Exception:
                pass

            # Last resort: terminate the process so Docker will restart the container
            os._exit(0)  # hard exit, no atexit handlers

        elif discord_message == "!status" and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            # Runtime
            delta = datetime.now() - self.start_datetime
            seconds_uptime = delta.total_seconds()
            hours_uptime = round(seconds_uptime / 60 / 60, 0)
            await message.channel.send(
                "Running for {0} day(s) and {1} hour(s)".format(
                    math.floor(hours_uptime / 24), hours_uptime % 24
                )
            )

            # Diesel.
            before = time.time() * 1000
            health = await healthcheck()
            if health:
                after = time.time() * 1000
                elapsed_time = round(after - before)
                await message.channel.send(
                    f"**Diesel Status:** {health} ({elapsed_time}ms response time)"
                )
            else:
                await message.channel.send(
                    f"**Diesel Status:** Diesel is not responding (check !logs)"
                )

            try:
                before = time.time() * 1000
                db_table_count = Data.singleton().get_db_tables()
                after = time.time() * 1000
                elapsed_time = round(after - before)
                await message.channel.send(
                    f"**DB Status:** {db_table_count} tables found ({elapsed_time}ms response time)"
                )
            except:
                pass

            # Hardware specs.
            try:
                soctemp = pathlib.Path("/armbian/soctemp")
                if soctemp.exists():
                    val = int(soctemp.read_text().strip())
                    if isinstance(val, int):
                        cpu_temp = round(val / 1000.0, 1)
                        await message.channel.send(f"**CPU Temp:** {cpu_temp} C")
            except:
                pass

            try:
                total_memory = int(
                    os.popen("cat /proc/meminfo | grep MemTotal")
                    .read()
                    .replace("MemTotal:", "")
                    .replace("kB", "")
                    .strip()
                )
                available_memory = int(
                    os.popen("cat /proc/meminfo | grep MemAvailable")
                    .read()
                    .replace("MemAvailable:", "")
                    .replace("kB", "")
                    .strip()
                )
                memory_usage = round((1 - available_memory / total_memory) * 100, 1)
                await message.channel.send(f"**RAM Usage:** {memory_usage}%")
            except:
                pass

            for thread_type, crash_count in global_settings.thread_crashes.items():
                await message.channel.send(
                    "**{0} crashes detected:** {1}".format(thread_type, crash_count)
                )

            for (
                thread_type,
                last_crash,
            ) in global_settings.last_datetime_crashed.items():
                last_crash_string = "N/A"
                if last_crash:
                    delta = datetime.now() - last_crash
                    last_crash_string = delta.total_seconds() / 3600
                    last_crash_string = round(last_crash_string, 1)
                await message.channel.send(
                    "**{0} last crashed:** {1} hours ago.".format(
                        thread_type, last_crash_string
                    )
                )

            asyncio_heartbeat = [
                f"{k}: {round((datetime.now() - v).total_seconds(), 1)}s ago"
                for k, v in global_settings.asyncio_threads_heartbeats.items()
            ]
            await message.channel.send(f"**Asyncio heartbeats:** {asyncio_heartbeat}")

            await self.add_response(message)

        elif discord_message == "!reset crashes" and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            global_settings.thread_crashes["thread"] = 0
            global_settings.thread_crashes["asyncio"] = 0
            await message.channel.send("Thread crash count was reset")
            global_settings.rleb_log_info("[DISCORD]: Thread count was reset.")
            await self.add_response(message)

        elif discord_message.startswith("!search"):
            tokens = discord_message.split()
            target = ""
            try:
                target = tokens[1]
            except IndexError:
                await message.channel.send(
                    "To search on liquipedia, use '!search <thing>'"
                )
                return
            url = "https://liquipedia.net/rocketleague/index.php?search={0}".format(
                target
            )
            embed = discord.Embed(
                title=target, url=url, color=random.choice(global_settings.colors)
            )
            await message.channel.send(embed=embed)
            await self.add_response(message)

        elif discord_message.startswith("!teams") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            global_settings.rleb_log_info("[DISCORD]: Starting team generation.")
            await message.channel.send("Starting team lookup...")
            tokens = discord_message.split()
            url = ""
            try:
                url = tokens[1]
            except Exception:
                await message.channel.send(
                    "Couldn't understand that. Expected '!teams liquipedia-url'."
                )
                return
            seconds = await handle_team_lookup(url, message.channel)
            await self.add_response(message)

        elif discord_message.startswith("!alias") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            global_settings.rleb_log_info("[DISCORD]: Starting alias")

            tokens = discord_message.split()
            url = ""
            try:
                operation = tokens[1]
            except Exception:
                await message.channel.send(
                    "Couldn't understand that. Expected `!alias add [long_name] [shortened_name]`, `!alias remove [long_name]` or `!alias list`."
                )
                return

            if operation == "list":
                long_to_short_name_map: dict[str, str] = (
                    Data.singleton().read_all_aliases()
                )
                if len(long_to_short_name_map) == 0:
                    await message.channel.send(
                        "No aliases found. `!alias add [long_name] [shortened_name]` to add one."
                    )
                    await self.add_response(message)
                    return

                return_message = "Found the following aliases:"
                for long, short in long_to_short_name_map.items():
                    return_message += f"\n{long} -> {short}"
                await stdout.print_to_channel(
                    message.channel, return_message, title="Aliases", use_hook=False
                )
                await self.add_response(message)

            elif operation == "remove":
                try:
                    long_name = tokens[2]
                except Exception:
                    await message.channel.send(
                        "Couldn't understand that. Expected `!alias add [long_name] [shortened_name]`, `!alias remove [long_name]` or `!alias list`."
                    )
                    return
                global_settings.rleb_log_info(f"Removing alias: {long_name}")
                Data.singleton().remove_alias(long_name)
                await message.channel.send(
                    "Alias removed. Use `!alias list` to see all existing aliases."
                )
                await self.add_response(message)

            elif operation == "add":
                try:
                    long_name = tokens[2]
                    short_name = tokens[3]
                except Exception:
                    await message.channel.send(
                        "Couldn't understand that. Expected `!alias add [long_name] [shortened_name]`, `!alias remove [long_name]` or `!alias list`."
                    )
                    return

                global_settings.rleb_log_info(
                    f"Adding alias: {long_name} -> {short_name}"
                )
                Data.singleton().add_alias(long_name, short_name)
                await message.channel.send(
                    "Alias added. Use `!alias list` to see all existing aliases."
                )
                await self.add_response(message)

            elif operation == "help":
                await message.channel.send(
                    "Usage: `!alias add [long_name] [shortened_name]`, `!alias remove [long_name]` or `!alias list`."
                )
                return
                await self.add_response(message)

        elif discord_message.startswith("!swiss") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            global_settings.rleb_log_info(
                "[DISCORD]: Starting swiss bracket generation."
            )
            await message.channel.send("Starting swiss bracket lookup...")
            tokens = discord_message.split()
            url = ""
            try:
                url = tokens[1]
            except Exception:
                await message.channel.send(
                    "Couldn't understand that. Expected '!swiss liquipedia-url'."
                )
                return
            seconds = await handle_swiss_lookup(url, message.channel)
            await self.add_response(message)

        elif (
            discord_message.startswith("!streams")
            or discord_message.startswith("!stream")
        ) and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            global_settings.rleb_log_info("[DISCORD]: Starting stream generation.")
            await message.channel.send("Starting stream lookup...")
            tokens = discord_message.split()
            url = ""
            try:
                url = tokens[1]
            except Exception:
                await message.channel.send(
                    "Couldn't understand that. Expected '!streams liquipedia-url'."
                )
                return
            seconds = await handle_stream_lookup(url, message.channel)
            await self.add_response(message)

        elif (
            discord_message.startswith("!broadcast")
            or discord_message.startswith("!broadcasts")
        ) and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            global_settings.rleb_log_info("[DISCORD]: Starting broadcast generation.")
            await message.channel.send("Starting broadcast stream lookup...")
            tokens = discord_message.split()
            url = ""
            try:
                url = tokens[1]
            except Exception:
                await message.channel.send(
                    "Couldn't understand that. Expected '!broadcasts liquipedia-url'."
                )
                return
            seconds = await handle_broadcast_lookup(url, message.channel)
            await self.add_response(message)

        elif discord_message.startswith("!coverage") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            global_settings.rleb_log_info("[DISCORD]: Starting coverage generation.")
            await message.channel.send("Starting coverage lookup...")
            tokens = discord_message.split()
            url = ""
            try:
                url = tokens[1]
            except Exception:
                await message.channel.send(
                    "Couldn't understand that. Expected '!coverage liquipedia-url'."
                )
                return
            await handle_coverage_lookup(url, message.channel)
            await self.add_response(message)

        elif discord_message.startswith("!bracket") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            global_settings.rleb_log_info(
                "[DISCORD]: Starting elim bracket generation."
            )
            await message.channel.send("Starting elimination bracket lookup...")
            tokens = discord_message.split()
            try:
                url = tokens[1]
                date_number = tokens[2]
            except Exception:
                await message.channel.send(
                    "Couldn't understand that. Expected '!bracket liquipedia-url date-of-the-month'."
                )
                return
            bracket_markdown = await diesel.get_bracket_markdown(url, int(date_number))
            if bracket_markdown != None:
                await stdout.print_to_channel(
                    message.channel, bracket_markdown, title="Bracket"
                )
            await self.add_response(message)

        elif discord_message.startswith("!autoupdate") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            global_settings.rleb_log_info("[DISCORD]: Beginning autoupdate command")
            tokens = discord_message.split()

            try:
                # !autoupdate stop id
                if tokens[1] == "stop":
                    global_settings.rleb_log_info("[DISCORD]: Stopping autoupdate")
                    if not tokens[2]:
                        await message.channel.send(
                            "Couldn't understand that. Expected `!autoupdate stop [auto update id]`"
                        )
                        return
                    auto_update_id = int(tokens[2])
                    auto_update = Data.singleton().read_auto_update_from_id(
                        auto_update_id
                    )
                    if not auto_update:
                        await message.channel.send(
                            "Couldn't find that auto update! Use `!autoupdate list` to view all auto update ids, and then use `!autoupdate stop id`."
                        )
                        return
                    Data.singleton().delete_auto_update(auto_update)
                    if auto_update_id in global_settings.auto_updates:
                        del global_settings.auto_updates[auto_update_id]
                    await message.channel.send(
                        random.choice(global_settings.success_emojis)
                        + " auto update stopped.\nUse `!autoupdate list` to see all updates."
                    )
                    await self.add_response(message)

                    return

                # !autoupdate help
                if tokens[1] == "help":
                    await message.channel.send("**To start autoupdating:**")
                    await message.channel.send(
                        "  `!autoupdate [reddit url] [liquipedia url] [tourney system] [options] [day]`"
                    )
                    await asyncio.sleep(1)
                    await message.channel.send(
                        "    `reddit url` = the url of the already made game thread that needs to be updated"
                    )
                    await message.channel.send(
                        "    `liquipedia url` = the url of the liquipedia page related to the event of the post"
                    )
                    await message.channel.send(
                        "    `tourney system` = one of the following: groups, swiss, or bracket"
                    )
                    await message.channel.send(
                        "    `options` = any of the following: prizepool, streams (for team streams), bracketrd1 (the first round of a bracket), or none"
                    )
                    await message.channel.send(
                        "      You can combine options with commas such as: prizepool,streams,bracketrd1"
                    )
                    await message.channel.send(
                        "    `day` = the day of the tournament on liquipedia that the post is for"
                    )
                    await asyncio.sleep(1)
                    await message.channel.send(
                        "**To list running auto updates:** `!autoupdate list`"
                    )
                    await message.channel.send(
                        "**To stop an auto update:** `!autoupdate stop [auto update id]` (id can be found in `autoupdate list`)"
                    )
                    await self.add_response(message)
                    return

                # !autoupdate list
                if tokens[1] == "list":
                    global_settings.rleb_log_info("[DISCORD]: Listing autoupdate")
                    auto_updates: list[AutoUpdate] = (
                        Data.singleton().read_all_auto_updates()
                    )
                    if len(auto_updates) == 0:
                        await message.channel.send(
                            "No auto updates are set. Use `!autoupdate [reddit-url] [liquipedia-url] [tourney_system] [options] [day]` to start one. `!autoupdate help` for more.\n"
                        )
                        await self.add_response(message)
                        return

                    for auto_update in sorted(
                        auto_updates, key=lambda x: x.seconds_since_epoch
                    ):
                        seconds_ago = time.time() - auto_update.seconds_since_epoch
                        hours_ago = round(seconds_ago / 3600, 1)
                        reddit_url = auto_update.reddit_url.split("reddit.com/")[-1]
                        embed = discord.Embed(
                            title=reddit_url,
                            url=auto_update.reddit_url,
                            color=random.choice(global_settings.colors),
                        )
                        embed.set_author(
                            name=f"Auto Update ID - {auto_update.auto_update_id}"
                        )
                        embed.description = f"Started {hours_ago} hours ago"
                        await message.channel.send(embed=embed)

                    await message.channel.send(
                        "Use `!autoupdate stop [id]` to stop an autoupdate. `!autoupdate help` for more."
                    )
                    await self.add_response(message)
                    return

                # !autoupdate reddit_url liqui_url tourney_system tourney_options day_number
                global_settings.rleb_log_info("[DISCORD]: Starting autoupdate")
                reddit_url = tokens[1]
                liqui_url = tokens[2]
                tourney_system = tokens[3]
                options = tokens[4]
                day_number = tokens[5]

                # cleanup all user input
                liqui_url = liqui_url.split("#")[0] if "#" in liqui_url else liqui_url
                reddit_url = (
                    reddit_url.split("#")[0] if "#" in reddit_url else reddit_url
                )
                stringified_options = "-".join(sorted(options.lower().split(",")))
                if stringified_options == "none":
                    template = tourney_system
                else:
                    template = f"{tourney_system}-{stringified_options}"
                auto_update = Data.singleton().write_auto_update(
                    reddit_url,
                    liqui_url,
                    tourney_system,
                    stringified_options,
                    int(day_number),
                )
                global_settings.auto_updates[auto_update.auto_update_id] = auto_update
                await message.channel.send(
                    random.choice(global_settings.success_emojis)
                    + " auto update set.\nUse `!autoupdate list` to see all updates. `!autoupdate help` for more."
                )
                await self.add_response(message)
            except Exception as e:
                await message.channel.send(
                    "Couldn't understand that. Use `!autoupdate help`."
                )
                global_settings.rleb_log_info(f"Failed to parse autoupdate: {str(e)}")
                return

        elif discord_message.startswith("!makethread") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            global_settings.rleb_log_info("[DISCORD]: Starting makethread")
            await message.channel.send("Starting to make thread...")
            tokens = discord_message.split()
            try:
                url = tokens[1]
                tourney_system = tokens[2]
                options = tokens[3]
                date_number = tokens[4]
            except Exception:
                await message.channel.send(
                    "Couldn't understand that. Expected `!makethread [liquipedia-url] [tourney_system] [options] [date]`. Example command is `!makethread www.google.com groups BracketRd1,Streams 1`. Valid tourney_systems are basic, groups, swiss, and bracket. Valid options are bracketrd1, prizepool, streams and/or none. To use more than 1 option, list together separated by commas with no space such as: bracketrd1,prizepool,stream."
                )
                return

            # turn "groups Streams,BracketRd1" into "groups-bracketrd1-streams"
            stringified_options = "-".join(sorted(options.lower().split(",")))
            if stringified_options == "none":
                template = tourney_system
            else:
                template = f"{tourney_system}-{stringified_options}"
            markdown = diesel.get_make_thread_markdown_date(
                url, template, int(date_number)
            )
            await stdout.print_to_channel(
                message.channel, markdown, title="Thread Markdown"
            )
            await self.add_response(message)

        elif discord_message.startswith("!groups") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            global_settings.rleb_log_info("[DISCORD]: Starting group generation.")
            await message.channel.send("Starting group lookup...")
            tokens = discord_message.split()
            url = ""
            try:
                url = tokens[1]
            except Exception:
                await message.channel.send(
                    "Couldn't understand that. Expected '!groups liquipedia-url'."
                )
                return
            seconds = await handle_group_lookup(url, message.channel)
            await self.add_response(message)

        elif discord_message.startswith("!schedule") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            global_settings.rleb_log_info(
                "[DISCORD]: Starting schedule markdown generation."
            )
            await message.channel.send("Starting schedule creation...")
            tokens = discord_message.split()
            url = ""
            try:
                url = tokens[1]
                date_number = tokens[2]
            except Exception:
                await message.channel.send(
                    "Couldn't understand that. Expected `!schedule liquipedia-url [date of the month]`.\nExample: `!schedule https://liquipedia.net/rocketleague/Rocket_League_Championship_Series/2022-23/Fall/North_America/Cup 12` will get you the schedule for events on the 12th of the current month."
                )
                return
            await diesel.handle_schedule_lookup_date(
                url, int(date_number), message.channel
            )
            await self.add_response(message)

        elif discord_message.startswith("!prizepool") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            global_settings.rleb_log_info("[DISCORD]: Starting prizepool generation.")
            await message.channel.send("Starting prizepool lookup...")
            tokens = discord_message.split()
            url = ""
            try:
                url = tokens[1]
            except Exception:
                await message.channel.send(
                    "Couldn't understand that. Expected '!prizepool liquipedia-url'."
                )
                return
            seconds = await handle_prizepool_lookup(url, message.channel)
            await self.add_response(message)

        elif discord_message.startswith("!mvp") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            global_settings.rleb_log_info(
                f"[DISCORD]: Starting mvp generation: {discord_message}"
            )

            tokens = discord_message.split()

            if len(tokens) < 3:
                await message.channel.send(
                    "Couldn't understand that. Expected '!mvp [create OR results] [list of liqui urls OR form url]'."
                )
                return

            option = tokens[1]
            if option == "create":
                urls = tokens[2:]
                if len(urls) < 1:
                    await message.channel.send(
                        "Couldn't understand that. Expected '!mvp create liquipedia-url-1 liquipedia-url-2 liquipedia-url-3 etc...'."
                    )
                    return
                await message.channel.send("Creating MVP voting form...")
                await handle_mvp_form_creation(urls, message.channel)  # type: ignore
            elif option == "results":
                form_url = tokens[2]
                await message.channel.send("Generating MVP results...")
                await handle_mvp_results_lookup(form_url, message.channel)
            else:
                await message.channel.send(
                    "Couldn't understand that. Expected either 'create' or 'results' in the second parameter. Ex) '!mvp create liqui_url_1 liqui_url_2'."
                )
            await self.add_response(message)

        elif discord_message.startswith("!events") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            global_settings.rleb_log_info("[DISCORD]: Starting event lookup.")
            tokens = discord_message.split()
            formatter = "reddit"
            days = 7
            try:
                formatter = tokens[1]
                start = int(tokens[2])
                end = int(tokens[3])
            except Exception:
                await message.channel.send(
                    "Couldn't understand that. Expected '!events [formatter] [start] [end]'. Example is '!events reddit 1 8' to get 7 days of events starting 1 day in the future. Valid formatters are `reddit` and `sheets`."
                )
                return
            await handle_calendar_lookup(message.channel, formatter, start, end)
            await self.add_response(message)

        elif discord_message.startswith("!remindme") and is_staff(message.author):
            global_settings.rleb_log_info("[DISCORD]: Handling remindme.")
            tokens = discord_message.split()

            if len(tokens) < 1:
                await message.channel.send(
                    "Couldn't understand that. Expected `!remindme [timespan] [message].` ex) `!remindme 6h Do laundry`. Allowed time units are s, m, d, w"
                )
                return

            if tokens[1] == "delete":
                try:
                    remindme_id = int(tokens[2])
                except:
                    await message.channel.send(
                        "Couldn't understand that. Expected `!remindme delete [id].`\n**Example**: `!remindme delete 152`.\nUse `!remindme list` to see all valid ids."
                    )
                    return

                # Check if reminder exists in database
                remindmes = Data.singleton().read_remindmes()
                if not any(r.remindme_id == remindme_id for r in remindmes):
                    await message.channel.send(
                        f"Couldn't find reminder with id `{remindme_id}`. Use `!remindme list` to view all reminder ids."
                    )
                    return

                Data.singleton().delete_remindme(remindme_id)

                await message.channel.send("Deleted reminder.")
                await self.add_response(message)
                return

            if tokens[1] == "list":
                remindmes: list[Remindme] = Data.singleton().read_remindmes()
                output = ""
                for remindme in remindmes:
                    total_seconds_left = remindme.trigger_timestamp - time.time()
                    minutes_left = int((total_seconds_left % 3600) / 60)
                    hours_left = int(total_seconds_left / 3600)
                    msg = remindme.message[:15] + "..."
                    author = remindme.discord_username
                    # * `[ID 502]` In T-3 hours and 12 minutes: `"test..."` for `voice123`
                    output += f"* `[ID {remindme.remindme_id}]` in {hours_left} hour(s) {minutes_left} minute(s): `{msg}` for {author}.\n"
                if len(remindmes) == 0:
                    output = "No reminders are set. Use `!remindme [time] [msg]` to schedule one. Example times: `5h`, `80s`, `1d`, `2w`, `8m`.\n"
                output += "Use `!remindme delete [id]` to cancel a reminder."
                await message.channel.send(output)
                await self.add_response(message)
                return

            if message.author.discriminator == "0":
                user = message.author.name.lower()
            else:
                user = message.author.name.lower() + "#" + message.author.discriminator
            extra = None
            try:
                target_time = tokens[1]
                reminder_message = " ".join(tokens[2:])
            except Exception:
                await message.channel.send(
                    "Couldn't understand that. Expected `!remindme [timespan] [message].` ex) `!remindme 6h Do laundry`. Allowed time units are s, m, h, d, w."
                )
                return

            seconds_multiplier = {
                "s": 1,
                "m": 60,
                "h": 60 * 60,
                "d": 60 * 60 * 24,
                "w": 60 * 60 * 24 * 7,
            }
            last_char = target_time[-1]
            units = target_time[:-1]

            # Ensure that units are numeric & last char is a valid time unit.
            should_exit_early = False
            if last_char not in seconds_multiplier:
                should_exit_early = True

            try:
                units = float(units)
            except:
                should_exit_early = True

            if should_exit_early:
                await message.channel.send(
                    "Couldn't understand that. Expected `!remindme [timespan] [message].` ex) `!remindme 6h Do laundry`. Allowed time units are s, m, h, d, w."
                )
                return

            total_time = seconds_multiplier[last_char] * units
            remindme: Remindme = Data.singleton().write_remindme(
                user, reminder_message, int(total_time), message.channel.id
            )
            # Remindme will be picked up by the check_remindmes() polling loop
            await message.channel.send(
                random.choice(global_settings.success_emojis)
                + " reminder set.\nUse `!remindme list` to see all reminders."
            )
            await self.add_response(message)

        elif discord_message.startswith("!tasks") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            global_settings.rleb_log_info("[DISCORD]: Starting task lookup.")
            tokens = discord_message.split()

            # User = the person requesting the command, unless explicitly stated.
            username = message.author.name.lower()
            discrim = message.author.discriminator
            user = message.author.name.lower() + "#" + message.author.discriminator
            if discrim == "0":
                user = message.author.name.lower()
            extra = ""
            try:
                user = tokens[1]
                extra = tokens[2]
            except Exception:
                pass
            await message.channel.send("Checking tasks...")
            await handle_task_lookup(message.channel, self, user, extra)
            if user == "broadcast" or user == "send":
                await message.channel.send(
                    random.choice(global_settings.success_emojis) + " tasks are sent."
                )
            await self.add_response(message)

        elif discord_message.startswith("!meme"):
            await self.send_meme(message.channel)
            await self.add_response(message)

        elif discord_message.startswith("!setmeme") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            tokens = discord_message.split()
            subreddit = ""
            try:
                subreddit = tokens[1]
            except Exception:
                pass

            original_meme_subreddit = self.meme_subreddit
            self.meme_subreddit = subreddit
            result = await self.send_meme(message.channel)
            if result == False:
                await message.channel("Failed to update mem channel!")
                self.meme_subreddit = original_meme_subreddit

            await self.add_response(message)

        elif discord_message.startswith("!echo"):
            message_without_command = "> {0}".format(
                discord_message.replace("!echo", "")
            )
            global_settings.rleb_log_info(
                f"[DISCORD] Echoing {message_without_command}"
            )
            await message.channel.send(message_without_command)
            await self.add_response(message)

        # !chat command handler
        if discord_message.startswith("!chat"):
            tokens = discord_message.split()
            if len(tokens) == 1 or (len(tokens) == 2 and tokens[1].lower() == "help"):
                await message.channel.send(
                    "Usage: !chat [message]\nExample: !chat What is the capital of France?"
                )
                return
            user_message = " ".join(tokens[1:])
            if not user_message:
                await message.channel.send("Please provide a message to send to RLEB.")
                return
            try:
                import chat

                response = await chat.ask_claude(user_message)
                await message.channel.send(response)
            except Exception as e:
                await message.channel.send(f"Error: {e}")
            return


def start() -> None:
    """Spawns the various discord asyncio threads."""
    client = RLEsportsBot()

    # Start listening to discord commands.
    # Background tasks are created in setup_hook.
    client.run(global_settings.TOKEN)
