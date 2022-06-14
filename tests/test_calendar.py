# Dumb hack to be able to access source code files on both windows and linux
import sys
import os

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/..")

import unittest
import unittest.mock as mock
from unittest.mock import patch
from tests.common.rleb_async_test_case import RLEBAsyncTestCase

import json
import google
import googleapiclient
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


class TestCalendar(RLEBAsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

        # import rleb_calendar after setUp is done so that rleb_settings loads with mocks/patches
        global rleb_calendar
        global rleb_settings
        global rleb_stdout
        import rleb_calendar
        import rleb_settings
        import rleb_stdout

        # Set up mock objects.
        self.mock_credentials = mock.Mock()

        def mock_from_service_account_info(args=[], scopes=None):
            return self.mock_credentials

        self.mock_service = mock.Mock()
        self.mock_event_list = mock.Mock()
        self.mock_upcoming_events = mock.Mock()
        with open("tests/resources/google_calendar_response.json", "r") as f:
            self.mock_upcoming_events.execute.return_value = json.load(f)

        self.mock_event_list.list.return_value = self.mock_upcoming_events
        self.mock_service.events.return_value = self.mock_event_list

        def mock_build(calendar=None, version=None, credentials=None):
            return self.mock_service

        # Patch google calendar apis with the mocks.
        credentials = patch.object(
            google.oauth2.service_account.Credentials,
            "from_service_account_info",
            new=mock_from_service_account_info,
        ).start()
        self.addCleanup(credentials)

        build = patch.object(rleb_calendar, "build", new=mock_build).start()
        self.addCleanup(build)

    async def test_reddit_events(self):
        mock_channel = mock.Mock()

        with patch.object(rleb_stdout, "print_to_channel") as mocked_print_to_channel:
            await rleb_calendar.handle_calendar_lookup(mock_channel, "reddit", 7)

            expected_markup = '\n# About\n\n You can post anything here that might not have been allowed as its own post. Whether that\'s quick questions, recently/frequently/over discussed content or "light" content that you don\'t deem worthy of its own thread.\n\n The table below features upcoming streams of S-Tier, A-Tier and the bigger B-Tier events including their streamed qualifiers[.](https://reddit-stream.com/comments/b6vu2e/) For a full list of all upcoming RLEsports events check [**Liquipedia**](https://liquipedia.net/rocketleague/Main_Page).\n# Tuesday, Jun 1\n|Scroll to view start times / links >>|**EDT**|**CET**|**AEST**|**Streams**|**Matches**|\n|:-|:-|:-|:-|:-|:-|\n|[**⚪ IWO: Europe East - Open Qual 1**](https://liquipedia.net/rocketleague/Intel_World_Open/EMEA/Europe_East/Open_Qualifier_1) |[**12:00**](https://www.google.com/search?q=12:00+ET) |18:00 |*2:00* | Player Streams |[**Bracket**](https://liquipedia.net/rocketleague/Intel_World_Open/EMEA/Europe_East/Open_Qualifier_1#Results)|\n|[**⚪ IWO: Germany - Open Qual 1**](https://liquipedia.net/rocketleague/Intel_World_Open/EMEA/Germany/Open_Qualifier_1) |[**12:00**](https://www.google.com/search?q=12:00+ET) |18:00 |*2:00* | Player Streams |[**Bracket**](https://liquipedia.net/rocketleague/Intel_World_Open/EMEA/Germany/Open_Qualifier_1#Results)|\n|[**⚪ IWO: Canada - Open Qual 1**](https://liquipedia.net/rocketleague/Intel_World_Open/EMEA/Germany/Open_Qualifier_1) |[**18:00**](https://www.google.com/search?q=18:00+ET) |*0:00* |*8:00* | Player Streams |[**Bracket**](https://liquipedia.net/rocketleague/Intel_World_Open/EMEA/Germany/Open_Qualifier_1#Results)|\n|[**⚪ IWO: United States - Open Qual 1**](https://liquipedia.net/rocketleague/Intel_World_Open/EMEA/Germany/Open_Qualifier_1) |[**18:00**](https://www.google.com/search?q=18:00+ET) |*0:00* |*8:00* | Player Streams |[**Bracket**](https://liquipedia.net/rocketleague/Intel_World_Open/EMEA/Germany/Open_Qualifier_1#Results)|\n# Wednesday, Jun 2\n|Scroll to view start times / links >>|**EDT**|**CET**|**AEST**|**Streams**|**Matches**|\n|:-|:-|:-|:-|:-|:-|\n|[**⚪ IWO: Australia - Open Qual. 1**](https://liquipedia.net/rocketleague/Intel_World_Open/Asia_Maritime_%26_Oceania/Australia/Open_Qualifier_1) |[**4:00**](https://www.google.com/search?q=4:00+ET) |10:00 |18:00 | Player Streams |[**Bracket**](https://liquipedia.net/rocketleague/Intel_World_Open/Asia_Maritime_%26_Oceania/Australia/Open_Qualifier_1#Results)|\n|[**⚪ IWO: Middle East - Open Qual. 1**](https://liquipedia.net/rocketleague/Intel_World_Open/EMEA/Middle_East/Open_Qualifier_1) |[**11:00**](https://www.google.com/search?q=11:00+ET) |17:00 |*1:00* | Player Streams |[**Bracket**](https://liquipedia.net/rocketleague/Intel_World_Open/EMEA/Middle_East/Open_Qualifier_1#Results)|\n|[**⚪ IWO: North & Central America - Open Qual. 1**](https://liquipedia.net/rocketleague/Intel_World_Open/Americas/North_%26_Central_America/Open_Qualifier_1) |[**18:00**](https://www.google.com/search?q=18:00+ET) |*0:00* |*8:00* | Player Streams |[**Bracket**](https://liquipedia.net/rocketleague/Intel_World_Open/Americas/North_%26_Central_America/Open_Qualifier_1#Results)|\n# Thursday, Jun 3\n|Scroll to view start times / links >>|**EDT**|**CET**|**AEST**|**Streams**|**Matches**|\n|:-|:-|:-|:-|:-|:-|\n|[**⚪ IWO: Europe West - Open Qual. 1**](https://liquipedia.net/rocketleague/Intel_World_Open/EMEA/Europe_West/Open_Qualifier_1) |[**12:00**](https://www.google.com/search?q=12:00+ET) |18:00 |*2:00* | Player Streams |[**Bracket**](https://liquipedia.net/rocketleague/Intel_World_Open/EMEA/Europe_West/Open_Qualifier_1#Results)|\n|[**⚪ IWO: France - Open Qual. 1**](https://liquipedia.net/rocketleague/Intel_World_Open/EMEA/France/Open_Qualifier_1) |[**12:00**](https://www.google.com/search?q=12:00+ET) |18:00 |*2:00* | Player Streams |[**Bracket**](https://liquipedia.net/rocketleague/Intel_World_Open/EMEA/France/Open_Qualifier_1#Results)|\n|[**⚪ IWO: South America - Open Qual. 1**](https://liquipedia.net/rocketleague/Intel_World_Open/Americas/South_America/Open_Qualifier_1) |[**17:00**](https://www.google.com/search?q=17:00+ET) |23:00 |*7:00* | Player Streams |[**Bracket**](https://liquipedia.net/rocketleague/Intel_World_Open/Americas/South_America/Open_Qualifier_1#Results)|\n# Friday, Jun 4\n|Scroll to view start times / links >>|**EDT**|**CET**|**AEST**|**Streams**|**Matches**|\n|:-|:-|:-|:-|:-|:-|\n|[**⚪ IWO: New Zealand - Open Qual. 1**](https://liquipedia.net/rocketleague/Intel_World_Open/Asia_Maritime_%26_Oceania/New_Zealand/Open_Qualifier_1) |[**2:00**](https://www.google.com/search?q=2:00+ET) |8:00 |16:00 | Player Streams |[**Bracket**](https://liquipedia.net/rocketleague/Intel_World_Open/Asia_Maritime_%26_Oceania/New_Zealand/Open_Qualifier_1#Results)|\n|[**⚪ IWO: Africa - Open Qual. 1**](https://liquipedia.net/rocketleague/Intel_World_Open/EMEA/Africa/Open_Qualifier_1) |[**12:00**](https://www.google.com/search?q=12:00+ET) |18:00 |*2:00* | Player Streams |[**Bracket**](https://liquipedia.net/rocketleague/Intel_World_Open/EMEA/Africa/Open_Qualifier_1#Results)|\n|[**⚪ IWO: Chile - Open Qual. 1**](https://liquipedia.net/rocketleague/Intel_World_Open/Americas/Chile/Closed_Qualifier) |[**18:00**](https://www.google.com/search?q=18:00+ET) |*0:00* |*8:00* | Player Streams |[**Bracket**](https://liquipedia.net/rocketleague/Intel_World_Open/Americas/Chile/Closed_Qualifier#Results)|\n|[**⚪ IWO: Mexico - Open Qual. 1**](https://liquipedia.net/rocketleague/Intel_World_Open/Americas/Mexico/Closed_Qualifier) |[**19:00**](https://www.google.com/search?q=19:00+ET) |*1:00* |*9:00* | Player Streams |[**Bracket**](https://liquipedia.net/rocketleague/Intel_World_Open/Americas/Mexico/Closed_Qualifier#Results)|\n# Saturday, Jun 5\n|Scroll to view start times / links >>|**EDT**|**CET**|**AEST**|**Streams**|**Matches**|\n|:-|:-|:-|:-|:-|:-|\n|[**⚪ IWO: Japan - Open Qual. 1**](https://liquipedia.net/rocketleague/Intel_World_Open/Asia_Mainland/Japan/Closed_Qualifier) |[**4:00**](https://www.google.com/search?q=4:00+ET) |10:00 |18:00 | Player Streams |[**Bracket**](https://liquipedia.net/rocketleague/Intel_World_Open/Asia_Mainland/Japan/Closed_Qualifier#Results)|\n|[**⚪ IWO: Europe North - Open Qual. 1**](https://liquipedia.net/rocketleague/Intel_World_Open/EMEA/Europe_North/Closed_Qualifier) |[**12:00**](https://www.google.com/search?q=12:00+ET) |18:00 |*2:00* | Player Streams |[**Bracket**](https://liquipedia.net/rocketleague/Intel_World_Open/EMEA/Europe_North/Closed_Qualifier#Results)|\n|[**IWO: United Kingdom - Open Qual. 1**](https://liquipedia.net/rocketleague/Intel_World_Open/EMEA/United_Kingdom/Open_Qualifier_1) |[**13:00**](https://www.google.com/search?q=13:00+ET) |19:00 |*3:00* | Player Streams |[**Bracket**](https://liquipedia.net/rocketleague/Intel_World_Open/EMEA/United_Kingdom/Open_Qualifier_1#Results)|\n|[**⚪ IWO: Americas/Argentina - Open Qual. 1**](https://liquipedia.net/rocketleague/Intel_World_Open/Americas/Argentina/Open_Qualifier_1) |[**17:00**](https://www.google.com/search?q=17:00+ET) |23:00 |*7:00* | Player streams |[**Bracket**](https://liquipedia.net/rocketleague/Intel_World_Open/Americas/Argentina/Open_Qualifier_1#Results)|\n\n\n\n# Event Threads\n\nEvents prefixed with ⚽ will have an **Event Thread** posted by mods.  Anyone can [**create an Event Thread**](https://www.reddit.com/r/RocketLeagueEsports/wiki/event_threads) or **Match Threads** for unmarked events. Follow the link to learn more.\n\n# Sidebar Schedule\n\nIf you are on the official **Reddit App**, you will find the schedule under the "**About**" tab. If you are browsing the **Desktop** version,  you can find the schedule on the sidebar of the [**new.reddit**](https://new.reddit.com/r/RocketLeagueEsports/) version of this subreddit. Alternatively you can use our [**Google Calendar**](https://www.reddit.com/r/RocketLeagueEsports/wiki/calendar) which is used to feed the schedule.\n\n# RLCS 2021-22 Wiki Pages\n\n▶ [**How it works**](https://www.reddit.com/r/RocketLeagueEsports/wiki/guide)\n\n▶ [**Broadcast Schedule**](https://www.reddit.com/r/RocketLeagueEsports/wiki/schedule)\n\n▶ [**Where to watch**](https://www.reddit.com/r/RocketLeagueEsports/wiki/watch)\n\n▶ [**Coverage**](https://www.reddit.com/r/RocketLeagueEsports/wiki/coverage)'
            mocked_print_to_channel.assert_awaited_once_with(
                mock_channel, expected_markup, title="reddit calendar for next 7 days"
            )

    async def test_google_sheets_events(self):
        mock_channel = mock.Mock()

        with patch.object(rleb_stdout, "print_to_channel") as mocked_print_to_channel:
            await rleb_calendar.handle_calendar_lookup(mock_channel, "sheets", 7)

            expected_markup = "IWO: Europe East - Open Qual 1\t\tIWO: Germany - Open Qual 1\t\tIWO: Canada - Open Qual 1\t\tIWO: United States - Open Qual 1\t\tIWO: Australia - Open Qual. 1\t\tIWO: Middle East - Open Qual. 1\t\tIWO: North & Central America - Open Qual. 1\t\tIWO: Europe West - Open Qual. 1\t\tIWO: France - Open Qual. 1\t\tIWO: South America - Open Qual. 1\t\tIWO: New Zealand - Open Qual. 1\t\tIWO: Africa - Open Qual. 1\t\tIWO: Chile - Open Qual. 1\t\tIWO: Mexico - Open Qual. 1\t\tIWO: Japan - Open Qual. 1\t\tIWO: Europe North - Open Qual. 1\t\tIWO: United Kingdom - Open Qual. 1\t\tIWO: Americas/Argentina - Open Qual. 1\t\t\n06/01/21\tTuesday\t06/01/21\tTuesday\t06/01/21\tTuesday\t06/01/21\tTuesday\t06/02/21\tWednesday\t06/02/21\tWednesday\t06/02/21\tWednesday\t06/03/21\tThursday\t06/03/21\tThursday\t06/03/21\tThursday\t06/04/21\tFriday\t06/04/21\tFriday\t06/04/21\tFriday\t06/04/21\tFriday\t06/05/21\tSaturday\t06/05/21\tSaturday\t06/05/21\tSaturday\t06/05/21\tSaturday\t\nSchedule 15:00\tUpdate 16:00\tSchedule 15:00\tUpdate 16:00\tSchedule 21:00\tUpdate 22:00\tSchedule 21:00\tUpdate 22:00\tSchedule 7:00\tUpdate 8:00\tSchedule 14:00\tUpdate 15:00\tSchedule 21:00\tUpdate 22:00\tSchedule 15:00\tUpdate 16:00\tSchedule 15:00\tUpdate 16:00\tSchedule 20:00\tUpdate 21:00\tSchedule 5:00\tUpdate 6:00\tSchedule 15:00\tUpdate 16:00\tSchedule 21:00\tUpdate 22:00\tSchedule 22:00\tUpdate 23:00\tSchedule 7:00\tUpdate 8:00\tSchedule 15:00\tUpdate 16:00\tSchedule 16:00\tUpdate 17:00\tSchedule 20:00\tUpdate 21:00\t"
            mocked_print_to_channel.assert_awaited_once_with(
                mock_channel, expected_markup, title="sheets calendar for next 7 days"
            )


if __name__ == "__main__":
    unittest.main()
