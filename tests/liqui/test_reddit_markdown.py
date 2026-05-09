"""
Tests for liqui/reddit_markdown/*.

All tests mock liqui_db_api.client methods so no internet or API key needed.
Fixtures in tests/resources/liqui_db_api_mock_responses/ provide realistic data.
"""

import json
import unittest
from unittest.mock import patch

FIXTURE_DIR = "tests/resources/liqui_db_api_mock_responses"


def _load(filename: str) -> list:
    with open(f"{FIXTURE_DIR}/{filename}", encoding="utf-8") as f:
        return json.load(f)["result"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_client(method: str, fixture_file: str):
    data = _load(fixture_file)
    return patch(f"liqui.liqui_db_api.client.{method}", return_value=data)


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

class TestBuildTeamsMarkdown(unittest.TestCase):

    def test_returns_string(self):
        from liqui.reddit_markdown.teams import build_teams_markdown
        with _patch_client("get_players", "squadplayer_teams_test.json"):
            result = build_teams_markdown("Test/Tournament")
        self.assertIsInstance(result, str)

    def test_header_row(self):
        from liqui.reddit_markdown.teams import build_teams_markdown
        with _patch_client("get_players", "squadplayer_teams_test.json"):
            result = build_teams_markdown("Test/Tournament")
        lines = result.splitlines()
        self.assertIn("|Team|Players|", lines[0])

    def test_separator_row(self):
        from liqui.reddit_markdown.teams import build_teams_markdown
        with _patch_client("get_players", "squadplayer_teams_test.json"):
            result = build_teams_markdown("Test/Tournament")
        lines = result.splitlines()
        self.assertEqual(lines[1], "|:-|:-|")

    def test_alpha_team_row(self):
        from liqui.reddit_markdown.teams import build_teams_markdown
        with _patch_client("get_players", "squadplayer_teams_test.json"):
            result = build_teams_markdown("Test/Tournament")
        self.assertIn("**Alpha**", result)
        self.assertIn("Player1", result)
        self.assertIn("Player2", result)

    def test_beta_team_row(self):
        from liqui.reddit_markdown.teams import build_teams_markdown
        with _patch_client("get_players", "squadplayer_teams_test.json"):
            result = build_teams_markdown("Test/Tournament")
        self.assertIn("**Beta**", result)
        self.assertIn("Player3", result)

    def test_two_teams_two_data_rows(self):
        from liqui.reddit_markdown.teams import build_teams_markdown
        with _patch_client("get_players", "squadplayer_teams_test.json"):
            result = build_teams_markdown("Test/Tournament")
        # header + separator + 2 team rows = 4 lines
        self.assertEqual(len(result.splitlines()), 4)

    def test_empty_players_returns_empty_string(self):
        from liqui.reddit_markdown.teams import build_teams_markdown
        with patch("liqui.liqui_db_api.client.get_players", return_value=[]):
            result = build_teams_markdown("Test/Tournament")
        self.assertEqual(result, "")

    def test_players_separated_by_comma(self):
        from liqui.reddit_markdown.teams import build_teams_markdown
        with _patch_client("get_players", "squadplayer_teams_test.json"):
            result = build_teams_markdown("Test/Tournament")
        self.assertIn("Player1, Player2", result)


# ---------------------------------------------------------------------------
# Prizepool
# ---------------------------------------------------------------------------

class TestBuildPrizepoolMarkdown(unittest.TestCase):

    def test_returns_string(self):
        from liqui.reddit_markdown.prizepool import build_prizepool_markdown
        with _patch_client("get_prizepool", "placement_teams_test.json"):
            result = build_prizepool_markdown("Test/Tournament")
        self.assertIsInstance(result, str)

    def test_header_row(self):
        from liqui.reddit_markdown.prizepool import build_prizepool_markdown
        with _patch_client("get_prizepool", "placement_teams_test.json"):
            result = build_prizepool_markdown("Test/Tournament")
        self.assertIn("|**Place**|**Prize**|**Team**|", result)

    def test_first_place_row(self):
        from liqui.reddit_markdown.prizepool import build_prizepool_markdown
        with _patch_client("get_prizepool", "placement_teams_test.json"):
            result = build_prizepool_markdown("Test/Tournament")
        self.assertIn("|**1**|$100,000|Alpha|", result)

    def test_second_place_row(self):
        from liqui.reddit_markdown.prizepool import build_prizepool_markdown
        with _patch_client("get_prizepool", "placement_teams_test.json"):
            result = build_prizepool_markdown("Test/Tournament")
        self.assertIn("|**2**|$60,000|Beta|", result)

    def test_tied_place_row(self):
        from liqui.reddit_markdown.prizepool import build_prizepool_markdown
        with _patch_client("get_prizepool", "placement_teams_test.json"):
            result = build_prizepool_markdown("Test/Tournament")
        self.assertIn("|**3-4**|$30,000|Gamma|", result)

    def test_three_data_rows(self):
        from liqui.reddit_markdown.prizepool import build_prizepool_markdown
        with _patch_client("get_prizepool", "placement_teams_test.json"):
            result = build_prizepool_markdown("Test/Tournament")
        # header + separator + 3 team rows = 5 lines
        self.assertEqual(len(result.splitlines()), 5)

    def test_tbd_entries_excluded(self):
        from liqui.reddit_markdown.prizepool import build_prizepool_markdown
        with _patch_client("get_prizepool", "placement.json"):  # ENC 2026, all TBD
            result = build_prizepool_markdown("Esports_Nations_Cup/2026")
        self.assertEqual(result, "")

    def test_zero_prize_shown_as_tbd(self):
        from liqui.reddit_markdown.prizepool import build_prizepool_markdown
        from liqui.reddit_markdown._utils import format_money
        self.assertEqual(format_money(0), "TBD")
        self.assertEqual(format_money(None), "TBD")

    def test_prize_formatted_with_dollar_and_commas(self):
        from liqui.reddit_markdown._utils import format_money
        self.assertEqual(format_money(1320000), "$1,320,000")
        self.assertEqual(format_money(100000), "$100,000")


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------

class TestBuildGroupsMarkdown(unittest.TestCase):

    def _build(self):
        from liqui.reddit_markdown.groups import build_groups_markdown
        standings = _load("standingstable_groups_test.json")
        matches = _load("match_groups_finished.json")
        with (
            patch("liqui.liqui_db_api.client.get_standings", return_value=standings),
            patch("liqui.liqui_db_api.client.get_matches", return_value=matches),
        ):
            return build_groups_markdown("Test/Tournament")

    def test_returns_string(self):
        self.assertIsInstance(self._build(), str)

    def test_group_name_in_header(self):
        result = self._build()
        self.assertIn("**Group A**", result)

    def test_alpha_first_place(self):
        result = self._build()
        lines = [l for l in result.splitlines() if "Alpha" in l]
        self.assertTrue(len(lines) > 0)
        # Alpha should be rank 1 (3-0)
        self.assertIn("|1|**Alpha**|3-0|", lines[0])

    def test_beta_second_place(self):
        result = self._build()
        lines = [l for l in result.splitlines() if "Beta" in l]
        self.assertTrue(len(lines) > 0)
        self.assertIn("|2|**Beta**|2-1|", lines[0])

    def test_gamma_third_place(self):
        result = self._build()
        lines = [l for l in result.splitlines() if "Gamma" in l]
        self.assertTrue(len(lines) > 0)
        self.assertIn("|3|**Gamma**|1-2|", lines[0])

    def test_delta_last_place(self):
        result = self._build()
        lines = [l for l in result.splitlines() if "Delta" in l]
        self.assertTrue(len(lines) > 0)
        self.assertIn("|4|**Delta**|0-3|", lines[0])

    def test_game_diff_positive_alpha(self):
        result = self._build()
        # Alpha: 3+3+3=9 GW, 1+2+0=3 GL → +6
        self.assertIn("+6", result.split("Alpha")[1].split("\n")[0])

    def test_game_diff_negative_delta(self):
        result = self._build()
        # Delta: 0+1+0=1 GW, 3+3+3=9 GL → -8... let me recalculate
        # match 2: Gamma beats Delta 3-0 → Delta gets 0 GW, 3 GL
        # match 4: Beta beats Delta 3-1 → Delta gets 1 GW, 3 GL
        # match 5: Alpha beats Delta 3-0 → Delta gets 0 GW, 3 GL
        # Delta total: 1 GW, 9 GL, diff = -8
        self.assertIn("-8", result.split("Delta")[1].split("\n")[0])

    def test_empty_standings_returns_empty(self):
        from liqui.reddit_markdown.groups import build_groups_markdown
        with patch("liqui.liqui_db_api.client.get_standings", return_value=[]):
            result = build_groups_markdown("Test/Tournament")
        self.assertEqual(result, "")

    def test_column_headers_present(self):
        result = self._build()
        self.assertIn("**Matches**", result)
        self.assertIn("**Game Diff**", result)


# ---------------------------------------------------------------------------
# Swiss
# ---------------------------------------------------------------------------

class TestBuildSwissMarkdown(unittest.TestCase):

    def _build(self):
        from liqui.reddit_markdown.swiss import build_swiss_markdown
        standings = _load("standingstable_swiss_test.json")
        matches = _load("match_groups_finished.json")
        with (
            patch("liqui.liqui_db_api.client.get_standings", return_value=standings),
            patch("liqui.liqui_db_api.client.get_matches", return_value=matches),
        ):
            return build_swiss_markdown("Test/Tournament")

    def test_returns_string(self):
        self.assertIsInstance(self._build(), str)

    def test_header_columns(self):
        result = self._build()
        self.assertIn("**Teams**", result)
        self.assertIn("**W-L**", result)
        self.assertIn("**Round 1**", result)

    def test_alpha_top_row(self):
        result = self._build()
        # Alpha 3-0 should be first
        lines = [l for l in result.splitlines() if "Alpha" in l]
        self.assertTrue(len(lines) > 0)
        self.assertIn("3-0", lines[0])

    def test_delta_last_row(self):
        result = self._build()
        # Match the team's own standings row, not opponent references inside other rows.
        lines = [l for l in result.splitlines() if "**Delta**" in l and "|0-3|" in l]
        self.assertTrue(len(lines) > 0, f"Delta 0-3 row not found in:\n{result}")

    def test_win_emoji_present(self):
        result = self._build()
        self.assertIn("✔️", result)

    def test_loss_emoji_present(self):
        result = self._build()
        self.assertIn("❌", result)

    def test_divider_row_present(self):
        result = self._build()
        self.assertIn(r"\-", result)

    def test_empty_standings_returns_empty(self):
        from liqui.reddit_markdown.swiss import build_swiss_markdown
        with patch("liqui.liqui_db_api.client.get_standings", return_value=[]):
            result = build_swiss_markdown("Test/Tournament")
        self.assertEqual(result, "")

    def test_no_finished_matches_returns_empty(self):
        from liqui.reddit_markdown.swiss import build_swiss_markdown
        standings = _load("standingstable_swiss_test.json")
        # All unfinished matches
        unfinished = _load("match.json")
        with (
            patch("liqui.liqui_db_api.client.get_standings", return_value=standings),
            patch("liqui.liqui_db_api.client.get_matches", return_value=unfinished),
        ):
            result = build_swiss_markdown("Test/Tournament")
        self.assertEqual(result, "")


# ---------------------------------------------------------------------------
# _utils
# ---------------------------------------------------------------------------

class TestUtils(unittest.TestCase):

    def test_url_to_page_name_https(self):
        from liqui.reddit_markdown._utils import url_to_page_name
        result = url_to_page_name(
            "https://liquipedia.net/rocketleague/RLCS/2025/World_Championship"
        )
        self.assertEqual(result, "RLCS/2025/World_Championship")

    def test_url_to_page_name_http(self):
        from liqui.reddit_markdown._utils import url_to_page_name
        result = url_to_page_name(
            "http://liquipedia.net/rocketleague/RLCS/2025"
        )
        self.assertEqual(result, "RLCS/2025")

    def test_ordinal_1st(self):
        from liqui.reddit_markdown._utils import ordinal
        self.assertEqual(ordinal(1), "1st")

    def test_ordinal_2nd(self):
        from liqui.reddit_markdown._utils import ordinal
        self.assertEqual(ordinal(2), "2nd")

    def test_ordinal_3rd(self):
        from liqui.reddit_markdown._utils import ordinal
        self.assertEqual(ordinal(3), "3rd")

    def test_ordinal_11th(self):
        from liqui.reddit_markdown._utils import ordinal
        self.assertEqual(ordinal(11), "11th")

    def test_ordinal_21st(self):
        from liqui.reddit_markdown._utils import ordinal
        self.assertEqual(ordinal(21), "21st")

    def test_liqui_link_escapes_parens(self):
        from liqui.reddit_markdown._utils import liqui_link
        result = liqui_link("Page(Name)")
        self.assertIn(r"\(", result)
        self.assertIn(r"\)", result)


if __name__ == "__main__":
    unittest.main()
