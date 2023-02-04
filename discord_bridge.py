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
import stdout
from data_bridge import Data, Remindme
from global_settings import sub, user_names_to_ids
from liqui.team_lookup import handle_team_lookup
from liqui.group_lookup import handle_group_lookup
from census import handle_flair_census
from calendar_event import handle_calendar_lookup
from tasks import handle_task_lookup
from liqui.swiss_lookup import handle_swiss_lookup
from liqui.bracket_lookup import handle_bracket_lookup
from liqui.mvp_lookup import (
    handle_mvp_form_creation,
    handle_mvp_results_lookup,
)
from liqui.diesel import (
    handle_stream_lookup,
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
    def __init__(self):
        """Initialize a new instance of RLEsportsBot."""
        super().__init__(intents=discord.Intents.all())

        # The datetime the bot started.
        self.start_datetime = datetime.now()

        # Stores map of username->datetime of users who have recently pinged.
        self.responses = {}

        # The subreddit of memes or images to flood into #bot-commands.
        self.meme_subreddit = "maps"

    async def on_ready(self):
        """Indicate bot has joined the discord."""
        global_settings.rleb_log_info("DISCORD: Logged on as {0}".format(self.user))
        self.new_post_channel = self.get_channel(global_settings.NEW_POSTS_CHANNEL_ID)
        self.modmail_channel = self.get_channel(global_settings.MODMAIL_CHANNEL_ID)
        self.bot_command_channel = self.get_channel(
            global_settings.BOT_COMMANDS_CHANNEL_ID
        )
        self.schedule_chat_channel = self.get_channel(
            global_settings.SCHEDULE_CHAT_CHANNEL_ID
        )
        self.roster_news_channel = self.get_channel(
            global_settings.ROSTER_NEWS_CHANNEL_ID
        )
        self.modlog_channel = self.get_channel(global_settings.MODLOG_CHANNEL_ID)
        self.thread_creation_channel = self.get_channel(
            global_settings.THREAD_CREATION_CHANNEL_ID
        )

        # Create a mapping of discord usernames to discord ids for future use.
        for m in self.new_post_channel.members:
            global_settings.user_names_to_ids[
                m.name.lower() + "#" + m.discriminator
            ] = m.id

        # If testing, ping the discord channel.
        if global_settings.RUNNING_MODE != "production":
            await self.bot_command_channel.send(
                "Bot is online, running in {0} under {1} mode.".format(
                    global_settings.RUNNING_ENVIRONMENT, global_settings.RUNNING_MODE
                )
            )
        else:
            await self.send_meme(self.bot_command_channel)

    async def send_meme(self, channel):
        meme_sub = global_settings.r.subreddit(self.meme_subreddit)
        if meme_sub.over18:
            return

        randomizer = random.randint(1, 10)
        count = 0

        tries = 0
        for meme in meme_sub.top("day"):
            if tries > 3:
                await channel.send("Couldn't find a suitable meme :(")
                break
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
            await channel.send("{0}".format(link))
            break

    async def check_new_submissions(self):
        """Check submissions queue to post in 'new posts' discord channel."""
        while True:
            try:
                while not global_settings.queues["submissions"].empty():
                    submission = global_settings.queues["submissions"].get()
                    global_settings.rleb_log_info(
                        "DISCORD: Received submission id {0}: {1}".format(
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
                        await self.roster_news_channel.send(embed=embed)

                    await self.new_post_channel.send(embed=embed)
                global_settings.asyncio_threads_heartbeats[
                    "submissions"
                ] = datetime.now()
                if not global_settings.discord_check_new_submission_enabled:
                    break
            except Exception as e:
                if global_settings.thread_crashes["asyncio"] > 5:
                    await self.bot_command_channel.send(
                        "ALERT: Asyncio thread has crashed more than 5 times."
                    )
                    developer = discord.utils.get(
                        self.get_all_members(),
                        name=global_settings.developer_name,
                        discriminator=global_settings.developer_discriminator,
                    )
                    await self.bot_command_channel.send(
                        "^ " + developer.mention + " fyi"
                    )
                    break
                global_settings.rleb_log_error(
                    "Discord: Submissions asyncio thread failed - {0}".format(e)
                )
                global_settings.rleb_log_error(traceback.format_exc())
                global_settings.thread_crashes["asyncio"] += 1
                global_settings.last_datetime_crashed["asyncio"] = datetime.now()
            await asyncio.sleep(global_settings.discord_async_interval_seconds)

    async def check_new_thread_creation(self):
        """Checks thread_creation queue to send warnings into #thread-creation."""
        while True:
            try:
                while not global_settings.queues["thread_creation"].empty():
                    message = global_settings.queues["thread_creation"].get()
                    global_settings.rleb_log_info(
                        "DISCORD: Received thread creation alert '{0}'".format(message)
                    )
                    thread_creation_message = await self.thread_creation_channel.send(
                        message
                    )
                    await thread_creation_message.edit(suppress=True)

                global_settings.asyncio_threads_heartbeats[
                    "thread_creation"
                ] = datetime.now()
                if not global_settings.discord_check_new_thread_creation_enabled:
                    break
            except Exception as e:
                if global_settings.thread_crashes["asyncio"] > 5:
                    await self.bot_command_channel.send(
                        "ALERT: Asyncio thread has crashed more than 5 times."
                    )
                    developer = discord.utils.get(
                        self.get_all_members(),
                        name=global_settings.developer_name,
                        discriminator=global_settings.developer_discriminator,
                    )
                    await self.bot_command_channel.send(
                        "^ " + developer.mention + " fyi"
                    )
                    break
                global_settings.rleb_log_error(
                    "DISCORD: Alert asyncio thread failed - {0}".format(e)
                )
                global_settings.rleb_log_error(traceback.format_exc())
                global_settings.thread_crashes["asyncio"] += 1
                global_settings.last_datetime_crashed["asyncio"] = datetime.now()
            await asyncio.sleep(global_settings.discord_async_interval_seconds)

    async def check_new_direct_messages(self):
        """Checks direct_messages queue to send DMs to discord users."""
        while True:
            try:
                while not global_settings.queues["direct_messages"].empty():
                    author_message_tuple = global_settings.queues[
                        "direct_messages"
                    ].get()
                    global_settings.rleb_log_info(
                        "DISCORD: Received DM '{0}'".format(author_message_tuple)
                    )
                    author = author_message_tuple[0]
                    message = author_message_tuple[1]
                    user_mapping = global_settings.user_names_to_ids
                    if user_mapping == None or len(user_mapping) == 0:
                        continue
                    discord_user = self.get_user(user_mapping[author])
                    if discord_user == None:
                        continue
                    message = "\n".join(
                        [
                            random.choice(global_settings.greetings),
                            "\n----------\n",
                            message,
                            "\n----------\n",
                        ]
                    )
                    if global_settings.RUNNING_MODE == "local":
                        await self.bot_command_channel.send(f"**DM For {author}**")
                        testing_msg = await self.bot_command_channel.send(message)
                        await testing_msg.edit(suppress=True)
                    else:
                        DM = await discord_user.send(message)
                        await DM.edit(suppress=True)

                global_settings.asyncio_threads_heartbeats[
                    "direct_messages"
                ] = datetime.now()
                if not global_settings.discord_check_direct_messages_enabled:
                    break
            except Exception as e:
                if global_settings.thread_crashes["asyncio"] > 5:
                    await self.bot_command_channel.send(
                        "ALERT: Asyncio thread has crashed more than 5 times."
                    )
                    developer = discord.utils.get(
                        self.get_all_members(),
                        name=global_settings.developer_name,
                        discriminator=global_settings.developer_discriminator,
                    )
                    await self.bot_command_channel.send(
                        "^ " + developer.mention + " fyi"
                    )
                    break
                global_settings.rleb_log_error(
                    "DISCORD: Alert asyncio thread failed - {0}".format(e)
                )
                global_settings.rleb_log_error(traceback.format_exc())
                global_settings.thread_crashes["asyncio"] += 1
                global_settings.last_datetime_crashed["asyncio"] = datetime.now()
            await asyncio.sleep(global_settings.discord_async_interval_seconds)

    async def check_new_alerts(self):
        """Check alerts queue to post in 'bot commands' discord channel."""
        while True:
            try:
                while not global_settings.queues["alerts"].empty():
                    alert = global_settings.queues["alerts"].get()
                    message = alert[0]
                    channel_id = alert[1]

                    global_settings.rleb_log_info(
                        "DISCORD: Received alert '{0}'".format(alert)
                    )

                    # Send to specific channel. If any issue arrises, send to bot commands instead.
                    try:
                        channel = self.get_channel(channel_id)
                        await channel.send(message)
                    except:
                        channel = self.bot_command_channel
                        await channel.send(message)
                global_settings.asyncio_threads_heartbeats["alerts"] = datetime.now()
                if not global_settings.discord_check_new_alerts_enabled:
                    break
            except Exception as e:
                if global_settings.thread_crashes["asyncio"] > 5:
                    await self.bot_command_channel.send(
                        "ALERT: Asyncio thread has crashed more than 5 times."
                    )
                    developer = discord.utils.get(
                        self.get_all_members(),
                        name=global_settings.developer_name,
                        discriminator=global_settings.developer_discriminator,
                    )
                    await self.bot_command_channel.send(
                        "^ " + developer.mention + " fyi"
                    )
                    break
                global_settings.rleb_log_error(
                    "DISCORD: Alert asyncio thread failed - {0}".format(e)
                )
                global_settings.rleb_log_error(traceback.format_exc())
                global_settings.thread_crashes["asyncio"] += 1
                global_settings.last_datetime_crashed["asyncio"] = datetime.now()
            await asyncio.sleep(global_settings.discord_async_interval_seconds)

    async def check_new_modfeed(self):
        """Check modmail/modlog queue to post in discord."""
        while True:
            try:
                # Mod Log
                while not global_settings.queues["modlog"].empty():
                    await asyncio.sleep(1)
                    item = global_settings.queues["modlog"].get()

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
                    except discord.errors.HTTPException as e:
                        # Message has invalid formatting. Just send basic msg.
                        await self.modlog_channel.send(item.description)

                # Mod Mail
                while not global_settings.queues["modmail"].empty():
                    item = global_settings.queues["modmail"].get()
                    global_settings.rleb_log_info(
                        "DISCORD: Received modmail id {0}: {1}".format(
                            item.id, item.body
                        )
                    )
                    embed = None

                    # On-going conversation.
                    if item.parent_id:
                        embed = discord.Embed(
                            title="Commented on '{0}'".format(item.subject),
                            url="https://mod.reddit.com/mail/all",
                            color=random.choice(global_settings.colors),
                        )
                        embed.set_author(name=item.author.name)
                    # New modmail
                    else:
                        embed = discord.Embed(
                            title="Created: '{0}'".format(item.subject),
                            url="https://mod.reddit.com/mail/all",
                            color=random.choice(global_settings.colors),
                        )
                        embed.set_author(name=item.author.name)

                    embed.description = f"{item.body}\n--------------------------------------------------------"

                    # Send everything.
                    try:
                        await self.modmail_channel.send(embed=embed)
                    except discord.errors.HTTPException as e:
                        # Message has invalid formatting. Just send basic msg.
                        await self.modmail_channel.send(
                            f"**{item.subject}** by {item.author.name}"
                        )

                global_settings.asyncio_threads_heartbeats["modmail"] = datetime.now()
                if not global_settings.discord_check_new_modmail_enabled:
                    break
            except Exception as e:
                if global_settings.thread_crashes["asyncio"] > 5:
                    await self.bot_command_channel.send(
                        "ALERT: Asyncio thread has crashed more than 5 times."
                    )
                    developer = discord.utils.get(
                        self.get_all_members(),
                        name=global_settings.developer_name,
                        discriminator=global_settings.developer_discriminator,
                    )
                    await self.bot_command_channel.send(
                        "^ " + developer.mention + " fyi"
                    )
                    break
                global_settings.rleb_log_error(
                    "DISCORD: Modfeed asyncio thread failed - {0}".format(e)
                )
                global_settings.rleb_log_error(traceback.format_exc())
                global_settings.thread_crashes["asyncio"] += 1
                global_settings.last_datetime_crashed["asyncio"] = datetime.now()
            await asyncio.sleep(global_settings.discord_async_interval_seconds)

    # Record that a user was responded to. Useful for responding "thanks".
    async def add_response(self, message):
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
        # Don't response to messages from yourself, lol.
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
                "DISCORD: New voting message: {0}".format(discord_message)
            )
            await message.add_reaction("👍")
            await message.add_reaction("👎")
            await message.add_reaction("🤷")
            return

        if str(message.channel) == "ban-review":
            global_settings.rleb_log_info(
                "DISCORD: New ban-review message: {0}".format(discord_message)
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
                del self.responses[str(message.author)]

        elif discord_message.startswith("!census") and is_staff(message.author):

            if not global_settings.is_discord_mod(message.author):
                return

            global_settings.rleb_log_info("DISCORD: Starting flair census.")
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
            await handle_flair_census(sub, amount, message.channel, divider)
            await self.add_response(message)

        elif discord_message.startswith("!migrate") and is_staff(message.author):

            if not global_settings.is_discord_mod(message.author):
                return

            # increase asyncio timeout so it doesn't seem like a crash
            global_settings.asyncio_timeout = 60 * 15

            global_settings.rleb_log_info("DISCORD: Starting migration")
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
            count = 0
            await message.channel.send("Checking flairs...")
            for flair in sub.flair(limit=None):
                if flair["flair_text"] != None and from_flair in flair["flair_text"]:
                    count += 1
            if from_flair != None and to_flair != None:
                await message.channel.send(
                    "Type '!confirm migrate' to migrate '{0}' -> '{1}' in the next 2 minutes. This will affect {2} users.".format(
                        from_flair, to_flair, count
                    )
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

            # increase asyncio timeout so it doesn't seem like a crash
            global_settings.asyncio_timeout = 60 * 15

            if (datetime.now() - self.migrate_request_time).total_seconds() > 120:
                await message.channel.send(
                    "Migration timed out. You must confirm within 2 minutes to migrate flairs."
                )
                global_settings.asyncio_timeout = 60 * 5
                return
            await message.channel.send(
                "Starting migration {0} -> {1}.".format(self.from_flair, self.to_flair)
            )
            for flair in sub.flair(limit=None):
                if (
                    flair["flair_text"] != None
                    and self.from_flair in flair["flair_text"]
                ):
                    user = flair["user"]
                    new_flair = flair["flair_text"].replace(
                        self.from_flair, self.to_flair
                    )
                    global_settings.rleb_log_info(
                        "DISCORD: Setting {0} to {1} (was {2})".format(
                            user.name, new_flair, flair["flair_text"]
                        )
                    )
                    sub.flair.set(user, text=new_flair, css_class="")
            await message.channel.send("Flair migration finished.")
            await self.add_response(message)

            # reset asyncio timeout
            global_settings.asyncio_timeout = 60 * 5

        elif discord_message.startswith("!dualflairs") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

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
            await message.channel.send(all_flairs)
            await self.add_response(message)

        elif discord_message.startswith("!triflairs remove") and is_staff(
            message.author
        ):

            if not global_settings.is_discord_mod(message.author):
                return

            tokens = discord_message.split()
            flair = None
            try:
                flair = tokens[2]
            except IndexError:
                await message.channel.send(
                    "Couldn't understand that. Expected '!triflairs remove :flair:'."
                )
                return
            await message.channel.send(
                "Type '!confirm remove' to remove the {0} flair.".format(flair)
            )
            self.flair_to_remove = flair
            self.remove_flair_time = datetime.now()
            await self.add_response(message)

        elif discord_message == "!confirm remove" and is_staff(message.author):

            if not global_settings.is_discord_mod(message.author):
                return

            if (datetime.now() - self.remove_flair_time).total_seconds() > 120:
                await message.channel.send(
                    "Removal timed out. You must confirm within 2 minutes to remove flairs."
                )
                return
            flairs = Data.singleton().read_triflairs()
            flair_list = list(map(lambda x: x[0], flairs))
            if not (self.flair_to_remove in flair_list):
                await message.channel.send(
                    "Couldn't find {0}! Type '!triflairs list' to view all flairs.".format(
                        self.flair_to_remove
                    )
                )
                return
            else:
                Data.singleton().yeet_triflair(self.flair_to_remove)
                await message.channel.send("Removed {0}.".format(self.flair_to_remove))
                await self.add_response(message)

        elif discord_message.startswith("!triflairs add") and is_staff(message.author):

            if not global_settings.is_discord_mod(message.author):
                return

            tokens = discord_message.split()

            flair = None
            try:
                flair = tokens[2]
            except IndexError:
                await message.channel.send(
                    "Couldn't understand that. Expected '!triflairs add :flair:'."
                )
                return
            if not flair.startswith(":"):
                await message.channel.send(
                    "Couldn't understand that. Make sure you are passing a :flair_code: and not an emoji 😭. You may have to disable Discord Nitro or auto emoji."
                )
                return
            self.flair_to_add = flair
            self.add_flair_time = datetime.now()
            await message.channel.send(
                "Type '!confirm add' to add the {0} flair.".format(flair)
            )
            await self.add_response(message)

        elif discord_message == "!confirm add" and is_staff(message.author):

            if not global_settings.is_discord_mod(message.author):
                return

            if (datetime.now() - self.add_flair_time).total_seconds() > 120:
                await message.channel.send(
                    "Addition timed out. You must confirm within 2 minutes to add flairs."
                )
                return
            flairs = Data.singleton().read_triflairs()
            flair_list = list(map(lambda x: x[0], flairs))
            if self.flair_to_add in flair_list:
                await message.channel.send(
                    "{0} is already in the flair list! Type '!triflairs list' to view all flairs.".format(
                        self.flair_to_add
                    )
                )
                return
            else:
                Data.singleton().add_triflair(self.flair_to_add)
                await message.channel.send("Added {0}.".format(self.flair_to_add))
                await self.add_response(message)

        elif discord_message.startswith("!flush") and is_staff(message.author):

            if not global_settings.is_discord_mod(message.author):
                return

            global_settings._flush_memory_log()
            await message.channel.send(":toilet:")

        elif discord_message.startswith("!weekly") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            await message.channel.send(
                "**Found the following scheduled posts on reddit:**"
            )
            scheduled_posts = health_check.get_scheduled_posts()
            for s in scheduled_posts:
                await message.channel.send(s)

            await message.channel.send(
                "**Found the following tasks on the weekly sheet:**"
            )
            weekly_tasks = health_check.get_weekly_tasks()
            for t in weekly_tasks:
                await message.channel.send(t)

            await self.add_response(message)

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
                db_logs = Data.singleton().read_logs()
                db_logs_as_list = list(map(lambda x: x[0], db_logs))
                logs = db_logs_as_list[(-1 * count) :]
            else:
                await message.channel.send(
                    "The first argument should be either 'memory' or 'db'."
                )
                return
            try:
                if logs == None or len(logs) == 0:
                    await message.channel.send("No logs to show.")
                    return
                await stdout.print_to_channel(
                    message.channel, "\n".join(logs), title="logs"
                )
            except discord.errors.HTTPException:
                global_settings.rleb_log_error(traceback.format_exc())
                await message.channel.send(
                    "Couldn't send logs over! (tip: there's a limit to the number of characters that can be sent. Make sure you aren't requesting too many logs. Use '!logs [db/memory] [n]', where n is a small number to avoid the character limit.)"
                )
            await self.add_response(message)
        elif discord_message.startswith("!shutdown") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            await message.channel.send("Later nerds.")
            global_settings.rleb_log_info("Shutting down.", should_flush=True)

            # Absolutely shrek the running process.
            if global_settings.RUNNING_ENVIRONMENT == "windows":
                os.kill(os.getpid(), signal.SIGTERM)
            else:
                os.popen("pkill -9 -f diesel")
                os.popen("pkill -9 -f rleb_core.py")

        elif discord_message.startswith("!deploy") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            await message.channel.send("brb")
            global_settings.rleb_log_info("Deploying.", should_flush=True)

            if global_settings.RUNNING_ENVIRONMENT == "windows":
                os.kill(os.getpid(), signal.SIGTERM)  # just shutdown on win
            else:
                current_path = str(pathlib.Path(__file__).parent.resolve())
                os.popen(f"{current_path}/deploy.sh")

        elif discord_message.startswith("!restart") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            await message.channel.send("See ya in a few minutes <3")
            global_settings.rleb_log_info("Restarting.", should_flush=True)

            if global_settings.RUNNING_ENVIRONMENT == "windows":
                os.kill(os.getpid(), signal.SIGTERM)  # just shutdown on win
            else:
                os.popen("sudo reboot now")

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
            after = time.time() * 1000
            elapsed_time = round(after - before)
            await message.channel.send(
                f"**Diesel Status:** {health} ({elapsed_time}ms response time)"
            )

            # Hardware specs.
            try:
                cpu_temp = round(
                    int(
                        os.popen("cat /sys/class/thermal/thermal_zone*/temp")
                        .read()
                        .strip()
                    )
                    / 1000,
                    1,
                )
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

            thread_heartbeat = [
                f"{k}: {round((datetime.now()-v).total_seconds(),1)}s ago"
                for k, v in global_settings.threads_heartbeats.items()
            ]
            await message.channel.send(f"**Thread heartbeats:** {thread_heartbeat}")

            thread_heartbeat = [
                f"{k}: {round((datetime.now()-v).total_seconds(),1)}s ago"
                for k, v in global_settings.asyncio_threads_heartbeats.items()
            ]
            await message.channel.send(f"**Asyncio heartbeats:** {thread_heartbeat}")

            await self.add_response(message)

        elif discord_message == "!reset crashes" and is_staff(message.author):

            if not global_settings.is_discord_mod(message.author):
                return

            global_settings.thread_crashes["thread"] = 0
            global_settings.thread_crashes["asyncio"] = 0
            await message.channel.send("Thread crash count was reset")
            global_settings.rleb_log_info("DISCORD: Thread count was reset.")
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

            global_settings.rleb_log_info("DISCORD: Starting team generation.")
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

        elif discord_message.startswith("!swiss") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            global_settings.rleb_log_info("DISCORD: Starting swiss bracket generation.")
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

            global_settings.rleb_log_info("DISCORD: Starting stream generation.")
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

        elif discord_message.startswith("!coverage") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            global_settings.rleb_log_info("DISCORD: Starting coverage generation.")
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

            global_settings.rleb_log_info("DISCORD: Starting elim bracket generation.")
            await message.channel.send("Starting elimination bracket lookup...")
            tokens = discord_message.split()
            try:
                url = tokens[1]
                day_number = tokens[2]
            except Exception:
                await message.channel.send(
                    "Couldn't understand that. Expected '!bracket liquipedia-url day-number'."
                )
                return
            await handle_bracket_lookup(url, message.channel, day_number)
            await self.add_response(message)

        elif discord_message.startswith("!groups") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            global_settings.rleb_log_info("DISCORD: Starting group generation.")
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
                "DISCORD: Starting schedule markdown generation."
            )
            await message.channel.send("Starting schedule creation...")
            tokens = discord_message.split()
            url = ""
            try:
                url = tokens[1]
                day_number = tokens[2]
            except Exception:
                await message.channel.send(
                    "Couldn't understand that. Expected `!schedule liquipedia-url [day #]`.\nExample: `!schedule https://liquipedia.net/rocketleague/Rocket_League_Championship_Series/2022-23/Fall/North_America/Cup 2` will get you the schedule for day 2 of the NA cup."
                )
                return
            await handle_schedule_lookup(url, day_number, message.channel)
            await self.add_response(message)

        elif discord_message.startswith("!prizepool") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            await message.channel.send("Sorry :(. !prizepool is currently disabled due to a change in liquipedia HTML. Should be back to normal in a couple weeks.")
            return

            global_settings.rleb_log_info("DISCORD: Starting prizepool generation.")
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
                f"DISCORD: Starting mvp generation: {discord_message}"
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
                await handle_mvp_form_creation(urls, message.channel)
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

            global_settings.rleb_log_info("DISCORD: Starting event lookup.")
            tokens = discord_message.split()
            formatter = "reddit"
            days = 7
            try:
                formatter = tokens[1]
                days = int(tokens[2])
            except Exception:
                await message.channel.send(
                    "Couldn't understand that. Expected '!events [formatter] [# days]'. Example is '!events reddit 7' to get the next 7 days of events. Valid formatters are `reddit` and `sheets`."
                )
                return
            await handle_calendar_lookup(message.channel, formatter, days)
            await self.add_response(message)

        elif discord_message.startswith("!remindme") and is_staff(message.author):
            global_settings.rleb_log_info("DISCORD: Handling remindme.")
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

                if remindme_id not in global_settings.remindme_timers:
                    await message.channel.send(
                        f"Couldn't find reminder with id `{remindme_id}`. Use `!remindme list` to view all reminder ids."
                    )
                    return

                global_settings.remindme_timers[remindme_id].cancel()
                del global_settings.remindme_timers[remindme_id]
                Data.singleton().delete_remindme(remindme_id)

                await message.channel.send("Deleted reminder.")
                await self.add_response(message)
                return

            if tokens[1] == "list":
                remindmes: list[Remindme] = Data.singleton().read_remindmes()
                output = ""
                for remindme in remindmes:
                    seconds_left = remindme.trigger_timestamp - time.time()
                    minutes_left = round(seconds_left / 60, 1)
                    msg = remindme.message
                    author = remindme.discord_username
                    output += f"[id {remindme.remindme_id}] - `{msg}` for {author} in {minutes_left} minutes\n"
                if len(remindmes) == 0:
                    output = "No reminders are set. Use `!remindme [time] [msg]` to schedule one. Example times: `5h`, `80s`, `1d`, `2w`, `8m`.\n"
                output += "Use `!remindme delete [id]` to cancel a reminder."
                await message.channel.send(output)
                await self.add_response(message)
                return

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
                user, reminder_message, total_time, message.channel.id
            )
            global_settings.schedule_remindme(remindme)
            await message.channel.send(
                random.choice(global_settings.success_emojis)
                + " reminder set.\nUse `!remindme list` to see all reminders."
            )
            await self.add_response(message)

        elif discord_message.startswith("!tasks") and is_staff(message.author):
            if not global_settings.is_discord_mod(message.author):
                return

            global_settings.rleb_log_info("DISCORD: Starting task lookup.")
            tokens = discord_message.split()

            # User = the person requesting the command, unless explicitly stated.
            user = message.author.name.lower() + "#" + message.author.discriminator
            extra = None
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
            try:
                global_settings.r.subreddit(self.meme_subreddit)
                self.meme_subreddit = subreddit
                await self.send_meme(message.channel)
            except:
                await message.channel("That isn't a real place!")
                self.meme_subreddit = original_meme_subreddit

            await self.add_response(message)

        elif discord_message.startswith("!echo"):
            message_without_command = "> {0}".format(
                discord_message.replace("!echo", "")
            )
            await message.channel.send(message_without_command)
            await self.add_response(message)


def start() -> None:
    """Spawns the various discord asyncio threads."""
    client = RLEsportsBot()

    # Create asyncronoush discord tasks.
    client.loop.create_task(client.check_new_submissions())
    client.loop.create_task(client.check_new_modfeed())
    client.loop.create_task(client.check_new_alerts())
    client.loop.create_task(client.check_new_direct_messages())
    client.loop.create_task(client.check_new_thread_creation())

    # Start listening to discord commands.
    client.run(global_settings.TOKEN)
