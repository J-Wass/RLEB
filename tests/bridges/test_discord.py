# Dumb hack to be able to access source code files on both windows and linux
import sys
import os

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/..")

import unittest
import unittest.mock as mock
from unittest.mock import MagicMock, patch, call

import requests
import discord
from threading import Thread
import asyncio


class TestDiscord(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

        # Mock asyncio.sleep to speed up tests (discord_bridge has 10-second startup delays for some tasks while the bot connects to discord)
        self.original_sleep = __import__("asyncio").sleep

        async def mock_sleep(delay):
            if delay >= 1:  # Mock long sleeps (startup delays)
                await self.original_sleep(0.001)  # Near-instant
            else:
                await self.original_sleep(delay)  # Keep short sleeps as-is

        self.sleep_patcher = patch("asyncio.sleep", new=mock_sleep)
        self.sleep_patcher.start()
        self.addCleanup(self.sleep_patcher.stop)

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
        # Mock wait_until_ready to return immediately in tests
        self.discord_client.wait_until_ready = mock.AsyncMock()

        self.discord_thread = Thread(
            target=self.discord_client.run,
            args=(global_settings.TOKEN,),
            name="Discord Test Thread",
        )
        self.discord_thread.setDaemon(True)

        global_settings.colors = [0x2644CE]

        # Speed up tests by reducing sleep times
        global_settings.discord_async_interval_seconds = 0.01

        # Manually create a mock reddit_bridge, since on_ready() is not called in tests.
        global_settings.reddit_bridge = mock.AsyncMock()

    async def test_reads_new_submissions(self):
        # Build a mock embed.
        self.mock_embed = patch("discord.Embed").start()
        self.addCleanup(self.mock_embed)

        self.mock_embedded_object = mock.Mock(autospec=discord.Embed)
        self.mock_embed.return_value = self.mock_embedded_object

        global_settings.reddit_bridge = mock.AsyncMock()

        # Build a mock reddit submission.
        mock_submission = mock.Mock()
        mock_submission.id = "submission_id"
        mock_submission.title = "title"
        mock_submission.permalink = "/r/permalink"
        mock_submission.author.name = "author"
        mock_submission.link_flair_text = "general"

        async def mock_get_submissions():
            yield mock_submission
            # After yielding once, disable to break the while loop
            global_settings.discord_check_new_submission_enabled = False

        global_settings.reddit_bridge.get_submissions = mock_get_submissions
        global_settings.discord_check_new_submission_enabled = True

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

        global_settings.reddit_bridge = mock.AsyncMock()

        # Build a mock reddit comment.
        mock_comment = mock.Mock()
        mock_comment.body = "test comment from verified user"
        mock_comment.permalink = "/r/permalink"
        mock_comment.author.name = "author"

        # Mock the async generator to yield our test comment then stop
        async def mock_stream_verified_comments():
            yield mock_comment
            # After yielding once, disable to break the while loop
            global_settings.discord_check_new_verified_comments_enabled = False

        global_settings.reddit_bridge.get_comments = mock_stream_verified_comments

        global_settings.discord_check_new_verified_comments_enabled = True

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

        global_settings.reddit_bridge = mock.AsyncMock()

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

        # Mock the async generators
        async def mock_stream_modlog():
            return
            yield  # Make this a generator

        async def mock_stream_modmail():
            yield mock_modmail
            # After yielding once, disable to break the while loop
            global_settings.discord_check_new_modmail_enabled = False

        global_settings.reddit_bridge.get_mod_logs = mock_stream_modlog
        global_settings.reddit_bridge.get_modmail = mock_stream_modmail

        global_settings.discord_check_new_modmail_enabled = True

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

        global_settings.reddit_bridge = mock.AsyncMock()

        # Build a mock reddit modlog.
        mock_modlog = mock.Mock()
        mock_modlog.id = "title"
        mock_modlog.details = "details"
        mock_modlog.mod = "mod"
        mock_modlog.description = "description"
        mock_modlog.target_title = "title"
        mock_modlog.target_author = "author"
        mock_modlog.action = "approvecomment"

        # Mock the async generators
        async def mock_stream_modlog():
            yield mock_modlog
            # After yielding once, disable to break the while loop
            global_settings.discord_check_new_modmail_enabled = False

        async def mock_stream_modmail():
            return
            yield  # Make this a generator

        global_settings.reddit_bridge.get_mod_logs = mock_stream_modlog
        global_settings.reddit_bridge.get_modmail = mock_stream_modmail

        global_settings.discord_check_new_modmail_enabled = True

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

    async def test_reads_new_roster_change_submission(self):
        # Build a mock embed.
        self.mock_embed = patch("discord.Embed").start()
        self.addCleanup(self.mock_embed)

        self.mock_embedded_object = mock.Mock(autospec=discord.Embed)
        self.mock_embed.return_value = self.mock_embedded_object

        global_settings.reddit_bridge = mock.AsyncMock()

        # Build a mock reddit submission.
        mock_submission = mock.Mock()
        mock_submission.title = "title"
        mock_submission.id = "submission_id"
        mock_submission.permalink = "/r/permalink"
        mock_submission.author.name = "author"
        mock_submission.link_flair_text = "roster news"

        # Mock the async generator to yield our test submission then stop
        async def mock_stream_submissions():
            yield mock_submission
            # After yielding once, disable to break the while loop
            global_settings.discord_check_new_submission_enabled = False

        global_settings.reddit_bridge.get_submissions = mock_stream_submissions
        global_settings.discord_check_new_submission_enabled = True

        await self.discord_client.check_new_submissions()
        self.discord_client.new_post_channel.send.assert_awaited_once_with(
            embed=self.mock_embedded_object
        )
        self.discord_client.roster_news_channel.send.assert_awaited_once_with(
            embed=self.mock_embedded_object
        )


if __name__ == "__main__":
    unittest.main()
