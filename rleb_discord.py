import discord
import random
from datetime import datetime
import time
import asyncio
from threading import Lock, Thread
import traceback
import math

import rleb_health
import rleb_settings
import rleb_stdout
from rleb_data import Data
from rleb_settings import sub
from rleb_liqui.rleb_team_lookup import handle_team_lookup
from rleb_liqui.rleb_group_lookup import handle_group_lookup
from rleb_census import handle_flair_census
from rleb_calendar import handle_calendar_lookup
from rleb_tasks import handle_task_lookup, user_names_to_ids
from rleb_liqui.rleb_swiss import handle_swiss_lookup
from rleb_liqui.rleb_bracket_lookup import handle_bracket_lookup
from rleb_liqui.rleb_mvp_lookup import handle_mvp_lookup
from rleb_liqui.rleb_prizepool_lookup import handle_prizepool_lookup

responses_lock = Lock()


def is_staff(user: discord.Member) -> bool:
    """Return true if discord user has the Subreddit Moderators role."""
    return "Subreddit Moderators" in map(lambda x: x.name, user.roles)


class RLEsportsBot(discord.Client):
    def __init__(self, threads):
        """Initialize a new instance of RLEsportsBot.

        Args:
            threads (List of Thread): List of threads used for monitoring both health.
        """
        super().__init__(intents=discord.Intents.all())

        # List of all threads running RLEB.
        self.threads = threads

        # The datetime the bot started.
        self.start_datetime = datetime.now()

        # Stores map of username->datetime of users who have recently pinged.
        self.responses = {}

        # The subreddit of memes or images to flood into #bot-commands.
        self.meme_subreddit = "EarthPorn"

    async def on_ready(self):
        """Indicate bot has joined the discord."""
        rleb_settings.rleb_log_info(
            "DISCORD: Logged on as {0}".format(self.user))
        self.new_post_channel = self.get_channel(
            rleb_settings.NEW_POSTS_CHANNEL_ID)
        self.trello_channel = self.get_channel(rleb_settings.TRELLO_CHANNEL_ID)
        self.modmail_channel = self.get_channel(
            rleb_settings.MODMAIL_CHANNEL_ID)
        self.bot_command_channel = self.get_channel(
            rleb_settings.BOT_COMMANDS_CHANNEL_ID
        )
        self.schedule_chat_channel = self.get_channel(
            rleb_settings.SCHEDULE_CHAT_CHANNEL_ID
        )
        self.roster_news_channel = self.get_channel(
            rleb_settings.ROSTER_NEWS_CHANNEL_ID
        )
        self.modlog_channel = self.get_channel(rleb_settings.MODLOG_CHANNEL_ID)

        # If testing, ping the discord channel.
        if rleb_settings.RUNNING_MODE != "production":
            await self.bot_command_channel.send(
                "Bot is online, running in {0} under {1} mode.".format(
                    rleb_settings.RUNNING_ENVIRONMENT, rleb_settings.RUNNING_MODE
                )
            )
        else:
            await self.send_meme(self.bot_command_channel)

    async def send_meme(self, channel):
        meme_sub = rleb_settings.r.subreddit(self.meme_subreddit)
        if meme_sub.over18:
            return
        randomizer = random.randint(1, 20)
        count = 0
        for meme in meme_sub.top("day"):
            if meme.over_18:
                continue
            if count <= randomizer:
                count += 1
                continue
            link = meme.url
            await channel.send("{0}".format(link))
            break

    async def check_new_submissions(self):
        """Check submissions queue to post in 'new posts' discord channel."""
        while True:
            try:
                while not rleb_settings.queues["submissions"].empty():
                    submission = rleb_settings.queues["submissions"].get()
                    rleb_settings.rleb_log_info(
                        "DISCORD: Received submission id {0}: {1}".format(
                            submission, submission.title
                        )
                    )
                    embed = discord.Embed(
                        title=submission.title,
                        url="https://www.reddit.com{0}".format(
                            submission.permalink),
                        color=random.choice(rleb_settings.colors),
                    )
                    embed.set_author(name=submission.author.name)

                    if "roster news" in submission.link_flair_text.strip().lower():
                        await self.roster_news_channel.send(embed=embed)

                    await self.new_post_channel.send(embed=embed)
                rleb_settings.asyncio_threads["submissions"] = datetime.now()
                if not rleb_settings.discord_check_new_submission_enabled:
                    break
            except Exception as e:
                if rleb_settings.thread_crashes["asyncio"] > 5:
                    await self.bot_command_channel.send(
                        "ALERT: Asyncio thread has crashed more than 5 times."
                    )
                    developer = discord.utils.get(
                        self.get_all_members(),
                        name=rleb_settings.developer_name,
                        discriminator=rleb_settings.developer_discriminator,
                    )
                    await self.bot_command_channel.send(
                        "^ " + developer.mention + " fyi"
                    )
                    break
                rleb_settings.rleb_log_error(
                    "Discord: Submissions asyncio thread failed - {0}".format(
                        e)
                )
                rleb_settings.rleb_log_error(traceback.format_exc())
                rleb_settings.thread_crashes["asyncio"] += 1
                rleb_settings.last_datetime_crashed["asyncio"] = datetime.now()
            await asyncio.sleep(rleb_settings.discord_async_interval_seconds)

    async def check_new_schedule_chat(self):
        """Checks schedule_chat queue to send warnings into #schedule_chat."""
        while True:
            try:
                while not rleb_settings.queues["schedule_chat"].empty():
                    message = rleb_settings.queues["schedule_chat"].get()
                    rleb_settings.rleb_log_info(
                        "DISCORD: Received schedule chat '{0}'".format(message)
                    )
                    schedule_chat_message = await self.schedule_chat_channel.send(
                        message
                    )
                    await schedule_chat_message.edit(suppress=True)

                rleb_settings.asyncio_threads["schedule_chat"] = datetime.now()
                if not rleb_settings.discord_check_new_schedule_chat_enabled:
                    break
            except Exception as e:
                if rleb_settings.thread_crashes["asyncio"] > 5:
                    await self.bot_command_channel.send(
                        "ALERT: Asyncio thread has crashed more than 5 times."
                    )
                    developer = discord.utils.get(
                        self.get_all_members(),
                        name=rleb_settings.developer_name,
                        discriminator=rleb_settings.developer_discriminator,
                    )
                    await self.bot_command_channel.send(
                        "^ " + developer.mention + " fyi"
                    )
                    break
                rleb_settings.rleb_log_error(
                    "DISCORD: Alert asyncio thread failed - {0}".format(e)
                )
                rleb_settings.rleb_log_error(traceback.format_exc())
                rleb_settings.thread_crashes["asyncio"] += 1
                rleb_settings.last_datetime_crashed["asyncio"] = datetime.now()
            await asyncio.sleep(rleb_settings.discord_async_interval_seconds)

    async def check_new_direct_messages(self):
        """Checks direct_messages queue to send DMs to discord users."""
        while True:
            try:
                while not rleb_settings.queues["direct_messages"].empty():
                    author_message_tuple = rleb_settings.queues["direct_messages"].get(
                    )
                    rleb_settings.rleb_log_info(
                        "DISCORD: Received DM '{0}'".format(
                            author_message_tuple)
                    )
                    author = author_message_tuple[0]
                    message = author_message_tuple[1]
                    user_mapping = user_names_to_ids(self.bot_command_channel)
                    if user_mapping == None or len(user_mapping) == 0:
                        continue
                    discord_user = self.get_user(user_mapping[author])
                    if discord_user == None:
                        continue
                    message = "\n".join(
                        [
                            random.choice(rleb_settings.greetings),
                            "\n----------\n",
                            message,
                            "\n----------\n",
                        ]
                    )
                    DM = await discord_user.send(message)
                    await DM.edit(suppress=True)

                rleb_settings.asyncio_threads["direct_messages"] = datetime.now(
                )
                if not rleb_settings.discord_check_direct_messages_enabled:
                    break
            except Exception as e:
                if rleb_settings.thread_crashes["asyncio"] > 5:
                    await self.bot_command_channel.send(
                        "ALERT: Asyncio thread has crashed more than 5 times."
                    )
                    developer = discord.utils.get(
                        self.get_all_members(),
                        name=rleb_settings.developer_name,
                        discriminator=rleb_settings.developer_discriminator,
                    )
                    await self.bot_command_channel.send(
                        "^ " + developer.mention + " fyi"
                    )
                    break
                rleb_settings.rleb_log_error(
                    "DISCORD: Alert asyncio thread failed - {0}".format(e)
                )
                rleb_settings.rleb_log_error(traceback.format_exc())
                rleb_settings.thread_crashes["asyncio"] += 1
                rleb_settings.last_datetime_crashed["asyncio"] = datetime.now()
            await asyncio.sleep(rleb_settings.discord_async_interval_seconds)

    async def check_new_alerts(self):
        """Check alerts queue to post in 'bot commands' discord channel."""
        while True:
            try:
                while not rleb_settings.queues["alerts"].empty():
                    alert = rleb_settings.queues["alerts"].get()
                    rleb_settings.rleb_log_info(
                        "DISCORD: Received alert '{0}'".format(alert)
                    )
                    await self.bot_command_channel.send("ALERT: " + alert)
                rleb_settings.asyncio_threads["alerts"] = datetime.now()
                if not rleb_settings.discord_check_new_alerts_enabled:
                    break
            except Exception as e:
                if rleb_settings.thread_crashes["asyncio"] > 5:
                    await self.bot_command_channel.send(
                        "ALERT: Asyncio thread has crashed more than 5 times."
                    )
                    developer = discord.utils.get(
                        self.get_all_members(),
                        name=rleb_settings.developer_name,
                        discriminator=rleb_settings.developer_discriminator,
                    )
                    await self.bot_command_channel.send(
                        "^ " + developer.mention + " fyi"
                    )
                    break
                rleb_settings.rleb_log_error(
                    "DISCORD: Alert asyncio thread failed - {0}".format(e)
                )
                rleb_settings.rleb_log_error(traceback.format_exc())
                rleb_settings.thread_crashes["asyncio"] += 1
                rleb_settings.last_datetime_crashed["asyncio"] = datetime.now()
            await asyncio.sleep(rleb_settings.discord_async_interval_seconds)

    async def check_new_modfeed(self):
        """Check modmail/modlog queue to post in discord."""
        while True:
            try:
                # Mod Log
                while not rleb_settings.queues["modlog"].empty():
                    await asyncio.sleep(1)
                    item = rleb_settings.queues["modlog"].get()

                    # Create an embed to post for each mod log.
                    embed = discord.Embed(
                        title=item.action.replace("_", " ").title(),
                        url="https://www.reddit.com/r/RocketLeagueEsports/about/log/",
                        color=random.choice(rleb_settings.colors),
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
                        content_array.append(
                            f"**Description**: {item.description}")
                    if len(item.details or "") > 0:
                        content_array.append(
                            f"**Extra Details**: {item.details}")
                    content_array.append(
                        "--------------------------------------------------------"
                    )
                    contents = "\n".join(content_array)

                    embed.description = contents

                    # Send everything.
                    await self.modlog_channel.send(embed=embed)

                # Mod Mail
                while not rleb_settings.queues["modmail"].empty():
                    item = rleb_settings.queues["modmail"].get()
                    rleb_settings.rleb_log_info(
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
                            color=random.choice(rleb_settings.colors),
                        )
                        embed.set_author(name=item.author.name)
                    # New modmail
                    else:
                        embed = discord.Embed(
                            title="Created: '{0}'".format(item.subject),
                            url="https://mod.reddit.com/mail/all",
                            color=random.choice(rleb_settings.colors),
                        )
                        embed.set_author(name=item.author.name)

                    embed.description = f"{item.body}\n--------------------------------------------------------"

                    # Send everything.
                    await self.modmail_channel.send(embed=embed)

                rleb_settings.asyncio_threads["modmail"] = datetime.now()
                if not rleb_settings.discord_check_new_modmail_enabled:
                    break
            except Exception as e:
                if rleb_settings.thread_crashes["asyncio"] > 5:
                    await self.bot_command_channel.send(
                        "ALERT: Asyncio thread has crashed more than 5 times."
                    )
                    developer = discord.utils.get(
                        self.get_all_members(),
                        name=rleb_settings.developer_name,
                        discriminator=rleb_settings.developer_discriminator,
                    )
                    await self.bot_command_channel.send(
                        "^ " + developer.mention + " fyi"
                    )
                    break
                rleb_settings.rleb_log_error(
                    "DISCORD: Modfeed asyncio thread failed - {0}".format(e)
                )
                rleb_settings.rleb_log_error(traceback.format_exc())
                rleb_settings.thread_crashes["asyncio"] += 1
                rleb_settings.last_datetime_crashed["asyncio"] = datetime.now()
            await asyncio.sleep(rleb_settings.discord_async_interval_seconds)

    async def check_new_trello_actions(self):
        """Check trello queue to post in discord."""
        while True:
            try:
                while not rleb_settings.queues["trello"].empty():
                    action = rleb_settings.queues["trello"].get()
                    rleb_settings.rleb_log_info(
                        "DISCORD: Received trello action {0}".format(
                            action["type"])
                    )
                    embed = discord.Embed(
                        title=action["message"],
                        url="https://trello.com/b/u16InUez/rl-esports-sub",
                        color=random.choice(rleb_settings.colors),
                    )
                    embed.set_author(name=action["memberCreator"]["username"])
                    await self.trello_channel.send(embed=embed)
                rleb_settings.asyncio_threads["trello"] = datetime.now()
            except Exception as e:
                if rleb_settings.thread_crashes["asyncio"] > 5:
                    await self.bot_command_channel.send(
                        "ALERT: Asyncio thread has crashed more than 5 times."
                    )
                    developer = discord.utils.get(
                        self.get_all_members(),
                        name=rleb_settings.developer_name,
                        discriminator=rleb_settings.developer_discriminator,
                    )
                    await self.bot_command_channel.send(
                        "^ " + developer.mention + " fyi"
                    )
                    break
                rleb_settings.rleb_log_error(
                    "DISCORD: Trello asyncio thread failed - {0}".format(e)
                )
                rleb_settings.rleb_log_error(traceback.format_exc())
                rleb_settings.thread_crashes["asyncio"] += 1
                rleb_settings.last_datetime_crashed["asyncio"] = datetime.now()
            await asyncio.sleep(rleb_settings.discord_async_interval_seconds)

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
        if rleb_settings.RUNNING_MODE == "local":
            if "!debug" not in discord_message:
                return
            discord_message = discord_message.replace("!debug ", "")

        if str(message.channel) == "voting":
            rleb_settings.rleb_log_info(
                "DISCORD: New voting message: {0}".format(discord_message)
            )
            await message.add_reaction("👍")
            await message.add_reaction("👎")
            await message.add_reaction("🤷")
            return

        if str(message.channel) == "ban-review":
            rleb_settings.rleb_log_info(
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
                thanks_responses = ["np", "no problem",
                                    "no worries", "you're welcome"]
                await message.channel.send(random.choice(thanks_responses))
                del self.responses[str(message.author)]

        elif discord_message.startswith("!census") and is_staff(message.author):

            if not rleb_settings.is_discord_mod(message.author):
                return

            rleb_settings.rleb_log_info("DISCORD: Starting flair census.")
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

            if not rleb_settings.is_discord_mod(message.author):
                return

            rleb_settings.rleb_log_info("DISCORD: Starting migration")
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
                return
            count = 0
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

        elif discord_message == "!confirm migrate" and is_staff(message.author):

            if not rleb_settings.is_discord_mod(message.author):
                return

            if (datetime.now() - self.migrate_request_time).total_seconds() > 120:
                await message.channel.send(
                    "Migration timed out. You must confirm within 2 minutes to migrate flairs."
                )
                return
            await message.channel.send(
                "Starting migration {0} -> {1}.".format(
                    self.from_flair, self.to_flair)
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
                    rleb_settings.rleb_log_info(
                        "DISCORD: Setting {0} to {1} (was {2})".format(
                            user.name, new_flair, flair["flair_text"]
                        )
                    )
                    sub.flair.set(user, text=new_flair, css_class="")
            await message.channel.send("Flair migration finished.")
            await self.add_response(message)

        elif discord_message.startswith("!dualflairs") and is_staff(message.author):
            if not rleb_settings.is_discord_mod(message.author):
                return

        elif discord_message == "!triflairs list" and is_staff(message.author):

            if not rleb_settings.is_discord_mod(message.author):
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

            if not rleb_settings.is_discord_mod(message.author):
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

            if not rleb_settings.is_discord_mod(message.author):
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

            if not rleb_settings.is_discord_mod(message.author):
                return

            tokens = discord_message.split()

            if not tokens[2].startswith(":"):
                await message.channel.send(
                    "Couldn't understand that. Expected '!triflairs add :flair:'."
                )
                return
            else:
                flair = None
                try:
                    flair = tokens[2]
                except IndexError:
                    await message.channel.send(
                        "Couldn't understand that. Expected '!triflairs add :flair:'."
                    )
                    return
                self.flair_to_add = flair
                self.add_flair_time = datetime.now()
                await message.channel.send(
                    "Type '!confirm add' to add the {0} flair.".format(flair)
                )
                await self.add_response(message)

        elif discord_message == "!confirm add" and is_staff(message.author):

            if not rleb_settings.is_discord_mod(message.author):
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

            if not rleb_settings.is_discord_mod(message.author):
                return

            rleb_settings._flush_memory_log()
            await message.channel.send(":toilet:")

        elif discord_message.startswith("!schedule") and is_staff(message.author):
            if not rleb_settings.is_discord_mod(message.author):
                return

            await message.channel.send(
                "**Found the following scheduled posts on reddit:**"
            )
            scheduled_posts = rleb_health.get_scheduled_posts()
            for s in scheduled_posts:
                await message.channel.send(s)

            await message.channel.send(
                "**Found the following tasks on the weekly sheet:**"
            )
            weekly_tasks = rleb_health.get_weekly_tasks()
            for t in weekly_tasks:
                await message.channel.send(t)

            await self.add_response(message)

        elif discord_message.startswith("!logs") and is_staff(message.author):

            if not rleb_settings.is_discord_mod(message.author):
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
                logs = rleb_settings.memory_log[(-1 * count):]
            elif datasource == "db":
                db_logs = Data.singleton().read_logs()
                db_logs_as_list = list(map(lambda x: x[0], db_logs))
                logs = db_logs_as_list[(-1 * count):]
            else:
                await message.channel.send(
                    "The first argument should be either 'memory' or 'db'."
                )
                return
            try:
                if logs == None or len(logs) == 0:
                    await message.channel.send("No logs to show.")
                    return
                await rleb_stdout.print_to_channel(
                    message.channel, "\n".join(logs), title="logs"
                )
            except discord.errors.HTTPException:
                rleb_settings.rleb_log_error(traceback.format_exc())
                await message.channel.send(
                    "Couldn't send logs over! (tip: there's a limit to the number of characters that can be sent. Make sure you aren't requesting too many logs. Use '!logs [db/memory] [n]', where n is a small number to avoid the character limit.)"
                )
            await self.add_response(message)

        elif discord_message == "!status" and is_staff(message.author):

            if not rleb_settings.is_discord_mod(message.author):
                return

            delta = datetime.now() - self.start_datetime
            seconds_uptime = delta.total_seconds()
            hours_uptime = round(seconds_uptime / 60 / 60, 0)
            await message.channel.send(
                "Running for {0} day(s) and {1} hour(s)".format(
                    math.floor(hours_uptime / 24), hours_uptime % 24
                )
            )
            for thread_type, crash_count in rleb_settings.thread_crashes.items():
                await message.channel.send(
                    "{0} crashes detected: {1}".format(
                        thread_type, crash_count)
                )

            for thread_type, last_crash in rleb_settings.last_datetime_crashed.items():
                last_crash_string = "N/A"
                if last_crash:
                    delta = datetime.now() - last_crash
                    last_crash_string = delta.total_seconds() / 3600
                    last_crash_string = round(last_crash_string, 1)
                await message.channel.send(
                    "{0} last crashed {1} hours ago.".format(
                        thread_type, last_crash_string
                    )
                )

            await message.channel.send(
                "Found {0} out of 7 threads running: {1}".format(
                    len(self.threads), list(
                        map(lambda x: x.name, self.threads))
                )
            )
            await self.add_response(message)

        elif discord_message == "!reset crashes" and is_staff(message.author):

            if not rleb_settings.is_discord_mod(message.author):
                return

            rleb_settings.thread_crashes["thread"] = 0
            rleb_settings.thread_crashes["asyncio"] = 0
            await message.channel.send("Thread crash count was reset")
            rleb_settings.rleb_log_info("DISCORD: Thread count was reset.")
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
                title=target, url=url, color=random.choice(
                    rleb_settings.colors)
            )
            await message.channel.send(embed=embed)
            await self.add_response(message)

        elif discord_message.startswith("!teams") and is_staff(message.author):
            if not rleb_settings.is_discord_mod(message.author):
                return

            rleb_settings.rleb_log_info("DISCORD: Starting team generation.")
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
            if not rleb_settings.is_discord_mod(message.author):
                return

            rleb_settings.rleb_log_info(
                "DISCORD: Starting swiss bracket generation.")
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

        elif discord_message.startswith("!bracket") and is_staff(message.author):
            if not rleb_settings.is_discord_mod(message.author):
                return

            rleb_settings.rleb_log_info(
                "DISCORD: Starting elim bracket generation.")
            await message.channel.send("Starting elimination bracket lookup...")
            tokens = discord_message.split()
            url = ""
            try:
                url = tokens[1]
            except Exception:
                await message.channel.send(
                    "Couldn't understand that. Expected '!bracket liquipedia-url'."
                )
                return
            await handle_bracket_lookup(url, message.channel)
            await self.add_response(message)

        elif discord_message.startswith("!groups") and is_staff(message.author):
            if not rleb_settings.is_discord_mod(message.author):
                return

            rleb_settings.rleb_log_info("DISCORD: Starting group generation.")
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

        elif discord_message.startswith("!prizepool") and is_staff(message.author):
            if not rleb_settings.is_discord_mod(message.author):
                return

            rleb_settings.rleb_log_info(
                "DISCORD: Starting prizepool generation.")
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
            if not rleb_settings.is_discord_mod(message.author):
                return

            rleb_settings.rleb_log_info("DISCORD: Starting mvp generation.")
            await message.channel.send("Creating MVP voting form...")
            tokens = discord_message.split()
            urls = tokens[1:]
            if len(urls) < 1:
                await message.channel.send(
                    "Couldn't understand that. Expected '!mvp liquipedia-url-1 liquipedia-url-2 liquipedia-url-3 etc...'."
                )
                return
            await handle_mvp_lookup(urls, message.channel)
            await self.add_response(message)

        elif discord_message.startswith("!events") and is_staff(message.author):
            if not rleb_settings.is_discord_mod(message.author):
                return

            rleb_settings.rleb_log_info("DISCORD: Starting event lookup.")
            tokens = discord_message.split()
            formatter = "reddit"
            days = 7
            try:
                formatter = tokens[1]
                days = int(tokens[2])
            except Exception:
                await message.channel.send(
                    "Couldn't understand that. Expected '!events [formatter] [# days]'. Example is '!events reddit 7' to get the next 7 days of events. Valid formatters are reddit and sheets."
                )
                return
            await handle_calendar_lookup(message.channel, formatter, days)
            await self.add_response(message)

        elif discord_message.startswith("!tasks") and is_staff(message.author):
            if not rleb_settings.is_discord_mod(message.author):
                return

            rleb_settings.rleb_log_info("DISCORD: Starting task lookup.")
            tokens = discord_message.split()

            # User = the person requesting the command, unless explicitly stated.
            user = message.author.name.lower() + "#" + message.author.discriminator
            extra = None
            try:
                user = tokens[1]
                extra = tokens[2]
            except Exception:
                pass
            await handle_task_lookup(message.channel, self, user, extra)
            await self.add_response(message)

        elif discord_message.startswith("!meme"):
            await self.send_meme(message.channel)
            await self.add_response(message)

        elif discord_message.startswith("!setmeme") and is_staff(message.author):
            if not rleb_settings.is_discord_mod(message.author):
                return

            tokens = discord_message.split()
            subreddit = ""
            try:
                subreddit = tokens[1]
            except Exception:
                pass

            original_meme_subreddit = self.meme_subreddit
            try:
                rleb_settings.r.subreddit(self.meme_subreddit)
                self.meme_subreddit = subreddit
                await self.send_meme(message.channel)
            except:
                await message.channel("That isn't a real place!")
                self.meme_subreddit = original_meme_subreddit

            await self.add_response(message)

        elif discord_message.startswith("!echo"):
            discord_message.remove("!echo")
            message_without_command = "> {0}".format(
                discord_message.remove("!echo"))
            await message.channel.send(message_without_command)
            await self.add_response(message)


def start(threads: list[Thread]) -> None:
    """Spawns the various discord asyncio threads.

    Args:
        threads (list[Thread]): List of threads used for monitoring both health.
    """
    client = RLEsportsBot(threads)

    # Create asyncronoush discord tasks.
    client.loop.create_task(client.check_new_submissions())
    client.loop.create_task(client.check_new_trello_actions())
    client.loop.create_task(client.check_new_modfeed())
    client.loop.create_task(client.check_new_alerts())
    client.loop.create_task(client.check_new_direct_messages())
    client.loop.create_task(client.check_new_schedule_chat())

    # Start listening to discord commands.
    client.run(rleb_settings.TOKEN)
