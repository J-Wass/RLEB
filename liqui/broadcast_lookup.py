"""Broadcast stream-link lookup powered by the Liquipedia DB API v3.

Replaces the diesel `/broadcast` route. Pulls the unique stream URLs
(YouTube, Twitch, etc.) attached to a tournament's matches and renders them
as a reddit markdown table so viewers can find the watch links.
"""

from __future__ import annotations

from typing import Optional
from urllib.parse import unquote

import discord

import global_settings
import stdout
from data_bridge import Data
from liqui.liquipedia_api import LiquipediaAPI, LiquipediaAPIError, default_client
from liqui.liquipedia_models import StreamLink


# Pretty platform names for the rendered table.
_PLATFORM_LABELS = {
    "youtube": "YouTube",
    "twitch": "Twitch",
    "facebook": "Facebook",
    "trovo": "Trovo",
    "afreeca": "AfreecaTV",
    "bilibili": "Bilibili",
    "douyu": "Douyu",
    "huya": "Huya",
    "kick": "Kick",
    "nimo": "Nimo TV",
    "tiktok": "TikTok",
    "youku": "Youku",
    "stream": "Stream",
}

# Common two-letter language codes — only used for nicer display labels.
_LANGUAGE_LABELS = {
    "en": "English",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "pt": "Portuguese",
    "it": "Italian",
    "ru": "Russian",
    "pl": "Polish",
    "tr": "Turkish",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "ar": "Arabic",
    "nl": "Dutch",
    "se": "Swedish",
    "no": "Norwegian",
    "da": "Danish",
    "fi": "Finnish",
}


def parse_liquipedia_url(url: str) -> tuple[str, str]:
    """Split a Liquipedia URL into (wiki, pagename).

    Example: "https://liquipedia.net/rocketleague/Rocket_League_Championship_Series/2026"
        -> ("rocketleague", "Rocket_League_Championship_Series/2026")
    """
    cleaned = url.strip()
    for prefix in ("https://", "http://"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
    if cleaned.startswith("www."):
        cleaned = cleaned[4:]
    if not cleaned.startswith("liquipedia.net/"):
        raise ValueError(f"Not a Liquipedia URL: {url!r}")
    path = cleaned[len("liquipedia.net/"):]
    for sep in ("?", "#"):
        if sep in path:
            path = path.split(sep, 1)[0]
    if "/" not in path:
        raise ValueError(f"URL missing wiki and page: {url!r}")
    wiki, _, pagename = path.partition("/")
    if not wiki or not pagename:
        raise ValueError(f"URL missing wiki and page: {url!r}")
    pagename = unquote(pagename).replace(" ", "_")
    return wiki, pagename


def _platform_label(platform: str) -> str:
    return _PLATFORM_LABELS.get(platform.lower(), platform.title())


def _language_label(lang: Optional[str]) -> str:
    if not lang:
        return ""
    return _LANGUAGE_LABELS.get(lang.lower(), lang.upper())


def _sort_key(s: StreamLink) -> tuple[int, str, str, int]:
    # English first, then alphabetical by language; YouTube before Twitch
    # within a language; preserve numeric ordering of variant index.
    lang = (s.language or "").lower()
    lang_rank = 0 if lang == "en" else (1 if lang else 2)
    platform_rank = {"youtube": 0, "twitch": 1}.get(s.platform.lower(), 2)
    return (lang_rank, lang, f"{platform_rank}_{s.platform}", s.index or 0)


def _stream_display_name(url: str) -> str:
    """Pretty-format the last path segment of a stream URL.

    Examples:
        https://twitch.tv/rocketleague           -> "Rocketleague"
        https://youtube.com/c/Rocket_League      -> "Rocket League"
        https://youtube.com/@RocketLeagueEsports -> "Rocketleagueesports"
        https://.../Special:Stream/youtube/RL    -> "Rl"
    """
    # Strip query string and fragment, drop trailing slashes.
    cleaned = url.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    segment = cleaned.rsplit("/", 1)[-1] if "/" in cleaned else cleaned
    segment = segment.lstrip("@")
    pretty = segment.replace("_", " ").replace("-", " ").strip()
    return pretty.title() if pretty else url


def streams_to_markdown(streams: list[StreamLink]) -> str:
    """Render stream links as a reddit markdown table."""
    if not streams:
        return "*No broadcast streams are listed for this page yet.*"

    rows = sorted(streams, key=_sort_key)
    lines = ["|Name|Platform|Language|", "|:-|:-|:-|"]
    for s in rows:
        name = _stream_display_name(s.url)
        lines.append(
            f"|[{name}]({s.url})"
            f"|{_platform_label(s.platform)}"
            f"|{_language_label(s.language) or '—'}|"
        )
    return "\n".join(lines)


def _apply_aliases(markdown: str) -> str:
    aliases = Data.singleton().read_all_aliases()
    for long_name, short_name in aliases.items():
        markdown = markdown.replace(
            long_name.replace("_", " "), short_name.replace("_", " ")
        )
    return markdown


async def handle_broadcast_lookup(
    url: str,
    channel: discord.channel.TextChannel,
    api: Optional[LiquipediaAPI] = None,
) -> None:
    """Look up broadcast streams for a Liquipedia tournament and post markdown."""
    global_settings.rleb_log_info(
        f"LIQUI_API: Creating broadcast stream lookup for {url}"
    )
    try:
        wiki, pagename = parse_liquipedia_url(url)
    except ValueError as e:
        await channel.send(f"Couldn't parse URL: {e}")
        return

    client = api or default_client()
    try:
        streams = client.tournament_streams(wiki=wiki, pagename=pagename)
    except LiquipediaAPIError as e:
        await channel.send(f"Failed to query Liquipedia streams: {e}")
        global_settings.rleb_log_error(f"LIQUI_API broadcast lookup failed: {e}")
        return
    except Exception as e:
        await channel.send("Failed to build broadcast streams table :(")
        await channel.send(str(e))
        global_settings.rleb_log_error(f"LIQUI_API broadcast lookup failed: {e}")
        return

    markdown = streams_to_markdown(streams)
    markdown = _apply_aliases(markdown)
    await stdout.print_to_channel(
        channel, markdown, title="Broadcasts", force_pastebin=True
    )
