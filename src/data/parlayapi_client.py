"""
ParlayAPI client (parlay-api.com).

Fetches live odds and player-prop data for supported sports.

Required environment variables
--------------------------------
PARLAYAPI_API_KEY   : API key issued by parlay-api.com
PARLAY_API_BASE_URL : Base URL for the v1 API, e.g. https://parlay-api.com/v1
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

# Map internal sport tokens to parlay-api.com sport keys
_SPORT_KEY_MAP: Dict[str, str] = {
    "mlb": "baseball_mlb",
    "wnba": "basketball_wnba",
}


class ParlayAPIClient:
    """Thin HTTP client for the parlay-api.com REST API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        if api_key is None:
            api_key = os.environ.get("PARLAYAPI_API_KEY", "").strip()
            if not api_key:
                raise RuntimeError(
                    "Missing required environment variable: PARLAYAPI_API_KEY. "
                    "Set it as a runtime env var or repository secret."
                )
        if base_url is None:
            base_url = os.environ.get("PARLAY_API_BASE_URL", "").strip()
            if not base_url:
                raise RuntimeError(
                    "Missing required environment variable: PARLAY_API_BASE_URL. "
                    "Set it as a runtime env var or repository secret."
                )

        self.api_key: str = api_key
        self.base_url: str = base_url.rstrip("/")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        return {"X-API-Key": self.api_key}

    @staticmethod
    def _sport_key(sport: str) -> str:
        key = _SPORT_KEY_MAP.get(sport.lower())
        if key is None:
            raise ValueError(
                f"Unsupported sport: '{sport}'. "
                f"Supported sports: {sorted(_SPORT_KEY_MAP)}"
            )
        return key

    def _get(self, path: str) -> Any:
        """Perform a GET request and return the parsed JSON payload."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            response = requests.get(url, headers=self._headers(), timeout=20)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"ParlayAPI request failed: {exc}") from exc

        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"ParlayAPI returned non-JSON response for {url}."
            ) from exc

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(tz=timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_odds(self, sport: str) -> List[Dict[str, Any]]:
        """
        Fetch moneyline / spread / totals odds for *sport*.

        Returns a flat list of records, one per (event, bookmaker, market).
        Each record contains:
          event_id, commence_time, home_team, away_team,
          bookmaker, bookmaker_title, market, outcomes, fetched_at
        """
        sport_key = self._sport_key(sport)
        payload = self._get(f"sports/{sport_key}/odds")

        fetched_at = self._now_iso()
        records: List[Dict[str, Any]] = []

        for event in payload:
            event_id = event.get("id", "")
            commence_time = event.get("commence_time", "")
            home_team = event.get("home_team", "")
            away_team = event.get("away_team", "")

            for bookmaker in event.get("bookmakers", []):
                bk_key = bookmaker.get("key", "")
                bk_title = bookmaker.get("title", "")

                for market in bookmaker.get("markets", []):
                    records.append(
                        {
                            "event_id": event_id,
                            "commence_time": commence_time,
                            "home_team": home_team,
                            "away_team": away_team,
                            "bookmaker": bk_key,
                            "bookmaker_title": bk_title,
                            "market": market.get("key", ""),
                            "outcomes": market.get("outcomes", []),
                            "market_source": "odds",
                            "fetched_at": fetched_at,
                        }
                    )

        return records

    def fetch_props(self, sport: str) -> List[Dict[str, Any]]:
        """
        Fetch player-prop lines for *sport*.

        Returns the same record structure as :meth:`fetch_odds` but with
        ``market_source == 'props'``.
        """
        sport_key = self._sport_key(sport)
        payload = self._get(f"sports/{sport_key}/props")

        fetched_at = self._now_iso()
        records: List[Dict[str, Any]] = []

        for event in payload:
            event_id = event.get("id", "")
            commence_time = event.get("commence_time", "")
            home_team = event.get("home_team", "")
            away_team = event.get("away_team", "")

            for bookmaker in event.get("bookmakers", []):
                bk_key = bookmaker.get("key", "")
                bk_title = bookmaker.get("title", "")

                for market in bookmaker.get("markets", []):
                    records.append(
                        {
                            "event_id": event_id,
                            "commence_time": commence_time,
                            "home_team": home_team,
                            "away_team": away_team,
                            "bookmaker": bk_key,
                            "bookmaker_title": bk_title,
                            "market": market.get("key", ""),
                            "outcomes": market.get("outcomes", []),
                            "market_source": "props",
                            "fetched_at": fetched_at,
                        }
                    )

        return records

    def fetch_all(self, sports: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Fetch both odds and props for every supported sport in *sports*.

        Unsupported sport tokens are silently skipped.

        Returns a dict with keys ``{sport}_odds`` and ``{sport}_props``
        for each supported sport.  Example for ``["mlb", "wnba"]``::

            {
                "mlb_odds":  [...],
                "mlb_props": [...],
                "wnba_odds":  [...],
                "wnba_props": [...],
            }
        """
        result: Dict[str, List[Dict[str, Any]]] = {}

        for sport in sports:
            if sport.lower() not in _SPORT_KEY_MAP:
                continue
            result[f"{sport}_odds"] = self.fetch_odds(sport)
            result[f"{sport}_props"] = self.fetch_props(sport)

        return result
