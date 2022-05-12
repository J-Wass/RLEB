# Dumb hack to be able to access source code files on both windows and linux
import sys
import os
from typing import Tuple

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/..")

import unittest
import unittest.mock as mock
from unittest.mock import patch, call
from tests.common.rleb_async_test_case import RLEBAsyncTestCase

import json
import google
import discord


class TestTasks(RLEBAsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

        # import rleb_tasks after setUp is done so that rleb_settings loads with mocks/patches
        global rleb_tasks
        global rleb_settings
        import rleb_tasks
        import rleb_settings

        # Set up mock objects.
        self.mock_service = mock.Mock()
        self.mock_sheet_query = mock.Mock()
        self.mock_values = mock.Mock()
        self.mock_sheet = mock.Mock()
        with open("tests/resources/google_sheets_response.json", "r") as f:
            self.mock_sheet_query.execute.return_value = json.load(f)

        self.mock_values.get.return_value = self.mock_sheet_query
        self.mock_sheet.values.return_value = self.mock_values
        self.mock_service.spreadsheets.return_value = self.mock_sheet

        def mock_build(calendar=None, version=None, credentials=None):
            return self.mock_service

        self.mock_credentials = mock.Mock()

        rleb_settings.greetings = ["Incoming!"]

        def mock_from_service_account_info(args=[], scopes=None):
            return self.mock_credentials

        # Patch google sheet apis with the mocks.
        credentials = patch.object(
            google.oauth2.service_account.Credentials,
            "from_service_account_info",
            new=mock_from_service_account_info,
        ).start()
        self.addCleanup(credentials)

        build = patch.object(rleb_tasks, "build", new=mock_build).start()
        self.addCleanup(build)

    async def test_tasks(self):
        mock_channel = mock.AsyncMock(spec=discord.TextChannel)
        mock_client = mock.Mock()
        user = "voices#6380"
        await rleb_tasks.handle_task_lookup(mock_channel, mock_client, user)

        event1_discord_markup = "**cool event** (Tuesday 2021-06-01)\n✏️ Creator/Scheduler (Schedule UTC): **hawkkn#0408**\n🚔 Updaters/Monitors: **ds0308#9530**, **voices#6380**\n\n-----------------------------------------------------------\n\n"
        event2_discord_markup = "**Weekly Points Standings** (Monday 2021-05-03)\n📌 Sticky: **No sticky**\n✏️ Creator/Scheduler (Post 16:00 UTC): **voices#6380**\n🚔 Updaters/Monitors: **No one needed**, **No one needed**\n\n-----------------------------------------------------------\n\n"
        mock_channel.send.assert_has_awaits(
            [call(event1_discord_markup), call(event2_discord_markup)]
        )

    async def test_task_all(self):
        mock_channel = mock.AsyncMock(spec=discord.TextChannel)
        mock_client = mock.Mock()
        user = "all"
        await rleb_tasks.handle_task_lookup(mock_channel, mock_client, user)

        event1_discord_markup = "**cool event** (Tuesday 2021-06-01)\n✏️ Creator/Scheduler (Schedule UTC): **hawkkn#0408**\n🚔 Updaters/Monitors: **ds0308#9530**, **voices#6380**\n\n-----------------------------------------------------------\n\n"
        event2_discord_markup = "**Weekly Points Standings** (Monday 2021-05-03)\n📌 Sticky: **No sticky**\n✏️ Creator/Scheduler (Post 16:00 UTC): **voices#6380**\n🚔 Updaters/Monitors: **No one needed**, **No one needed**\n\n-----------------------------------------------------------\n\n"
        event3_discord_markup = "**Weekly Schedule/Ask Questions** (Monday 2021-05-03)\n📌 Sticky: **First sticky**\n✏️ Creator/Scheduler (Schedule 10:00 UTC): **hawkkn#0408**\n🚔 Updaters/Monitors: **No one needed**, **No one needed**\n\n-----------------------------------------------------------\n\n"
        mock_channel.send.assert_has_awaits(
            [
                call(event1_discord_markup),
                call(event3_discord_markup),
                call(event2_discord_markup),
            ]
        )

    async def test_task_broadcast(self):
        mock_channel = mock.AsyncMock(spec=discord.TextChannel)

        # Set up a bunch of mocked members to map usernames to ids.
        mock_voices_member = mock.Mock()
        mock_voices_member.name = "voices"
        mock_voices_member.discriminator = "6380"
        mock_voices_member.id = 345639629459816458

        mock_hawknn_member = mock.Mock()
        mock_hawknn_member.name = "hawkkn"
        mock_hawknn_member.discriminator = "0408"
        mock_hawknn_member.id = 364941319296253954

        mock_channel.members = [mock_voices_member, mock_hawknn_member]

        # Set up mocked discord users to broadcast to.
        mock_voices = mock.AsyncMock(spec=discord.User)
        mock_hawkkn = mock.AsyncMock(spec=discord.User)

        def mock_get_user(id):
            if id == 364941319296253954:
                return mock_hawkkn
            if id == 345639629459816458:
                return mock_voices
            return None

        mock_client = mock.Mock()
        mock_client.get_user = mock_get_user

        await rleb_tasks.handle_task_lookup(
            mock_channel, mock_client, "broadcast", None
        )

        greeting = "Incoming!\n\n"
        event1_discord_markup = "**cool event** (Tuesday 2021-06-01)\n✏️ Creator/Scheduler (Schedule UTC): **hawkkn#0408**\n🚔 Updaters/Monitors: **ds0308#9530**, **voices#6380**\n\n-----------------------------------------------------------\n\n"
        event2_discord_markup = "**Weekly Points Standings** (Monday 2021-05-03)\n📌 Sticky: **No sticky**\n✏️ Creator/Scheduler (Post 16:00 UTC): **voices#6380**\n🚔 Updaters/Monitors: **No one needed**, **No one needed**\n\n-----------------------------------------------------------\n\n"
        event3_discord_markup = "**Weekly Schedule/Ask Questions** (Monday 2021-05-03)\n📌 Sticky: **First sticky**\n✏️ Creator/Scheduler (Schedule 10:00 UTC): **hawkkn#0408**\n🚔 Updaters/Monitors: **No one needed**, **No one needed**\n\n-----------------------------------------------------------\n\n"
        mock_voices.send.assert_awaited_once_with(
            greeting + event1_discord_markup + event2_discord_markup
        )
        mock_hawkkn.send.assert_awaited_once_with(
            greeting + event1_discord_markup + event3_discord_markup
        )

    async def test_task_send(self):
        mock_channel = mock.AsyncMock(spec=discord.TextChannel)

        # Set up a bunch of mocked members to map usernames to ids.
        mock_voices_member = mock.Mock()
        mock_voices_member.name = "voices"
        mock_voices_member.discriminator = "6380"
        mock_voices_member.id = 345639629459816458

        mock_hawknn_member = mock.Mock()
        mock_hawknn_member.name = "hawkkn"
        mock_hawknn_member.discriminator = "0408"
        mock_hawknn_member.id = 364941319296253954

        mock_channel.members = [mock_voices_member, mock_hawknn_member]

        # Set up mocked discord users to broadcast to.
        mock_voices = mock.AsyncMock(spec=discord.User)
        mock_hawkkn = mock.AsyncMock(spec=discord.User)

        def mock_get_user(id):
            if id == 364941319296253954:
                return mock_hawkkn
            if id == 345639629459816458:
                return mock_voices
            return None

        mock_client = mock.Mock()
        mock_client.get_user = mock_get_user

        await rleb_tasks.handle_task_lookup(
            mock_channel, mock_client, "send", extra="voices#6380"
        )

        greeting = "Incoming!\n\n"
        event1_discord_markup = "**cool event** (Tuesday 2021-06-01)\n✏️ Creator/Scheduler (Schedule UTC): **hawkkn#0408**\n🚔 Updaters/Monitors: **ds0308#9530**, **voices#6380**\n\n-----------------------------------------------------------\n\n"
        event2_discord_markup = "**Weekly Points Standings** (Monday 2021-05-03)\n📌 Sticky: **No sticky**\n✏️ Creator/Scheduler (Post 16:00 UTC): **voices#6380**\n🚔 Updaters/Monitors: **No one needed**, **No one needed**\n\n-----------------------------------------------------------\n\n"
        event3_discord_markup = "**Weekly Schedule/Ask Questions** (Monday 2021-05-03)\n📌 Sticky: **First sticky**\n✏️ Creator/Scheduler (Schedule 10:00 UTC): **hawkkn#0408**\n🚔 Updaters/Monitors: **No one needed**, **No one needed**\n\n-----------------------------------------------------------\n\n"
        mock_voices.send.assert_awaited_once_with(
            greeting + event1_discord_markup + event2_discord_markup
        )

        mock_hawkkn.send.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
