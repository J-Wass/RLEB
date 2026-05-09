"""
Liquipedia DB API v3 client.

This module is the future replacement for the HTML-scraping approach used
by the other liqui/* modules. It uses the structured JSON API at
https://api.liquipedia.net/api/v3/ instead of parsing MediaWiki HTML.

Migration plan:
  team_lookup.py      -> get_teams() / get_players()
  bracket_lookup.py   -> get_matches()
  group_lookup.py     -> get_standings()
  swiss_lookup.py     -> get_standings() with [[type::swiss]] condition
  prizepool_lookup.py -> get_prizepool()
  diesel broadcasts   -> get_broadcasts()
  diesel schedule     -> get_matches() filtered by date range

API reference: liqui/doc1.md
Response envelope: {"result": [...], "error": [...], "warning": [...]}
Conditions syntax: [[field::value]] with AND/OR, e.g. [[parent::RLCS/2025/Worlds]]
"""

import configparser
import logging
import os
from typing import Any

import requests

_BASE_URL = "https://api.liquipedia.net/api/v3"
_WIKI = "rocketleague"

_config = configparser.ConfigParser(interpolation=None)
if os.path.exists("rleb_secrets.ini"):
    _config.read("rleb_secrets.ini")
else:
    _config.read("rleb_secrets_sample.ini")

_API_KEY = _config["Liquipedia"]["LIQUIPEDIA_API_KEY"]

log = logging.getLogger(__name__)


def _tournament_condition(tournament_page: str) -> str:
    """Build the standard parent condition for tournament-scoped queries."""
    return f"[[parent::{tournament_page}]]"


class LiquipediaApiClient:
    """Client for the Liquipedia DB API v3."""

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": "r/RocketLeagueEsports Thread Tools",
                "Authorization": f"Apikey {_API_KEY}",
                "Accept-Encoding": "gzip",
            }
        )

    def _get(
        self,
        endpoint: str,
        conditions: str | None = None,
        query: str | None = None,
        order: str | None = None,
        groupby: str | None = None,
        limit: int = 100,
        offset: int = 0,
        **extra_params: Any,
    ) -> list[dict[str, Any]]:
        """
        GET an API endpoint and return the unwrapped result list.

        Raises requests.HTTPError on non-2xx responses.
        Logs any API warnings.
        """
        params: dict[str, Any] = {"wiki": _WIKI, "limit": limit, "offset": offset}
        if conditions:
            params["conditions"] = conditions
        if query:
            params["query"] = query
        if order:
            params["order"] = order
        if groupby:
            params["groupby"] = groupby
        params.update(extra_params)

        response = self._session.get(f"{_BASE_URL}/{endpoint}", params=params)
        response.raise_for_status()

        data = response.json()
        if warnings := data.get("warning"):
            for w in warnings:
                log.warning("Liquipedia API warning (%s): %s", endpoint, w)

        return data.get("result", [])

    # ------------------------------------------------------------------
    # Matches — replaces bracket_lookup.py and diesel schedule endpoints
    # ------------------------------------------------------------------

    def get_matches(
        self,
        tournament_page: str,
        extra_conditions: str | None = None,
        query: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Return match data for a tournament.

        Args:
            tournament_page: Liquipedia page name, e.g. "RLCS/2025/World_Championship"
            extra_conditions: Optional additional [[field::value]] conditions joined with AND.
            query: Comma-separated field names to return. Default returns all fields.
            limit: Max results (default 100, max 1000).
            offset: Pagination offset.

        Returns:
            List of match dicts. Key fields:
              match2id, match2opponents (json), match2games (json),
              status, finished (bool), date, bestof,
              stream (json), parent, tournament, section.

        Replaces: bracket_lookup.py, diesel /bracket and /makethread endpoints.
        """
        conditions = _tournament_condition(tournament_page)
        if extra_conditions:
            conditions = f"{conditions} AND {extra_conditions}"
        return self._get(
            "match",
            conditions=conditions,
            query=query,
            order="date ASC",
            limit=limit,
            offset=offset,
        )

    def get_schedule(
        self,
        tournament_page: str,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Return matches for a tournament filtered by date range.

        Args:
            tournament_page: Liquipedia page name.
            date_from: ISO date string "YYYY-MM-DD" (inclusive lower bound).
            date_to: ISO date string "YYYY-MM-DD" (inclusive upper bound).
            limit: Max results.
            offset: Pagination offset.

        Returns:
            Same shape as get_matches(), ordered by date ASC.

        Replaces: diesel /schedule endpoint.
        """
        parts = [_tournament_condition(tournament_page)]
        if date_from:
            parts.append(f"[[date::>{date_from}]]")
        if date_to:
            parts.append(f"[[date::<{date_to}]]")
        return self._get(
            "match",
            conditions=" AND ".join(parts),
            order="date ASC",
            limit=limit,
            offset=offset,
        )

    # ------------------------------------------------------------------
    # Standings (groups + swiss) — replaces group_lookup.py, swiss_lookup.py
    # ------------------------------------------------------------------

    def get_standings(
        self,
        tournament_page: str,
        standings_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Return standings tables for a tournament (groups, swiss, etc.).

        Args:
            tournament_page: Liquipedia page name.
            standings_type: Optional type filter, e.g. "swiss", "league". If None,
                            all standing table types are returned.
            limit: Max results.
            offset: Pagination offset.

        Returns:
            List of standingstable dicts. Key fields:
              parent, standingsindex, title, tournament, section,
              type, matches (json), config (json).

        Replaces: group_lookup.py (standings_type=None), swiss_lookup.py (standings_type="swiss"),
                  diesel /groups and /swiss endpoints.
        """
        parts = [_tournament_condition(tournament_page)]
        if standings_type:
            parts.append(f"[[type::{standings_type}]]")
        return self._get(
            "standingstable",
            conditions=" AND ".join(parts),
            order="standingsindex ASC",
            limit=limit,
            offset=offset,
        )

    # ------------------------------------------------------------------
    # Prize pool — replaces prizepool_lookup.py
    # ------------------------------------------------------------------

    def get_prizepool(
        self,
        tournament_page: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Return placement/prize pool data for a tournament.

        Args:
            tournament_page: Liquipedia page name.
            limit: Max results.
            offset: Pagination offset.

        Returns:
            List of placement dicts ordered by placement. Key fields:
              placement, prizemoney, individualprizemoney,
              opponentname, opponenttemplate, opponentplayers (json),
              parent, tournament, date, liquipediatier.

        Replaces: prizepool_lookup.py and diesel /prizepool endpoint.
        """
        return self._get(
            "placement",
            conditions=_tournament_condition(tournament_page),
            order="prizepoolindex ASC",
            limit=limit,
            offset=offset,
        )

    # ------------------------------------------------------------------
    # Broadcasts — replaces diesel broadcast/stream endpoints
    # ------------------------------------------------------------------

    def get_broadcasts(
        self,
        tournament_page: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Return broadcast/stream info for a tournament.

        Args:
            tournament_page: Liquipedia page name.
            limit: Max results.
            offset: Pagination offset.

        Returns:
            List of broadcaster dicts ordered by weight DESC. Key fields:
              id, name, page, position, language, flag, weight, date, parent.

        Replaces: diesel /broadcast and /streams endpoints.
        """
        return self._get(
            "broadcasters",
            conditions=_tournament_condition(tournament_page),
            order="weight DESC",
            limit=limit,
            offset=offset,
        )

    # ------------------------------------------------------------------
    # Tournament metadata
    # ------------------------------------------------------------------

    def get_tournament(
        self,
        tournament_page: str,
    ) -> dict[str, Any] | None:
        """
        Return metadata for a single tournament.

        Args:
            tournament_page: Liquipedia page name.

        Returns:
            Tournament dict or None if not found. Key fields:
              pagename, name, shortname, startdate, enddate,
              prizepool, participantsnumber, liquipediatier,
              status, format, seriespage, locations (json).
        """
        results = self._get(
            "tournament",
            conditions=f"[[pagename::{tournament_page}]]",
            limit=1,
        )
        return results[0] if results else None

    def get_series(
        self,
        series_page: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Return metadata for a tournament series.

        Args:
            series_page: Liquipedia series page name.
            limit: Max results.
            offset: Pagination offset.

        Returns:
            List of series dicts. Key fields:
              pagename, name, abbreviation, game, type,
              organizers (json), locations (json), prizepool,
              liquipediatier, launcheddate, defunctdate, links (json).
        """
        return self._get(
            "series",
            conditions=f"[[pagename::{series_page}]]",
            limit=limit,
            offset=offset,
        )

    # ------------------------------------------------------------------
    # Teams & players
    # ------------------------------------------------------------------

    def get_teams(
        self,
        conditions: str | None = None,
        query: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Return team records.

        Teams aren't directly filterable by tournament page in /v3/team.
        Use get_players() to find which teams participated, then look up
        team details here by pagename.

        Args:
            conditions: [[field::value]] condition string.
            query: Comma-separated field names to return.
            limit: Max results.
            offset: Pagination offset.

        Returns:
            List of team dicts. Key fields:
              pagename, name, template, locations (json), region,
              logourl, logodarkurl, status, links (json).

        Replaces: team_lookup.py.
        """
        return self._get(
            "team",
            conditions=conditions,
            query=query,
            limit=limit,
            offset=offset,
        )

    def get_players(
        self,
        tournament_page: str,
        query: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Return squad players for a tournament.

        Args:
            tournament_page: Liquipedia page name.
            query: Comma-separated field names to return.
            limit: Max results.
            offset: Pagination offset.

        Returns:
            List of squadplayer dicts with player and team membership info.

        Used with: get_teams() to build full tournament roster tables.
        Replaces: team_lookup.py player roster parsing.
        """
        return self._get(
            "squadplayer",
            conditions=_tournament_condition(tournament_page),
            query=query,
            limit=limit,
            offset=offset,
        )


# Module-level singleton — import and use directly.
client = LiquipediaApiClient()
