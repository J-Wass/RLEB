# coding: utf-8

# Dumb hack to be able to access source code files on both windows and linux
import discord
from tests.common.rleb_async_test_case import RLEBAsyncTestCase
from unittest.mock import patch
import unittest.mock as mock
import unittest
import sys
import os

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/..")


class TestBracketLookup(RLEBAsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

        # Import rleb_bracket_lookup after setUp is done so that rleb_settings loads with mocks/patches.
        global stdout
        global bracket_lookup
        import stdout
        from liqui import bracket_lookup

    async def test_bracket(self):
        mock_channel = mock.Mock(spec=discord.TextChannel)

        with patch.object(stdout, "print_to_channel") as mocked_print_to_channel:
            await bracket_lookup.handle_bracket_lookup(
                "https://liquipedia.net/rocketleague/Rocket_League_Championship_Series/2021-22/Winter",
                mock_channel,
                1,
            )

            expected_markup = "\n|**Elimination**|**UTC**|[**Liquipedia Bracket**](https://liquipedia.net/rocketleague/Rocket_League_Championship_Series/2021-22/Winter#Results)|\n|:-|:-|:-|\n|`▼ Upper Semis`||`(Bo?)`|\n|`▼ Upper Final`||`(Bo?)`|\n|`▼ Grand Final`||`(Bo?)`|\n|`▼ Lower Round 1`||`(Bo?)`|\n|`▼ Lower Round 2`||`(Bo?)`|\n|`▼ Lower Quarters`||`(Bo?)`|\n|`▼ Lower Semis`||`(Bo?)`|\n|`▼ Lower Final`||`(Bo?)`|\n|Endpoint CeX|**0 - 3**|**FaZe Clan**|\n|**Team Queso**|**3 - 2**|The General NRG|\n|**Team BDS**|**3 - 2**|Pioneers|\n|Dignitas|**2 - 3**|**Evil Geniuses**|\n|**Team Queso**|**3 - 0**|Evil Geniuses|\n|**FaZe Clan**|**3 - 0**|Team BDS|\n|FURIA|**2 - 4**|**G2 Esports**|\n|Version1|**2 - 4**|**Spacestation**|\n|FURIA|**3 - 4**|**Team Queso**|\n|Version1|**3 - 4**|**FaZe Clan**|\n|Spacestation|**1 - 4**|**G2 Esports**|\n|FaZe Clan|**1 - 4**|**Team Queso**|\n|Spacestation|**3 - 4**|**Team Queso**|\n|G2 Esports|**3 - 4**|**Team Queso**|"
            mocked_print_to_channel.assert_awaited_once_with(
                mock_channel,
                expected_markup,
                title="Elimination Bracket",
                force_pastebin=True,
            )

    async def test_not_started_bracket(self):
        mock_channel = mock.Mock(spec=discord.TextChannel)

        with patch.object(stdout, "print_to_channel") as mocked_print_to_channel:
            await bracket_lookup.handle_bracket_lookup(
                "https://liquipedia.net/rocketleague/RL_Oceania/ANZAC_Day_Invitational/2022",
                mock_channel,
                1,
            )

            expected_markup = "\n|**Elimination**|**UTC**|[**Liquipedia Bracket**](https://liquipedia.net/rocketleague/RL_Oceania/ANZAC_Day_Invitational/2022#Results)|\n|:-|:-|:-|\n|`▼ Quarter-Finals`||`(Bo?)`|\n|`▼ Semi-Finals`||`(Bo?)`|\n|`▼ Final`||`(Bo?)`|\n|Dire Wolves|[**07:00 UTC**](https://www.google.com/search?q=07:00 UTC)|Team Bliss|\n|Kaka's Minions|[**07:45 UTC**](https://www.google.com/search?q=07:45 UTC)|Three One Two's|\n|Pioneers|[**08:30 UTC**](https://www.google.com/search?q=08:30 UTC)|TBD|\n|us r bad|[**09:30 UTC**](https://www.google.com/search?q=09:30 UTC)|TBD|\n|TBD|[**10:30 UTC**](https://www.google.com/search?q=10:30 UTC)|TBD|"
            mocked_print_to_channel.assert_awaited_once_with(
                mock_channel,
                expected_markup,
                title="Elimination Bracket",
                force_pastebin=True,
            )


if __name__ == "__main__":
    unittest.main()
