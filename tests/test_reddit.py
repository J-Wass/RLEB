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
        global rleb_dualflairs
        import rleb_reddit
        import rleb_settings
        import rleb_dualflairs
        rleb_settings.queues['submissions'] = Queue()
        rleb_settings.queues['modmail'] = Queue()
        rleb_settings.thread_restart_interval_seconds = 0

    def test_read_new_submissions(self):
        rleb_settings.read_new_submissions_enabled = False

        mock_submission = mock.Mock(spec=praw.models.Submission)
        mock_submission.created_utc = datetime.now().timestamp()

        def mock_submissions(args=[]):
            """ Mock method for sub.stream.submissions()."""
            return [mock_submission]

        # Mock the new submissions stream to be an array of 1.
        mock_sub = patch.object(rleb_reddit.sub.stream,
                                "submissions",
                                new=mock_submissions).start()
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
            """ Mock method for sub.stream.submissions()."""
            return [mock_inbox_item]

        # Mock the inbox stream to be an array of 1.
        inbox_stream = patch.object(rleb_reddit.r.inbox,
                                    "stream",
                                    new=mock_inbox_stream).start()
        self.addCleanup(inbox_stream)

        # Assert that dualflairs was called.
        mock_dualflairs = patch.object(rleb_reddit, "handle_dualflair").start()
        self.addCleanup(mock_dualflairs)
        rleb_reddit.monitor_subreddit()
        mock_dualflairs.assert_called_once_with(rleb_settings.sub, "some_user",
                                                "flair request body")

    def test_monitor_modmail(self):
        rleb_settings.monitor_modmail_enabled = False
        rleb_settings.modmail_polling_interval_seconds = 0

        mock_modmail_item = mock.Mock()
        mock_modmail_item.id = "123"

        def mock_modmail_stream(args=[]):
            """ Mock method for sub.stream.submissions()."""
            return [mock_modmail_item]

        # Mock the modmail stream to be an array of 1.
        modmail_stream = patch.object(rleb_reddit.sub.mod,
                                      "unread",
                                      new=mock_modmail_stream).start()
        self.addCleanup(modmail_stream)

        # Assert that the new modmail is in the modmail queue after the method.
        self.assertEqual(rleb_settings.queues["modmail"].qsize(), 0)
        rleb_reddit.monitor_modmail()
        self.assertEqual(rleb_settings.queues["modmail"].qsize(), 1)

        modmail_from_queue = rleb_settings.queues["modmail"].get()
        self.assertEqual(modmail_from_queue, mock_modmail_item)


if __name__ == '__main__':
    unittest.main()
