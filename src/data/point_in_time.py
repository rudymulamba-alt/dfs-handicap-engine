"""Point-in-time data capture and state management"""

import hashlib
import json
import os
from datetime import datetime
from typing import Dict, List, Any
from dataclasses import dataclass
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


class PointInTimeCapture:
    """Captures all external state atomically"""

    @staticmethod
    def _require_env(name: str) -> str:
        value = os.environ.get(name, "").strip()
        if not value:
            raise RuntimeError(
                f"Missing required environment variable: {name}. "
                f"Configure it as a runtime env var or repository secret."
            )
        return value

    def _fetch_parlay_odds(self, sports: List[str], date: str) -> Dict[str, Any]:
        """
        Fetch live odds from the configured Parlay API endpoint.

        Required env vars:
          - PARLAY_API_KEY
          - PARLAY_API2
          - SPORTSBOOKODDS
        """
        api_key = self._require_env("PARLAY_API_KEY")
        api_base = self._require_env("PARLAY_API2")
        odds_path = self._require_env("SPORTSBOOKODDS")

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

        if payload is None:
            raise RuntimeError("Parlay API returned an empty payload.")

        # Normalize to dict so downstream hashing and consumers are deterministic.
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, list):
            return {f"item_{idx}": item for idx, item in enumerate(payload)}

        raise RuntimeError("Parlay API payload has unsupported format.")

    def capture_slate_state(self, sports: List[str], date: str, api_key: str) -> PointInTimeState:
        """Main PIT capture"""
        ts = datetime.now().isoformat()
        
        # Mock MLB games for 2026-08-19
        mlb_games = [
            {"id": "mlb_1", "away": "DET", "home": "PIT", "time": "12:35 PM", "pitcher_away": "Jobe", "pitcher_home": "Skenes"},
            {"id": "mlb_2", "away": "SD", "home": "NYM", "time": "1:10 PM", "pitcher_away": "King", "pitcher_home": "Stock"},
            {"id": "mlb_3", "away": "ATL", "home": "MIN", "time": "1:40 PM", "pitcher_away": "Smith-Shawver", "pitcher_home": "Bradley"},
            {"id": "mlb_4", "away": "CWS", "home": "CHC", "time": "2:20 PM", "pitcher_away": "Newcomb", "pitcher_home": "Holmes"},
            {"id": "mlb_5", "away": "ARI", "home": "BOS", "time": "4:10 PM", "pitcher_away": "Pfaadt", "pitcher_home": "Tolle"},
            {"id": "mlb_6", "away": "MIA", "home": "PHI", "time": "6:05 PM", "pitcher_away": "Alcantara", "pitcher_home": "Nola"},
            {"id": "mlb_7", "away": "NYY", "home": "BAL", "time": "6:35 PM", "pitcher_away": "Warren", "pitcher_home": "Bassitt"},
            {"id": "mlb_8", "away": "SF", "home": "CLE", "time": "6:40 PM", "pitcher_away": "Wilkinson", "pitcher_home": "Messick"},
            {"id": "mlb_9", "away": "STL", "home": "CIN", "time": "6:40 PM", "pitcher_away": "Liberatore", "pitcher_home": "Burns"},
            {"id": "mlb_10", "away": "TOR", "home": "TB", "time": "6:40 PM", "pitcher_away": "Scherzer", "pitcher_home": "Rasmussen"},
            {"id": "mlb_11", "away": "OAK", "home": "KC", "time": "7:40 PM", "pitcher_away": "Unknown", "pitcher_home": "Unknown"},
            {"id": "mlb_12", "away": "SEA", "home": "MIL", "time": "7:40 PM", "pitcher_away": "Gilbert", "pitcher_home": "May"},
            {"id": "mlb_13", "away": "WSH", "home": "TEX", "time": "8:05 PM", "pitcher_away": "Cavalli", "pitcher_home": "Rocker"},
            {"id": "mlb_14", "away": "LAA", "home": "HOU", "time": "8:10 PM", "pitcher_away": "Ureña", "pitcher_home": "Pecko"},
            {"id": "mlb_15", "away": "LAD", "home": "COL", "time": "8:40 PM", "pitcher_away": "Sasaki", "pitcher_home": "Freeland"},
        ]
        
        # Mock WNBA games
        wnba_games = [
            {"id": "wnba_1", "away": "TOR", "home": "WAS", "time": "4:30 PM"},
            {"id": "wnba_2", "away": "MIN", "home": "GSV", "time": "7:00 PM"},
        ]
        
        # Live Parlay API odds (no silent fallback to mocks)
        _ = api_key  # maintained for signature compatibility; auth is env-driven
        parlay_odds = self._fetch_parlay_odds(sports, date)
        
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
        
        # Create information state hash
        state_str = json.dumps([mlb_games, wnba_games, parlay_odds], default=str, sort_keys=True)
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
            information_state_hash=info_hash
        )
