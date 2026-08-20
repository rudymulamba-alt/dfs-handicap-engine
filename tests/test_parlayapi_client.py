"""
Unit tests for ParlayAPIClient.

All HTTP calls are mocked — no real network traffic is made.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(json_data, status_code=200):
    """Build a mock requests.Response-like object."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    if status_code >= 400:
        import requests as _req
        resp.raise_for_status.side_effect = _req.HTTPError(
            f"HTTP {status_code}", response=resp
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


# Minimal valid ParlayAPI event payload (matches documented structure)
_MLB_ODDS_PAYLOAD = [
    {
        "id": "event_mlb_001",
        "sport_key": "baseball_mlb",
        "commence_time": "2026-08-20T17:05:00Z",
        "home_team": "New York Yankees",
        "away_team": "Boston Red Sox",
        "bookmakers": [
            {
                "key": "fanduel",
                "title": "FanDuel",
                "last_update": "2026-08-20T14:00:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "New York Yankees", "price": -150},
                            {"name": "Boston Red Sox", "price": 130},
                        ],
                    },
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "price": -110, "point": 8.5},
                            {"name": "Under", "price": -110, "point": 8.5},
                        ],
                    },
                ],
            },
            {
                "key": "draftkings",
                "title": "DraftKings",
                "last_update": "2026-08-20T14:05:00Z",
                "markets": [
                    {
                        "key": "spreads",
                        "outcomes": [
                            {"name": "New York Yankees", "price": -110, "point": -1.5},
                            {"name": "Boston Red Sox", "price": -110, "point": 1.5},
                        ],
                    }
                ],
            },
        ],
    }
]

_MLB_PROPS_PAYLOAD = [
    {
        "id": "event_mlb_001",
        "sport_key": "baseball_mlb",
        "commence_time": "2026-08-20T17:05:00Z",
        "home_team": "New York Yankees",
        "away_team": "Boston Red Sox",
        "bookmakers": [
            {
                "key": "parlayplay",
                "title": "ParlayPlay",
                "last_update": "2026-08-20T14:10:00Z",
                "markets": [
                    {
                        "key": "pitcher_strikeouts",
                        "outcomes": [
                            {
                                "name": "Over",
                                "price": -115,
                                "point": 6.5,
                                "description": "Gerrit Cole",
                            },
                            {
                                "name": "Under",
                                "price": -105,
                                "point": 6.5,
                                "description": "Gerrit Cole",
                            },
                        ],
                    }
                ],
            }
        ],
    }
]

_WNBA_ODDS_PAYLOAD = [
    {
        "id": "event_wnba_001",
        "sport_key": "basketball_wnba",
        "commence_time": "2026-08-20T23:00:00Z",
        "home_team": "Las Vegas Aces",
        "away_team": "New York Liberty",
        "bookmakers": [
            {
                "key": "betmgm",
                "title": "BetMGM",
                "last_update": "2026-08-20T18:00:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Las Vegas Aces", "price": -130},
                            {"name": "New York Liberty", "price": 110},
                        ],
                    }
                ],
            }
        ],
    }
]

_WNBA_PROPS_PAYLOAD = [
    {
        "id": "event_wnba_001",
        "sport_key": "basketball_wnba",
        "commence_time": "2026-08-20T23:00:00Z",
        "home_team": "Las Vegas Aces",
        "away_team": "New York Liberty",
        "bookmakers": [
            {
                "key": "fanduel",
                "title": "FanDuel",
                "last_update": "2026-08-20T18:05:00Z",
                "markets": [
                    {
                        "key": "player_points",
                        "outcomes": [
                            {
                                "name": "Over",
                                "price": -110,
                                "point": 22.5,
                                "description": "A'ja Wilson",
                            },
                            {
                                "name": "Under",
                                "price": -110,
                                "point": 22.5,
                                "description": "A'ja Wilson",
                            },
                        ],
                    }
                ],
            }
        ],
    }
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    """Provide required env vars for every test in this module."""
    monkeypatch.setenv("PARLAYAPI_API_KEY", "test-parlayapi-key")
    monkeypatch.setenv("PARLAY_API_BASE_URL", "https://parlay-api.com/v1")


# ---------------------------------------------------------------------------
# ParlayAPIClient construction
# ---------------------------------------------------------------------------

class TestParlayAPIClientConstruction:
    def test_reads_api_key_from_env(self):
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient()
        assert client.api_key == "test-parlayapi-key"

    def test_reads_base_url_from_env(self):
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient()
        assert client.base_url == "https://parlay-api.com/v1"

    def test_explicit_params_override_env(self):
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient(api_key="explicit-key", base_url="https://other.example.com/v1")
        assert client.api_key == "explicit-key"
        assert client.base_url == "https://other.example.com/v1"

    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("PARLAYAPI_API_KEY")
        from src.data.parlayapi_client import ParlayAPIClient
        with pytest.raises(RuntimeError, match="PARLAYAPI_API_KEY"):
            ParlayAPIClient()

    def test_missing_base_url_raises(self, monkeypatch):
        monkeypatch.delenv("PARLAY_API_BASE_URL")
        from src.data.parlayapi_client import ParlayAPIClient
        with pytest.raises(RuntimeError, match="PARLAY_API_BASE_URL"):
            ParlayAPIClient()

    def test_trailing_slash_stripped_from_base_url(self):
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient(
            api_key="k",
            base_url="https://parlay-api.com/v1/",
        )
        assert not client.base_url.endswith("/")


# ---------------------------------------------------------------------------
# Authentication header
# ---------------------------------------------------------------------------

class TestAuthHeader:
    def test_x_api_key_header_sent(self):
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient()
        with patch("src.data.parlayapi_client.requests.get",
                   return_value=_make_response(_MLB_ODDS_PAYLOAD)) as mock_get:
            client.fetch_odds("mlb")

        _, kwargs = mock_get.call_args
        headers = kwargs.get("headers", {})
        assert headers.get("X-API-Key") == "test-parlayapi-key"

    def test_does_not_use_bearer_token(self):
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient()
        with patch("src.data.parlayapi_client.requests.get",
                   return_value=_make_response(_MLB_ODDS_PAYLOAD)) as mock_get:
            client.fetch_odds("mlb")

        _, kwargs = mock_get.call_args
        headers = kwargs.get("headers", {})
        assert "Authorization" not in headers


# ---------------------------------------------------------------------------
# fetch_odds
# ---------------------------------------------------------------------------

class TestFetchOdds:
    def test_mlb_odds_endpoint_url(self):
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient()
        with patch("src.data.parlayapi_client.requests.get",
                   return_value=_make_response(_MLB_ODDS_PAYLOAD)) as mock_get:
            client.fetch_odds("mlb")

        url = mock_get.call_args[0][0]
        assert "sports/baseball_mlb/odds" in url

    def test_wnba_odds_endpoint_url(self):
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient()
        with patch("src.data.parlayapi_client.requests.get",
                   return_value=_make_response(_WNBA_ODDS_PAYLOAD)) as mock_get:
            client.fetch_odds("wnba")

        url = mock_get.call_args[0][0]
        assert "sports/basketball_wnba/odds" in url

    def test_mlb_odds_returns_list_of_records(self):
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient()
        with patch("src.data.parlayapi_client.requests.get",
                   return_value=_make_response(_MLB_ODDS_PAYLOAD)):
            records = client.fetch_odds("mlb")

        assert isinstance(records, list)
        assert len(records) > 0

    def test_record_preserves_event_id(self):
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient()
        with patch("src.data.parlayapi_client.requests.get",
                   return_value=_make_response(_MLB_ODDS_PAYLOAD)):
            records = client.fetch_odds("mlb")

        event_ids = {r["event_id"] for r in records}
        assert "event_mlb_001" in event_ids

    def test_record_preserves_bookmaker(self):
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient()
        with patch("src.data.parlayapi_client.requests.get",
                   return_value=_make_response(_MLB_ODDS_PAYLOAD)):
            records = client.fetch_odds("mlb")

        bookmakers = {r["bookmaker"] for r in records}
        assert "fanduel" in bookmakers
        assert "draftkings" in bookmakers

    def test_record_preserves_market(self):
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient()
        with patch("src.data.parlayapi_client.requests.get",
                   return_value=_make_response(_MLB_ODDS_PAYLOAD)):
            records = client.fetch_odds("mlb")

        markets = {r["market"] for r in records}
        assert "h2h" in markets
        assert "totals" in markets

    def test_record_preserves_outcomes_with_line(self):
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient()
        with patch("src.data.parlayapi_client.requests.get",
                   return_value=_make_response(_MLB_ODDS_PAYLOAD)):
            records = client.fetch_odds("mlb")

        totals_records = [r for r in records if r["market"] == "totals"]
        assert totals_records
        outcomes = totals_records[0]["outcomes"]
        assert any(oc["point"] == 8.5 for oc in outcomes)

    def test_record_has_fetched_at_timestamp(self):
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient()
        with patch("src.data.parlayapi_client.requests.get",
                   return_value=_make_response(_MLB_ODDS_PAYLOAD)):
            records = client.fetch_odds("mlb")

        assert all("fetched_at" in r for r in records)
        assert all(r["fetched_at"] for r in records)

    def test_record_has_commence_time(self):
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient()
        with patch("src.data.parlayapi_client.requests.get",
                   return_value=_make_response(_MLB_ODDS_PAYLOAD)):
            records = client.fetch_odds("mlb")

        assert all("commence_time" in r for r in records)
        assert all(r["commence_time"] for r in records)

    def test_invalid_sport_raises(self):
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient()
        with pytest.raises(ValueError, match="Unsupported sport"):
            client.fetch_odds("nfl")

    def test_http_error_raises_runtime_error(self):
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient()
        with patch("src.data.parlayapi_client.requests.get",
                   return_value=_make_response({}, status_code=401)):
            with pytest.raises(RuntimeError, match="ParlayAPI request failed"):
                client.fetch_odds("mlb")

    def test_non_json_response_raises(self):
        from src.data.parlayapi_client import ParlayAPIClient
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.side_effect = ValueError("No JSON")
        client = ParlayAPIClient()
        with patch("src.data.parlayapi_client.requests.get", return_value=resp):
            with pytest.raises(RuntimeError, match="non-JSON"):
                client.fetch_odds("mlb")

    def test_empty_list_payload_returns_empty(self):
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient()
        with patch("src.data.parlayapi_client.requests.get",
                   return_value=_make_response([])):
            records = client.fetch_odds("mlb")
        assert records == []


# ---------------------------------------------------------------------------
# fetch_props
# ---------------------------------------------------------------------------

class TestFetchProps:
    def test_mlb_props_endpoint_url(self):
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient()
        with patch("src.data.parlayapi_client.requests.get",
                   return_value=_make_response(_MLB_PROPS_PAYLOAD)) as mock_get:
            client.fetch_props("mlb")

        url = mock_get.call_args[0][0]
        assert "sports/baseball_mlb/props" in url

    def test_wnba_props_endpoint_url(self):
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient()
        with patch("src.data.parlayapi_client.requests.get",
                   return_value=_make_response(_WNBA_PROPS_PAYLOAD)) as mock_get:
            client.fetch_props("wnba")

        url = mock_get.call_args[0][0]
        assert "sports/basketball_wnba/props" in url

    def test_parlayplay_bookmaker_present_in_mlb_props(self):
        """ParlayPlay must appear as a bookmaker/source in the returned prop records."""
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient()
        with patch("src.data.parlayapi_client.requests.get",
                   return_value=_make_response(_MLB_PROPS_PAYLOAD)):
            records = client.fetch_props("mlb")

        bookmakers = {r["bookmaker"] for r in records}
        assert "parlayplay" in bookmakers, (
            "Expected 'parlayplay' bookmaker key in MLB props records. "
            f"Got: {bookmakers}"
        )

    def test_parlayplay_bookmaker_title_present(self):
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient()
        with patch("src.data.parlayapi_client.requests.get",
                   return_value=_make_response(_MLB_PROPS_PAYLOAD)):
            records = client.fetch_props("mlb")

        titles = {r["bookmaker_title"] for r in records}
        assert "ParlayPlay" in titles

    def test_pitcher_strikeouts_market_preserved(self):
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient()
        with patch("src.data.parlayapi_client.requests.get",
                   return_value=_make_response(_MLB_PROPS_PAYLOAD)):
            records = client.fetch_props("mlb")

        markets = {r["market"] for r in records}
        assert "pitcher_strikeouts" in markets

    def test_prop_outcomes_include_line(self):
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient()
        with patch("src.data.parlayapi_client.requests.get",
                   return_value=_make_response(_MLB_PROPS_PAYLOAD)):
            records = client.fetch_props("mlb")

        k_records = [r for r in records if r["market"] == "pitcher_strikeouts"]
        assert k_records
        outcomes = k_records[0]["outcomes"]
        assert any(oc["point"] == 6.5 for oc in outcomes)

    def test_wnba_player_points_market_preserved(self):
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient()
        with patch("src.data.parlayapi_client.requests.get",
                   return_value=_make_response(_WNBA_PROPS_PAYLOAD)):
            records = client.fetch_props("wnba")

        markets = {r["market"] for r in records}
        assert "player_points" in markets

    def test_market_source_is_props(self):
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient()
        with patch("src.data.parlayapi_client.requests.get",
                   return_value=_make_response(_MLB_PROPS_PAYLOAD)):
            records = client.fetch_props("mlb")

        assert all(r["market_source"] == "props" for r in records)


# ---------------------------------------------------------------------------
# fetch_all
# ---------------------------------------------------------------------------

class TestFetchAll:
    def _side_effect_factory(self, sport_payloads: dict):
        """Return a side_effect function that serves payloads by URL path."""

        def _side_effect(url, **kwargs):
            for path_fragment, payload in sport_payloads.items():
                if path_fragment in url:
                    return _make_response(payload)
            return _make_response([])

        return _side_effect

    def test_fetch_all_returns_expected_keys(self):
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient()
        side_effect = self._side_effect_factory(
            {
                "baseball_mlb/odds": _MLB_ODDS_PAYLOAD,
                "baseball_mlb/props": _MLB_PROPS_PAYLOAD,
                "basketball_wnba/odds": _WNBA_ODDS_PAYLOAD,
                "basketball_wnba/props": _WNBA_PROPS_PAYLOAD,
            }
        )
        with patch("src.data.parlayapi_client.requests.get", side_effect=side_effect):
            result = client.fetch_all(["mlb", "wnba"])

        assert set(result.keys()) == {"mlb_odds", "mlb_props", "wnba_odds", "wnba_props"}

    def test_fetch_all_mlb_only(self):
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient()
        side_effect = self._side_effect_factory(
            {
                "baseball_mlb/odds": _MLB_ODDS_PAYLOAD,
                "baseball_mlb/props": _MLB_PROPS_PAYLOAD,
            }
        )
        with patch("src.data.parlayapi_client.requests.get", side_effect=side_effect):
            result = client.fetch_all(["mlb"])

        assert "mlb_odds" in result
        assert "mlb_props" in result
        assert "wnba_odds" not in result

    def test_fetch_all_unsupported_sport_skipped(self):
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient()
        with patch("src.data.parlayapi_client.requests.get",
                   return_value=_make_response([])):
            result = client.fetch_all(["nfl"])

        assert result == {}

    def test_fetch_all_makes_four_requests_for_mlb_wnba(self):
        from src.data.parlayapi_client import ParlayAPIClient
        client = ParlayAPIClient()
        with patch("src.data.parlayapi_client.requests.get",
                   return_value=_make_response([])) as mock_get:
            client.fetch_all(["mlb", "wnba"])

        assert mock_get.call_count == 4


# ---------------------------------------------------------------------------
# Integration with PointInTimeState
# ---------------------------------------------------------------------------

# Minimal fake slate data used by TestPointInTimeIntegration.
# The test date used throughout this class is "2026-08-20".
_PIT_MLB_ODDS = [
    {
        "event_id": "pit_event_mlb_001",
        "commence_time": "2026-08-20T17:00:00Z",
        "home_team": "Team A",
        "away_team": "Team B",
        "bookmaker": "fanduel",
        "bookmaker_title": "FanDuel",
        "market": "h2h",
        "outcomes": [],
        "market_source": "odds",
        "fetched_at": "2026-08-20T14:00:00Z",
    }
]


def _pit_slate_side_effect(sport, date):
    """Return minimal (odds, props) tuples for any sport at 2026-08-20."""
    return _PIT_MLB_ODDS, []


class TestPointInTimeIntegration:
    @pytest.fixture(autouse=True)
    def mock_slate_fetch(self):
        """Patch _fetch_sport_slate for all tests in this class so that
        the slate ingestion path does not require real credentials."""
        with patch(
            "src.data.point_in_time.PointInTimeCapture._fetch_sport_slate",
            side_effect=_pit_slate_side_effect,
        ):
            yield

    def test_parlayapi_odds_field_exists_on_state(self):
        """PointInTimeState dataclass must have a parlayapi_odds field."""
        from src.data.point_in_time import PointInTimeState
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(PointInTimeState)}
        assert "parlayapi_odds" in field_names

    def test_parlayapi_odds_defaults_to_empty_dict(self):
        from src.data.point_in_time import PointInTimeState
        state = PointInTimeState(
            timestamp="t",
            sport="mlb",
            slate_date="2026-08-20",
            mlb_games=[],
            wnba_games=[],
            parlay_odds={},
            dfs_products={},
            lineups={},
            injuries={},
            weather={},
            information_state_hash="abc",
        )
        assert state.parlayapi_odds == {}

    def test_capture_slate_state_skips_parlayapi_when_no_key(self, monkeypatch):
        """When PARLAYAPI_API_KEY is absent, parlayapi_odds must be empty."""
        monkeypatch.delenv("PARLAYAPI_API_KEY", raising=False)
        monkeypatch.setenv("PARLAY_API_KEY", "b365-key")
        monkeypatch.setenv("PARLAY_API2", "https://example.test")
        monkeypatch.setenv("SPORTSBOOKODDS", "sportsbook/odds")

        b365_response = MagicMock()
        b365_response.raise_for_status.return_value = None
        b365_response.json.return_value = {"mlb_line": {"price": -110}}

        from src.data.point_in_time import PointInTimeCapture
        with patch("src.data.point_in_time.requests.get",
                   return_value=b365_response):
            state = PointInTimeCapture().capture_slate_state(
                ["mlb"], "2026-08-20", "b365-key"
            )

        assert state.parlayapi_odds == {}

    def test_capture_slate_state_includes_parlayapi_odds_when_key_present(
        self, monkeypatch
    ):
        """When credentials are set, parlayapi_odds is populated."""
        monkeypatch.setenv("PARLAY_API_KEY", "b365-key")
        monkeypatch.setenv("PARLAY_API2", "https://example.test")
        monkeypatch.setenv("SPORTSBOOKODDS", "sportsbook/odds")
        # PARLAYAPI_API_KEY and PARLAY_API_BASE_URL are already set by autouse fixture

        b365_response = MagicMock()
        b365_response.raise_for_status.return_value = None
        b365_response.json.return_value = {"mlb_line": {"price": -110}}

        def _route(url, **kwargs):
            if "example.test" in url:
                return b365_response
            # ParlayAPI calls
            if "odds" in url:
                return _make_response(_MLB_ODDS_PAYLOAD)
            return _make_response(_MLB_PROPS_PAYLOAD)

        from src.data.point_in_time import PointInTimeCapture
        with patch("src.data.point_in_time.requests.get", side_effect=_route), \
             patch("src.data.parlayapi_client.requests.get", side_effect=_route):
            state = PointInTimeCapture().capture_slate_state(
                ["mlb"], "2026-08-20", "b365-key"
            )

        assert "mlb_odds" in state.parlayapi_odds or "mlb_props" in state.parlayapi_odds

    def test_b365api_parlay_odds_unchanged(self, monkeypatch):
        """b365api parlay_odds path must be completely unaffected."""
        monkeypatch.delenv("PARLAYAPI_API_KEY", raising=False)
        monkeypatch.setenv("PARLAY_API_KEY", "b365-key")
        monkeypatch.setenv("PARLAY_API2", "https://b365.example.test")
        monkeypatch.setenv("SPORTSBOOKODDS", "sportsbook/odds")

        expected_odds = {"mlb_moneyline": {"home": -120, "away": 105}}
        b365_response = MagicMock()
        b365_response.raise_for_status.return_value = None
        b365_response.json.return_value = expected_odds

        from src.data.point_in_time import PointInTimeCapture
        with patch("src.data.point_in_time.requests.get",
                   return_value=b365_response):
            state = PointInTimeCapture().capture_slate_state(
                ["mlb"], "2026-08-20", "b365-key"
            )

        assert state.parlay_odds == expected_odds

    def test_snapshot_mode_loads_valid_local_json(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PARLAY_ODDS_SNAPSHOT_MODE", "true")
        monkeypatch.delenv("PARLAYAPI_API_KEY", raising=False)
        monkeypatch.delenv("PARLAY_API_BASE_URL", raising=False)
        monkeypatch.setenv("PARLAY_API_KEY", "b365-key")
        monkeypatch.setenv("PARLAY_API2", "https://b365.example.test")
        monkeypatch.setenv("SPORTSBOOKODDS", "sportsbook/odds")
        snapshot_payload = {"mlb_moneyline": {"home": -120, "away": 105}}
        snapshot_path = tmp_path / "parlay_odds_snapshot.json"
        snapshot_path.write_text(
            '{"mlb_moneyline": {"home": -120, "away": 105}}',
            encoding="utf-8",
        )

        from src.data.point_in_time import PointInTimeCapture
        monkeypatch.setattr(
            PointInTimeCapture,
            "_PARLAY_ODDS_SNAPSHOT_PATH",
            snapshot_path,
        )

        with patch("src.data.point_in_time.requests.get") as mock_get:
            state = PointInTimeCapture().capture_slate_state(
                ["mlb"], "2026-08-20", "unused-key"
            )

        assert state.parlay_odds == snapshot_payload
        mock_get.assert_not_called()

    def test_snapshot_mode_missing_snapshot_raises(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PARLAY_ODDS_SNAPSHOT_MODE", "true")

        from src.data.point_in_time import PointInTimeCapture
        monkeypatch.setattr(
            PointInTimeCapture,
            "_PARLAY_ODDS_SNAPSHOT_PATH",
            tmp_path / "missing_snapshot.json",
        )

        with pytest.raises(RuntimeError, match="snapshot not found"):
            PointInTimeCapture().capture_slate_state(
                ["mlb"], "2026-08-20", "unused-key"
            )

    def test_snapshot_mode_malformed_json_raises(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PARLAY_ODDS_SNAPSHOT_MODE", "true")
        snapshot_path = tmp_path / "parlay_odds_snapshot.json"
        snapshot_path.write_text("{not-json", encoding="utf-8")

        from src.data.point_in_time import PointInTimeCapture
        monkeypatch.setattr(
            PointInTimeCapture,
            "_PARLAY_ODDS_SNAPSHOT_PATH",
            snapshot_path,
        )

        with pytest.raises(RuntimeError, match="malformed JSON"):
            PointInTimeCapture().capture_slate_state(
                ["mlb"], "2026-08-20", "unused-key"
            )

    def test_live_mode_ignores_snapshot_and_still_calls_http(self, monkeypatch, tmp_path):
        monkeypatch.delenv("PARLAY_ODDS_SNAPSHOT_MODE", raising=False)
        monkeypatch.delenv("PARLAYAPI_API_KEY", raising=False)
        monkeypatch.setenv("PARLAY_API_KEY", "b365-key")
        monkeypatch.setenv("PARLAY_API2", "https://b365.example.test")
        monkeypatch.setenv("SPORTSBOOKODDS", "sportsbook/odds")
        snapshot_path = tmp_path / "parlay_odds_snapshot.json"
        snapshot_path.write_text('{"from_snapshot": true}', encoding="utf-8")

        expected_odds = {"from_live_api": True}
        b365_response = MagicMock()
        b365_response.raise_for_status.return_value = None
        b365_response.json.return_value = expected_odds

        from src.data.point_in_time import PointInTimeCapture
        monkeypatch.setattr(
            PointInTimeCapture,
            "_PARLAY_ODDS_SNAPSHOT_PATH",
            snapshot_path,
        )

        with patch("src.data.point_in_time.requests.get",
                   return_value=b365_response) as mock_get:
            state = PointInTimeCapture().capture_slate_state(
                ["mlb"], "2026-08-20", "b365-key"
            )

        assert state.parlay_odds == expected_odds
        mock_get.assert_called_once()

    def test_parlayapi_odds_included_in_state_hash(self, monkeypatch):
        """
        Changing parlayapi_odds must change information_state_hash.
        This verifies the field is included in the hash computation.
        """
        monkeypatch.setenv("PARLAY_API_KEY", "b365-key")
        monkeypatch.setenv("PARLAY_API2", "https://example.test")
        monkeypatch.setenv("SPORTSBOOKODDS", "sportsbook/odds")

        b365_response = MagicMock()
        b365_response.raise_for_status.return_value = None
        b365_response.json.return_value = {}

        # State with NO ParlayAPI data
        monkeypatch.delenv("PARLAYAPI_API_KEY", raising=False)
        from src.data.point_in_time import PointInTimeCapture
        with patch("src.data.point_in_time.requests.get",
                   return_value=b365_response):
            state_no_parlayapi = PointInTimeCapture().capture_slate_state(
                ["mlb"], "2026-08-20", "b365-key"
            )

        # State WITH ParlayAPI data (same b365 response)
        monkeypatch.setenv("PARLAYAPI_API_KEY", "test-parlayapi-key")

        def _route(url, **kwargs):
            if "example.test" in url:
                return b365_response
            if "odds" in url:
                return _make_response(_MLB_ODDS_PAYLOAD)
            return _make_response(_MLB_PROPS_PAYLOAD)

        with patch("src.data.point_in_time.requests.get", side_effect=_route), \
             patch("src.data.parlayapi_client.requests.get", side_effect=_route):
            state_with_parlayapi = PointInTimeCapture().capture_slate_state(
                ["mlb"], "2026-08-20", "b365-key"
            )

        # Hashes should differ because parlayapi_odds is part of hash input
        assert (
            state_no_parlayapi.information_state_hash
            != state_with_parlayapi.information_state_hash
        )
