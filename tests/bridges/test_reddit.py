import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os
from datetime import datetime
import asyncio

# Add parent directory to path so we can import modules
sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/../..")

from reddit_bridge import RedditBridge, multiflair_request_keys
import global_settings


class TestRedditBridge(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Mock global settings
        self.mock_settings = patch("global_settings.rleb_log_info").start()
        self.mock_error = patch("global_settings.rleb_log_error").start()

        # Mock the Data singleton used in handle_flair_request
        self.mock_data_cls = patch("reddit_bridge.Data").start()
        self.mock_data_instance = self.mock_data_cls.singleton.return_value

        # Mock asyncpraw.Reddit
        self.mock_reddit_cls = patch("reddit_bridge.asyncpraw.Reddit").start()
        self.mock_reddit = self.mock_reddit_cls.return_value

        # Create instance of RedditBridge
        self.bridge = RedditBridge(
            "client_id", "secret", "agent", "user", "pass", "test_sub"
        )

        # Mock the subreddit object that gets created in start()
        self.mock_subreddit = AsyncMock()
        self.bridge.subreddit = self.mock_subreddit

        # Setup mock streams on the bridge instance directly for testing
        self.bridge.submission_stream = AsyncMock()
        self.bridge.comment_stream = AsyncMock()
        self.bridge.inbox_stream = AsyncMock()
        self.bridge.modmail_stream = AsyncMock()
        self.bridge.mod_log = AsyncMock()

        # Reset lists
        self.bridge.comments = []
        self.bridge.submissions = []
        self.bridge.mod_logs = []
        self.bridge.conversations = []
        self.bridge.moderators = []

    async def asyncTearDown(self):
        patch.stopall()

    async def test_start(self):
        """Test that start() initializes the subreddit and streams."""
        # Mock the reddit.subreddit coroutine
        self.mock_reddit.subreddit = AsyncMock(return_value=self.mock_subreddit)

        # Mock the stream generators to just be empty async iterators so start() doesn't hang if it iterates
        self.mock_subreddit.stream.submissions = MagicMock()
        self.mock_subreddit.stream.comments = MagicMock()
        self.mock_reddit.inbox.stream = MagicMock()
        self.mock_subreddit.mod.stream.modmail_conversations = MagicMock()
        self.mock_subreddit.mod.stream.log = MagicMock()

        # Mock get_moderators since it's called in start
        self.bridge.get_moderators = AsyncMock()

        # We need to prevent the event loop from actually scheduling the infinite tasks
        with patch("asyncio.get_event_loop") as mock_loop:
            await self.bridge.start()

            self.mock_reddit.subreddit.assert_called_with("test_sub")
            self.mock_subreddit.load.assert_called_once()

            # Verify create_task was called for the 5 loops
            self.assertEqual(mock_loop.return_value.create_task.call_count, 5)

    async def test_stream_new_submissions(self):
        """Test appending new submissions to the list."""
        mock_sub = MagicMock()
        mock_sub.title = "Test Submission"

        # Setup the stream to yield one submission.
        async def mock_stream_gen():
            yield mock_sub

        self.bridge.submission_stream = mock_stream_gen()

        # The method is an infinite loop, run it as a task.
        task = asyncio.create_task(self.bridge.stream_new_submissions())

        # Let the task run long enough to process the one item.
        await asyncio.sleep(0.1)

        # The task should have processed the submission and be stuck in a busy loop
        # because the async generator is exhausted.
        self.assertEqual(len(self.bridge.submissions), 1)
        self.assertEqual(self.bridge.submissions[0].title, "Test Submission")

        # Cancel the task to prevent the test from hanging.
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass  # Expected

    async def test_stream_verified_comments(self):
        """Test filtering of verified comments."""
        global_settings.verified_needle = "verified"

        # Comment 1: Verified
        comment_verified = MagicMock()
        comment_verified.author = "verified_user"

        # Comment 2: Not Verified
        comment_normie = MagicMock()
        comment_normie.author = "normie_user"

        # Mock the flair call
        async def mock_flair_gen(author):
            if author == "verified_user":
                yield {"flair_text": "verified pro"}
            else:
                yield {"flair_text": "random fan"}

        self.bridge.subreddit.flair = mock_flair_gen  # type: ignore

        async def mock_stream_gen():
            yield comment_verified
            yield comment_normie
            yield None

        self.bridge.comment_stream = mock_stream_gen()

        task = asyncio.create_task(self.bridge.stream_verified_comments())

        await asyncio.sleep(0.1)

        self.assertEqual(len(self.bridge.comments), 1)
        self.assertEqual(self.bridge.comments[0].author, "verified_user")

        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass  # Expected

    async def test_process_inbox_flair_request(self):
        """Test processing a flair request from inbox."""
        mock_message = MagicMock()
        mock_message.subject = (
            "Flair Request"  # Matches a key in multiflair_request_keys
        )
        mock_message.body = ":NRG: :G2:"
        mock_message.author = "fan_boy"

        async def mock_stream_gen():
            yield mock_message
            yield None

        self.bridge.inbox_stream = mock_stream_gen()
        self.bridge.handle_flair_request = AsyncMock()

        task = asyncio.create_task(self.bridge.process_inbox())

        await asyncio.sleep(0.1)

        # Should verify handle_flair_request was called
        self.bridge.handle_flair_request.assert_called_once_with(
            mock_message.author, mock_message.body
        )

        # Verify message marked as read
        self.bridge.reddit.inbox.mark_read.assert_called_once()  # type: ignore

        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass  # Expected

    async def test_stream_modmail_flair_request(self):
        """Test modmail stream handling a flair request."""
        mock_convo = MagicMock()
        mock_convo.subject = "Triflair Request"
        mock_convo.id = "123"
        mock_convo.messages = [MagicMock(body_markdown="body", author="user")]
        mock_convo.authors = ["user"]
        mock_convo.load = AsyncMock()
        mock_convo.reply = AsyncMock()
        mock_convo.archive = AsyncMock()

        async def mock_stream_gen():
            yield mock_convo
            yield None

        self.bridge.modmail_stream = mock_stream_gen()
        self.bridge.handle_flair_request = AsyncMock(
            return_value={"Succeeded": True, "Message": "Done"}
        )

        task = asyncio.create_task(self.bridge.stream_modmail())

        await asyncio.sleep(0.1)

        self.bridge.handle_flair_request.assert_called_once()
        mock_convo.reply.assert_called_with("Done")
        mock_convo.archive.assert_called()

        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass  # Expected

    async def test_stream_modmail_removal_reason(self):
        """Test modmail stream filtering removal reasons."""
        mock_convo = MagicMock()
        mock_convo.subject = "Your comment was removed from /r/RocketLeagueEsports"
        # Only 1 message means it's just the notification, not a reply
        mock_convo.messages = [MagicMock()]

        async def mock_stream_gen():
            yield mock_convo
            yield None

        self.bridge.modmail_stream = mock_stream_gen()

        task = asyncio.create_task(self.bridge.stream_modmail())

        await asyncio.sleep(0.1)

        # Should NOT be added to conversations list
        self.assertEqual(len(self.bridge.conversations), 0)

        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass  # Expected

    async def test_handle_flair_request_success(self):
        """Test the logic for handling a valid flair request."""
        # Setup Data stub to return allowed flairs
        self.mock_data_instance.read_triflairs.return_value = [(":NRG:",), (":G2:",)]

        user = MagicMock()
        user.name = "TestUser"
        body = "Can I have :NRG: and :G2: please"

        # User is not a moderator
        self.bridge.moderators = []

        result = await self.bridge.handle_flair_request(user, body)

        self.assertTrue(result["Succeeded"])
        self.assertIn(":NRG:", result["Message"])
        self.assertIn(":G2:", result["Message"])

        # Verify set call
        self.bridge.subreddit.flair.set.assert_called_once()
        _, kwargs = self.bridge.subreddit.flair.set.call_args
        self.assertEqual(kwargs["text"], ":NRG: :G2:")

    async def test_handle_flair_request_too_many(self):
        """Test rejection when too many flairs are requested."""
        self.mock_data_instance.read_triflairs.return_value = [
            (":A:",),
            (":B:",),
            (":C:",),
            (":D:",),
        ]
        global_settings.number_of_allowed_flairs = 2

        user = MagicMock()
        user.name = "GreedyUser"
        body = ":A: :B: :C:"

        result = await self.bridge.handle_flair_request(user, body)

        self.assertFalse(result["Succeeded"])
        self.assertIn("limit is 2", result["Message"])
        self.bridge.subreddit.flair.set.assert_not_called()

    async def test_handle_flair_request_invalid_flair(self):
        """Test rejection when requesting an invalid flair."""
        self.mock_data_instance.read_triflairs.return_value = [(":NRG:",)]

        user = MagicMock()
        user.name = "ConfusedUser"
        body = ":NRG: :Invalid:"

        result = await self.bridge.handle_flair_request(user, body)

        self.assertFalse(result["Succeeded"])
        self.assertIn("not allowed", result["Message"])
        self.assertIn(":Invalid:", result["Message"])

    async def test_stream_modlog_appends_log(self):
        """Test that a valid mod log is appended."""
        global_settings.filtered_mod_log = ["some_bot"]
        global_settings.allowed_mod_actions = ["removelink"]

        mock_log = MagicMock()
        mock_log.mod = "a_moderator"
        mock_log.action = "removelink"
        mock_log.id = "1"

        async def mock_stream_gen():
            yield mock_log

        self.bridge.mod_log = mock_stream_gen()

        task = asyncio.create_task(self.bridge.stream_modlog())
        await asyncio.sleep(0.1)

        self.assertEqual(len(self.bridge.mod_logs), 1)
        self.assertEqual(self.bridge.mod_logs[0].id, "1")

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def test_stream_modlog_ignores_filtered_mod(self):
        """Test that a mod log from a filtered mod is ignored."""
        global_settings.filtered_mod_log = ["filtered_bot"]
        global_settings.allowed_mod_actions = ["removelink"]

        mock_log = MagicMock()
        mock_log.mod = "filtered_bot"
        mock_log.action = "removelink"
        mock_log.id = "1"

        async def mock_stream_gen():
            yield mock_log

        self.bridge.mod_log = mock_stream_gen()

        task = asyncio.create_task(self.bridge.stream_modlog())
        await asyncio.sleep(0.1)

        self.assertEqual(len(self.bridge.mod_logs), 0)

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def test_stream_modlog_ignores_disallowed_action(self):
        """Test that a mod log with a disallowed action is ignored."""
        global_settings.filtered_mod_log = ["some_bot"]
        global_settings.allowed_mod_actions = ["removelink"]

        mock_log = MagicMock()
        mock_log.mod = "a_moderator"
        mock_log.action = "approvelink"
        mock_log.id = "1"

        async def mock_stream_gen():
            yield mock_log

        self.bridge.mod_log = mock_stream_gen()

        task = asyncio.create_task(self.bridge.stream_modlog())
        await asyncio.sleep(0.1)

        self.assertEqual(len(self.bridge.mod_logs), 0)

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
