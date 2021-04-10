import unittest
import unittest.mock as mock
from unittest.mock import patch

import psycopg2
import praw

class RLEBTestCase(unittest.TestCase):
    """RLEB Test Case."""

    def setUp(self):
        # Patchers.
        reddit_init_patcher = patch("praw.Reddit")
        psycopg2_connect_patcher = patch("psycopg2.connect")
        psycopg2_extras_execute_values_patcher = patch("psycopg2.extras.execute_values")
        mock_reddit_init = reddit_init_patcher.start()
        mock_psycopg2_connect = psycopg2_connect_patcher.start()
        mock_psycopg2_extras_execute_values = psycopg2_extras_execute_values_patcher.start()
        self.addCleanup(reddit_init_patcher.stop)
        self.addCleanup(psycopg2_connect_patcher.stop)
        self.addCleanup(psycopg2_extras_execute_values_patcher.stop)

        # Build some mock objects.
        self.mock_db = mock.Mock()
        self.mock_reddit = mock.Mock(spec=praw.Reddit)

        # Send mocks through patches.
        mock_psycopg2_connect.return_value = self.mock_db
        mock_reddit_init.return_value = self.mock_reddit
        mock_psycopg2_extras_execute_values.return_value = mock.Mock()

        # Stub everything.
        self.stub_psycopg2()
        self.stub_praw()
        return super().setUp()

    def stub_psycopg2(self):
        """Mock postgreSQL to return certain values."""
        mock_cursor = mock.Mock()
        self.mock_db.cursor.return_value = mock_cursor
        self.mock_db.commit.return_value = ""

        mock_cursor.execute.return_value = ""
        mock_cursor.fetchall.return_value = [(":NRG:",), (":G2:",), (":C9:",)]

    def stub_praw(self):
        mock_sub = mock.Mock(spec=praw.models.Subreddit)
        self.mock_reddit.return_value.subreddit = mock_sub

        mock_moderator = mock.Mock()
        mock_sub.moderator.return_value = [mock_moderator]
        mock_moderator.name.return_value = "These_Voices"
        

