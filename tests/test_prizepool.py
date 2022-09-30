# coding: utf-8

# Dumb hack to be able to access source code files on both windows and linux
import sys
import os

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/..")

import unittest
import unittest.mock as mock
from unittest.mock import patch, call

from tests.common.rleb_async_test_case import RLEBAsyncTestCase

import discord


class TestPrizepoolLookup(RLEBAsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

        # Import rleb_swiss after setUp is done so that rleb_settings loads with mocks/patches.
        global rleb_stdout
        global rleb_prizepool_lookup
        import rleb_stdout
        from rleb_liqui import rleb_prizepool_lookup

    async def test_prizepool_complete(self):
        mock_channel = mock.Mock(spec=discord.TextChannel)

        with patch.object(rleb_prizepool_lookup, "print_to_channel") as mocked_print_to_channel:
            await rleb_prizepool_lookup.handle_prizepool_lookup(
                "https://liquipedia.net/rocketleague/Rocket_League_Championship_Series/2021-22/Spring/North_America/1",
                mock_channel,
            )

            expected_markup = "|**Place**|**Prize**|**Team**|**RLCS Points**|\n|:-|:-|:-|:-|\n|**1st** | $30,000 | G2 Esports | +401 **()** |\n|**2nd** | $20,000 | Spacestation Gaming | +350 **()** |\n|**3rd** | $10,000 | FaZe Clan | +300 **()** |\n|**4th** | $8,000 | Ghost Gaming | +250 **()** |\n|**5th-6th** | $6,000 | Version1 | +210 **()** |\n|**5th-6th** | $6,000 | Team Envy | +210 **()** |\n|**7th-8th** | $4,000 | Akrew | +180 **()** |\n|**7th-8th** | $4,000 | Rogue | +180 **()** |"
            mocked_print_to_channel.assert_awaited_once_with(
                mock_channel, expected_markup
            )

if __name__ == "__main__":
    unittest.main()
