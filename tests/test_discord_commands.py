# Dumb hack to be able to access source code files on both windows and linux
from threading import Thread
import discord
from tests.common.rleb_async_test_case import RLEBAsyncTestCase
from unittest.mock import patch, call
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

        # Import rleb_discord after setUp is done so that rleb_settings loads with mocks/patches.
        global rleb_settings
        global rleb_discord
        import rleb_settings
        import rleb_discord

        self.discord_client = rleb_discord.RLEsportsBot([])
        self.mock_channel = mock.MagicMock(discord.TextChannel)

        self.discord_thread = Thread(
            target=self.discord_client.run,
            args=(rleb_settings.TOKEN,),
            name="Discord Test Thread",
        )
        self.discord_thread.setDaemon(True)

        # Otherwise, we'd need to add !debug before each command.
        rleb_settings.RUNNING_MODE = "production"
        rleb_settings.verified_moderators = ["test_mod#1"]
        rleb_settings.hooks = ["Hook"]

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

    @mock.patch("rleb_discord.handle_flair_census")
    async def test_census(self, mock_rleb_census):

        # Users can't use census
        await self._send_message("!census 5 ,", from_staff_user=False)
        mock_rleb_census.assert_not_awaited()
        mock_rleb_census.reset_mock()

        # Mod can use census
        await self._send_message("!census 5 ,", from_staff_user=True)
        mock_rleb_census.assert_awaited_once_with(
            rleb_settings.sub, 5, self.mock_channel, ","
        )
        mock_rleb_census.reset_mock()

        # Census works without optional divider
        await self._send_message("!census 10", from_staff_user=True)
        mock_rleb_census.assert_awaited_once_with(
            rleb_settings.sub, 10, self.mock_channel, ","
        )

    async def test_triflairs(self):
        # sending emoji instead of ":flair:"
        await self._send_message("!triflairs add 😄", from_staff_user=True)
        self.mock_channel.send.assert_awaited_with(
            "Couldn't understand that. Make sure you are passing a :flair_code: and not an emoji 😭. You may have to disable Discord Nitro or auto emoji."
        )
        self.mock_channel.reset_mock()
