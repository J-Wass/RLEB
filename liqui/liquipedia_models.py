"""Typed dataclasses representing rows from the Liquipedia DB API v3."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


def _as_int(value: Any, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


@dataclass(frozen=True)
class Broadcaster:
    """A row from /v3/broadcasters."""

    pageid: int
    pagename: str
    id: str
    name: str
    page: str
    position: str
    language: str
    flag: str
    weight: int
    date: str
    parent: str
    wiki: str
    extradata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, raw: Mapping[str, Any]) -> "Broadcaster":
        return cls(
            pageid=_as_int(raw.get("pageid")),
            pagename=_as_str(raw.get("pagename")),
            id=_as_str(raw.get("id")),
            name=_as_str(raw.get("name")),
            page=_as_str(raw.get("page")),
            position=_as_str(raw.get("position")),
            language=_as_str(raw.get("language")),
            flag=_as_str(raw.get("flag")),
            weight=_as_int(raw.get("weight")),
            date=_as_str(raw.get("date")),
            parent=_as_str(raw.get("parent")),
            wiki=_as_str(raw.get("wiki")),
            extradata=raw.get("extradata") or {},
        )


@dataclass(frozen=True)
class StreamLink:
    """A single broadcast stream URL extracted from a match's `stream` dict.

    The Liquipedia match API exposes streams as keys like:
      - `youtube` (default channel for the platform)
      - `twitch_en_1`, `twitch_de_2` (platform_language_index variants)
    """

    platform: str  # "youtube", "twitch", etc.
    language: Optional[str]  # "en", "de", ... or None for the default
    index: Optional[int]  # 1, 2, ... or None for the default
    url: str

    @classmethod
    def from_stream_entry(cls, key: str, url: str) -> "StreamLink":
        parts = key.split("_")
        platform = parts[0]
        language: Optional[str] = parts[1] if len(parts) > 1 else None
        index: Optional[int] = None
        if len(parts) > 2:
            try:
                index = int(parts[2])
            except ValueError:
                index = None
        return cls(platform=platform, language=language, index=index, url=url)


@dataclass(frozen=True)
class Match:
    """A row from /v3/match. Only the fields the broadcast lookup needs are
    parsed — the raw payload is preserved on `raw` for callers that want more.
    """

    pageid: int
    pagename: str
    parent: str
    tournament: str
    date: str
    streams: tuple[StreamLink, ...]
    wiki: str
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_api(cls, raw: Mapping[str, Any]) -> "Match":
        stream_dict = raw.get("stream") or {}
        streams = tuple(
            StreamLink.from_stream_entry(k, v)
            for k, v in stream_dict.items()
            if isinstance(v, str) and v
        )
        return cls(
            pageid=_as_int(raw.get("pageid")),
            pagename=_as_str(raw.get("pagename")),
            parent=_as_str(raw.get("parent")),
            tournament=_as_str(raw.get("tournament")),
            date=_as_str(raw.get("date")),
            streams=streams,
            wiki=_as_str(raw.get("wiki")),
            raw=raw,
        )
