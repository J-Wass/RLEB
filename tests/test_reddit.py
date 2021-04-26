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

class TestReddit(RLEBTestCase):
    def setUp(self):
        super().setUp()

        # import rleb_reddit after setUp is done so that rleb_settings loads with mocks/patches
        global rleb_reddit
        global rleb_settings
        import rleb_reddit
        import rleb_settings
        rleb_settings.queues['submissions'] = Queue()
        rleb_settings.queues['modmail'] = Queue()
        rleb_settings.thread_restart_interval_seconds = 0
        

    def test_read_new_submissions(self):
        rleb_settings.submissions_startup_delay = 0
        rleb_settings.read_new_submissions_enabled = False

        mock_submission = mock.Mock(spec=praw.models.Submission)
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



if __name__ == '__main__':
    unittest.main()
