import sys
import os

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/../..")

import unittest
import unittest.mock as mock
from unittest.mock import patch, AsyncMock
from ..common import common_utils


import requests
import discord

from data_bridge import Data


class MockRequest:
    """Mock request class for stubbing requests.get()."""

    def __init__(self, content):
        self.content = content


class TestGroupLookup(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

        self.data_stub = AsyncMock(spec=Data)
        self.mock_data = patch(
            "data_bridge.Data.singleton", return_value=self.data_stub
        ).start()

        self.stub_network()

        # Import rleb_group_lookup after setUp is done so that rleb_settings loads with mocks/patches.
        global stdout
        global group_lookup
        import stdout
        from liqui import group_lookup

    def stub_network(self):
        self.network_map = common_utils.common_proxies
        self.forced_status_code = 200
        # Cache file contents to avoid repeated I/O
        self._file_cache = {}

        def mock_request(url=None, headers=None, data=None, json=None, args=[]):
            if url is None:
                return

            local_file_proxy = self.network_map.get(url)

            if local_file_proxy:
                # Use cache if available
                if local_file_proxy not in self._file_cache:
                    with open(local_file_proxy, encoding="utf8") as f:
                        self._file_cache[local_file_proxy] = f.read()

                return common_utils.MockRequest(
                    self._file_cache[local_file_proxy],
                    status_code=self.forced_status_code,
                )

        self.mock_requests_get = patch.object(requests, "get", new=mock_request).start()
        self.mock_requests_post = patch.object(
            requests, "post", new=mock_request
        ).start()
        self.addCleanup(self.mock_requests_get)
        self.addCleanup(self.mock_requests_post)

    async def skip_test_group_lookup(self):
        mock_channel = mock.Mock(spec=discord.TextChannel)

        with patch.object(stdout, "print_to_channel") as mocked_print_to_channel:
            await group_lookup.handle_group_lookup(
                "https://liquipedia.net/rocketleague/Rocket_League_Championship_Series/Season_X/Spring/Oceania",
                mock_channel,
            )

            expected_markup = "|||||\n|:-|:-|:-|:-|\n|**#**|**Group A** &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; |**Matches** |**Game Diff** |\n|1|[**Ground Zero Gaming**](https://liquipedia.net/rocketleague/Ground_Zero_Gaming)|4-0|+10|\n|2|[**Cringe Society**](https://liquipedia.net/rocketleague/Cringe_Society)|3-1|+1|\n|3|[**LG Dire Wolves**](https://liquipedia.net/rocketleague/Dire_Wolves)|1-3|-3|\n|4|[**R!OT Gaming**](https://liquipedia.net/rocketleague/R!OT_Gaming)|1-3|-3|\n|5|[**Overt**](https://liquipedia.net/rocketleague/Overt)|1-3|-5|\n\n&#x200B;\n\n|||||\n|:-|:-|:-|:-|\n|**#**|**Group B** &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; |**Matches** |**Game Diff** |\n|1|[**Renegades**](https://liquipedia.net/rocketleague/Renegades)|3-1|+6|\n|2|[**Mindfreak**](https://liquipedia.net/rocketleague/Mindfreak)|3-1|+4|\n|3|[**Canberra Havoc**](https://liquipedia.net/rocketleague/Canberra_Havoc)|2-2|-1|\n|4|[**Team Eros**](https://liquipedia.net/rocketleague/Team_Eros)|2-2|-1|\n|5|[**Donkey squad**](https://liquipedia.net/rocketleague/Donkey_squad)|0-4|-8|\n\n&#x200B;\n\n"
            mocked_print_to_channel.assert_awaited_with(
                mock_channel, expected_markup, title="Groups"
            )

    async def test_group_lookup_fails(self):
        # Mock the liquipedia page to return nothing.
        def mock_liquipedia(args=[]):
            return None

        bad_url = "bad url"
        mock_request = patch.object(requests, "get", new=mock_liquipedia).start()
        self.addCleanup(mock_request)

        mock_channel = mock.Mock(spec=discord.TextChannel)
        await group_lookup.handle_group_lookup("bad url", mock_channel)

        self.assertEqual(
            mock_channel.send.mock_calls,
            [
                mock.call("Building group table from Diesel..."),
                mock.call("Failed to build group table from Diesel. Trying RLEB..."),
                mock.call("Couldn't load bad url!\nError: list index out of range"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
