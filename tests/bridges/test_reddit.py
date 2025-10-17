# Dumb hack to be able to access source code files on both windows and linux
import sys
import os

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/..")

import unittest
import unittest.mock as mock
from unittest.mock import patch
from tests.common.rleb_async_test_case import RLEBAsyncTestCase
from praw.models import ModmailConversation

from queue import Queue
import praw
import asyncio
from datetime import datetime, timezone


class TestReddit(RLEBAsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

        # import rleb_reddit after setUp is done so that rleb_settings loads with mocks/patches
        global reddit_bridge
        global global_settings
        global triflairs
        import reddit_bridge
        import global_settings
        import triflairs

        global_settings.thread_restart_interval_seconds = 0

    async def test_stream_new_submissions(self):
        mock_submission = mock.Mock(spec=praw.models.Submission)
        mock_submission.created_utc = datetime.now().timestamp()

        def mock_submissions(pause_after=0):
            """Mock method for sub.stream.submissions()."""
            yield mock_submission
            yield None  # PRAW streams yield None when pause_after is used

        # Mock the new submissions stream
        mock_sub = patch.object(
            reddit_bridge.sub.stream, "submissions", new=mock_submissions
        ).start()
        self.addCleanup(mock_sub)

        # Collect items from the async generator
        submissions = []
        async for submission in reddit_bridge.stream_new_submissions():
            submissions.append(submission)

        self.assertEqual(len(submissions), 1)
        self.assertEqual(submissions[0], mock_submission)

    async def test_stream_new_submissions_old_submission(self):
        mock_submission = mock.Mock(spec=praw.models.Submission)
        # Old submission from 10 minutes ago
        mock_submission.created_utc = datetime.now().timestamp() - 600

        def mock_submissions(pause_after=0):
            yield mock_submission
            yield None

        mock_sub = patch.object(
            reddit_bridge.sub.stream, "submissions", new=mock_submissions
        ).start()
        self.addCleanup(mock_sub)

        # Collect submissions
        submissions = []
        async for submission in reddit_bridge.stream_new_submissions():
            submissions.append(submission)

        # Old submission should be filtered out
        self.assertEqual(len(submissions), 0)


    async def test_stream_verified_comments(self):
        global_settings.verified_needle = "verified"

        mock_comment = mock.Mock()
        mock_comment.created_utc = datetime.now().timestamp()
        mock_comment.author = "test_user"

        def mock_comments(skip_existing=True, pause_after=0):
            yield mock_comment
            yield None

        def mock_flair(user):
            return [{"flair_text": "verified user"}]

        with patch.object(reddit_bridge.sub.stream, "comments", new=mock_comments):
            # Mock sub.flair as a callable
            with patch("global_settings.sub") as mock_sub:
                mock_sub.stream.comments = mock_comments
                mock_sub.flair = mock.Mock(side_effect=mock_flair)
                # Update reddit_bridge.sub to use our mock
                with patch.object(reddit_bridge, "sub", mock_sub):
                    comments = []
                    async for comment in reddit_bridge.stream_verified_comments():
                        comments.append(comment)

                    self.assertEqual(len(comments), 1)
                    self.assertEqual(comments[0], mock_comment)

    async def test_stream_verified_comments_old_comment(self):
        mock_comment = mock.Mock()
        mock_comment.created_utc = datetime.now().timestamp() - 600

        def mock_comments(skip_existing=True, pause_after=0):
            yield mock_comment
            yield None

        with patch.object(reddit_bridge.sub.stream, "comments", new=mock_comments):
            comments = []
            async for comment in reddit_bridge.stream_verified_comments():
                comments.append(comment)

            # Old comment should be filtered out
            self.assertEqual(len(comments), 0)

    async def test_stream_verified_comments_no_verified_flair(self):
        global_settings.verified_needle = "verified"

        mock_comment = mock.Mock()
        mock_comment.created_utc = datetime.now().timestamp()
        mock_comment.author = "test_user"

        def mock_comments(skip_existing=True, pause_after=0):
            yield mock_comment
            yield None

        def mock_flair(user):
            return [{"flair_text": "regular user"}]

        with patch.object(reddit_bridge.sub.stream, "comments", new=mock_comments):
            # Mock sub.flair as a callable
            with patch("global_settings.sub") as mock_sub:
                mock_sub.stream.comments = mock_comments
                mock_sub.flair = mock.Mock(side_effect=mock_flair)
                # Update reddit_bridge.sub to use our mock
                with patch.object(reddit_bridge, "sub", mock_sub):
                    comments = []
                    async for comment in reddit_bridge.stream_verified_comments():
                        comments.append(comment)

                    # Comment without verified flair should be filtered out
                    self.assertEqual(len(comments), 0)

    async def test_process_inbox(self):
        mock_inbox_item = mock.Mock(spec=praw.models.Message)
        mock_inbox_item.subject = "flair request"
        mock_inbox_item.body = "flair request body"
        mock_inbox_item.author = "some_user"

        def mock_inbox_stream(pause_after=0):
            """Mock method for r.inbox.stream()."""
            yield mock_inbox_item
            yield None

        # Mock the inbox stream
        inbox_stream = patch.object(
            reddit_bridge.r.inbox, "stream", new=mock_inbox_stream
        ).start()
        self.addCleanup(inbox_stream)

        # Mock mark_read
        mark_read = patch.object(reddit_bridge.r.inbox, "mark_read").start()
        self.addCleanup(mark_read)

        # Mock handle_flair_request to verify it gets called
        mock_dualflairs = patch.object(reddit_bridge, "handle_flair_request").start()
        self.addCleanup(mock_dualflairs)

        # Run the process_inbox async function (not a generator)
        await reddit_bridge.process_inbox()

        mock_dualflairs.assert_called_once_with(
            global_settings.sub, "some_user", "flair request body"
        )

    async def test_stream_modmail_old_conversation(self):
        mock_modmail_item = mock.Mock(spec=ModmailConversation)
        mock_modmail_item.id = "123"
        # Old conversation from 10 minutes ago
        old_time = datetime.now(timezone.utc).timestamp() - 600
        mock_modmail_item.last_updated = datetime.fromtimestamp(old_time, tz=timezone.utc).isoformat()
        mock_modmail_item.messages = [1]
        mock_modmail_item.subject = "test"

        def mock_conversations(state="new"):
            return [mock_modmail_item]

        with patch.object(reddit_bridge.sub.modmail, "conversations", new=mock_conversations):
            modmails = []
            async for modmail in reddit_bridge.stream_modmail():
                modmails.append(modmail)

            # Old modmail should be filtered out
            self.assertEqual(len(modmails), 0)

    async def test_stream_modlog(self):
        mock_modlog_item = mock.Mock()
        mock_modlog_item.id = "123"
        mock_modlog_item.action = "removecomment"
        mock_modlog_item.mod = "some_mod"

        def mock_stream_generator(*args, **kwargs):
            """Mock for praw.models.util.stream_generator()."""
            yield mock_modlog_item
            yield None

        # Mock the stream_generator used by stream_modlog
        with patch.object(praw.models.util, "stream_generator", new=mock_stream_generator):
            # Collect items from the async generator
            modlogs = []
            async for modlog in reddit_bridge.stream_modlog():
                modlogs.append(modlog)

            self.assertEqual(len(modlogs), 1)
            self.assertEqual(modlogs[0], mock_modlog_item)


if __name__ == "__main__":
    unittest.main()
