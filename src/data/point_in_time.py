"""Point-in-time data capture and state management"""

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import requests


@dataclass
class PointInTimeState:
    """Captures all external state at a single frozen moment"""
    timestamp: str
    sport: str
    slate_date: str
    mlb_games: List[Dict]
    wnba_games: List[Dict]
    parlay_odds: Dict[str, Any]
    dfs_products: Dict[str, Any]
    lineups: Dict[str, Any]
    injuries: Dict[str, Any]
    weather: Dict[str, Any]
    information_state_hash: str
    # ParlayAPI data (parlay-api.com) — separate from the b365api parlay_odds above.
    # Stored as a dict keyed by sport token, each value being a dict with
    # "odds" and "props" lists as returned by ParlayAPIClient.fetch_all().
    parlayapi_odds: Dict[str, Any] = field(default_factory=dict)


class PointInTimeCapture:
    """Captures all external state atomically"""

    _PARLAY_ODDS_SNAPSHOT_PATH = (
        Path(__file__).resolve().parents[2] / "data" / "parlay_odds_snapshot.json"
    )

    @staticmethod
    def _require_env(name: str) -> str:
        value = os.environ.get(name, "").strip()
        if not value:
            raise RuntimeError(
                f"Missing required environment variable: {name}. "
                f"Configure it as a runtime env var or repository secret."
            )
        return value

    # Default base URL for the Parlay API service.
    # Can be overridden via B365_API_BASE_URL for backward compatibility.
    _PARLAY_API_BASE_URL = "https://parlay-api.com"

    @staticmethod
    def _normalize_parlay_payload(payload: Any) -> Dict[str, Any]:
        if payload is None:
            raise RuntimeError("Parlay API returned an empty payload.")

        # Normalize to dict so downstream hashing and consumers are deterministic.
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, list):
            return {f"item_{idx}": item for idx, item in enumerate(payload)}

        raise RuntimeError("Parlay API payload has unsupported format.")

    @staticmethod
    def _snapshot_mode_enabled() -> bool:
        value = os.environ.get("PARLAY_ODDS_SNAPSHOT_MODE", "").strip().lower()
        return value in {"1", "true", "yes", "on"}

    def _load_local_parlay_odds_snapshot(self) -> Dict[str, Any]:
        snapshot_path = self._PARLAY_ODDS_SNAPSHOT_PATH
        if not snapshot_path.exists():
            raise RuntimeError(
                f"Local parlay odds snapshot not found: {snapshot_path}"
            )

        try:
            with snapshot_path.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Local parlay odds snapshot is malformed JSON: {snapshot_path}"
            ) from exc
        except OSError as exc:
            raise RuntimeError(
                f"Local parlay odds snapshot could not be read: {snapshot_path}"
            ) from exc

        return self._normalize_parlay_payload(payload)

    def _fetch_parlay_odds(self, sports: List[str], date: str) -> Dict[str, Any]:
        """
        Fetch live odds from the Parlay API service.

        Required env vars:
          - PARLAY_API2  — API credential/token issued by Parlay API

        Optional env vars:
          - B365_API_BASE_URL  — override the default base URL
                                 (default: https://parlay-api.com)
          - SPORTSBOOKODDS     — override the odds endpoint path
                                 (default: v1/bet365/odds)

        Legacy env vars (kept for backward compatibility, ignored when
        PARLAY_API2 is set):
          - PARLAY_API_KEY     — previously used as the b365api credential
        """
        if self._snapshot_mode_enabled():
            return self._load_local_parlay_odds_snapshot()

        # PARLAY_API2 is the sole required credential.  Fall back to the legacy
        # PARLAY_API_KEY name so that any existing CI setup continues to work.
        api_key = (
            os.environ.get("PARLAY_API2", "").strip()
            or os.environ.get("PARLAY_API_KEY", "").strip()
        )
        if not api_key:
            raise RuntimeError(
                "Missing required environment variable: PARLAY_API2. "
                "Set your b365api token as PARLAY_API2."
            )

        api_base = (
            os.environ.get("B365_API_BASE_URL", "").strip()
            or self._PARLAY_API_BASE_URL
        )
        odds_path = (
            os.environ.get("SPORTSBOOKODDS", "").strip()
            or "v1/bet365/odds"
        )

        endpoint = f"{api_base.rstrip('/')}/{odds_path.lstrip('/')}"
        headers = {"Authorization": "Bearer " + api_key}
        params = {
            "token": api_key,
            "sport": ",".join(sports),
            "date": date,
        }

        try:
            response = requests.get(endpoint, headers=headers, params=params, timeout=20)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"Parlay API request failed: {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError("Parlay API returned non-JSON response.") from exc

        return self._normalize_parlay_payload(payload)

    def _fetch_sport_slate(
        self,
        sport: str,
        date: str,
    ) -> tuple:
        """
        Fetch odds + props from ParlayAPIClient for *sport*.

        Returns (odds_records, props_records).

        Raises RuntimeError if PARLAYAPI_API_KEY / PARLAY_API_BASE_URL are
        absent — the caller must not silently fall back to mock data.
        """
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient()
        odds = client.fetch_odds(sport)
        props = client.fetch_props(sport)
        return odds, props

    def capture_slate_state(self, sports: List[str], date: str, api_key: str) -> PointInTimeState:
        """Main PIT capture"""
        ts = datetime.now().isoformat()

        from src.data.slate_normalizer import normalize_mlb_slate, normalize_wnba_slate

        # MLB slate — sourced from ParlayAPIClient (parlay-api.com).
        # Raises RuntimeError if credentials are absent or no games are found
        # for the requested date; no silent fallback to hardcoded data.
        mlb_games: List[Dict] = []
        if "mlb" in sports:
            mlb_odds, mlb_props = self._fetch_sport_slate("mlb", date)
            mlb_games = normalize_mlb_slate(mlb_odds, mlb_props, date)

        # WNBA slate — same approach.
        wnba_games: List[Dict] = []
        if "wnba" in sports:
            wnba_odds, wnba_props = self._fetch_sport_slate("wnba", date)
            wnba_games = normalize_wnba_slate(wnba_odds, wnba_props, date)

        # Live b365api odds (no silent fallback to mocks)
        _ = api_key  # maintained for signature compatibility; auth is env-driven
        parlay_odds = self._fetch_parlay_odds(sports, date)

        # ParlayAPI (parlay-api.com) — separate data source, fetched only when
        # the required credentials are configured.  A missing key is non-fatal
        # here so that the b365api path continues to work independently; a
        # RuntimeError from ParlayAPIClient propagates naturally when the vars
        # are present but the request fails.
        parlayapi_odds: Dict[str, Any] = {}
        if os.environ.get("PARLAYAPI_API_KEY", "").strip() and \
                os.environ.get("PARLAY_API_BASE_URL", "").strip():
            from src.data.parlayapi_client import ParlayAPIClient
            parlayapi_odds = ParlayAPIClient().fetch_all(sports)
        
        # Mock DFS products
        dfs_products = {
            "draftkingspick6": {
                "mlb_1_pitcher_strikeouts_6.5": {"multiplier": 1.85, "threshold": 6.5},
            },
            "parlayplay": {
                "mlb_1_pitcher_strikeouts_6.5": {"payout_multiple": 2.1, "threshold": 6.5},
            },
            "chalkboard": {
                "wnba_1_player_points_18.5": {"multiplier": 1.65, "threshold": 18.5},
            },
        }
        
        # Information state hash.
        # parlayapi_odds is included because it is live external market data
        # that affects the informational state of the system at capture time,
        # consistent with how parlay_odds (b365api) is already included.  Any
        # change in the ParlayAPI market data will therefore produce a different
        # hash, enabling downstream consumers to detect staleness.
        state_str = json.dumps(
            [mlb_games, wnba_games, parlay_odds, parlayapi_odds],
            default=str,
            sort_keys=True,
        )
        info_hash = hashlib.sha256(state_str.encode()).hexdigest()
        
        return PointInTimeState(
            timestamp=ts,
            sport=",".join(sports),
            slate_date=date,
            mlb_games=mlb_games if "mlb" in sports else [],
            wnba_games=wnba_games if "wnba" in sports else [],
            parlay_odds=parlay_odds,
            dfs_products=dfs_products,
            lineups={},
            injuries={},
            weather={},
            information_state_hash=info_hash,
            parlayapi_odds=parlayapi_odds,
        )
