import unittest
import unittest.mock as mock
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

import psycopg2
import praw


class RLEBAsyncTestCase(IsolatedAsyncioTestCase):
    """RLEB Test Case."""
    async def asyncSetUp(self):
        super().setUp()

        # Patch praw and postgreSQL.
        self.mock_reddit = patch("praw.Reddit").start()
        self.mock_db = patch("psycopg2.connect").start()
        self.addCleanup(self.mock_reddit.stop)
        self.addCleanup(self.mock_db)

        # Stubs.
        self.stub_psycopg2()
        self.stub_praw()

    def stub_psycopg2(self):
        mock_cursor = mock.Mock()
        mock_cursor.execute.return_value = ""
        mock_cursor.fetchall.return_value = [(":NRG:", ), (":G2:", ),
                                             (":C9:", )]

        self.mock_db.return_value.cursor.return_value = mock_cursor

    def stub_praw(self):
        mock_moderator = mock.Mock(auto_spec=praw.models.Redditor)
        mock_moderator.name = "mr_mod"

        mock_sub = mock.Mock(spec=praw.models.Subreddit)
        mock_sub.return_value.moderator.return_value = [mock_moderator]

        self.mock_reddit.return_value.subreddit = mock_sub