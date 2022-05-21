# Dumb hack to be able to access source code files on both windows and linux
import sys
import os

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/..")

import unittest
import unittest.mock as mock
from unittest.mock import patch
from tests.common.rleb_test_case import RLEBTestCase

from queue import Queue
import praw
from datetime import datetime


class TestReddit(RLEBTestCase):
    def setUp(self):
        super().setUp()

        # import rleb_reddit after setUp is done so that rleb_settings loads with mocks/patches
        global rleb_reddit
        global rleb_settings
        global rleb_triflairs
        import rleb_reddit
        import rleb_settings
        import rleb_triflairs

        rleb_settings.queues["submissions"] = Queue()
        rleb_settings.queues["modmail"] = Queue()
        rleb_settings.queues["modlog"] = Queue()
        rleb_settings.thread_restart_interval_seconds = 0

    def test_read_new_submissions(self):
        rleb_settings.read_new_submissions_enabled = False

        mock_submission = mock.Mock(spec=praw.models.Submission)
        mock_submission.created_utc = datetime.now().timestamp()

        def mock_submissions(args=[]):
            """Mock method for sub.stream.submissions()."""
            return [mock_submission]

        # Mock the new submissions stream to be an array of 1.
        mock_sub = patch.object(
            rleb_reddit.sub.stream, "submissions", new=mock_submissions
        ).start()
        self.addCleanup(mock_sub)

        # Assert that the new submissions is in the submissions queue after the method.
        self.assertEqual(rleb_settings.queues["submissions"].qsize(), 0)
        rleb_reddit.read_new_submissions()
        self.assertEqual(rleb_settings.queues["submissions"].qsize(), 1)

        submission_from_queue = rleb_settings.queues["submissions"].get()
        self.assertEqual(submission_from_queue, mock_submission)

    def test_monitor_subreddit(self):
        rleb_settings.monitor_subreddit_enabled = False

        mock_inbox_item = mock.Mock(spec=praw.models.Message)
        mock_inbox_item.subject = "flair request"
        mock_inbox_item.body = "flair request body"
        mock_inbox_item.author = "some_user"

        def mock_inbox_stream(args=[]):
            """Mock method for sub.stream.submissions()."""
            return [mock_inbox_item]

        # Mock the inbox stream to be an array of 1.
        inbox_stream = patch.object(
            rleb_reddit.r.inbox, "stream", new=mock_inbox_stream
        ).start()
        self.addCleanup(inbox_stream)

        # Assert that dualflairs was called.
        mock_dualflairs = patch.object(rleb_reddit, "handle_flair_request").start()
        self.addCleanup(mock_dualflairs)
        rleb_reddit.monitor_subreddit()
        mock_dualflairs.assert_called_once_with(
            rleb_settings.sub, "some_user", "flair request body"
        )

    def test_monitor_modmail(self):
        rleb_settings.monitor_modmail_enabled = False
        rleb_settings.modmail_polling_interval_seconds = 0

        mock_modmail_item = mock.Mock()
        mock_modmail_item.id = "123"

        def mock_modmail_stream(args=[]):
            """Mock method for sub.stream.submissions()."""
            return [mock_modmail_item]

        # Mock the modmail stream to be an array of 1.
        modmail_stream = patch.object(
            rleb_reddit.sub.mod, "unread", new=mock_modmail_stream
        ).start()
        self.addCleanup(modmail_stream)

        # Assert that the new modmail is in the modmail queue after the method.
        self.assertEqual(rleb_settings.queues["modmail"].qsize(), 0)
        rleb_reddit.monitor_modmail()
        self.assertEqual(rleb_settings.queues["modmail"].qsize(), 1)

        modmail_from_queue = rleb_settings.queues["modmail"].get()
        self.assertEqual(modmail_from_queue, mock_modmail_item)

    def test_monitor_modmail_for_multiflair(self):
        rleb_settings.monitor_modmail_enabled = False
        rleb_settings.modmail_polling_interval_seconds = 0

        mock_user = mock.Mock()
        mock_modmail_item = mock.Mock()
        mock_modmail_item.id = "123"
        mock_modmail_item.subject = "triflair"
        mock_modmail_item.body = ":NRG: :G2:"
        mock_modmail_item.author = mock_user

        mock_sub_flair = mock.MagicMock()
        rleb_settings.sub.flair = mock_sub_flair

        def mock_modmail_stream(args=[]):
            """Mock method for sub.stream.submissions()."""
            return [mock_modmail_item]

        # Mock the modmail stream to be an array of 1.
        modmail_stream = patch.object(
            rleb_reddit.sub.mod, "unread", new=mock_modmail_stream
        ).start()
        self.addCleanup(modmail_stream)

        # Assert that the new modmail is in the modmail queue after the method.
        self.assertEqual(rleb_settings.queues["modmail"].qsize(), 0)

        rleb_reddit.monitor_modmail()
        self.assertEqual(rleb_settings.queues["modmail"].qsize(), 0)

        mock_sub_flair.set.assert_called_once_with(
            mock_user, text=":NRG: :G2:", css_class=""
        )

    def test_monitor_modlog(self):
        rleb_settings.monitor_modlog_enabled = False
        rleb_settings.modmail_polling_interval_seconds = 0

        mock_modlog_item = mock.Mock()
        mock_modlog_item.id = "123"
        mock_modlog_item.action = "removecomment"

        def mock_modlog_stream(
            args=[], pause_after=None, skip_existing=True, attribute_name="id"
        ):
            """Mock method for sub.stream.submissions()."""
            return [mock_modlog_item]

        # Mock the modmail stream to be an array of 1.
        modlog_stream = patch.object(
            praw.models.util, "stream_generator", new=mock_modlog_stream
        ).start()
        self.addCleanup(modlog_stream)

        # Assert that the new modmail is in the modmail queue after the method.
        self.assertEqual(rleb_settings.queues["modlog"].qsize(), 0)
        rleb_reddit.monitor_modlog()
        self.assertEqual(rleb_settings.queues["modlog"].qsize(), 1)

        modlog_from_queue = rleb_settings.queues["modlog"].get()
        self.assertEqual(modlog_from_queue, mock_modlog_item)

    def test_monitor_modlog_unallowed_action(self):
        rleb_settings.monitor_modlog_enabled = False
        rleb_settings.modmail_polling_interval_seconds = 0

        mock_modlog_item = mock.Mock()
        mock_modlog_item.id = "123"
        mock_modlog_item.action = "unallowed action"

        def mock_modlog_stream(
            args=[], pause_after=None, skip_existing=True, attribute_name="id"
        ):
            """Mock method for sub.stream.submissions()."""
            return [mock_modlog_item]

        # Mock the modmail stream to be an array of 1.
        modlog_stream = patch.object(
            praw.models.util, "stream_generator", new=mock_modlog_stream
        ).start()
        self.addCleanup(modlog_stream)

        # Assert that the new modmail is in the modmail queue after the method.
        self.assertEqual(rleb_settings.queues["modlog"].qsize(), 0)
        rleb_reddit.monitor_modlog()
        self.assertEqual(rleb_settings.queues["modlog"].qsize(), 0)


if __name__ == "__main__":
    unittest.main()
