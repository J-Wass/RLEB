# coding: utf-8

import sys
import os

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/../..")

import unittest
import unittest.mock as mock
from unittest.mock import patch, AsyncMock

from ..common import common_utils
from data_bridge import Data

import requests

import discord


class TestSwissLookup(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

        self.data_stub = AsyncMock(spec=Data)
        self.mock_data = patch(
            "data_bridge.Data.singleton", return_value=self.data_stub
        ).start()

        self.stub_network()

        # Import rleb_swiss after setUp is done so that rleb_settings loads with mocks/patches.
        global stdout
        global swiss_lookup
        import stdout
        from liqui import swiss_lookup

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

    async def test_swiss_complete(self):
        mock_channel = mock.Mock(spec=discord.TextChannel)

        with patch.object(stdout, "print_to_channel") as mocked_print_to_channel:
            await swiss_lookup.handle_swiss_lookup(
                "https://liquipedia.net/rocketleague/Rocket_League_Championship_Series/2021-22/Fall/North_America/2",
                mock_channel,
            )

            expected_markup = "|**#**|**Teams**|**W-L**|**Round 1**|**Round 2**|**Round 3**|**Round 4**|**Round 5**|\n|:-|:-|:-|:-|:-|:-|:-|:-|\n1 |[**G2**](https://liquipedia.net/rocketleague/G2_Esports)|**3-0**|✔️ 3-0 GG|✔️ 3-0 SSG|✔️ 3-0 XSET| | \n2 |[**NV**](https://liquipedia.net/rocketleague/Team_Envy)|**3-0**|✔️ 3-2 Susquehanna Soniqs|✔️ 3-1 FAZE|✔️ 3-2 The General NRG| | \n3 |[**The General NRG**](https://liquipedia.net/rocketleague/NRG)|**3-1**|✔️ 3-0 NEF|✔️ 3-0 VIB|❌ 2-3 NV|✔️ 3-0 GG| \n4 |[**TN**](https://liquipedia.net/rocketleague/True_Neutral)|**3-1**|✔️ 3-1 TOR|❌ 2-3 XSET|✔️ 3-2 RBG|✔️ 3-0 FAZE| \n5 |[**XSET**](https://liquipedia.net/rocketleague/XSET)|**3-1**|✔️ 3-0 RGE|✔️ 3-2 TN|❌ 0-3 G2|✔️ 3-2 TOR| \n6 |[**SSG**](https://liquipedia.net/rocketleague/Spacestation_Gaming)|**3-2**|✔️ 3-1 EU|❌ 0-3 G2|❌ 2-3 GG|✔️ 3-1 RGE|✔️ 3-1 FAZE\n7 |[**V1**](https://liquipedia.net/rocketleague/Version1)|**3-2**|❌ 1-3 VIB|✔️ 3-2 NEF|❌ 1-3 FAZE|✔️ 3-1 Susquehanna Soniqs|✔️ 3-1 TOR\n8 |[**GG**](https://liquipedia.net/rocketleague/Ghost_Gaming)|**3-2**|❌ 0-3 G2|✔️ 3-0 EU|✔️ 3-2 SSG|❌ 0-3 The General NRG|✔️ 3-1 VIB\n|\\-|\\- - - - -|\\- - -||||||\n9 |[**TOR**](https://liquipedia.net/rocketleague/Torrent)|**2-3**|❌ 1-3 TN|✔️ 3-1 RGE|✔️ 3-0 VIB|❌ 2-3 XSET|❌ 1-3 V1\n10 |[**FAZE**](https://liquipedia.net/rocketleague/FaZe_Clan)|**2-3**|✔️ 3-0 RBG|❌ 1-3 NV|✔️ 3-1 V1|❌ 0-3 TN|❌ 1-3 SSG\n11 |[**VIB**](https://liquipedia.net/rocketleague/Vibrance)|**2-3**|✔️ 3-1 V1|❌ 0-3 The General NRG|❌ 0-3 TOR|✔️ 3-1 RBG|❌ 1-3 GG\n12 |[**SQ**](https://liquipedia.net/rocketleague/Soniqs)|**1-3**|❌ 2-3 NV|❌ 1-3 RBG|✔️ 3-0 EU|❌ 1-3 V1| \n13 |[**RBG**](https://liquipedia.net/rocketleague/RBG_Esports)|**1-3**|❌ 0-3 FAZE|✔️ 3-1 Susquehanna Soniqs|❌ 2-3 TN|❌ 1-3 VIB| \n13 |[**RGE**](https://liquipedia.net/rocketleague/Rogue)|**1-3**|❌ 0-3 XSET|❌ 1-3 TOR|✔️ 3-0 NEF|❌ 1-3 SSG| \n15 |[**NEF**](https://liquipedia.net/rocketleague/Nefarious)|**0-3**|❌ 0-3 The General NRG|❌ 2-3 V1|❌ 0-3 RGE| | \n16 |[**EU**](https://liquipedia.net/rocketleague/EUnited)|**0-3**|❌ 1-3 SSG|❌ 0-3 GG|❌ 0-3 Susquehanna Soniqs| | "
            mocked_print_to_channel.assert_awaited_once_with(
                mock_channel, expected_markup, title="Swiss Bracket"
            )

    async def test_swiss_incomplete(self):
        mock_channel = mock.Mock(spec=discord.TextChannel)

        with patch.object(stdout, "print_to_channel") as mocked_print_to_channel:
            await swiss_lookup.handle_swiss_lookup(
                "https://liquipedia.net/rocketleague/Rocket_League_Championship_Series/2021-22/Spring/North_America/1/Closed_Qualifier",
                mock_channel,
            )

            expected_markup = "|**#**|**Teams**|**W-L**|**Round 1**|**Round 2**|**Round 3**|**Round 4**|**Round 5**|\n|:-|:-|:-|:-|:-|:-|:-|:-|\n |[**XSET**](https://liquipedia.net/rocketleague/XSET)|**-**| | | | | \n |[**Rogue**](https://liquipedia.net/rocketleague/Rogue)|**-**| | | | | \n |[**Ghost Gaming**](https://liquipedia.net/rocketleague/Ghost_Gaming)|**-**| | | | | \n |[**Soniqs**](https://liquipedia.net/rocketleague/Soniqs)|**-**| | | | | \n |[**Torrent**](https://liquipedia.net/rocketleague/Torrent)|**-**| | | | | \n |[**Shopify Rebellion**](https://liquipedia.net/rocketleague/Shopify_Rebellion)|**-**| | | | | \n |[**Charlotte Phoenix**](https://liquipedia.net/rocketleague/Charlotte_Phoenix)|**-**| | | | | \n |[**Akrew**](https://liquipedia.net/rocketleague/Akrew)|**-**| | | | | \n|\\-|\\- - - - -|\\- - -||||||\n |**TBD**|**-**| | | | | \n |**TBD**|**-**| | | | | \n |**TBD**|**-**| | | | | \n |**TBD**|**-**| | | | | \n |**TBD**|**-**| | | | | \n |**TBD**|**-**| | | | | \n |**TBD**|**-**| | | | | \n |**TBD**|**-**| | | | | "
            mocked_print_to_channel.assert_awaited_once_with(
                mock_channel, expected_markup, title="Swiss Bracket"
            )

    async def test_swiss_parenthesis(self):
        mock_channel = mock.Mock(spec=discord.TextChannel)

        with patch.object(stdout, "print_to_channel") as mocked_print_to_channel:
            await swiss_lookup.handle_swiss_lookup(
                "https://liquipedia.net/rocketleague/Rocket_League_Championship_Series/2021-22/Fall/Sub-Saharan_Africa/1",
                mock_channel,
            )

            expected_markup = '|**#**|**Teams**|**W-L**|**Round 1**|**Round 2**|**Round 3**|**Round 4**|**Round 5**|\n|:-|:-|:-|:-|:-|:-|:-|:-|\n1 |[**OP**](https://liquipedia.net/rocketleague/Orlando_Pirates_Exdee)|**3-0**|✔️ 3-0 BW|✔️ 3-0 Mist|✔️ 3-2 WAT| | \n2 |[**Orgless**](https://liquipedia.net/rocketleague/Orgless_\\(South_African_Team\\))|**3-0**|✔️ 3-2 Inferno|✔️ 3-0 Atomic|✔️ 3-2 OOR| | \n3 |[**ATK**](https://liquipedia.net/rocketleague/ATK)|**3-1**|✔️ 3-0 AU|❌ 1-3 WAT|✔️ 3-0 EXP|✔️ 3-0 TKO| \n4 |[**OOR**](https://liquipedia.net/rocketleague/Bot_Gaming)|**3-1**|✔️ 3-1 TKO|✔️ 3-2 EXO|❌ 2-3 Orgless|✔️ 3-1 Mist| \n4 |[**WAT**](https://liquipedia.net/rocketleague/Water)|**3-1**|✔️ W-FF EXP|✔️ 3-1 ATK|❌ 2-3 OP|✔️ 3-0 Atomic| \n6 |[**EXO**](https://liquipedia.net/rocketleague/Exotic_Esports)|**3-2**|✔️ 3-2 LLG|❌ 2-3 OOR|❌ 2-3 TKO|✔️ 3-1 BW|✔️ 3-2 Mist\n7 |[**Atomic**](https://liquipedia.net/rocketleague/Atomic_\\(South_African_Team\\))|**3-2**|✔️ 3-2 EXP|❌ 0-3 Orgless|✔️ 3-0 LLG|❌ 0-3 WAT|✔️ 3-0 AU\n8 |[**EXP**](https://liquipedia.net/rocketleague/Expandas)|**3-2**|❌ 2-3 Atomic|✔️ W-FF GHST|❌ 0-3 ATK|✔️ 3-2 LLG|✔️ 3-0 TKO\n|\\-|\\- - - - -|\\- - -||||||\n9 |[**Mist**](https://liquipedia.net/rocketleague/index.php?title=Mist_\\(South_African_Team\\)&action=edit&redlink=1)|**2-3**|✔️ W-FF GHST|❌ 0-3 OP|✔️ 3-1 Inferno|❌ 1-3 OOR|❌ 2-3 EXO\n9 |[**TKO X1**](https://liquipedia.net/rocketleague/TKO_X1)|**2-3**|❌ 1-3 OOR|✔️ 3-0 AU|✔️ 3-2 EXO|❌ 0-3 ATK|❌ 0-3 EXP\n11 |[**AU**](https://liquipedia.net/rocketleague/Aufbau)|**2-3**|❌ 0-3 ATK|❌ 0-3 TKO|✔️ W-FF EXP|✔️ 3-0 Inferno|❌ 0-3 Atomic\n12 |[**Inferno**](https://liquipedia.net/rocketleague/index.php?title=Inferno_\\(South_African_Team\\)&action=edit&redlink=1)|**1-3**|❌ 2-3 Orgless|✔️ 3-0 BW|❌ 1-3 Mist|❌ 0-3 AU| \n13 |[**LLG**](https://liquipedia.net/rocketleague/Lost_Legion_Giants)|**1-3**|❌ 2-3 EXO|✔️ W-FF EXP|❌ 0-3 Atomic|❌ 2-3 EXP| \n14 |[**BW**](https://liquipedia.net/rocketleague/index.php?title=Lost_Legion_Benchwarmers&action=edit&redlink=1)|**1-3**|❌ 0-3 OP|❌ 0-3 Inferno|✔️ W-FF GHST|❌ 1-3 EXO| \nDQ |[**EXP**](https://liquipedia.net/rocketleague/index.php?title=Expanzees&action=edit&redlink=1)|**0-3**|❌ FF-W WAT|❌ FF-W LLG|❌ FF-W AU| | \nDQ |[**GHST**](https://liquipedia.net/rocketleague/index.php?title=Lost_Legion_Ghosts&action=edit&redlink=1)|**0-3**|❌ FF-W Mist|❌ FF-W EXP|❌ FF-W BW| | '
            mocked_print_to_channel.assert_awaited_once_with(
                mock_channel, expected_markup, title="Swiss Bracket"
            )


if __name__ == "__main__":
    unittest.main()
