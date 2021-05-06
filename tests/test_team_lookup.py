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

class TestTeamLookup(RLEBAsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

        # Import rleb_team_lookup after setUp is done so that rleb_settings loads with mocks/patches.
        global rleb_stdout
        global rleb_team_lookup
        import rleb_stdout
        import rleb_team_lookup

    async def test_team_lookup(self):

        # Mock the liquipedia page so tests can run offline.
        def mock_liquipedia(args = []):
            with open('tests/resources/liquipedia_na_grid.html', encoding="utf8") as f:
                return MockRequest(f.read())
        mock_request = patch.object(requests,
                                       "get",
                                       new=mock_liquipedia).start()
        self.addCleanup(mock_request)

        mock_channel = mock.Mock(spec=discord.TextChannel)

        with patch.object(rleb_stdout, 'print_to_channel') as mocked_print_to_channel:
            await rleb_team_lookup.handle_team_lookup('liquipedia url', mock_channel)

            expected_markup = "|Team|\n:--:|\n[**72PC**](https://liquipedia.net/rocketleague/72PC) - Jacob, Spyder, Sea-Bass|\n[**AllMid**](https://liquipedia.net/rocketleague/AllMid) - RawGreg, A Savvy Seal, ElOmarMaton|\n[**Circuitry Gaming**](https://liquipedia.net/rocketleague/Circuitry_Gaming) - Skyzz, Adverse, Fefe|\n[**Continuum**](https://liquipedia.net/rocketleague/Continuum_(North_American_Team)) - Astroh, Aeon, Kronovi|\n[**Defiance**](https://liquipedia.net/rocketleague/Defiance) - Vijal, kfrost, Mazo|\n[**Dimes and Demos**](https://liquipedia.net/rocketleague/index.php?title=Dimes_and_Demos&action=edit&redlink=1) - Salidow, Roxrz, Pure|\n[**Ducklings**](https://liquipedia.net/rocketleague/Ducklings) - NoMansion, Waves, NEHEITIOS|\n[**Dumb Dumb and Dumber**](https://liquipedia.net/rocketleague/index.php?title=Dumb_Dumb_and_Dumber&action=edit&redlink=1) - skies., unnaturxl, ledog03|\n[**Empty Space**](https://liquipedia.net/rocketleague/Empty_Space) - Alpa, Thundah, Crave|\n[**.EXE**](https://liquipedia.net/rocketleague/Team_.EXE) - Monster442, Titoh, Brendan|\n[**Fishh 'R' Us**](https://liquipedia.net/rocketleague/index.php?title=Fishh_%27R%27_Us&action=edit&redlink=1) - FishhR, Volterohh, Powerful|\n[**Flamin' Hot Cheetos**](https://liquipedia.net/rocketleague/index.php?title=Flamin%27_Hot_Cheetos&action=edit&redlink=1) - Niitrous., nexuhtyy, Dauxed|\n[**gwill and sons**](https://liquipedia.net/rocketleague/index.php?title=Gwill_and_sons&action=edit&redlink=1) - Smacked, Dekey, gwillikers|\n[**Here for Pacos bed**](https://liquipedia.net/rocketleague/Here_for_Pacos_bed) - Grills, WhereIsYrPaco, Itz-Cha|\n[**Integrity Esports**](https://liquipedia.net/rocketleague/Integrity_Esports) - JD, Gengar Gengar, Talliebird|\n[**Kings Gambit**](https://liquipedia.net/rocketleague/index.php?title=Kings_Gambit&action=edit&redlink=1) - JosherSquasher, Titanium, Gib|\n[**Lights Out!**](https://liquipedia.net/rocketleague/Lights_Out!) - Kevpert, Toe, coco-ice44|\n[**Melon Patch Gaming**](https://liquipedia.net/rocketleague/Melon_Patch_Gaming) - Bumpin, surreal, Ozmo|\n[**Metro**](https://liquipedia.net/rocketleague/index.php?title=Metro&action=edit&redlink=1) - Grazy, Spartan, Hopper|\n[**Mirage**](https://liquipedia.net/rocketleague/Mirage) - Vegas, Linear, Nibra|\n[**Monkey Business**](https://liquipedia.net/rocketleague/Monkey_Business) - Jay, Ghostcrash, blaze|\n[**OnlyTheFamily**](https://liquipedia.net/rocketleague/OnlyTheFamily_(American_Team)) - Crispp., iRicky01, Leakez|\n[**Parabellum Esports**](https://liquipedia.net/rocketleague/Parabellum_Esports) - Lemonpuppy, Darou, Comp|\n[**PrideStark Empire**](https://liquipedia.net/rocketleague/PrideStark_Empire) - Splashy, Sharp, Porklet|\n[**Scuba Squad**](https://liquipedia.net/rocketleague/Scuba_Squad) - Angel, Oath, Shea|\n[**shootahs**](https://liquipedia.net/rocketleague/index.php?title=Shootahs&action=edit&redlink=1) - Imagine, angelsspitt, indigo|\n[**Slaughter House**](https://liquipedia.net/rocketleague/Slaughter_House) - blaze, Soulless, slushi|\n[**Sol**](https://liquipedia.net/rocketleague/Sol) - Paarthurnax, Stealth, Night|\n[**Stromboli**](https://liquipedia.net/rocketleague/Stromboli) - AlRaz, kinseh, Shadow|\n[**Tequila**](https://liquipedia.net/rocketleague/Tequila) - Duck, Falss, FTMHere|\n[**The Rejects**](https://liquipedia.net/rocketleague/The_Rejects) - WondaMike, hockE, Chronic|\n[**wumbology**](https://liquipedia.net/rocketleague/index.php?title=Wumbology&action=edit&redlink=1) - taysech, CombatImp, Slepy|\n"
            mocked_print_to_channel.assert_awaited_once_with(mock_channel, expected_markup, title="Teams")

    async def test_team_lookup_fails(self):

        # Mock the liquipedia page to return nothing.
        def mock_liquipedia(args = []):
            return None
        mock_request = patch.object(requests,
                                       "get",
                                       new=mock_liquipedia).start()
        self.addCleanup(mock_request)

        mock_channel = mock.Mock(spec=discord.TextChannel)
        await rleb_team_lookup.handle_team_lookup('bad url', mock_channel)
        mock_channel.send.assert_awaited_once_with("Couldn't load bad url!\nError: 'NoneType' object has no attribute 'content'")

if __name__ == '__main__':
    unittest.main()
