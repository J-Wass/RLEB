"""Client for the Liquipedia DB API v3.

Reference: https://api.liquipedia.net/api/v3/

All requests must be GET, authenticated via an `Authorization: Apikey <key>`
header, and include a `wiki` query parameter. The client must accept gzip.
Liquipedia's published policy throttles API v3 callers to ~1 request every 2
seconds per endpoint; this module enforces that locally so callers don't have
to track it.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Iterable, Optional, Union

import requests

import global_settings
from liqui.liquipedia_models import Broadcaster, Match, StreamLink


BASE_URL = "https://api.liquipedia.net/api/v3"
DEFAULT_USER_AGENT = "RLEB/1.0 (r/RocketLeagueEsports; https://github.com/J-Wass/RLEB)"
MIN_SECONDS_BETWEEN_CALLS_PER_ENDPOINT = 4.0


class LiquipediaAPIError(Exception):
    """Raised when the Liquipedia API returns an error payload or a non-2xx status."""


class LiquipediaAPI:
    """Thin wrapper around the Liquipedia DB API v3."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        user_agent: str = DEFAULT_USER_AGENT,
        base_url: str = BASE_URL,
        min_seconds_between_calls: float = MIN_SECONDS_BETWEEN_CALLS_PER_ENDPOINT,
        session: Optional[requests.Session] = None,
    ) -> None:
        self._api_key = api_key or global_settings.LIQUIPEDIA_API_KEY
        if not self._api_key:
            raise LiquipediaAPIError(
                "No Liquipedia API key configured. Set LIQUIPEDIA_API_KEY env var "
                "or [Liquipedia] LIQUIPEDIA_API_KEY in rleb_secrets.ini."
            )
        self._base_url = base_url.rstrip("/")
        self._min_interval = min_seconds_between_calls
        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Apikey {self._api_key}",
                "Accept-Encoding": "gzip",
                "User-Agent": user_agent,
            }
        )
        # Per-endpoint last-call timestamps for local throttling.
        self._last_call: dict[str, float] = {}
        self._throttle_lock = threading.Lock()

    def get(
        self,
        endpoint: str,
        wiki: Union[str, Iterable[str]],
        *,
        conditions: Optional[str] = None,
        query: Optional[str] = None,
        order: Optional[str] = None,
        groupby: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        extra_params: Optional[dict[str, Any]] = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """GET a single page of results from `endpoint` (e.g. "match", "tournament").

        `wiki` may be a single wiki id ("rocketleague") or an iterable of ids,
        which will be pipe-joined per the v3 multi-wiki convention.

        Returns the parsed JSON body. Raises `LiquipediaAPIError` on HTTP errors
        or when the response payload contains an `error` array.
        """
        endpoint_path = endpoint.strip("/")
        url = f"{self._base_url}/{endpoint_path}"

        params: dict[str, Any] = {"wiki": _format_wiki(wiki)}
        if conditions is not None:
            params["conditions"] = conditions
        if query is not None:
            params["query"] = query
        if order is not None:
            params["order"] = order
        if groupby is not None:
            params["groupby"] = groupby
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if extra_params:
            params.update(extra_params)

        self._throttle(endpoint_path)
        response = self._session.get(url, params=params, timeout=timeout)
        if response.status_code >= 300:
            raise LiquipediaAPIError(
                f"Liquipedia API {endpoint_path} returned HTTP {response.status_code}: "
                f"{response.text[:500]}"
            )

        try:
            payload = response.json()
        except ValueError as e:
            raise LiquipediaAPIError(
                f"Liquipedia API {endpoint_path} returned non-JSON body: "
                f"{response.text[:500]}"
            ) from e

        errors = payload.get("error") or []
        if errors:
            raise LiquipediaAPIError(
                f"Liquipedia API {endpoint_path} error: {'; '.join(map(str, errors))}"
            )
        return payload

    def get_all(
        self,
        endpoint: str,
        wiki: Union[str, Iterable[str]],
        *,
        page_size: int = 1000,
        max_results: Optional[int] = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Page through `endpoint` until the API returns fewer than `page_size`
        results (or `max_results` is hit). Returns the concatenated `result` list.
        """
        if page_size <= 0 or page_size > 1000:
            raise ValueError("page_size must be in (0, 1000]")

        kwargs.pop("limit", None)
        offset = int(kwargs.pop("offset", 0) or 0)

        collected: list[dict[str, Any]] = []
        while True:
            payload = self.get(
                endpoint, wiki, limit=page_size, offset=offset, **kwargs
            )
            batch = payload.get("result") or []
            collected.extend(batch)
            if len(batch) < page_size:
                break
            if max_results is not None and len(collected) >= max_results:
                break
            offset += page_size

        if max_results is not None:
            return collected[:max_results]
        return collected

    def broadcasters(
        self,
        wiki: Union[str, Iterable[str]] = "rocketleague",
        *,
        pagename: Optional[str] = None,
        parent: Optional[str] = None,
        conditions: Optional[str] = None,
        order: Optional[str] = "weight DESC, name ASC",
        max_results: Optional[int] = None,
    ) -> list[Broadcaster]:
        """Typed wrapper around /v3/broadcasters.

        Provide `pagename` (e.g. "Rocket_League_Championship_Series/2026") to
        scope to a single tournament page, or `parent` to scope to any of its
        subpages. `conditions` overrides both if given (full control).
        """
        if conditions is None:
            clauses: list[str] = []
            if pagename is not None:
                clauses.append(f"[[pagename::{pagename}]]")
            if parent is not None:
                clauses.append(f"[[parent::{parent}]]")
            conditions = " AND ".join(clauses) if clauses else None

        rows = self.get_all(
            "broadcasters",
            wiki,
            conditions=conditions,
            order=order,
            max_results=max_results,
        )
        return [Broadcaster.from_api(r) for r in rows]

    def matches(
        self,
        wiki: Union[str, Iterable[str]] = "rocketleague",
        *,
        pagename: Optional[str] = None,
        parent: Optional[str] = None,
        conditions: Optional[str] = None,
        order: Optional[str] = "date ASC",
        streamurls: bool = True,
        max_results: Optional[int] = None,
    ) -> list[Match]:
        """Typed wrapper around /v3/match.

        `streamurls=True` (default) asks the API to return real provider URLs
        when available; otherwise the API may return Liquipedia redirector URLs.
        """
        if conditions is None:
            clauses: list[str] = []
            if pagename is not None:
                clauses.append(f"[[pagename::{pagename}]]")
            if parent is not None:
                clauses.append(f"[[parent::{parent}]]")
            conditions = " AND ".join(clauses) if clauses else None

        rows = self.get_all(
            "match",
            wiki,
            conditions=conditions,
            order=order,
            extra_params={"streamurls": "true"} if streamurls else None,
            max_results=max_results,
        )
        return [Match.from_api(r) for r in rows]

    def tournament_streams(
        self,
        wiki: str,
        pagename: str,
        *,
        include_subpages: bool = True,
    ) -> list[StreamLink]:
        """Aggregate the unique broadcast stream URLs for a tournament page.

        Pulls matches for `pagename` (and, if `include_subpages`, child pages
        via `parent`), dedupes their stream entries, and returns one
        `StreamLink` per unique URL.
        """
        matches = self.matches(wiki=wiki, pagename=pagename)
        if include_subpages:
            matches.extend(self.matches(wiki=wiki, parent=pagename))

        seen: dict[str, StreamLink] = {}
        for m in matches:
            for s in m.streams:
                if s.url not in seen:
                    seen[s.url] = s
        return list(seen.values())

    def _throttle(self, endpoint_path: str) -> None:
        if self._min_interval <= 0:
            return
        with self._throttle_lock:
            last = self._last_call.get(endpoint_path, 0.0)
            wait = self._min_interval - (time.monotonic() - last)
            if wait > 0:
                time.sleep(wait)
            self._last_call[endpoint_path] = time.monotonic()


def _format_wiki(wiki: Union[str, Iterable[str]]) -> str:
    if isinstance(wiki, str):
        return wiki
    return "|".join(wiki)


_default_client: Optional[LiquipediaAPI] = None
_default_client_lock = threading.Lock()


def default_client() -> LiquipediaAPI:
    """Return a shared `LiquipediaAPI` built from `global_settings`."""
    global _default_client
    with _default_client_lock:
        if _default_client is None:
            _default_client = LiquipediaAPI()
        return _default_client
