# Dumb hack to be able to access source code files on both windows and linux
import sys
import os

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/..")

import unittest
import unittest.mock as mock
from unittest.mock import patch, call

from tests.common.rleb_async_test_case import RLEBAsyncTestCase

import requests
import discord


class MockRequest:
    """Mock request class for stubbing requests.get()."""

    def __init__(self, content):
        self.content = content


class TestGroupLookup(RLEBAsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

        # Import rleb_group_lookup after setUp is done so that rleb_settings loads with mocks/patches.
        global rleb_stdout
        global rleb_group_lookup
        import rleb_stdout
        from rleb_liqui import rleb_group_lookup

    async def test_group_lookup(self):
        mock_channel = mock.Mock(spec=discord.TextChannel)

        with patch.object(rleb_stdout, "print_to_channel") as mocked_print_to_channel:
            await rleb_group_lookup.handle_group_lookup(
                "https://liquipedia.net/rocketleague/Rocket_League_Championship_Series/Season_X/Spring/Oceania",
                mock_channel,
            )

            expected_markup = "|||||\n|:-|:-|:-|:-|\n|**#**|**Group A** &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; |**Matches** |**Game Diff** |\n|1|[**Ground Zero Gaming**](https://liquipedia.net/rocketleague/Ground_Zero_Gaming)|4-0|+10|\n|2|[**Cringe Society**](https://liquipedia.net/rocketleague/Cringe_Society)|3-1|+1|\n|3|[**LG Dire Wolves**](https://liquipedia.net/rocketleague/Dire_Wolves)|1-3|-3|\n|4|[**R!OT Gaming**](https://liquipedia.net/rocketleague/R!OT_Gaming)|1-3|-3|\n|5|[**Overt**](https://liquipedia.net/rocketleague/Overt)|1-3|-5|\n\n&#x200B;\n\n|||||\n|:-|:-|:-|:-|\n|**#**|**Group B** &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; &#x200B; |**Matches** |**Game Diff** |\n|1|[**Renegades**](https://liquipedia.net/rocketleague/Renegades)|3-1|+6|\n|2|[**Mindfreak**](https://liquipedia.net/rocketleague/Mindfreak)|3-1|+4|\n|3|[**Canberra Havoc**](https://liquipedia.net/rocketleague/Canberra_Havoc)|2-2|-1|\n|4|[**Team Eros**](https://liquipedia.net/rocketleague/Team_Eros)|2-2|-1|\n|5|[**Donkey squad**](https://liquipedia.net/rocketleague/Donkey_squad)|0-4|-8|\n\n&#x200B;\n\n"
            mocked_print_to_channel.assert_awaited_once_with(
                mock_channel, expected_markup, title="Groups"
            )

    async def test_group_lookup_fails(self):

        # Mock the liquipedia page to return nothing.
        def mock_liquipedia(args=[]):
            return None

        mock_request = patch.object(requests, "get", new=mock_liquipedia).start()
        self.addCleanup(mock_request)

        mock_channel = mock.Mock(spec=discord.TextChannel)
        await rleb_group_lookup.handle_group_lookup("bad url", mock_channel)
        mock_channel.send.assert_awaited_once_with(
            "Couldn't load bad url!\nError: list index out of range"
        )


if __name__ == "__main__":
    unittest.main()
