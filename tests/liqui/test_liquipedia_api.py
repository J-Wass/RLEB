# Tests for liqui/liquipedia_api.py and liqui/liquipedia_models.py.
import os
import sys
import unittest
import unittest.mock as mock

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/../..")

from liqui.liquipedia_api import (
    BASE_URL,
    LiquipediaAPI,
    LiquipediaAPIError,
)
from liqui.liquipedia_models import Broadcaster, Match, StreamLink


def _stub_session(payloads):
    """Build a mock requests.Session that returns the given payloads in order.

    `payloads` is a list of (status_code, json_body) tuples. The mock records
    every call so tests can assert on URLs, params, and headers.
    """
    responses = []
    for status, body in payloads:
        resp = mock.MagicMock()
        resp.status_code = status
        resp.json.return_value = body
        resp.text = str(body)
        responses.append(resp)

    session = mock.MagicMock()
    session.headers = {}
    session.get.side_effect = responses
    return session


def _make_api(payloads, **kwargs):
    session = _stub_session(payloads)
    api = LiquipediaAPI(
        api_key="test_key",
        min_seconds_between_calls=0,
        session=session,
        **kwargs,
    )
    return api, session


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


class TestStreamLink(unittest.TestCase):
    def test_default_key_has_no_language_or_index(self):
        s = StreamLink.from_stream_entry("youtube", "https://yt/rl")
        self.assertEqual(s.platform, "youtube")
        self.assertIsNone(s.language)
        self.assertIsNone(s.index)
        self.assertEqual(s.url, "https://yt/rl")

    def test_language_only_key(self):
        s = StreamLink.from_stream_entry("twitch_en", "https://tw/en")
        self.assertEqual(s.platform, "twitch")
        self.assertEqual(s.language, "en")
        self.assertIsNone(s.index)

    def test_language_and_index_key(self):
        s = StreamLink.from_stream_entry("twitch_de_2", "https://tw/de2")
        self.assertEqual(s.platform, "twitch")
        self.assertEqual(s.language, "de")
        self.assertEqual(s.index, 2)

    def test_non_numeric_index_falls_back_to_none(self):
        s = StreamLink.from_stream_entry("twitch_en_main", "https://tw/main")
        self.assertEqual(s.platform, "twitch")
        self.assertEqual(s.language, "en")
        self.assertIsNone(s.index)


class TestBroadcaster(unittest.TestCase):
    def test_from_api_coerces_types(self):
        raw = {
            "pageid": "123",
            "pagename": "X",
            "id": "Eve",
            "name": "Evelyn",
            "page": "Eve",
            "position": "Caster",
            "language": "en",
            "flag": "united_states",
            "weight": "5",
            "date": "2026-01-01",
            "parent": "X",
            "wiki": "rocketleague",
            "extradata": {"status": ""},
        }
        b = Broadcaster.from_api(raw)
        self.assertEqual(b.pageid, 123)
        self.assertEqual(b.weight, 5)
        self.assertEqual(b.name, "Evelyn")
        self.assertEqual(b.extradata["status"], "")

    def test_from_api_handles_missing_fields(self):
        b = Broadcaster.from_api({})
        self.assertEqual(b.pageid, 0)
        self.assertEqual(b.weight, 0)
        self.assertEqual(b.name, "")
        self.assertEqual(b.extradata, {})


class TestMatch(unittest.TestCase):
    def test_from_api_parses_streams(self):
        m = Match.from_api({
            "pageid": 1,
            "pagename": "X",
            "parent": "X",
            "tournament": "T",
            "date": "2026-01-01",
            "wiki": "rocketleague",
            "stream": {
                "youtube": "https://yt/rl",
                "twitch_en_1": "https://tw/en1",
                "twitch_de_1": "https://tw/de1",
                "blank": "",  # ignored — empty url
                "bad": 42,    # ignored — non-string
            },
        })
        self.assertEqual(len(m.streams), 3)
        urls = {s.url for s in m.streams}
        self.assertEqual(
            urls,
            {"https://yt/rl", "https://tw/en1", "https://tw/de1"},
        )

    def test_from_api_handles_no_stream(self):
        m = Match.from_api({"pageid": 1, "pagename": "X"})
        self.assertEqual(m.streams, ())


# ---------------------------------------------------------------------------
# LiquipediaAPI
# ---------------------------------------------------------------------------


class TestLiquipediaAPI(unittest.TestCase):
    def test_missing_api_key_raises(self):
        with mock.patch("liqui.liquipedia_api.global_settings") as gs:
            gs.LIQUIPEDIA_API_KEY = ""
            with self.assertRaises(LiquipediaAPIError):
                LiquipediaAPI()

    def test_get_builds_correct_request(self):
        api, session = _make_api([(200, {"result": [{"id": "x"}]})])
        api.get(
            "match",
            "rocketleague",
            conditions="[[pagename::X]]",
            limit=10,
            offset=5,
            extra_params={"streamurls": "true"},
        )
        session.get.assert_called_once()
        args, kwargs = session.get.call_args
        self.assertEqual(args[0], f"{BASE_URL}/match")
        params = kwargs["params"]
        self.assertEqual(params["wiki"], "rocketleague")
        self.assertEqual(params["conditions"], "[[pagename::X]]")
        self.assertEqual(params["limit"], 10)
        self.assertEqual(params["offset"], 5)
        self.assertEqual(params["streamurls"], "true")

    def test_get_multi_wiki_pipe_joins(self):
        api, session = _make_api([(200, {"result": []})])
        api.get("match", ["rocketleague", "dota2"])
        params = session.get.call_args.kwargs["params"]
        self.assertEqual(params["wiki"], "rocketleague|dota2")

    def test_get_sets_auth_header_on_session(self):
        _, session = _make_api([(200, {"result": []})])
        self.assertEqual(session.headers["Authorization"], "Apikey test_key")
        self.assertEqual(session.headers["Accept-Encoding"], "gzip")
        self.assertIn("User-Agent", session.headers)

    def test_http_error_raises(self):
        api, _ = _make_api([(429, {"error": ["rate limit"]})])
        with self.assertRaises(LiquipediaAPIError) as ctx:
            api.get("match", "rocketleague")
        self.assertIn("429", str(ctx.exception))

    def test_payload_error_raises(self):
        api, _ = _make_api([(200, {"result": [], "error": ["bad conditions"]})])
        with self.assertRaises(LiquipediaAPIError) as ctx:
            api.get("match", "rocketleague")
        self.assertIn("bad conditions", str(ctx.exception))

    def test_get_all_pages_until_short_batch(self):
        page1 = {"result": [{"i": i} for i in range(1000)]}
        page2 = {"result": [{"i": i} for i in range(1000, 1500)]}
        api, session = _make_api([(200, page1), (200, page2)])
        rows = api.get_all("match", "rocketleague")
        self.assertEqual(len(rows), 1500)
        self.assertEqual(session.get.call_count, 2)
        # Second call should have advanced the offset.
        second_params = session.get.call_args_list[1].kwargs["params"]
        self.assertEqual(second_params["offset"], 1000)

    def test_get_all_respects_max_results(self):
        page1 = {"result": [{"i": i} for i in range(1000)]}
        page2 = {"result": [{"i": i} for i in range(1000, 2000)]}
        api, _ = _make_api([(200, page1), (200, page2)])
        rows = api.get_all("match", "rocketleague", max_results=1200)
        self.assertEqual(len(rows), 1200)


class TestBroadcastersMethod(unittest.TestCase):
    def test_returns_typed_dataclasses_with_pagename_condition(self):
        body = {
            "result": [
                {
                    "pageid": 1, "pagename": "X", "id": "Eve", "name": "Evelyn",
                    "page": "Eve", "position": "Caster", "language": "en",
                    "flag": "united_states", "weight": 100, "date": "2026-01-01",
                    "parent": "X", "wiki": "rocketleague", "extradata": {},
                },
            ]
        }
        api, session = _make_api([(200, body)])
        result = api.broadcasters(wiki="rocketleague", pagename="X")
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], Broadcaster)
        self.assertEqual(result[0].name, "Evelyn")
        params = session.get.call_args.kwargs["params"]
        self.assertEqual(params["conditions"], "[[pagename::X]]")


class TestMatchesMethod(unittest.TestCase):
    def test_passes_streamurls_when_enabled(self):
        api, session = _make_api([(200, {"result": []})])
        api.matches(wiki="rocketleague", pagename="X", streamurls=True)
        params = session.get.call_args.kwargs["params"]
        self.assertEqual(params["streamurls"], "true")

    def test_streamurls_disabled_omits_param(self):
        api, session = _make_api([(200, {"result": []})])
        api.matches(wiki="rocketleague", pagename="X", streamurls=False)
        params = session.get.call_args.kwargs["params"]
        self.assertNotIn("streamurls", params)

    def test_returns_typed_match_dataclasses(self):
        body = {"result": [{
            "pageid": 1, "pagename": "X", "parent": "X", "tournament": "T",
            "date": "2026-01-01", "wiki": "rocketleague",
            "stream": {"youtube": "https://yt/x"},
        }]}
        api, _ = _make_api([(200, body)])
        matches = api.matches(wiki="rocketleague", pagename="X")
        self.assertEqual(len(matches), 1)
        self.assertIsInstance(matches[0], Match)
        self.assertEqual(matches[0].streams[0].url, "https://yt/x")


class TestTournamentStreams(unittest.TestCase):
    def test_dedupes_across_matches_and_subpages(self):
        page_body = {"result": [
            {
                "pageid": 1, "pagename": "X", "parent": "X",
                "wiki": "rocketleague",
                "stream": {"youtube": "https://yt/x", "twitch_en_1": "https://tw/en"},
            },
            {
                "pageid": 1, "pagename": "X", "parent": "X",
                "wiki": "rocketleague",
                # duplicate URLs across matches collapse.
                "stream": {"youtube": "https://yt/x", "twitch_de_1": "https://tw/de"},
            },
        ]}
        subpage_body = {"result": [
            {
                "pageid": 2, "pagename": "X/Day1", "parent": "X",
                "wiki": "rocketleague",
                "stream": {"twitch_de_1": "https://tw/de"},  # also duplicate
            },
        ]}
        api, session = _make_api([(200, page_body), (200, subpage_body)])
        streams = api.tournament_streams("rocketleague", "X")
        urls = sorted(s.url for s in streams)
        self.assertEqual(
            urls,
            ["https://tw/de", "https://tw/en", "https://yt/x"],
        )
        # Two calls: one pagename-scoped, one parent-scoped.
        self.assertEqual(session.get.call_count, 2)


if __name__ == "__main__":
    unittest.main()
