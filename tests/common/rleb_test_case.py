import unittest
import unittest.mock as mock
from unittest.mock import AsyncMock, patch

import praw
import requests

from data_bridge import Data, Remindme

from ..common import common_utils


class RLEBTestCase(unittest.TestCase):
    """RLEB Test Case."""

    def setUp(self):
        super().setUp()

        # Patch praw and postgreSQL.
        self.mock_reddit = patch("praw.Reddit").start()
        self.data_stub = AsyncMock(spec=Data)
        self.mock_data = patch("data_bridge.Data.singleton", return_value=self.data_stub).start()

        self.addCleanup(self.mock_reddit.stop)
        self.addCleanup(self.mock_data.stop)

        # Stubs.
        self.stub_db()
        self.stub_praw()
        self.stub_network()

    def stub_network(self):
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

    def stub_db(self):
        self.data_stub.read_triflairs.return_value = [(":NRG:",), (":G2:",), (":C9:",)]
        self.data_stub.write_remindme.return_value = Remindme(1, "tester#123", "message lol", 123, 321)

    def stub_praw(self):
        mock_moderator = mock.Mock(auto_spec=praw.models.Redditor)
        mock_moderator.name = "mr_mod"

        mock_sub = mock.Mock(spec=praw.models.Subreddit)
        mock_sub.return_value.moderator.return_value = [mock_moderator]

        self.mock_reddit.return_value.subreddit = mock_sub