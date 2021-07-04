import discord
from discord.utils import get
import random
from datetime import datetime
import time
import asyncio
from threading import Lock
import traceback
import math

import rleb_settings
from rleb_settings import sub
from rleb_team_lookup import handle_team_lookup
from rleb_group_lookup import handle_group_lookup
from rleb_census import handle_flair_census
from rleb_calendar import handle_calendar_lookup
from rleb_tasks import handle_task_lookup

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

    async def on_ready(self):
        """Indicate bot has joined the discord."""
        rleb_settings.rleb_log_info('DISCORD: Logged on as {0}'.format(
            self.user))
        rleb_settings.rleb_log_info(
            'DISCORD: Loading channel settings: new_posts: {0}, trello: {1}, modmail: {2}, bot_commands: {3}'
            .format(rleb_settings.NEW_POSTS_CHANNEL_ID,
                    rleb_settings.TRELLO_CHANNEL_ID,
                    rleb_settings.MODMAIL_CHANNEL_ID,
                    rleb_settings.BOT_COMMANDS_CHANNEL_ID))
        self.new_post_channel = self.get_channel(
            rleb_settings.NEW_POSTS_CHANNEL_ID)
        self.trello_channel = self.get_channel(rleb_settings.TRELLO_CHANNEL_ID)
        self.modmail_channel = self.get_channel(
            rleb_settings.MODMAIL_CHANNEL_ID)
        self.bot_command_channel = self.get_channel(
            rleb_settings.BOT_COMMANDS_CHANNEL_ID)

        # If testing, ping the discord channel.
        if rleb_settings.RUNNING_MODE != "production":
            await self.bot_command_channel.send(
                "Bot is online, running in {0} under {1} mode.".format(
                    rleb_settings.RUNNING_ENVIRONMENT, rleb_settings.RUNNING_MODE))
        else:
            await self.send_meme(self.bot_command_channel)

    async def send_meme(self, channel):
        dankmemes = rleb_settings.r.subreddit("wholesomememes")
        randomizer = random.randint(1, 20)
        count = 0
        for meme in dankmemes.top("day"):
            if count <= randomizer:
                count += 1
                continue
            link = meme.url
            await channel.send("{0}".format(link))
            break

    async def check_new_submissions(self):
        """Check submissions queue to post in 'new posts' discord channel."""
        while (True):
            try:
                while not rleb_settings.queues['submissions'].empty():
                    submission = rleb_settings.queues['submissions'].get()
                    rleb_settings.rleb_log_info(
                        "DISCORD: Received submission id {0}: {1}".format(
                            submission, submission.title))
                    embed = discord.Embed(
                        title=submission.title,
                        url="https://www.reddit.com{0}".format(
                            submission.permalink),
                        color=random.choice(rleb_settings.colors))
                    embed.set_author(name=submission.author.name)
                    await self.new_post_channel.send(embed=embed)
                rleb_settings.asyncio_threads['submissions'] = datetime.now()
                if not rleb_settings.discord_check_new_submission_enabled:
                    break
            except Exception as e:
                if rleb_settings.thread_crashes['asyncio'] > 5:
                    await self.bot_command_channel.send(
                        'ALERT: Asyncio thread has crashed more than 5 times.')
                    developer = discord.utils.get(
                        self.get_all_members(),
                        name=rleb_settings.developer_name,
                        discriminator=rleb_settings.developer_discriminator)
                    await self.bot_command_channel.send("^ " +
                                                        developer.mention +
                                                        " fyi")
                    break
                rleb_settings.rleb_log_error(
                    "Discord: Submissions asyncio thread failed - {0}".format(
                        e))
                rleb_settings.rleb_log_error(traceback.format_exc())
                rleb_settings.thread_crashes['asyncio'] += 1
                rleb_settings.last_datetime_crashed['asyncio'] = datetime.now()
            await asyncio.sleep(rleb_settings.discord_async_interval_seconds)

    async def check_new_alerts(self):
        """Check alerts queue to post in 'bot commands' discord channel."""
        while (True):
            try:
                while not rleb_settings.queues['alerts'].empty():
                    alert = rleb_settings.queues['alerts'].get()
                    rleb_settings.rleb_log_info(
                        "DISCORD: Received alert '{0}'".format(alert))
                    await self.bot_command_channel.send('ALERT: ' + alert)
                rleb_settings.asyncio_threads['alerts'] = datetime.now()
            except Exception as e:
                if rleb_settings.thread_crashes['asyncio'] > 5:
                    await self.bot_command_channel.send(
                        'ALERT: Asyncio thread has crashed more than 5 times.')
                    developer = discord.utils.get(
                        self.get_all_members(),
                        name=rleb_settings.developer_name,
                        discriminator=rleb_settings.developer_discriminator)
                    await self.bot_command_channel.send("^ " +
                                                        developer.mention +
                                                        " fyi")
                    break
                rleb_settings.rleb_log_error(
                    "DISCORD: Alert asyncio thread failed - {0}".format(e))
                rleb_settings.rleb_log_error(traceback.format_exc())
                rleb_settings.thread_crashes['asyncio'] += 1
                rleb_settings.last_datetime_crashed['asyncio'] = datetime.now()
            await asyncio.sleep(20)

    async def check_new_modmail(self):
        """Check modmail queue to post in 'modmail' discord channel."""
        while (True):
            try:
                while not rleb_settings.queues['modmail'].empty():
                    item = rleb_settings.queues['modmail'].get()
                    rleb_settings.rleb_log_info(
                        "DISCORD: Received modmail id {0}: {1}".format(
                            item.id, item.body))
                    embed = None
                    if item.parent_id:
                        embed = discord.Embed(
                            title="Commented on '{0}'".format(item.subject),
                            url="https://mod.reddit.com/mail/all",
                            color=random.choice(rleb_settings.colors))
                        embed.set_author(name=item.author.name)
                    else:
                        embed = discord.Embed(
                            title="Created: '{0}'".format(item.subject),
                            url="https://mod.reddit.com/mail/all",
                            color=random.choice(rleb_settings.colors))
                        embed.set_author(name=item.author.name)
                    await self.modmail_channel.send(embed=embed)
                    time.sleep(1)
                    await self.modmail_channel.send("{0}: \"{1}\"".format(
                        item.author.name, item.body))
                    removed_post = await self.post_removed(item)
                    if removed_post:
                        time.sleep(1)
                        await self.modmail_channel.send(
                            "Removed Post (by {0}): {1}".format(
                                str(removed_post.author),
                                str(removed_post.selftext)
                                or str(removed_post.url)))
                    await self.modmail_channel.send(
                        "--------------------------------------------------------"
                    )
                rleb_settings.asyncio_threads['modmail'] = datetime.now()
            except Exception as e:
                if rleb_settings.thread_crashes['asyncio'] > 5:
                    await self.bot_command_channel.send(
                        'ALERT: Asyncio thread has crashed more than 5 times.')
                    developer = discord.utils.get(
                        self.get_all_members(),
                        name=rleb_settings.developer_name,
                        discriminator=rleb_settings.developer_discriminator)
                    await self.bot_command_channel.send("^ " +
                                                        developer.mention +
                                                        " fyi")
                    break
                rleb_settings.rleb_log_error(
                    "DISCORD: Modmail asyncio thread failed - {0}".format(e))
                rleb_settings.rleb_log_error(traceback.format_exc())
                rleb_settings.thread_crashes['asyncio'] += 1
                rleb_settings.last_datetime_crashed['asyncio'] = datetime.now()
            await asyncio.sleep(20)

    async def check_new_trello_actions(self):
        """Check trello queue to post in discord."""
        while (True):
            try:
                while not rleb_settings.queues['trello'].empty():
                    action = rleb_settings.queues['trello'].get()
                    rleb_settings.rleb_log_info(
                        "DISCORD: Received trello action {0}".format(
                            action["type"]))
                    embed = discord.Embed(
                        title=action["message"],
                        url="https://trello.com/b/u16InUez/rl-esports-sub",
                        color=random.choice(rleb_settings.colors))
                    embed.set_author(name=action["memberCreator"]["username"])
                    await self.trello_channel.send(embed=embed)
                rleb_settings.asyncio_threads['trello'] = datetime.now()
            except Exception as e:
                if rleb_settings.thread_crashes['asyncio'] > 5:
                    await self.bot_command_channel.send(
                        'ALERT: Asyncio thread has crashed more than 5 times.')
                    developer = discord.utils.get(
                        self.get_all_members(),
                        name=rleb_settings.developer_name,
                        discriminator=rleb_settings.developer_discriminator)
                    await self.bot_command_channel.send("^ " +
                                                        developer.mention +
                                                        " fyi")
                    break
                rleb_settings.rleb_log_error(
                    "DISCORD: Trello asyncio thread failed - {0}".format(e))
                rleb_settings.rleb_log_error(traceback.format_exc())
                rleb_settings.thread_crashes['asyncio'] += 1
                rleb_settings.last_datetime_crashed['asyncio'] = datetime.now()
            await asyncio.sleep(20)

    async def post_removed(self, item):
        """Take in a modmail item and return either a comment if this modmail
           was an automod notification about a removed comment, else returns
           None.

           Args:
             item (praw.models.ModmailMessage): PRAW modmail message.

           Returns (praw.models.Submission): The comment that was removed by the
           modmail item.
        """
        if "Please investigate and ensure that this action was correct" not in item.body:
            return None
        tokens = item.body.split()
        link = tokens[0]
        if not link.startswith(
                "https://www.reddit.com/r/RocketLeagueEsports/comments"):
            return None
        return rleb_settings.r.submission(url=link)

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
        if "RLesports" in str(message.author):
            return

        await self.remove_old_responses()

        if str(message.channel) == 'voting':
            rleb_settings.rleb_log_info(
                "DISCORD: New voting message: {0}".format(message.content))
            await message.add_reaction('👍')
            await message.add_reaction('👎')
            await message.add_reaction('🤷')
            return

        if str(message.channel) == 'ban-review':
            rleb_settings.rleb_log_info(
                "DISCORD: New ban-remove message: {0}".format(message.content))
            await message.add_reaction('1️⃣')
            await message.add_reaction('2️⃣')
            await message.add_reaction('3️⃣')
            await message.add_reaction('💀')
            await message.add_reaction('⚠️')
            return

        elif (message.content == "thanks" or message.content == "thank you"
              or message.content == "ty" or message.content == "thx"):
            if str(message.author) in self.responses:
                thanks_responses = [
                    "np", "no problem", "no worries", "you're welcome"
                ]
                await message.channel.send(random.choice(thanks_responses))
                del self.responses[str(message.author)]

        elif message.content.startswith("!census") and is_staff(
                message.author):

            if (not rleb_settings.is_discord_mod(message.author)):
                return

            rleb_settings.rleb_log_info("DISCORD: Starting flair census.")
            await message.channel.send(
                "Starting flair census, this may take a minute...")
            tokens = message.content.split()
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
                if divider == ' ':
                    divider = ","
            except Exception:
                divider = ","
            await handle_flair_census(sub, amount, message.channel, divider)
            await self.add_response(message)

        elif message.content.startswith("!migrate") and is_staff(
                message.author):

            if (not rleb_settings.is_discord_mod(message.author)):
                return

            rleb_settings.rleb_log_info("DISCORD: Starting migration")
            tokens = message.content.split()
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
                if flair['flair_text'] != None and from_flair in flair[
                        'flair_text']:
                    count += 1
            if (from_flair != None and to_flair != None):
                await message.channel.send(
                    "Type '!confirm migrate' to migrate '{0}' -> '{1}' in the next 2 minutes. This will affect {2} users."
                    .format(from_flair, to_flair, count))
                self.to_flair = to_flair
                self.from_flair = from_flair
                self.migrate_request_time = datetime.now()
                await self.add_response(message)

        elif message.content == "!confirm migrate" and is_staff(
                message.author):

            if (not rleb_settings.is_discord_mod(message.author)):
                return

            if ((datetime.now() - self.migrate_request_time).total_seconds() >
                    120):
                await message.channel.send(
                    "Migration timed out. You must confirm within 2 minutes to migrate flairs."
                )
                return
            await message.channel.send("Starting migration {0} -> {1}.".format(
                self.from_flair, self.to_flair))
            for flair in sub.flair(limit=None):
                if flair['flair_text'] != None and self.from_flair in flair[
                        'flair_text']:
                    user = flair['user']
                    new_flair = flair['flair_text'].replace(
                        self.from_flair, self.to_flair)
                    rleb_settings.rleb_log_info(
                        "DISCORD: Setting {0} to {1} (was {2})".format(
                            user.name, new_flair, flair['flair_text']))
                    sub.flair.set(user, text=new_flair, css_class="")
            await message.channel.send("Flair migration finished.")
            await self.add_response(message)

        elif message.content == "!dualflairs list":

            if (not rleb_settings.is_discord_mod(message.author)):
                return

            all_flairs = ""
            db = rleb_settings.postgresConnection()
            cursor = db.cursor()
            cursor.execute("SELECT * FROM dualflairs;")
            flairs = cursor.fetchall()
            flair_list = list(map(lambda x: x[0], flairs))
            flair_list.sort()
            for flair in flair_list:
                all_flairs += flair
                all_flairs += "\n"
            await message.channel.send(all_flairs)
            await self.add_response(message)

        elif message.content.startswith("!dualflairs remove") and is_staff(message.author):

            if (not rleb_settings.is_discord_mod(message.author)):
                return

            tokens = message.content.split()
            flair = None
            try:
                flair = tokens[2]
            except IndexError:
                await message.channel.send(
                    "Couldn't understand that. Expected '!dualflairs remove:flair:'."
                )
                return
            await message.channel.send(
                "Type '!confirm remove' to remove the {0} flair.".format(flair)
            )
            self.flair_to_remove = flair
            self.remove_flair_time = datetime.now()
            await self.add_response(message)

        elif message.content == '!confirm remove' and is_staff(message.author):

            if (not rleb_settings.is_discord_mod(message.author)):
                return

            if ((datetime.now() - self.remove_flair_time).total_seconds() >
                    120):
                await message.channel.send(
                    "Removal timed out. You must confirm within 2 minutes to remove flairs."
                )
                return
            db = rleb_settings.postgresConnection()
            cursor = db.cursor()
            cursor.execute("SELECT * FROM dualflairs;")
            flairs = cursor.fetchall()
            flair_list = list(map(lambda x: x[0], flairs))
            if not (self.flair_to_remove in flair_list):
                await message.channel.send(
                    "Couldn't find {0}! Type '!dualflairs list' to view all flairs."
                    .format(self.flair_to_remove))
                return
            else:
                cursor.execute("DELETE FROM dualflairs WHERE dualflair = %s",
                               (self.flair_to_remove, ))
                db.commit()
                await message.channel.send("Removed {0}.".format(
                    self.flair_to_remove))
                await self.add_response(message)

        elif message.content.startswith("!dualflairs add") and is_staff(message.author):

            if (not rleb_settings.is_discord_mod(message.author)):
                return

            tokens = message.content.split()
            flair = None
            try:
                flair = tokens[2]
            except IndexError:
                await message.channel.send(
                    "Couldn't understand that. Expected '!dualflairs add :flair:'."
                )
                return
            self.flair_to_add = flair
            self.add_flair_time = datetime.now()
            await message.channel.send(
                "Type '!confirm add' to add the {0} flair.".format(flair))
            await self.add_response(message)

        elif message.content == '!confirm add' and is_staff(message.author):

            if (not rleb_settings.is_discord_mod(message.author)):
                return

            if ((datetime.now() - self.add_flair_time).total_seconds() > 120):
                await message.channel.send(
                    "Addition timed out. You must confirm within 2 minutes to add flairs."
                )
                return
            db = rleb_settings.postgresConnection()
            cursor = db.cursor()
            cursor.execute("SELECT * FROM dualflairs;")
            flairs = cursor.fetchall()
            flair_list = list(map(lambda x: x[0], flairs))
            if self.flair_to_add in flair_list:
                await message.channel.send(
                    "{0} is already in the flair list! Type '!dualflairs list' to view all flairs."
                    .format(self.flair_to_add))
                return
            else:
                cursor.execute("""INSERT INTO dualflairs VALUES (%s)""",
                               (self.flair_to_add, ))
                db.commit()
                await message.channel.send("Added {0}.".format(
                    self.flair_to_add))
                await self.add_response(message)

        elif message.content.startswith('!flush') and is_staff(message.author):

            if (not rleb_settings.is_discord_mod(message.author)):
                return

            rleb_settings.flush_memory_log()
            await message.channel.send(":toilet:")

        elif message.content.startswith('!logs') and is_staff(message.author):

            if (not rleb_settings.is_discord_mod(message.author)):
                return

            tokens = message.content.split()
            datasource = 'memory'
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
            if datasource == 'memory':
                logs = status_list = rleb_settings.memory_log[(-1 * count):]
            elif datasource == 'db':
                db = rleb_settings.postgresConnection()
                cursor = db.cursor()
                cursor.execute("SELECT * FROM logs;")
                db_logs = cursor.fetchall()
                db_logs_as_list = list(map(lambda x: x[0], db_logs))
                logs = db_logs_as_list[(-1 * count):]
            else:
                await message.channel.send(
                    "The first argument should be either 'memory' or 'db'.")
                return
            try:
                if logs == None or len(logs) == 0:
                    await message.channel.send("No logs to show.")
                    return
                await message.channel.send("\n".join(logs))
            except discord.errors.HTTPException:
                rleb_settings.rleb_log_error(traceback.format_exc())
                await message.channel.send(
                    "Couldn't send logs over! (tip: there's a limit to the number of characters that can be sent. Make sure you aren't requesting too many logs. Use '!logs [db/memory] [n]', where n is a small number to avoid the character limit.)"
                )
            await self.add_response(message)

        elif message.content == '!status' and is_staff(message.author):

            if (not rleb_settings.is_discord_mod(message.author)):
                return

            delta = datetime.now() - self.start_datetime
            seconds_uptime = delta.total_seconds()
            hours_uptime = round(seconds_uptime / 60 / 60, 0)
            await message.channel.send(
                "Running for {0} day(s) and {1} hour(s)".format(
                    math.floor(hours_uptime / 24), hours_uptime % 24))
            for thread_type, crash_count in rleb_settings.thread_crashes.items(
            ):
                await message.channel.send("{0} crashes detected: {1}".format(
                    thread_type, crash_count))

            for thread_type, last_crash in rleb_settings.last_datetime_crashed.items(
            ):
                last_crash_string = "N/A"
                if last_crash:
                    delta = datetime.now() - last_crash
                    last_crash_string = delta.total_seconds() / 3600
                    last_crash_string = round(last_crash_string, 1)
                await message.channel.send(
                    "{0} last crashed {1} hours ago.".format(
                        thread_type, last_crash_string))

            await message.channel.send(
                "Found {0} out of 5 threads running: {1}".format(
                    len(self.threads), list(map(lambda x: x.name,
                                                self.threads))))
            await self.add_response(message)

        elif message.content == '!reset crashes' and is_staff(message.author):

            if (not rleb_settings.is_discord_mod(message.author)):
                return

            rleb_settings.thread_crashes['thread'] = 0
            rleb_settings.thread_crashes['asyncio'] = 0
            await message.channel.send("Thread crash count was reset")
            rleb_settings.rleb_log_info("DISCORD: Thread count was reset.")
            await self.add_response(message)

        elif message.content.startswith("!search"):
            tokens = message.content.split()
            target = ""
            try:
                target = tokens[1]
            except IndexError:
                await message.channel.send(
                    "To search on liquipedia, use '!search <thing>'")
                return
            url = "https://liquipedia.net/rocketleague/index.php?search={0}".format(
                target)
            embed = discord.Embed(title=target,
                                  url=url,
                                  color=random.choice(rleb_settings.colors))
            await message.channel.send(embed=embed)
            await self.add_response(message)

        elif message.content.startswith("!teams") and is_staff(message.author):
            rleb_settings.rleb_log_info("DISCORD: Starting team generation.")
            await message.channel.send(
                "Starting team lookup, this may take a minute...")
            tokens = message.content.split()
            url = 10
            try:
                url = tokens[1]
            except Exception:
                await message.channel.send(
                    "Couldn't understand that. Expected '!teams liquipedia-url'."
                )
                return
            seconds = await handle_team_lookup(url, message.channel)
            await self.add_response(message)

        elif message.content.startswith("!groups") and is_staff(
                message.author):
            rleb_settings.rleb_log_info("DISCORD: Starting group generation.")
            await message.channel.send(
                "Starting group lookup, this may take a minute...")
            tokens = message.content.split()
            url = 10
            try:
                url = tokens[1]
            except Exception:
                await message.channel.send(
                    "Couldn't understand that. Expected '!groups liquipedia-url'."
                )
                return
            seconds = await handle_group_lookup(url, message.channel)
            await self.add_response(message)

        elif message.content.startswith("!events") and is_staff(message.author):
            rleb_settings.rleb_log_info("DISCORD: Starting event lookup.")
            tokens = message.content.split()
            formatter = 'reddit'
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

        elif message.content.startswith("!tasks") and is_staff(message.author):
            rleb_settings.rleb_log_info("DISCORD: Starting task lookup.")
            tokens = message.content.split()
            user = message.author.name.lower() + '#' + message.author.discriminator
            try:
                user = tokens[1]
            except Exception:
                pass
            await handle_task_lookup(message.channel, self, user)
            await self.add_response(message)

        elif message.content.startswith("!meme"):
            await self.send_meme(message.channel)
            await self.add_response(message)


def start(threads):
    """Spawns the various discord asyncio threads.

    Args:
        threads (List of Thread): List of threads used for monitoring both health.
    """
    client = RLEsportsBot(threads)

    # Create asyncronoush discord tasks.
    client.loop.create_task(client.check_new_submissions())
    client.loop.create_task(client.check_new_trello_actions())
    client.loop.create_task(client.check_new_modmail())
    client.loop.create_task(client.check_new_alerts())

    # Start listening to discord commands.
    client.run(rleb_settings.TOKEN)
