# Tests for liqui/broadcast_lookup.py.
import os
import sys
import unittest
import unittest.mock as mock
from unittest.mock import patch

import discord

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/../..")

from liqui import broadcast_lookup
from liqui.broadcast_lookup import (
    _stream_display_name,
    handle_broadcast_lookup,
    parse_liquipedia_url,
    streams_to_markdown,
)
from liqui.liquipedia_models import StreamLink


class StubLiquipediaAPI:
    """Offline stand-in for LiquipediaAPI used by broadcast_lookup tests."""

    def __init__(self, streams=None, raise_exc=None):
        self._streams = streams or []
        self._raise = raise_exc
        self.calls: list[tuple[str, str]] = []

    def tournament_streams(self, wiki, pagename, **_):
        self.calls.append((wiki, pagename))
        if self._raise is not None:
            raise self._raise
        return list(self._streams)


class TestParseLiquipediaUrl(unittest.TestCase):
    def test_https(self):
        self.assertEqual(
            parse_liquipedia_url("https://liquipedia.net/rocketleague/RLCS/2026"),
            ("rocketleague", "RLCS/2026"),
        )

    def test_http_with_www(self):
        self.assertEqual(
            parse_liquipedia_url("http://www.liquipedia.net/dota2/Some_Page/2024"),
            ("dota2", "Some_Page/2024"),
        )

    def test_strips_query_and_fragment(self):
        self.assertEqual(
            parse_liquipedia_url(
                "https://liquipedia.net/rocketleague/RLCS/2026?foo=bar#baz"
            ),
            ("rocketleague", "RLCS/2026"),
        )

    def test_percent_encoded_segment_decoded(self):
        wiki, pagename = parse_liquipedia_url(
            "https://liquipedia.net/rocketleague/Some%20Page/2024"
        )
        self.assertEqual(wiki, "rocketleague")
        self.assertEqual(pagename, "Some_Page/2024")

    def test_rejects_non_liquipedia(self):
        with self.assertRaises(ValueError):
            parse_liquipedia_url("https://example.com/x")

    def test_rejects_missing_page(self):
        with self.assertRaises(ValueError):
            parse_liquipedia_url("https://liquipedia.net/rocketleague")


class TestStreamDisplayName(unittest.TestCase):
    def test_simple_handle(self):
        self.assertEqual(
            _stream_display_name("https://twitch.tv/rocketleague"),
            "Rocketleague",
        )

    def test_underscored_segment(self):
        self.assertEqual(
            _stream_display_name("https://youtube.com/c/Rocket_League"),
            "Rocket League",
        )

    def test_at_handle_stripped(self):
        self.assertEqual(
            _stream_display_name("https://youtube.com/@RocketLeague"),
            "Rocketleague",
        )

    def test_trailing_slash_and_query_ignored(self):
        self.assertEqual(
            _stream_display_name("https://twitch.tv/RL_BR/?utm=1#top"),
            "Rl Br",
        )

    def test_special_stream_url(self):
        self.assertEqual(
            _stream_display_name(
                "https://liquipedia.net/rocketleague/Special:Stream/youtube/Rocket_League"
            ),
            "Rocket League",
        )


class TestStreamsToMarkdown(unittest.TestCase):
    def test_empty_streams_friendly_message(self):
        md = streams_to_markdown([])
        self.assertIn("No broadcast streams", md)

    def test_renders_name_platform_language_columns(self):
        streams = [
            StreamLink("twitch", "en", 1, "https://twitch.tv/rl_en"),
            StreamLink("twitch", "de", 1, "https://twitch.tv/rl_de"),
            StreamLink("youtube", None, None, "https://youtube.com/c/Rocket_League"),
        ]
        md = streams_to_markdown(streams)
        lines = md.splitlines()
        self.assertEqual(lines[0], "|Name|Platform|Language|")
        self.assertEqual(lines[1], "|:-|:-|:-|")
        # Body rows include the link with pretty name + platform/language cells.
        body = "\n".join(lines[2:])
        self.assertIn("[Rl En](https://twitch.tv/rl_en)|Twitch|English", body)
        self.assertIn("[Rl De](https://twitch.tv/rl_de)|Twitch|German", body)
        self.assertIn("[Rocket League](https://youtube.com/c/Rocket_League)|YouTube", body)

    def test_english_sorted_first(self):
        streams = [
            StreamLink("twitch", "de", 1, "https://tw/de"),
            StreamLink("twitch", "en", 1, "https://tw/en"),
        ]
        md = streams_to_markdown(streams)
        en_pos = md.index("https://tw/en")
        de_pos = md.index("https://tw/de")
        self.assertLess(en_pos, de_pos)

    def test_youtube_sorted_before_twitch_within_language(self):
        streams = [
            StreamLink("twitch", "en", 1, "https://tw/en"),
            StreamLink("youtube", "en", 1, "https://yt/en"),
        ]
        md = streams_to_markdown(streams)
        self.assertLess(md.index("https://yt/en"), md.index("https://tw/en"))


class TestHandleBroadcastLookup(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.mock_data = mock.MagicMock()
        self.mock_data.read_all_aliases.return_value = {}
        self.mock_singleton = patch(
            "data_bridge.Data.singleton", return_value=self.mock_data
        ).start()
        self.addCleanup(self.mock_singleton.stop)

        self.channel = mock.AsyncMock(spec=discord.TextChannel)

    async def test_renders_streams_via_stub_api(self):
        api = StubLiquipediaAPI(streams=[
            StreamLink("twitch", "en", 1, "https://twitch.tv/rl_en"),
            StreamLink("youtube", None, None, "https://youtube.com/c/Rocket_League"),
        ])
        with patch(
            "stdout.print_to_channel", new_callable=mock.AsyncMock
        ) as mock_print:
            await handle_broadcast_lookup(
                "https://liquipedia.net/rocketleague/RLCS/2026",
                self.channel,
                api=api,
            )
        self.assertEqual(api.calls, [("rocketleague", "RLCS/2026")])
        mock_print.assert_awaited_once()
        # Second positional arg is the markdown body.
        markdown = mock_print.call_args.args[1]
        self.assertIn("|Name|Platform|Language|", markdown)
        self.assertIn("https://twitch.tv/rl_en", markdown)
        self.assertIn("https://youtube.com/c/Rocket_League", markdown)

    async def test_invalid_url_reports_and_skips_api(self):
        api = StubLiquipediaAPI()
        with patch("stdout.print_to_channel", new_callable=mock.AsyncMock) as mock_print:
            await handle_broadcast_lookup("not-a-url", self.channel, api=api)
        self.channel.send.assert_awaited()
        mock_print.assert_not_awaited()
        self.assertEqual(api.calls, [])

    async def test_api_error_is_reported(self):
        from liqui.liquipedia_api import LiquipediaAPIError

        api = StubLiquipediaAPI(raise_exc=LiquipediaAPIError("boom"))
        with patch("stdout.print_to_channel", new_callable=mock.AsyncMock) as mock_print:
            await handle_broadcast_lookup(
                "https://liquipedia.net/rocketleague/RLCS/2026",
                self.channel,
                api=api,
            )
        self.channel.send.assert_awaited()
        mock_print.assert_not_awaited()

    async def test_aliases_applied_to_markdown(self):
        self.mock_data.read_all_aliases.return_value = {"Rocket_League": "RL"}
        api = StubLiquipediaAPI(streams=[
            StreamLink("youtube", None, None, "https://youtube.com/c/Rocket_League"),
        ])
        with patch("stdout.print_to_channel", new_callable=mock.AsyncMock) as mock_print:
            await handle_broadcast_lookup(
                "https://liquipedia.net/rocketleague/RLCS/2026",
                self.channel,
                api=api,
            )
        markdown = mock_print.call_args.args[1]
        # Display name "Rocket League" should have alias applied.
        self.assertIn("RL", markdown)
        self.assertNotIn("[Rocket League]", markdown)


if __name__ == "__main__":
    unittest.main()
