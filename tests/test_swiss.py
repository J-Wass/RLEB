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


class MockRequest():
    """Mock request class for stubbing requests.get()."""
    def __init__(self, content):
        self.content = content


class TestSwissLookup(RLEBAsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

        # Import rleb_swiss after setUp is done so that rleb_settings loads with mocks/patches.
        global rleb_stdout
        global rleb_swiss
        import rleb_stdout
        from rleb_liqui import rleb_swiss

    async def test_swiss_complete(self):

        # Mock the liquipedia page so tests can run offline.
        def mock_liquipedia(args=[]):
            with open('tests/resources/swiss_completed.htm',
                      encoding="utf8") as f:
                return MockRequest(f.read())

        mock_request = patch.object(requests, "get",
                                    new=mock_liquipedia).start()
        self.addCleanup(mock_request)

        mock_channel = mock.Mock(spec=discord.TextChannel)

        with patch.object(rleb_stdout,
                          'print_to_channel') as mocked_print_to_channel:
            await rleb_swiss.handle_swiss_lookup('liquipedia url',
                                                      mock_channel)

            expected_markup = "|**#**|**Teams**|**W-L**|**Round 1**|**Round 2**|**Round 3**|**Round 4**|**Round 5**|\n|:-|:-|:-|:-|:-|:-|:-|:-|\n1 |[**G2**](https://liquipedia.net/rocketleague/G2_Esports)|**3-0**|✔️ 3-0 GG|✔️ 3-0 SSG|✔️ 3-0 XSET| | \n2 |[**Team Envy**](https://liquipedia.net/rocketleague/Team_Envy)|**3-0**|✔️ 3-2 SQ|✔️ 3-1 FAZE|✔️ 3-2 NRG| | \n3 |[**NRG**](https://liquipedia.net/rocketleague/NRG)|**3-1**|✔️ 3-0 NEF|✔️ 3-0 VIB|❌ 2-3 Team Envy|✔️ 3-0 GG| \n4 |[**TN**](https://liquipedia.net/rocketleague/True_Neutral)|**3-1**|✔️ 3-1 TOR|❌ 2-3 XSET|✔️ 3-2 RBG|✔️ 3-0 FAZE| \n5 |[**XSET**](https://liquipedia.net/rocketleague/XSET)|**3-1**|✔️ 3-0 RGE|✔️ 3-2 TN|❌ 0-3 G2|✔️ 3-2 TOR| \n6 |[**SSG**](https://liquipedia.net/rocketleague/Spacestation_Gaming)|**3-2**|✔️ 3-1 EU|❌ 0-3 G2|❌ 2-3 GG|✔️ 3-1 RGE|✔️ 3-1 FAZE\n7 |[**V1**](https://liquipedia.net/rocketleague/Version1)|**3-2**|❌ 1-3 VIB|✔️ 3-2 NEF|❌ 1-3 FAZE|✔️ 3-1 SQ|✔️ 3-1 TOR\n8 |[**GG**](https://liquipedia.net/rocketleague/Ghost_Gaming)|**3-2**|❌ 0-3 G2|✔️ 3-0 EU|✔️ 3-2 SSG|❌ 0-3 NRG|✔️ 3-1 VIB\n|\\-|\\- - - - -|\\- - -||||||\n9 |[**TOR**](https://liquipedia.net/rocketleague/Torrent)|**2-3**|❌ 1-3 TN|✔️ 3-1 RGE|✔️ 3-0 VIB|❌ 2-3 XSET|❌ 1-3 V1\n10 |[**FAZE**](https://liquipedia.net/rocketleague/FaZe_Clan)|**2-3**|✔️ 3-0 RBG|❌ 1-3 Team Envy|✔️ 3-1 V1|❌ 0-3 TN|❌ 1-3 SSG\n11 |[**VIB**](https://liquipedia.net/rocketleague/Vibrance)|**2-3**|✔️ 3-1 V1|❌ 0-3 NRG|❌ 0-3 TOR|✔️ 3-1 RBG|❌ 1-3 GG\n12 |[**SQ**](https://liquipedia.net/rocketleague/Susquehanna_Soniqs)|**1-3**|❌ 2-3 Team Envy|❌ 1-3 RBG|✔️ 3-0 EU|❌ 1-3 V1| \n13 |[**RBG**](https://liquipedia.net/rocketleague/RBG_Esports)|**1-3**|❌ 0-3 FAZE|✔️ 3-1 SQ|❌ 2-3 TN|❌ 1-3 VIB| \n13 |[**RGE**](https://liquipedia.net/rocketleague/Rogue)|**1-3**|❌ 0-3 XSET|❌ 1-3 TOR|✔️ 3-0 NEF|❌ 1-3 SSG| \n15 |[**NEF**](https://liquipedia.net/rocketleague/Nefarious)|**0-3**|❌ 0-3 NRG|❌ 2-3 V1|❌ 0-3 RGE| | \n16 |[**EU**](https://liquipedia.net/rocketleague/EUnited)|**0-3**|❌ 1-3 SSG|❌ 0-3 GG|❌ 0-3 SQ| | "
            mocked_print_to_channel.assert_awaited_once_with(mock_channel,
                                                             expected_markup,
                                                             title="Swiss Bracket")

    async def test_swiss_incomplete(self):

        # Mock the liquipedia page so tests can run offline.
        def mock_liquipedia(args=[]):
            with open('tests/resources/swiss_not_filled_out.htm',
                      encoding="utf8") as f:
                return MockRequest(f.read())

        mock_request = patch.object(requests, "get",
                                    new=mock_liquipedia).start()
        self.addCleanup(mock_request)

        mock_channel = mock.Mock(spec=discord.TextChannel)

        with patch.object(rleb_stdout,
                          'print_to_channel') as mocked_print_to_channel:
            await rleb_swiss.handle_swiss_lookup('liquipedia url',
                                                      mock_channel)

            expected_markup = "|**#**|**Teams**|**W-L**|**Round 1**|**Round 2**|**Round 3**|**Round 4**|**Round 5**|\n|:-|:-|:-|:-|:-|:-|:-|:-|\n |[**FaZe Clan**](https://liquipedia.net/rocketleague/FaZe_Clan)|**-**| | | | | \n |[**The General NRG**](https://liquipedia.net/rocketleague/NRG)|**-**| | | | | \n |[**Spacestation Gaming**](https://liquipedia.net/rocketleague/Spacestation_Gaming)|**-**| | | | | \n |[**Version1**](https://liquipedia.net/rocketleague/Version1)|**-**| | | | | \n |**TBD**|**-**| | | | | \n |**TBD**|**-**| | | | | \n |**TBD**|**-**| | | | | \n |**TBD**|**-**| | | | | \n|\\-|\\- - - - -|\\- - -||||||\n |**TBD**|**-**| | | | | \n |**TBD**|**-**| | | | | \n |**TBD**|**-**| | | | | \n |**TBD**|**-**| | | | | \n |**TBD**|**-**| | | | | \n |**TBD**|**-**| | | | | \n |**TBD**|**-**| | | | | \n |**TBD**|**-**| | | | | "
            mocked_print_to_channel.assert_awaited_once_with(mock_channel,
                                                             expected_markup,
                                                             title="Swiss Bracket")

    async def test_swiss_parenthesis(self):

        # Mock the liquipedia page so tests can run offline.
        def mock_liquipedia(args=[]):
            with open('tests/resources/swiss_with_parenthesis.htm',
                      encoding="utf8") as f:
                return MockRequest(f.read())

        mock_request = patch.object(requests, "get",
                                    new=mock_liquipedia).start()
        self.addCleanup(mock_request)

        mock_channel = mock.Mock(spec=discord.TextChannel)

        with patch.object(rleb_stdout,
                          'print_to_channel') as mocked_print_to_channel:
            await rleb_swiss.handle_swiss_lookup('liquipedia url',
                                                      mock_channel)

            expected_markup = "|**#**|**Teams**|**W-L**|**Round 1**|**Round 2**|**Round 3**|**Round 4**|**Round 5**|\n|:-|:-|:-|:-|:-|:-|:-|:-|\n1 |[**OP**](https://liquipedia.net/rocketleague/Orlando_Pirates_Exdee)|**3-0**|✔️ 3-0 BW|✔️ 3-0 Mist|✔️ 3-2 WAT| | \n2 |[**Orgless**](https://liquipedia.net/rocketleague/Orgless_\\(South_African_Team\\))|**3-0**|✔️ 3-2 Inferno|✔️ 3-0 ATMC|✔️ 3-2 OOR| | \n3 |[**ATK**](https://liquipedia.net/rocketleague/ATK)|**3-1**|✔️ 3-0 AUF|❌ 1-3 WAT|✔️ 3-0 EXP|✔️ 3-0 TKO| \n4 |[**OOR**](https://liquipedia.net/rocketleague/Out_of_Retirement)|**3-1**|✔️ 3-1 TKO|✔️ 3-2 EXO|❌ 2-3 Orgless|✔️ 3-1 Mist| \n4 |[**WAT**](https://liquipedia.net/rocketleague/Water)|**3-1**|✔️ 0-0 EXP|✔️ 3-1 ATK|❌ 2-3 OP|✔️ 3-0 ATMC| \n6 |[**EXO**](https://liquipedia.net/rocketleague/Exotic_Esports)|**3-2**|✔️ 3-2 LLG|❌ 2-3 OOR|❌ 2-3 TKO|✔️ 3-1 BW|✔️ 3-2 Mist\n7 |[**ATMC**](https://liquipedia.net/rocketleague/Atomic_Esports)|**3-2**|✔️ 3-2 EXP|❌ 0-3 Orgless|✔️ 3-0 LLG|❌ 0-3 WAT|✔️ 3-0 AUF\n8 |[**EXP**](https://liquipedia.net/rocketleague/Expandas)|**3-2**|❌ 2-3 ATMC|✔️ 0-0 GHST|❌ 0-3 ATK|✔️ 3-2 LLG|✔️ 3-0 TKO\n|\\-|\\- - - - -|\\- - -||||||\n9 |[**Mist**](https://liquipedia.net/rocketleague/index.php?title=Mist_\\(South_African_Team\\)&action=edit&redlink=1)|**2-3**|✔️ 0-0 GHST|❌ 0-3 OP|✔️ 3-1 Inferno|❌ 1-3 OOR|❌ 2-3 EXO\n9 |[**TKO**](https://liquipedia.net/rocketleague/index.php?title=TKO_X1&action=edit&redlink=1)|**2-3**|❌ 1-3 OOR|✔️ 3-0 AUF|✔️ 3-2 EXO|❌ 0-3 ATK|❌ 0-3 EXP\n11 |[**AUF**](https://liquipedia.net/rocketleague/index.php?title=Aufbau&action=edit&redlink=1)|**2-3**|❌ 0-3 ATK|❌ 0-3 TKO|✔️ 0-0 EXP|✔️ 3-0 Inferno|❌ 0-3 ATMC\n12 |[**Inferno**](https://liquipedia.net/rocketleague/index.php?title=Inferno_\\(South_African_Team\\)&action=edit&redlink=1)|**1-3**|❌ 2-3 Orgless|✔️ 3-0 BW|❌ 1-3 Mist|❌ 0-3 AUF| \n13 |[**LLG**](https://liquipedia.net/rocketleague/index.php?title=Lost_Legion_Giants&action=edit&redlink=1)|**1-3**|❌ 2-3 EXO|✔️ 0-0 EXP|❌ 0-3 ATMC|❌ 2-3 EXP| \n14 |[**BW**](https://liquipedia.net/rocketleague/index.php?title=Lost_Legion_Benchwarmers&action=edit&redlink=1)|**1-3**|❌ 0-3 OP|❌ 0-3 Inferno|✔️ 0-0 GHST|❌ 1-3 EXO| \nDQ |[**EXP**](https://liquipedia.net/rocketleague/index.php?title=Expanzees&action=edit&redlink=1)|**0-3**|❌ 0-0 WAT|❌ 0-0 LLG|❌ 0-0 AUF| | \nDQ |[**GHST**](https://liquipedia.net/rocketleague/index.php?title=Lost_Legion_Ghosts&action=edit&redlink=1)|**0-3**|❌ 0-0 Mist|❌ 0-0 EXP|❌ 0-0 BW| | "
            mocked_print_to_channel.assert_awaited_once_with(mock_channel,
                                                             expected_markup,
                                                             title="Swiss Bracket")


if __name__ == '__main__':
    unittest.main()
