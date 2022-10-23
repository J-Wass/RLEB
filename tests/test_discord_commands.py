# Dumb hack to be able to access source code files on both windows and linux
import queue
from threading import Thread
import time
import discord
from data_bridge import Remindme
from tests.common.rleb_async_test_case import RLEBAsyncTestCase
from unittest.mock import MagicMock
import unittest.mock as mock
import sys
import os

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/..")


class TestDiscordCommands(RLEBAsyncTestCase):
    async def _send_message(self, message: str, from_staff_user: bool = False) -> None:
        """Sends a message to discord chat, triggering bot response.

        Args:
            message (str): The discord command as string, ex '!census 4'.
            from_staff_user (bool): Whether the message came from a staff moderator.
        """
        discord_message = mock.MagicMock(spec=discord.Message)
        discord_message.content = message
        discord_message.channel = self.mock_channel

        mock_author = mock.MagicMock(spec=discord.Member)
        mock_author.roles = []
        mock_author.name = "test_user"
        mock_author.discriminator = "1"
        if from_staff_user:
            mock_author.name = "test_mod"
            mod_role = mock.MagicMock(spec=discord.Role)
            mod_role.name = "Subreddit Moderators"
            mock_author.roles.append(mod_role)

        discord_message.author = mock_author
        await self.discord_client.on_message(discord_message)

    async def asyncSetUp(self):
        await super().asyncSetUp()

        # Import discord_bridge after setUp is done so that rleb_settings loads with mocks/patches.
        global global_settings
        global discord_bridge
        import global_settings
        import discord_bridge

        self.discord_client = discord_bridge.RLEsportsBot([])
        self.mock_channel = mock.MagicMock(discord.TextChannel)
        self.mock_channel.id = 1

        self.discord_client.bot_command_channel = mock.AsyncMock()
        self.discord_client.get_channel = MagicMock(
            return_value=self.discord_client.bot_command_channel
        )

        self.discord_thread = Thread(
            target=self.discord_client.run,
            args=(global_settings.TOKEN,),
            name="Discord Test Thread",
        )
        self.discord_thread.setDaemon(True)

        # Otherwise, we'd need to add !debug before each command.
        global_settings.RUNNING_MODE = "production"
        global_settings.verified_moderators = ["test_mod#1"]

        # Remove randomness.
        global_settings.hooks = ["Hook"]
        global_settings.success_emojis = ["!"]

        global_settings.discord_async_interval_seconds = 1
        global_settings.user_names_to_ids = {"test_mod#1": 567}

    async def test_bracket(self):
        # Not staff.
        await self._send_message("!bracket", from_staff_user=False)
        self.mock_channel.send.assert_not_awaited()
        self.mock_channel.reset_mock()

        # Missing liqui url.
        await self._send_message("!bracket", from_staff_user=True)
        self.mock_channel.send.assert_awaited_with(
            "Couldn't understand that. Expected '!bracket liquipedia-url'."
        )
        self.mock_channel.reset_mock()

        # Happy path.
        await self._send_message(
            "!bracket https://liquipedia.net/rocketleague/Rocket_League_Championship_Series/2021-22/Winter",
            from_staff_user=True,
        )
        self.mock_channel.send.assert_awaited_with(
            "**Hook**: https://paste.ee/p/fake_url"
        )

    @mock.patch("discord_bridge.handle_flair_census")
    async def test_census(self, mock_rleb_census):

        # Users can't use census
        await self._send_message("!census 5 ,", from_staff_user=False)
        mock_rleb_census.assert_not_awaited()
        mock_rleb_census.reset_mock()

        # Mod can use census
        await self._send_message("!census 5 ,", from_staff_user=True)
        mock_rleb_census.assert_awaited_once_with(
            global_settings.sub, 5, self.mock_channel, ","
        )
        mock_rleb_census.reset_mock()

        # Census works without optional divider
        await self._send_message("!census 10", from_staff_user=True)
        mock_rleb_census.assert_awaited_once_with(
            global_settings.sub, 10, self.mock_channel, ","
        )

    async def test_triflairs(self):
        # sending emoji instead of ":flair:"
        await self._send_message("!triflairs add 😄", from_staff_user=True)
        self.mock_channel.send.assert_awaited_with(
            "Couldn't understand that. Make sure you are passing a :flair_code: and not an emoji 😭. You may have to disable Discord Nitro or auto emoji."
        )

    async def test_remindme(self):
        global_settings.queues["alerts"] = queue.Queue()

        # Only used by mods.
        await self._send_message("!remindme", from_staff_user=False)
        self.mock_channel.send.assert_not_awaited()
        self.mock_channel.reset_mock()

        # Create a timer.
        await self._send_message("!remindme 1s yo", from_staff_user=True)
        self.mock_channel.send.assert_awaited_with(
            "! reminder set.\nUse `!remindme list` to see all reminders."
        )
        global_settings.remindme_timers[1].cancel()
        del global_settings.remindme_timers[1]
        self.mock_channel.reset_mock()

        # Create a timer with a floating value.
        await self._send_message("!remindme 1.5s yoyo", from_staff_user=True)
        self.mock_channel.send.assert_awaited_with(
            "! reminder set.\nUse `!remindme list` to see all reminders."
        )
        global_settings.remindme_timers[1].cancel()
        del global_settings.remindme_timers[1]
        self.mock_channel.reset_mock()

        # Delete a timer.
        global_settings.schedule_remindme(
            Remindme(2, "test#mod", "msg", time.time() + 60, self.mock_channel.id)
        )
        self.assertEqual(len(global_settings.remindme_timers), 1)
        await self._send_message("!remindme delete 2", from_staff_user=True)
        self.assertEqual(len(global_settings.remindme_timers), 0)
        self.mock_channel.send.assert_awaited_with("Deleted reminder.")
        self.mock_channel.reset_mock()
