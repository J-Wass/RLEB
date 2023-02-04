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

        self.discord_client = discord_bridge.RLEsportsBot()
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

    async def test_bracket_e2e(self):
        # Not staff.
        await self._send_message("!bracket", from_staff_user=False)
        self.mock_channel.send.assert_not_awaited()
        self.mock_channel.reset_mock()

        # Missing liqui url.
        await self._send_message("!bracket", from_staff_user=True)
        self.mock_channel.send.assert_awaited_with(
            "Couldn't understand that. Expected '!bracket liquipedia-url day-number'."
        )
        self.mock_channel.reset_mock()

        # Happy path.
        await self._send_message(
            "!bracket https://liquipedia.net/rocketleague/Rocket_League_Championship_Series/2021-22/Winter 1",
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

    @mock.patch("discord_bridge.handle_team_lookup")
    async def test_teams(self, mock_handle_team_lookup):
        # Happy path.
        await self._send_message("!teams url", from_staff_user=True)
        mock_handle_team_lookup.assert_awaited_with("url", self.mock_channel)
        mock_handle_team_lookup.reset_mock()

        # No url.
        await self._send_message("!teams", from_staff_user=True)
        self.mock_channel.send.assert_awaited_with(
            "Couldn't understand that. Expected '!teams liquipedia-url'."
        )
        self.mock_channel.send.reset_mock()
        mock_handle_team_lookup.assert_not_awaited()

        # Not a mod.
        await self._send_message("!teams url", from_staff_user=False)
        self.mock_channel.send.assert_not_awaited()
        mock_handle_team_lookup.assert_not_awaited()

    @mock.patch("discord_bridge.handle_swiss_lookup")
    async def test_swiss(self, mock_handle_swiss_lookup):
        # Happy path.
        await self._send_message("!swiss url", from_staff_user=True)
        mock_handle_swiss_lookup.assert_awaited_with("url", self.mock_channel)
        mock_handle_swiss_lookup.reset_mock()

        # No url.
        await self._send_message("!swiss", from_staff_user=True)
        self.mock_channel.send.assert_awaited_with(
            "Couldn't understand that. Expected '!swiss liquipedia-url'."
        )
        self.mock_channel.send.reset_mock()
        mock_handle_swiss_lookup.assert_not_awaited()

        # Not a mod.
        await self._send_message("!swiss url", from_staff_user=False)
        self.mock_channel.send.assert_not_awaited()
        mock_handle_swiss_lookup.assert_not_awaited()

    @mock.patch("discord_bridge.handle_coverage_lookup")
    async def test_coverage(self, mock_handle_coverage_lookup):
        # Happy path.
        await self._send_message("!coverage url", from_staff_user=True)
        mock_handle_coverage_lookup.assert_awaited_with("url", self.mock_channel)
        mock_handle_coverage_lookup.reset_mock()

        # No url.
        await self._send_message("!coverage", from_staff_user=True)
        self.mock_channel.send.assert_awaited_with(
            "Couldn't understand that. Expected '!coverage liquipedia-url'."
        )
        self.mock_channel.send.reset_mock()
        mock_handle_coverage_lookup.assert_not_awaited()

        # Not a mod.
        await self._send_message("!coverage url", from_staff_user=False)
        self.mock_channel.send.assert_not_awaited()
        mock_handle_coverage_lookup.assert_not_awaited()

    @mock.patch("discord_bridge.handle_bracket_lookup")
    async def test_bracket(self, mock_handle_bracket_lookup):
        # Happy path.
        await self._send_message("!bracket url 1", from_staff_user=True)
        mock_handle_bracket_lookup.assert_awaited_with("url", self.mock_channel, '1')
        mock_handle_bracket_lookup.reset_mock()

        # No url.
        await self._send_message("!bracket", from_staff_user=True)
        self.mock_channel.send.assert_awaited_with(
            "Couldn't understand that. Expected '!bracket liquipedia-url day-number'."
        )
        self.mock_channel.send.reset_mock()
        mock_handle_bracket_lookup.assert_not_awaited()

        # Not a mod.
        await self._send_message("!bracket url 1", from_staff_user=False)
        self.mock_channel.send.assert_not_awaited()
        mock_handle_bracket_lookup.assert_not_awaited()

    @mock.patch("discord_bridge.handle_group_lookup")
    async def test_groups(self, mock_handle_group_lookup):
        # Happy path.
        await self._send_message("!groups url", from_staff_user=True)
        mock_handle_group_lookup.assert_awaited_with("url", self.mock_channel)
        mock_handle_group_lookup.reset_mock()

        # No url.
        await self._send_message("!groups", from_staff_user=True)
        self.mock_channel.send.assert_awaited_with(
            "Couldn't understand that. Expected '!groups liquipedia-url'."
        )
        self.mock_channel.send.reset_mock()
        mock_handle_group_lookup.assert_not_awaited()

        # Not a mod.
        await self._send_message("!groups url", from_staff_user=False)
        self.mock_channel.send.assert_not_awaited()
        mock_handle_group_lookup.assert_not_awaited()

    @mock.patch("discord_bridge.handle_prizepool_lookup")
    async def skip_test_prizepool(self, mock_handle_prizepool_lookup):
        # Happy path.
        await self._send_message("!prizepool url", from_staff_user=True)
        mock_handle_prizepool_lookup.assert_awaited_with("url", self.mock_channel)
        mock_handle_prizepool_lookup.reset_mock()

        # No url.
        await self._send_message("!prizepool", from_staff_user=True)
        self.mock_channel.send.assert_awaited_with(
            "Couldn't understand that. Expected '!prizepool liquipedia-url'."
        )
        self.mock_channel.send.reset_mock()
        mock_handle_prizepool_lookup.assert_not_awaited()

        # Not a mod.
        await self._send_message("!prizepool url", from_staff_user=False)
        self.mock_channel.send.assert_not_awaited()
        mock_handle_prizepool_lookup.assert_not_awaited()

    @mock.patch("discord_bridge.handle_mvp_form_creation")
    async def test_mvp_creation(self, mock_handle_mvp_form_creation):
        # Happy path, multiple urls.
        await self._send_message("!mvp create url1 url2", from_staff_user=True)
        mock_handle_mvp_form_creation.assert_awaited_with(
            ["url1", "url2"], self.mock_channel
        )
        mock_handle_mvp_form_creation.reset_mock()

        # Happy path, one url.
        await self._send_message("!mvp create url", from_staff_user=True)
        mock_handle_mvp_form_creation.assert_awaited_with(["url"], self.mock_channel)
        mock_handle_mvp_form_creation.reset_mock()

        # No urls.
        await self._send_message("!mvp create", from_staff_user=True)
        self.mock_channel.send.assert_awaited_with(
            "Couldn't understand that. Expected '!mvp [create OR results] [list of liqui urls OR form url]'."
        )
        self.mock_channel.send.reset_mock()
        mock_handle_mvp_form_creation.assert_not_awaited()

        # Not a mod.
        await self._send_message("!mvp create url", from_staff_user=False)
        self.mock_channel.send.assert_not_awaited()
        mock_handle_mvp_form_creation.assert_not_awaited()

    @mock.patch("discord_bridge.handle_mvp_results_lookup")
    async def test_mvp_results(self, mock_handle_mvp_results_lookup):
        # Happy path.
        await self._send_message("!mvp results url", from_staff_user=True)
        mock_handle_mvp_results_lookup.assert_awaited_with("url", self.mock_channel)
        mock_handle_mvp_results_lookup.reset_mock()

        # No url.
        await self._send_message("!mvp results", from_staff_user=True)
        self.mock_channel.send.assert_awaited_with(
            "Couldn't understand that. Expected '!mvp [create OR results] [list of liqui urls OR form url]'."
        )
        self.mock_channel.send.reset_mock()
        mock_handle_mvp_results_lookup.assert_not_awaited()

        # Not a mod.
        await self._send_message("!mvp results url", from_staff_user=False)
        self.mock_channel.send.assert_not_awaited()
        self.mock_channel.reset_mock()
        mock_handle_mvp_results_lookup.assert_not_awaited()
        mock_handle_mvp_results_lookup.reset_mock()

        # Not create or results.
        await self._send_message("!mvp bad_option url", from_staff_user=True)
        self.mock_channel.send.assert_awaited_with(
            "Couldn't understand that. Expected either 'create' or 'results' in the second parameter. Ex) '!mvp create liqui_url_1 liqui_url_2'."
        )
        mock_handle_mvp_results_lookup.assert_not_awaited()

    @mock.patch("discord_bridge.handle_calendar_lookup")
    async def test_events(self, mock_handle_calendar_lookup):
        # Happy path: reddit
        await self._send_message("!events reddit 4", from_staff_user=True)
        mock_handle_calendar_lookup.assert_awaited_with(self.mock_channel, "reddit", 4)
        mock_handle_calendar_lookup.reset_mock()

        # Happy path: sheets
        await self._send_message("!events sheets 4", from_staff_user=True)
        mock_handle_calendar_lookup.assert_awaited_with(self.mock_channel, "sheets", 4)
        mock_handle_calendar_lookup.reset_mock()

        # Missing number of days
        await self._send_message("!events sheets", from_staff_user=True)
        self.mock_channel.send.assert_awaited_with(
            "Couldn't understand that. Expected '!events [formatter] [# days]'. Example is '!events reddit 7' to get the next 7 days of events. Valid formatters are `reddit` and `sheets`."
        )
        self.mock_channel.send.reset_mock()
        mock_handle_calendar_lookup.assert_not_awaited()
        mock_handle_calendar_lookup.reset_mock()

        # Not a mod.
        await self._send_message("!events sheets 4", from_staff_user=False)
        self.mock_channel.send.assert_not_awaited()
        mock_handle_calendar_lookup.assert_not_awaited()
