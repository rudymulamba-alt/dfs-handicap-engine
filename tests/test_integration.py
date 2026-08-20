"""Integration test: full pipeline runs end-to-end."""

import os
from unittest.mock import Mock, patch


# ---------------------------------------------------------------------------
# Shared mock helpers
# ---------------------------------------------------------------------------

def _mock_parlay_response():
    """Mock response for the b365api (PARLAY_API2) odds fetch."""
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "mlb_1_pitcher_strikeouts_jobe_over_6.5": {"price": -115, "implied_prob": 0.535},
        "wnba_1_player_points_over_18.5": {"price": -110, "implied_prob": 0.524},
    }
    return response


# Realistic ParlayAPIClient records for the slate fetch
_MOCK_MLB_ODDS = [
    {
        "event_id": "event_mlb_001",
        "commence_time": "2026-08-19T17:05:00Z",
        "home_team": "Pittsburgh Pirates",
        "away_team": "Detroit Tigers",
        "bookmaker": "fanduel",
        "bookmaker_title": "FanDuel",
        "market": "h2h",
        "outcomes": [{"name": "Pittsburgh Pirates", "price": -120}, {"name": "Detroit Tigers", "price": 105}],
        "market_source": "odds",
        "fetched_at": "2026-08-19T14:00:00Z",
    },
    {
        "event_id": "event_mlb_002",
        "commence_time": "2026-08-19T23:05:00Z",
        "home_team": "Philadelphia Phillies",
        "away_team": "Miami Marlins",
        "bookmaker": "fanduel",
        "bookmaker_title": "FanDuel",
        "market": "h2h",
        "outcomes": [{"name": "Philadelphia Phillies", "price": -200}, {"name": "Miami Marlins", "price": 170}],
        "market_source": "odds",
        "fetched_at": "2026-08-19T14:00:00Z",
    },
]

_MOCK_MLB_PROPS = [
    {
        "event_id": "event_mlb_001",
        "commence_time": "2026-08-19T17:05:00Z",
        "home_team": "Pittsburgh Pirates",
        "away_team": "Detroit Tigers",
        "bookmaker": "parlayplay",
        "bookmaker_title": "ParlayPlay",
        "market": "pitcher_strikeouts",
        "outcomes": [
            {"name": "Over", "price": -115, "point": 6.5, "description": "Jobe"},
            {"name": "Under", "price": -105, "point": 6.5, "description": "Jobe"},
        ],
        "market_source": "props",
        "fetched_at": "2026-08-19T14:10:00Z",
    },
    {
        "event_id": "event_mlb_001",
        "commence_time": "2026-08-19T17:05:00Z",
        "home_team": "Pittsburgh Pirates",
        "away_team": "Detroit Tigers",
        "bookmaker": "parlayplay",
        "bookmaker_title": "ParlayPlay",
        "market": "pitcher_strikeouts",
        "outcomes": [
            {"name": "Over", "price": -110, "point": 6.5, "description": "Skenes"},
            {"name": "Under", "price": -110, "point": 6.5, "description": "Skenes"},
        ],
        "market_source": "props",
        "fetched_at": "2026-08-19T14:10:00Z",
    },
]

_MOCK_WNBA_ODDS = [
    {
        "event_id": "event_wnba_001",
        "commence_time": "2026-08-19T20:30:00Z",
        "home_team": "Washington Mystics",
        "away_team": "Toronto Tempo",
        "bookmaker": "betmgm",
        "bookmaker_title": "BetMGM",
        "market": "h2h",
        "outcomes": [{"name": "Washington Mystics", "price": -130}, {"name": "Toronto Tempo", "price": 110}],
        "market_source": "odds",
        "fetched_at": "2026-08-19T18:00:00Z",
    },
]

_MOCK_WNBA_PROPS = [
    {
        "event_id": "event_wnba_001",
        "commence_time": "2026-08-19T20:30:00Z",
        "home_team": "Washington Mystics",
        "away_team": "Toronto Tempo",
        "bookmaker": "fanduel",
        "bookmaker_title": "FanDuel",
        "market": "player_points",
        "outcomes": [
            {"name": "Over", "price": -110, "point": 18.5, "description": "A'ja Wilson"},
            {"name": "Under", "price": -110, "point": 18.5, "description": "A'ja Wilson"},
        ],
        "market_source": "props",
        "fetched_at": "2026-08-19T18:05:00Z",
    },
]


def _slate_side_effect(sport, date):
    """Return mocked (odds, props) tuples per sport, matching the test date."""
    if sport == "mlb":
        return _MOCK_MLB_ODDS, _MOCK_MLB_PROPS
    if sport == "wnba":
        return _MOCK_WNBA_ODDS, _MOCK_WNBA_PROPS
    return [], []


def test_full_pipeline_runs():
    """Run the full engine pipeline and verify output structure."""
    os.environ.setdefault("PARLAY_API_KEY", "test_key")
    os.environ.setdefault("PARLAY_API2", "https://example.test")
    os.environ.setdefault("SPORTSBOOKODDS", "sportsbook/odds")
    os.environ.setdefault("DATABASE_URL", "sqlite:///test_integration.db")

    from src.stage1_core_a import Stage1CoreA, reconcile_forecasts
    from src.stage2_blind_challenge import Stage2ABlindChallenger
    from src.stage2_product_validator import Stage2BProductValidator
    from src.portfolio_optimizer import PortfolioOptimizer
    from src.data.point_in_time import PointInTimeCapture
    from dataclasses import asdict

    with (
        patch(
            "src.data.point_in_time.PointInTimeCapture._fetch_sport_slate",
            side_effect=_slate_side_effect,
        ),
        patch("src.data.point_in_time.requests.get", return_value=_mock_parlay_response()),
    ):
        pit_state = PointInTimeCapture().capture_slate_state(
            ["mlb", "wnba"], "2026-08-19", "test_key"
        )

    stage1 = Stage1CoreA(pit_state).scan_and_shortlist(["mlb", "wnba"], "DEEP")
    assert len(stage1["all_markets"]) > 0
    assert isinstance(stage1["live_survivors"], list)

    handoffs = [
        {
            "handoff_id": f"handoff_{f.forecast_id}",
            "forecast": asdict(f),
            "frozen_at": "2026-08-19T10:00:00",
        }
        for f in stage1["live_survivors"]
    ]

    challenger = Stage2ABlindChallenger()
    reviews = [challenger.challenge_blind(h) for h in handoffs]
    assert len(reviews) == len(handoffs)

    fused = reconcile_forecasts(stage1["live_survivors"], reviews)
    assert len(fused) == len(reviews)
    for f in fused:
        assert 0.0 <= f["p_fused"] <= 1.0

    validator = Stage2BProductValidator(pit_state)
    validations = []
    for fc in fused:
        for plat in ["DRAFTKINGS_PICK6", "PARLAYPLAY", "CHALKBOARD"]:
            validations.append(validator.validate_product(fc, plat))

    assert len(validations) > 0
    assert all("final_tier" in v for v in validations)

    approved = [v for v in validations if v["final_tier"] != "PASS"]
    entries = PortfolioOptimizer(1000.0).build_and_optimize(
        approved, pit_state, ["DRAFTKINGS_PICK6", "PARLAYPLAY", "CHALKBOARD"]
    )
    assert "all_entries" in entries
    assert "recommended" in entries


def test_platform_product_key_matching():
    """Platform key normalisation should correctly find products."""
    os.environ.setdefault("PARLAY_API_KEY", "test_key")
    os.environ.setdefault("PARLAY_API2", "https://example.test")
    os.environ.setdefault("SPORTSBOOKODDS", "sportsbook/odds")

    from src.data.point_in_time import PointInTimeCapture
    from src.stage2_product_validator import Stage2BProductValidator

    with (
        patch(
            "src.data.point_in_time.PointInTimeCapture._fetch_sport_slate",
            side_effect=_slate_side_effect,
        ),
        patch("src.data.point_in_time.requests.get", return_value=_mock_parlay_response()),
    ):
        pit_state = PointInTimeCapture().capture_slate_state(["mlb"], "2026-08-19", "test_key")
    validator = Stage2BProductValidator(pit_state)

    fused_forecast = {
        "forecast_id": "fc_test",
        "event_id": "mlb_1",
        "player_id": "Jobe",
        "market": "pitcher_strikeouts",
        "threshold": 6.5,
        "p_fused": 0.55,
        "p_market": 0.50,
        "sim_tier": "SIM-T1",
        "p_core_a": 0.55,
        "p_core_b": 0.52,
    }

    # DRAFTKINGS_PICK6 normalises to "draftkingspick6" which is in dfs_products
    result = validator.validate_product(fused_forecast, "DRAFTKINGS_PICK6")
    assert result["forecast_id"] == "fc_test"
    assert result["platform"] == "DRAFTKINGS_PICK6"
    # Should find the product (not INSUFFICIENT_PRODUCT_INFORMATION)
    assert result["verdict"] != "INSUFFICIENT_PRODUCT_INFORMATION"


# ---------------------------------------------------------------------------
# Phase 1: Real slate ingestion integration tests
# ---------------------------------------------------------------------------

def test_mlb_slate_populated_from_api():
    """MLB games list is built from mocked ParlayAPIClient response."""
    os.environ.setdefault("PARLAY_API_KEY", "test_key")
    os.environ.setdefault("PARLAY_API2", "https://example.test")
    os.environ.setdefault("SPORTSBOOKODDS", "sportsbook/odds")

    from src.data.point_in_time import PointInTimeCapture

    with (
        patch(
            "src.data.point_in_time.PointInTimeCapture._fetch_sport_slate",
            side_effect=_slate_side_effect,
        ),
        patch("src.data.point_in_time.requests.get", return_value=_mock_parlay_response()),
    ):
        pit_state = PointInTimeCapture().capture_slate_state(["mlb"], "2026-08-19", "test_key")

    # Should have real games (2 in mock), not the old hardcoded 15
    assert len(pit_state.mlb_games) == 2
    ids = {g["id"] for g in pit_state.mlb_games}
    assert "event_mlb_001" in ids
    assert "event_mlb_002" in ids

    # Each game must carry the required Stage 1 interface keys
    for game in pit_state.mlb_games:
        assert {"id", "away", "home", "time", "pitcher_away", "pitcher_home"}.issubset(game)

    # Pitcher names from props response
    g1 = next(g for g in pit_state.mlb_games if g["id"] == "event_mlb_001")
    assert g1["pitcher_away"] == "Jobe"
    assert g1["pitcher_home"] == "Skenes"


def test_wnba_slate_populated_from_api():
    """WNBA games list is built from mocked ParlayAPIClient response."""
    os.environ.setdefault("PARLAY_API_KEY", "test_key")
    os.environ.setdefault("PARLAY_API2", "https://example.test")
    os.environ.setdefault("SPORTSBOOKODDS", "sportsbook/odds")

    from src.data.point_in_time import PointInTimeCapture

    with (
        patch(
            "src.data.point_in_time.PointInTimeCapture._fetch_sport_slate",
            side_effect=_slate_side_effect,
        ),
        patch("src.data.point_in_time.requests.get", return_value=_mock_parlay_response()),
    ):
        pit_state = PointInTimeCapture().capture_slate_state(["wnba"], "2026-08-19", "test_key")

    assert len(pit_state.wnba_games) == 1
    game = pit_state.wnba_games[0]
    assert game["id"] == "event_wnba_001"
    assert {"id", "away", "home", "time", "players"}.issubset(game)

    player_names = {p["name"] for p in game["players"]}
    assert "A'ja Wilson" in player_names


def test_slate_absent_raises_clearly():
    """An empty API response for a requested date raises RuntimeError, not silent fallback."""
    os.environ.setdefault("PARLAY_API_KEY", "test_key")
    os.environ.setdefault("PARLAY_API2", "https://example.test")
    os.environ.setdefault("SPORTSBOOKODDS", "sportsbook/odds")

    from src.data.point_in_time import PointInTimeCapture
    import pytest

    def _empty_slate(sport, date):
        return [], []  # no games for any sport

    with (
        patch(
            "src.data.point_in_time.PointInTimeCapture._fetch_sport_slate",
            side_effect=_empty_slate,
        ),
        patch("src.data.point_in_time.requests.get", return_value=_mock_parlay_response()),
    ):
        with pytest.raises(RuntimeError, match="no games found"):
            PointInTimeCapture().capture_slate_state(["mlb"], "2099-01-01", "test_key")


def test_slate_date_filtering():
    """Games on other dates are excluded from the slate."""
    os.environ.setdefault("PARLAY_API_KEY", "test_key")
    os.environ.setdefault("PARLAY_API2", "https://example.test")
    os.environ.setdefault("SPORTSBOOKODDS", "sportsbook/odds")

    from src.data.point_in_time import PointInTimeCapture

    # event_mlb_002 is on 2026-08-19; ask for 2026-08-20 → only other-date events
    wrong_date_odds = [
        {
            "event_id": "event_mlb_tomorrow",
            "commence_time": "2026-08-20T20:00:00Z",
            "home_team": "Team A",
            "away_team": "Team B",
            "bookmaker": "fanduel",
            "bookmaker_title": "FanDuel",
            "market": "h2h",
            "outcomes": [],
            "market_source": "odds",
            "fetched_at": "2026-08-19T14:00:00Z",
        }
    ]

    def _tomorrow_slate(sport, date):
        if sport == "mlb":
            return wrong_date_odds, []
        return [], []

    with (
        patch(
            "src.data.point_in_time.PointInTimeCapture._fetch_sport_slate",
            side_effect=_tomorrow_slate,
        ),
        patch("src.data.point_in_time.requests.get", return_value=_mock_parlay_response()),
    ):
        pit_state = PointInTimeCapture().capture_slate_state(["mlb"], "2026-08-20", "test_key")

    assert len(pit_state.mlb_games) == 1
    assert pit_state.mlb_games[0]["id"] == "event_mlb_tomorrow"
