# Dumb hack to be able to access source code files on both windows and linux
import sys
import os

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/..")

import unittest
import unittest.mock as mock
from unittest.mock import patch, call

from tests.common.rleb_async_test_case import RLEBAsyncTestCase

import requests
import discord
from threading import Thread
from queue import Queue


class TestDiscord(RLEBAsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

        # Import rleb_discord after setUp is done so that rleb_settings loads with mocks/patches.
        global rleb_settings
        global rleb_discord
        import rleb_settings
        import rleb_discord

        self.discord_client = rleb_discord.RLEsportsBot([])
        self.discord_client.new_post_channel = mock.AsyncMock()
        self.discord_client.roster_news_channel = mock.AsyncMock()
        self.discord_client.modmail_channel = mock.AsyncMock()
        self.discord_client.bot_command_channel = mock.AsyncMock()

        # Used for passing reddit submissions from reddit to discord.
        submissions_queue = Queue()
        # Used for passing trello actions from reddit to discord.
        trello_queue = Queue()
        # Used for passing modmail from reddit to discord.
        modmail_queue = Queue()
        # Used for passing alerts from reddit to discord.
        alert_queue = Queue()

        rleb_settings.queues['submissions'] = submissions_queue
        rleb_settings.queues['trello'] = trello_queue
        rleb_settings.queues['modmail'] = modmail_queue
        rleb_settings.queues['alerts'] = alert_queue

        rleb_settings.colors = [0x2644ce]

        rleb_settings.discord_async_interval_seconds = 1

    async def test_reads_new_submissions(self):
        # Build a mock embed.
        self.mock_embed = patch("discord.Embed").start()
        self.addCleanup(self.mock_embed)

        self.mock_embedded_object = mock.Mock(autospec=discord.Embed)
        self.mock_embed.return_value = self.mock_embedded_object

        # Build a mock reddit submission.
        mock_submission = mock.Mock()
        mock_submission.title = "title"
        mock_submission.permalink = "/r/permalink"
        mock_submission.author.name = "author"
        mock_submission.link_flair_text = "general"

        # Add the submission to the queue.
        rleb_settings.queues['submissions'].put(mock_submission)

        rleb_settings.discord_check_new_submission_enabled = False

        await self.discord_client.check_new_submissions()
        self.discord_client.new_post_channel.send.assert_awaited_once_with(
            embed=self.mock_embedded_object)
        self.discord_client.roster_news_channel.assert_not_awaited()

    async def test_reads_new_modmail(self):
        # Build a mock embed.
        self.mock_embed = patch("discord.Embed").start()
        self.addCleanup(self.mock_embed)

        self.mock_embedded_object = mock.Mock(autospec=discord.Embed)
        self.mock_embed.return_value = self.mock_embedded_object

        # Build a mock reddit modmail.
        mock_modmail = mock.Mock()
        mock_modmail.id = "title"
        mock_modmail.subject = "modmail subject"
        mock_modmail.body = "modmail body"
        mock_modmail.author.name = "author"

        # Add the modmail to the queue.
        rleb_settings.queues['modmail'].put(mock_modmail)

        rleb_settings.discord_check_new_modmail_enabled = False

        await self.discord_client.check_new_modmail()

        self.discord_client.modmail_channel.send.assert_has_awaits([
            call(embed=self.mock_embedded_object),
            call('author: "modmail body"'),
            call('--------------------------------------------------------')
        ])

    async def test_reads_new_alerts(self):
        # Add the alert to the queue.
        rleb_settings.queues['alerts'].put('this is a test alert')

        rleb_settings.discord_check_new_alerts_enabled = False

        await self.discord_client.check_new_alerts()

        self.discord_client.bot_command_channel.send.assert_awaited_with(
            'ALERT: this is a test alert')

    async def test_reads_new_roster_change_submission(self):
        # Build a mock embed.
        self.mock_embed = patch("discord.Embed").start()
        self.addCleanup(self.mock_embed)

        self.mock_embedded_object = mock.Mock(autospec=discord.Embed)
        self.mock_embed.return_value = self.mock_embedded_object

        # Build a mock reddit submission.
        mock_submission = mock.Mock()
        mock_submission.title = "title"
        mock_submission.permalink = "/r/permalink"
        mock_submission.author.name = "author"
        mock_submission.link_flair_text = "roster news"

        # Add the submission to the queue.
        rleb_settings.queues['submissions'].put(mock_submission)

        rleb_settings.discord_check_new_submission_enabled = False

        await self.discord_client.check_new_submissions()
        self.discord_client.new_post_channel.send.assert_awaited_once_with(
            embed=self.mock_embedded_object)
        self.discord_client.roster_news_channel.send.assert_awaited_once_with(
            embed=self.mock_embedded_object)


if __name__ == '__main__':
    unittest.main()
