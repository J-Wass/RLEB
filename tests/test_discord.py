# Dumb hack to be able to access source code files on both windows and linux
import sys
import os

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/..")

import unittest
import unittest.mock as mock
from unittest.mock import MagicMock, patch, call

from tests.common.rleb_async_test_case import RLEBAsyncTestCase

import requests
import discord
from threading import Thread
from queue import Queue


class TestDiscord(RLEBAsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

        # Import discord_bridge after setUp is done so that rleb_settings loads with mocks/patches.
        global global_settings
        global discord_bridge
        import global_settings
        import discord_bridge

        self.discord_client = discord_bridge.RLEsportsBot()
        self.discord_client.new_post_channel = mock.AsyncMock()
        self.discord_client.verified_comments_channel = mock.AsyncMock()
        self.discord_client.roster_news_channel = mock.AsyncMock()
        self.discord_client.modmail_channel = mock.AsyncMock()
        self.discord_client.modlog_channel = mock.AsyncMock()
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

        # Used for passing reddit submissions from reddit to discord.
        submissions_queue = Queue()
        # Used for passing modmail from reddit to discord.
        modmail_queue = Queue()
        # Used for passing alerts from reddit to discord.
        alert_queue = Queue()
        # Used for passing alerts from reddit to discord.
        verified_comments_queue = Queue()

        global_settings.queues["submissions"] = submissions_queue
        global_settings.queues["verified_comments"] = verified_comments_queue
        global_settings.queues["modmail"] = modmail_queue
        global_settings.queues["alerts"] = alert_queue
        global_settings.queues["modlog"] = Queue()

        global_settings.colors = [0x2644CE]

        global_settings.discord_async_interval_seconds = 1

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
        global_settings.queues["submissions"].put(mock_submission)

        global_settings.discord_check_new_submission_enabled = False

        await self.discord_client.check_new_submissions()
        self.discord_client.new_post_channel.send.assert_awaited_once_with(
            embed=self.mock_embedded_object
        )
        self.discord_client.roster_news_channel.assert_not_awaited()

    async def test_reads_new_verified_coments(self):
        # Build a mock embed.
        self.mock_embed = patch("discord.Embed").start()
        self.addCleanup(self.mock_embed)

        self.mock_embedded_object = mock.Mock(autospec=discord.Embed)
        self.mock_embed.return_value = self.mock_embedded_object

        # Build a mock reddit submission.
        mock_submission = mock.Mock()
        mock_submission.body = "test comment from verified user"
        mock_submission.permalink = "/r/permalink"
        mock_submission.author.name = "author"

        # Add the submission to the queue.
        global_settings.queues["verified_comments"].put(mock_submission)

        global_settings.discord_check_new_verified_comments_enabled = False

        await self.discord_client.check_new_verified_comments()
        self.discord_client.verified_comments_channel.send.assert_awaited_once_with(
            embed=self.mock_embedded_object
        )
        self.discord_client.roster_news_channel.assert_not_awaited()

    async def test_reads_new_modmail(self):
        # Build a mock embed.
        self.mock_embed = patch("discord.Embed").start()
        self.addCleanup(self.mock_embed)

        self.mock_embedded_object = mock.Mock(autospec=discord.Embed)
        self.mock_embed.return_value = self.mock_embedded_object

        # Build a mock reddit modmail.
        mock_author = mock.Mock()
        mock_author.name = "author"

        mock_message = mock.Mock()
        mock_message.body_markdown = "modmail body"

        mock_modmail = mock.Mock()
        mock_modmail.id = "title"
        mock_modmail.subject = "modmail subject"
        mock_modmail.messages = [mock_message]
        mock_modmail.authors = [mock_author]
        mock_modmail.parent_id = None

        # Add the modmail to the queue.
        global_settings.queues["modmail"].put(mock_modmail)

        global_settings.discord_check_new_modmail_enabled = False

        await self.discord_client.check_new_modfeed()

        self.mock_embed.assert_called_with(
            title="Created: 'modmail subject'",
            url="https://mod.reddit.com/mail/all",
            color=0x2644CE,
        )
        self.mock_embedded_object.set_author.assert_called_with(name="author")
        self.assertEqual(
            self.mock_embedded_object.description,
            f"modmail body\n--------------------------------------------------------",
        )

        self.discord_client.modmail_channel.send.assert_has_awaits(
            [
                call(embed=self.mock_embedded_object),
            ]
        )

    async def test_reads_new_modlogs(self):
        # Build a mock embed.
        self.mock_embed = patch("discord.Embed").start()
        self.addCleanup(self.mock_embed)

        self.mock_embedded_object = mock.Mock(autospec=discord.Embed)
        self.mock_embed.return_value = self.mock_embedded_object

        # Build a mock reddit modlog.
        mock_modlog = mock.Mock()
        mock_modlog.id = "title"
        mock_modlog.details = "details"
        mock_modlog.mod = "mod"
        mock_modlog.description = "description"
        mock_modlog.target_title = "title"
        mock_modlog.target_author = "author"
        mock_modlog.action = "approvecomment"

        # Add the modmail to the queue.
        global_settings.queues["modlog"].put(mock_modlog)

        global_settings.discord_check_new_modmail_enabled = False

        await self.discord_client.check_new_modfeed()

        self.mock_embed.assert_called_with(
            title="Approvecomment",
            url="https://www.reddit.com/r/RocketLeagueEsports/about/log/",
            color=2507982,
        )
        self.mock_embedded_object.set_author.assert_called_with(name="mod")

        self.assertEqual(
            self.mock_embedded_object.description,
            "**Title**: title\n**User**: author\n**Description**: description\n**Extra Details**: details\n--------------------------------------------------------",
        )
        self.discord_client.modlog_channel.send.assert_has_awaits(
            [
                call(embed=self.mock_embedded_object),
            ]
        )

    async def test_reads_new_alerts(self):
        # Add the alert to the queue.
        global_settings.queues["alerts"].put(("this is a test alert", 123))

        global_settings.discord_check_new_alerts_enabled = False

        await self.discord_client.check_new_alerts()
        self.discord_client.bot_command_channel.send.assert_awaited_with(
            "this is a test alert"
        )

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
        global_settings.queues["submissions"].put(mock_submission)

        global_settings.discord_check_new_submission_enabled = False

        await self.discord_client.check_new_submissions()
        self.discord_client.new_post_channel.send.assert_awaited_once_with(
            embed=self.mock_embedded_object
        )
        self.discord_client.roster_news_channel.send.assert_awaited_once_with(
            embed=self.mock_embedded_object
        )


if __name__ == "__main__":
    unittest.main()
