import unittest.mock as mock
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

import praw
import requests

from ..common import common_utils


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

        # Network Proxy.
        self.network_map = common_utils.common_proxies
        self.forced_status_code = 200

        def mock_request(url=None, headers=None, data=None, json=None, args=[]):
            if url is None:
                return

            local_file_proxy = self.network_map[url]

            if local_file_proxy:
                print(f"RLEB PROXY: Redirecting {url} to {local_file_proxy}")
                with open(local_file_proxy, encoding="utf8") as f:
                    return common_utils.MockRequest(
                        f.read(), status_code=self.forced_status_code
                    )
            else:
                print(f"RLEB PROXY: Did not proxy {url}, it will hit production.")

        self.mock_requests_get = patch.object(requests, "get", new=mock_request).start()
        self.mock_requests_post = patch.object(
            requests, "post", new=mock_request
        ).start()
        self.addCleanup(self.mock_requests_get)
        self.addCleanup(self.mock_requests_post)

    def stub_psycopg2(self):
        mock_cursor = mock.Mock()
        mock_cursor.execute.return_value = ""
        mock_cursor.fetchall.return_value = [(":NRG:",), (":G2:",), (":C9:",)]
        mock_cursor.fetchone.return_value = [1]

        self.mock_db.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        self.mock_db.return_value.cursor.return_value = mock_cursor

    def stub_praw(self):
        mock_moderator = mock.Mock(auto_spec=praw.models.Redditor)
        mock_moderator.name = "mr_mod"

        mock_sub = mock.Mock(spec=praw.models.Subreddit)
        mock_sub.return_value.moderator.return_value = [mock_moderator]

        self.mock_reddit.return_value.subreddit = mock_sub
