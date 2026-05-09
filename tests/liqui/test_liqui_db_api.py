"""
Tests for liqui/liqui_db_api.py.

All HTTP calls are intercepted — no internet required. Fixtures in
tests/resources/liqui_db_api_mock_responses/ were generated from the real
Liquipedia DB API v3 and saved once; tests run against those snapshots.
"""

import json
import logging
import unittest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURE_DIR = "tests/resources/liqui_db_api_mock_responses"


def _load(filename: str) -> dict:
    with open(f"{FIXTURE_DIR}/{filename}", encoding="utf-8") as f:
        return json.load(f)


class MockResponse:
    """Minimal requests.Response stand-in used by all tests."""

    def __init__(self, data: dict, status_code: int = 200):
        self._data = data
        self.status_code = status_code

    def json(self) -> dict:
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            from requests import HTTPError
            raise HTTPError(response=self)


def _mock_session_get(fixture_filename: str, status_code: int = 200):
    """Return a patch target that yields the named fixture."""
    return MagicMock(return_value=MockResponse(_load(fixture_filename), status_code))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

PARENT = "Esports_Nations_Cup/2026"


class TestLiquipediaApiClientMatches(unittest.TestCase):

    def setUp(self):
        from liqui.liqui_db_api import LiquipediaApiClient
        self.client = LiquipediaApiClient()

    def test_get_matches_returns_list(self):
        self.client._session.get = _mock_session_get("match.json")
        result = self.client.get_matches(PARENT)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 5)

    def test_get_matches_first_item_has_expected_fields(self):
        self.client._session.get = _mock_session_get("match.json")
        result = self.client.get_matches(PARENT)
        first = result[0]
        self.assertIn("match2id", first)
        self.assertIn("match2opponents", first)
        self.assertIn("finished", first)
        self.assertIn("date", first)
        self.assertIn("parent", first)
        self.assertEqual(first["parent"], PARENT)

    def test_get_matches_sends_parent_condition(self):
        self.client._session.get = _mock_session_get("match.json")
        self.client.get_matches(PARENT)
        _, kwargs = self.client._session.get.call_args
        params = kwargs.get("params", {})
        self.assertIn(f"[[parent::{PARENT}]]", params["conditions"])

    def test_get_matches_extra_conditions_appended(self):
        self.client._session.get = _mock_session_get("match.json")
        self.client.get_matches(PARENT, extra_conditions="[[finished::true]]")
        _, kwargs = self.client._session.get.call_args
        cond = kwargs["params"]["conditions"]
        self.assertIn(f"[[parent::{PARENT}]]", cond)
        self.assertIn("[[finished::true]]", cond)

    def test_get_matches_default_order_is_date_asc(self):
        self.client._session.get = _mock_session_get("match.json")
        self.client.get_matches(PARENT)
        _, kwargs = self.client._session.get.call_args
        self.assertEqual(kwargs["params"]["order"], "date ASC")

    def test_get_matches_passes_limit_and_offset(self):
        self.client._session.get = _mock_session_get("match.json")
        self.client.get_matches(PARENT, limit=10, offset=5)
        _, kwargs = self.client._session.get.call_args
        self.assertEqual(kwargs["params"]["limit"], 10)
        self.assertEqual(kwargs["params"]["offset"], 5)

    def test_get_matches_wiki_always_rocketleague(self):
        self.client._session.get = _mock_session_get("match.json")
        self.client.get_matches(PARENT)
        _, kwargs = self.client._session.get.call_args
        self.assertEqual(kwargs["params"]["wiki"], "rocketleague")


class TestLiquipediaApiClientSchedule(unittest.TestCase):

    def setUp(self):
        from liqui.liqui_db_api import LiquipediaApiClient
        self.client = LiquipediaApiClient()

    def test_get_schedule_no_dates(self):
        self.client._session.get = _mock_session_get("match.json")
        result = self.client.get_schedule(PARENT)
        self.assertIsInstance(result, list)

    def test_get_schedule_date_from_added_to_conditions(self):
        self.client._session.get = _mock_session_get("match.json")
        self.client.get_schedule(PARENT, date_from="2026-11-05")
        _, kwargs = self.client._session.get.call_args
        self.assertIn("[[date::>2026-11-05]]", kwargs["params"]["conditions"])

    def test_get_schedule_date_to_added_to_conditions(self):
        self.client._session.get = _mock_session_get("match.json")
        self.client.get_schedule(PARENT, date_to="2026-11-08")
        _, kwargs = self.client._session.get.call_args
        self.assertIn("[[date::<2026-11-08]]", kwargs["params"]["conditions"])

    def test_get_schedule_both_dates_in_conditions(self):
        self.client._session.get = _mock_session_get("match.json")
        self.client.get_schedule(PARENT, date_from="2026-11-05", date_to="2026-11-08")
        _, kwargs = self.client._session.get.call_args
        cond = kwargs["params"]["conditions"]
        self.assertIn(f"[[parent::{PARENT}]]", cond)
        self.assertIn("[[date::>2026-11-05]]", cond)
        self.assertIn("[[date::<2026-11-08]]", cond)


class TestLiquipediaApiClientStandings(unittest.TestCase):

    def setUp(self):
        from liqui.liqui_db_api import LiquipediaApiClient
        self.client = LiquipediaApiClient()

    def test_get_standings_returns_list(self):
        self.client._session.get = _mock_session_get("standingstable.json")
        result = self.client.get_standings(PARENT)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_get_standings_first_item_fields(self):
        self.client._session.get = _mock_session_get("standingstable.json")
        result = self.client.get_standings(PARENT)
        first = result[0]
        self.assertIn("parent", first)
        self.assertIn("standingsindex", first)
        self.assertIn("title", first)
        self.assertIn("type", first)
        self.assertIn("matches", first)

    def test_get_standings_no_type_filter(self):
        self.client._session.get = _mock_session_get("standingstable.json")
        self.client.get_standings(PARENT)
        _, kwargs = self.client._session.get.call_args
        cond = kwargs["params"]["conditions"]
        self.assertEqual(cond, f"[[parent::{PARENT}]]")

    def test_get_standings_swiss_type_filter(self):
        self.client._session.get = _mock_session_get("standingstable.json")
        self.client.get_standings(PARENT, standings_type="swiss")
        _, kwargs = self.client._session.get.call_args
        cond = kwargs["params"]["conditions"]
        self.assertIn("[[type::swiss]]", cond)

    def test_get_standings_ordered_by_index(self):
        self.client._session.get = _mock_session_get("standingstable.json")
        self.client.get_standings(PARENT)
        _, kwargs = self.client._session.get.call_args
        self.assertEqual(kwargs["params"]["order"], "standingsindex ASC")


class TestLiquipediaApiClientPrizepool(unittest.TestCase):

    def setUp(self):
        from liqui.liqui_db_api import LiquipediaApiClient
        self.client = LiquipediaApiClient()

    def test_get_prizepool_returns_list(self):
        self.client._session.get = _mock_session_get("placement.json")
        result = self.client.get_prizepool(PARENT)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 10)

    def test_get_prizepool_first_item_fields(self):
        self.client._session.get = _mock_session_get("placement.json")
        result = self.client.get_prizepool(PARENT)
        first = result[0]
        self.assertIn("placement", first)
        self.assertIn("prizemoney", first)
        self.assertIn("opponentname", first)
        self.assertIn("opponenttemplate", first)
        self.assertIn("parent", first)

    def test_get_prizepool_ordered_by_prizepoolindex(self):
        self.client._session.get = _mock_session_get("placement.json")
        self.client.get_prizepool(PARENT)
        _, kwargs = self.client._session.get.call_args
        self.assertEqual(kwargs["params"]["order"], "prizepoolindex ASC")

    def test_get_prizepool_parent_condition(self):
        self.client._session.get = _mock_session_get("placement.json")
        self.client.get_prizepool(PARENT)
        _, kwargs = self.client._session.get.call_args
        self.assertIn(f"[[parent::{PARENT}]]", kwargs["params"]["conditions"])


class TestLiquipediaApiClientBroadcasts(unittest.TestCase):

    def setUp(self):
        from liqui.liqui_db_api import LiquipediaApiClient
        self.client = LiquipediaApiClient()

    def test_get_broadcasts_returns_list(self):
        self.client._session.get = _mock_session_get("broadcasters.json")
        result = self.client.get_broadcasts(PARENT)
        self.assertIsInstance(result, list)

    def test_get_broadcasts_ordered_by_weight_desc(self):
        self.client._session.get = _mock_session_get("broadcasters.json")
        self.client.get_broadcasts(PARENT)
        _, kwargs = self.client._session.get.call_args
        self.assertEqual(kwargs["params"]["order"], "weight DESC")

    def test_get_broadcasts_parent_condition(self):
        self.client._session.get = _mock_session_get("broadcasters.json")
        self.client.get_broadcasts(PARENT)
        _, kwargs = self.client._session.get.call_args
        self.assertIn(f"[[parent::{PARENT}]]", kwargs["params"]["conditions"])


class TestLiquipediaApiClientTournament(unittest.TestCase):

    def setUp(self):
        from liqui.liqui_db_api import LiquipediaApiClient
        self.client = LiquipediaApiClient()

    def test_get_tournament_returns_dict(self):
        self.client._session.get = _mock_session_get("tournament.json")
        result = self.client.get_tournament(PARENT)
        self.assertIsInstance(result, dict)

    def test_get_tournament_fields(self):
        self.client._session.get = _mock_session_get("tournament.json")
        result = self.client.get_tournament(PARENT)
        self.assertEqual(result["pagename"], PARENT)
        self.assertIn("name", result)
        self.assertIn("startdate", result)
        self.assertIn("enddate", result)
        self.assertIn("prizepool", result)
        self.assertIn("liquipediatier", result)

    def test_get_tournament_pagename_condition(self):
        self.client._session.get = _mock_session_get("tournament.json")
        self.client.get_tournament(PARENT)
        _, kwargs = self.client._session.get.call_args
        self.assertIn(f"[[pagename::{PARENT}]]", kwargs["params"]["conditions"])

    def test_get_tournament_returns_none_when_not_found(self):
        self.client._session.get = MagicMock(
            return_value=MockResponse({"result": []})
        )
        result = self.client.get_tournament("Nonexistent/Page")
        self.assertIsNone(result)

    def test_get_tournament_limit_1(self):
        self.client._session.get = _mock_session_get("tournament.json")
        self.client.get_tournament(PARENT)
        _, kwargs = self.client._session.get.call_args
        self.assertEqual(kwargs["params"]["limit"], 1)


class TestLiquipediaApiClientSeries(unittest.TestCase):

    def setUp(self):
        from liqui.liqui_db_api import LiquipediaApiClient
        self.client = LiquipediaApiClient()

    def test_get_series_returns_list(self):
        self.client._session.get = _mock_session_get("series.json")
        result = self.client.get_series("Esports_Nations_Cup")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    def test_get_series_fields(self):
        self.client._session.get = _mock_session_get("series.json")
        result = self.client.get_series("Esports_Nations_Cup")
        first = result[0]
        self.assertIn("pagename", first)
        self.assertIn("name", first)
        self.assertIn("prizepool", first)
        self.assertIn("liquipediatier", first)
        self.assertIn("organizers", first)

    def test_get_series_pagename_condition(self):
        self.client._session.get = _mock_session_get("series.json")
        self.client.get_series("Esports_Nations_Cup")
        _, kwargs = self.client._session.get.call_args
        self.assertIn("[[pagename::Esports_Nations_Cup]]", kwargs["params"]["conditions"])


class TestLiquipediaApiClientTeams(unittest.TestCase):

    def setUp(self):
        from liqui.liqui_db_api import LiquipediaApiClient
        self.client = LiquipediaApiClient()

    def test_get_teams_returns_list(self):
        self.client._session.get = _mock_session_get("team.json")
        result = self.client.get_teams(conditions="[[pagename::Team_Falcons]]")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    def test_get_teams_fields(self):
        self.client._session.get = _mock_session_get("team.json")
        result = self.client.get_teams(conditions="[[pagename::Team_Falcons]]")
        first = result[0]
        self.assertIn("pagename", first)
        self.assertIn("name", first)
        self.assertIn("template", first)
        self.assertIn("logourl", first)
        self.assertIn("status", first)

    def test_get_teams_passes_conditions(self):
        self.client._session.get = _mock_session_get("team.json")
        self.client.get_teams(conditions="[[pagename::Team_Falcons]]")
        _, kwargs = self.client._session.get.call_args
        self.assertEqual(kwargs["params"]["conditions"], "[[pagename::Team_Falcons]]")

    def test_get_teams_no_conditions(self):
        self.client._session.get = _mock_session_get("team.json")
        self.client.get_teams()
        _, kwargs = self.client._session.get.call_args
        self.assertNotIn("conditions", kwargs["params"])


class TestLiquipediaApiClientPlayers(unittest.TestCase):

    def setUp(self):
        from liqui.liqui_db_api import LiquipediaApiClient
        self.client = LiquipediaApiClient()

    def test_get_players_returns_list(self):
        self.client._session.get = _mock_session_get("squadplayer.json")
        result = self.client.get_players(PARENT)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)

    def test_get_players_fields(self):
        self.client._session.get = _mock_session_get("squadplayer.json")
        result = self.client.get_players(PARENT)
        first = result[0]
        self.assertIn("id", first)
        self.assertIn("name", first)
        self.assertIn("team", first)
        self.assertIn("nationality", first)

    def test_get_players_parent_condition(self):
        self.client._session.get = _mock_session_get("squadplayer.json")
        self.client.get_players(PARENT)
        _, kwargs = self.client._session.get.call_args
        self.assertIn(f"[[parent::{PARENT}]]", kwargs["params"]["conditions"])

    def test_get_player_individual(self):
        self.client._session.get = _mock_session_get("player.json")
        # get_players goes to /squadplayer; direct player lookup uses get_teams-style pass-through
        # Here we test _get directly against the player endpoint
        result = self.client._get("player", conditions="[[pagename::Vatira]]", limit=1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "Vatira")
        self.assertEqual(result[0]["name"], "Axel Touret")
        self.assertEqual(result[0]["nationality"], "France")


class TestLiquipediaApiClientErrors(unittest.TestCase):

    def setUp(self):
        from liqui.liqui_db_api import LiquipediaApiClient
        self.client = LiquipediaApiClient()

    def test_get_raises_on_http_error(self):
        from requests import HTTPError
        self.client._session.get = MagicMock(
            return_value=MockResponse({}, status_code=429)
        )
        with self.assertRaises(HTTPError):
            self.client.get_matches(PARENT)

    def test_get_returns_empty_list_on_api_error_result(self):
        # API errors return 200 with {"error": [...], "result": []}
        self.client._session.get = _mock_session_get("api_error.json")
        result = self.client._get("tournament", conditions=f"[[pagename::{PARENT}]]")
        self.assertEqual(result, [])

    def test_get_logs_warnings(self):
        self.client._session.get = _mock_session_get("api_warning.json")
        with self.assertLogs("liqui.liqui_db_api", level=logging.WARNING) as cm:
            result = self.client._get("match", conditions=f"[[parent::{PARENT}]]")
        self.assertEqual(len(result), 1)
        self.assertTrue(any("struggled to load" in line for line in cm.output))


class TestLiquipediaApiClientHeaders(unittest.TestCase):

    def test_authorization_header_set(self):
        from liqui.liqui_db_api import LiquipediaApiClient
        client = LiquipediaApiClient()
        self.assertIn("Authorization", client._session.headers)
        self.assertTrue(client._session.headers["Authorization"].startswith("Apikey "))

    def test_accept_encoding_gzip(self):
        from liqui.liqui_db_api import LiquipediaApiClient
        client = LiquipediaApiClient()
        self.assertEqual(client._session.headers.get("Accept-Encoding"), "gzip")

    def test_user_agent_set(self):
        from liqui.liqui_db_api import LiquipediaApiClient
        client = LiquipediaApiClient()
        self.assertIn("User-Agent", client._session.headers)


class TestLiquipediaApiClientSingleton(unittest.TestCase):

    def test_module_client_is_instance(self):
        from liqui import liqui_db_api
        from liqui.liqui_db_api import LiquipediaApiClient
        self.assertIsInstance(liqui_db_api.client, LiquipediaApiClient)


if __name__ == "__main__":
    unittest.main()
