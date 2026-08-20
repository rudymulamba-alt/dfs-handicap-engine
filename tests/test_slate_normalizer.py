"""
Unit tests for src.data.slate_normalizer.

All tests use inline fixture data; no network calls are made.
"""
import pytest
from src.data.slate_normalizer import (
    normalize_mlb_slate,
    normalize_wnba_slate,
    _date_of,
    _extract_pitchers,
    _extract_players,
)

# ---------------------------------------------------------------------------
# Shared fixture data (mirrors ParlayAPIClient output format)
# ---------------------------------------------------------------------------

_MLB_ODDS = [
    {
        "event_id": "event_mlb_001",
        "commence_time": "2026-08-20T17:05:00Z",
        "home_team": "New York Yankees",
        "away_team": "Boston Red Sox",
        "bookmaker": "fanduel",
        "bookmaker_title": "FanDuel",
        "market": "h2h",
        "outcomes": [
            {"name": "New York Yankees", "price": -150},
            {"name": "Boston Red Sox", "price": 130},
        ],
        "market_source": "odds",
        "fetched_at": "2026-08-20T14:00:00Z",
    },
    {
        "event_id": "event_mlb_002",
        "commence_time": "2026-08-20T20:10:00Z",
        "home_team": "Houston Astros",
        "away_team": "Los Angeles Angels",
        "bookmaker": "draftkings",
        "bookmaker_title": "DraftKings",
        "market": "h2h",
        "outcomes": [
            {"name": "Houston Astros", "price": -160},
            {"name": "Los Angeles Angels", "price": 140},
        ],
        "market_source": "odds",
        "fetched_at": "2026-08-20T14:00:00Z",
    },
    # duplicate event_id — should be deduped
    {
        "event_id": "event_mlb_001",
        "commence_time": "2026-08-20T17:05:00Z",
        "home_team": "New York Yankees",
        "away_team": "Boston Red Sox",
        "bookmaker": "betmgm",
        "bookmaker_title": "BetMGM",
        "market": "totals",
        "outcomes": [
            {"name": "Over", "price": -110, "point": 8.5},
            {"name": "Under", "price": -110, "point": 8.5},
        ],
        "market_source": "odds",
        "fetched_at": "2026-08-20T14:05:00Z",
    },
    # wrong date — should be excluded
    {
        "event_id": "event_mlb_003",
        "commence_time": "2026-08-21T13:05:00Z",
        "home_team": "Chicago Cubs",
        "away_team": "St. Louis Cardinals",
        "bookmaker": "fanduel",
        "bookmaker_title": "FanDuel",
        "market": "h2h",
        "outcomes": [],
        "market_source": "odds",
        "fetched_at": "2026-08-20T14:00:00Z",
    },
]

_MLB_PROPS = [
    {
        "event_id": "event_mlb_001",
        "commence_time": "2026-08-20T17:05:00Z",
        "home_team": "New York Yankees",
        "away_team": "Boston Red Sox",
        "bookmaker": "parlayplay",
        "bookmaker_title": "ParlayPlay",
        "market": "pitcher_strikeouts",
        "outcomes": [
            {"name": "Over", "price": -115, "point": 6.5, "description": "Gerrit Cole"},
            {"name": "Under", "price": -105, "point": 6.5, "description": "Gerrit Cole"},
        ],
        "market_source": "props",
        "fetched_at": "2026-08-20T14:10:00Z",
    },
    {
        "event_id": "event_mlb_001",
        "commence_time": "2026-08-20T17:05:00Z",
        "home_team": "New York Yankees",
        "away_team": "Boston Red Sox",
        "bookmaker": "parlayplay",
        "bookmaker_title": "ParlayPlay",
        "market": "pitcher_strikeouts",
        "outcomes": [
            {"name": "Over", "price": -120, "point": 5.5, "description": "Nathan Eovaldi"},
            {"name": "Under", "price": -100, "point": 5.5, "description": "Nathan Eovaldi"},
        ],
        "market_source": "props",
        "fetched_at": "2026-08-20T14:10:00Z",
    },
]

_WNBA_ODDS = [
    {
        "event_id": "event_wnba_001",
        "commence_time": "2026-08-20T23:00:00Z",
        "home_team": "Las Vegas Aces",
        "away_team": "New York Liberty",
        "bookmaker": "betmgm",
        "bookmaker_title": "BetMGM",
        "market": "h2h",
        "outcomes": [
            {"name": "Las Vegas Aces", "price": -130},
            {"name": "New York Liberty", "price": 110},
        ],
        "market_source": "odds",
        "fetched_at": "2026-08-20T18:00:00Z",
    },
]

_WNBA_PROPS = [
    {
        "event_id": "event_wnba_001",
        "commence_time": "2026-08-20T23:00:00Z",
        "home_team": "Las Vegas Aces",
        "away_team": "New York Liberty",
        "bookmaker": "fanduel",
        "bookmaker_title": "FanDuel",
        "market": "player_points",
        "outcomes": [
            {"name": "Over", "price": -110, "point": 22.5, "description": "A'ja Wilson"},
            {"name": "Under", "price": -110, "point": 22.5, "description": "A'ja Wilson"},
        ],
        "market_source": "props",
        "fetched_at": "2026-08-20T18:05:00Z",
    },
    {
        "event_id": "event_wnba_001",
        "commence_time": "2026-08-20T23:00:00Z",
        "home_team": "Las Vegas Aces",
        "away_team": "New York Liberty",
        "bookmaker": "fanduel",
        "bookmaker_title": "FanDuel",
        "market": "player_assists",
        "outcomes": [
            {"name": "Over", "price": -115, "point": 4.5, "description": "Sabrina Ionescu"},
            {"name": "Under", "price": -105, "point": 4.5, "description": "Sabrina Ionescu"},
        ],
        "market_source": "props",
        "fetched_at": "2026-08-20T18:05:00Z",
    },
]

TARGET_DATE = "2026-08-20"


# ---------------------------------------------------------------------------
# _date_of
# ---------------------------------------------------------------------------

class TestDateOf:
    def test_z_suffix(self):
        assert _date_of("2026-08-20T17:05:00Z") == "2026-08-20"

    def test_utc_offset(self):
        assert _date_of("2026-08-20T17:05:00+00:00") == "2026-08-20"

    def test_next_day(self):
        assert _date_of("2026-08-21T00:00:00Z") == "2026-08-21"

    def test_empty_string_returns_empty(self):
        assert _date_of("") == ""

    def test_garbage_returns_empty(self):
        assert _date_of("not-a-date") == ""


# ---------------------------------------------------------------------------
# _extract_pitchers
# ---------------------------------------------------------------------------

class TestExtractPitchers:
    def test_two_pitchers_found(self):
        result = _extract_pitchers(_MLB_PROPS, "event_mlb_001")
        assert result["pitcher_away"] == "Gerrit Cole"
        assert result["pitcher_home"] == "Nathan Eovaldi"

    def test_unknown_event_returns_unknown(self):
        result = _extract_pitchers(_MLB_PROPS, "event_mlb_999")
        assert result == {"pitcher_away": "Unknown", "pitcher_home": "Unknown"}

    def test_only_one_pitcher_found(self):
        single_prop = [_MLB_PROPS[0]]
        result = _extract_pitchers(single_prop, "event_mlb_001")
        assert result["pitcher_away"] == "Gerrit Cole"
        assert result["pitcher_home"] == "Gerrit Cole"

    def test_ignores_non_strikeout_markets(self):
        props_with_other = _MLB_PROPS + [{
            "event_id": "event_mlb_001",
            "market": "player_hits",
            "outcomes": [{"description": "Aaron Judge"}],
        }]
        result = _extract_pitchers(props_with_other, "event_mlb_001")
        # Aaron Judge should not appear in pitcher names
        assert result["pitcher_away"] not in ("Aaron Judge",)


# ---------------------------------------------------------------------------
# _extract_players
# ---------------------------------------------------------------------------

class TestExtractPlayers:
    def test_two_players_extracted(self):
        players = _extract_players(_WNBA_PROPS, "event_wnba_001")
        names = [p["name"] for p in players]
        assert "A'ja Wilson" in names
        assert "Sabrina Ionescu" in names

    def test_markets_preserved(self):
        players = _extract_players(_WNBA_PROPS, "event_wnba_001")
        markets = {p["market"] for p in players}
        assert "player_points" in markets
        assert "player_assists" in markets

    def test_unknown_event_returns_empty(self):
        assert _extract_players(_WNBA_PROPS, "event_wnba_999") == []

    def test_deduplication(self):
        # Duplicate outcomes for same player+market should not double-count
        props = _WNBA_PROPS + [{
            "event_id": "event_wnba_001",
            "market": "player_points",
            "outcomes": [{"description": "A'ja Wilson", "name": "Over"}],
        }]
        players = _extract_players(props, "event_wnba_001")
        wilson_entries = [p for p in players if p["name"] == "A'ja Wilson" and p["market"] == "player_points"]
        assert len(wilson_entries) == 1


# ---------------------------------------------------------------------------
# normalize_mlb_slate
# ---------------------------------------------------------------------------

class TestNormalizeMLBSlate:
    def test_returns_correct_game_count(self):
        games = normalize_mlb_slate(_MLB_ODDS, _MLB_PROPS, TARGET_DATE)
        # event_mlb_001 and event_mlb_002 are on TARGET_DATE; 003 is excluded
        assert len(games) == 2

    def test_required_keys_present(self):
        games = normalize_mlb_slate(_MLB_ODDS, _MLB_PROPS, TARGET_DATE)
        required = {"id", "away", "home", "time", "pitcher_away", "pitcher_home"}
        for game in games:
            assert required.issubset(game.keys()), f"Missing keys in {game}"

    def test_event_ids_correct(self):
        games = normalize_mlb_slate(_MLB_ODDS, _MLB_PROPS, TARGET_DATE)
        ids = {g["id"] for g in games}
        assert "event_mlb_001" in ids
        assert "event_mlb_002" in ids
        assert "event_mlb_003" not in ids

    def test_team_names_preserved(self):
        games = normalize_mlb_slate(_MLB_ODDS, _MLB_PROPS, TARGET_DATE)
        game = next(g for g in games if g["id"] == "event_mlb_001")
        assert game["home"] == "New York Yankees"
        assert game["away"] == "Boston Red Sox"

    def test_commence_time_preserved(self):
        games = normalize_mlb_slate(_MLB_ODDS, _MLB_PROPS, TARGET_DATE)
        game = next(g for g in games if g["id"] == "event_mlb_001")
        assert game["time"] == "2026-08-20T17:05:00Z"

    def test_pitcher_names_populated(self):
        games = normalize_mlb_slate(_MLB_ODDS, _MLB_PROPS, TARGET_DATE)
        game = next(g for g in games if g["id"] == "event_mlb_001")
        assert game["pitcher_away"] == "Gerrit Cole"
        assert game["pitcher_home"] == "Nathan Eovaldi"

    def test_no_props_gives_unknown_pitchers(self):
        games = normalize_mlb_slate(_MLB_ODDS, [], TARGET_DATE)
        game = next(g for g in games if g["id"] == "event_mlb_001")
        assert game["pitcher_away"] == "Unknown"
        assert game["pitcher_home"] == "Unknown"

    def test_duplicate_event_ids_deduped(self):
        games = normalize_mlb_slate(_MLB_ODDS, _MLB_PROPS, TARGET_DATE)
        ids = [g["id"] for g in games]
        assert len(ids) == len(set(ids)), "Duplicate event IDs found"

    def test_wrong_date_raises(self):
        with pytest.raises(RuntimeError, match="no games found"):
            normalize_mlb_slate(_MLB_ODDS, _MLB_PROPS, "2099-01-01")

    def test_empty_odds_raises(self):
        with pytest.raises(RuntimeError, match="no games found"):
            normalize_mlb_slate([], _MLB_PROPS, TARGET_DATE)


# ---------------------------------------------------------------------------
# normalize_wnba_slate
# ---------------------------------------------------------------------------

class TestNormalizeWNBASlate:
    def test_returns_correct_game_count(self):
        games = normalize_wnba_slate(_WNBA_ODDS, _WNBA_PROPS, TARGET_DATE)
        assert len(games) == 1

    def test_required_keys_present(self):
        games = normalize_wnba_slate(_WNBA_ODDS, _WNBA_PROPS, TARGET_DATE)
        required = {"id", "away", "home", "time", "players"}
        for game in games:
            assert required.issubset(game.keys())

    def test_event_id_correct(self):
        games = normalize_wnba_slate(_WNBA_ODDS, _WNBA_PROPS, TARGET_DATE)
        assert games[0]["id"] == "event_wnba_001"

    def test_team_names_preserved(self):
        games = normalize_wnba_slate(_WNBA_ODDS, _WNBA_PROPS, TARGET_DATE)
        g = games[0]
        assert g["home"] == "Las Vegas Aces"
        assert g["away"] == "New York Liberty"

    def test_commence_time_preserved(self):
        games = normalize_wnba_slate(_WNBA_ODDS, _WNBA_PROPS, TARGET_DATE)
        assert games[0]["time"] == "2026-08-20T23:00:00Z"

    def test_players_list_populated(self):
        games = normalize_wnba_slate(_WNBA_ODDS, _WNBA_PROPS, TARGET_DATE)
        players = games[0]["players"]
        assert isinstance(players, list)
        assert len(players) == 2

    def test_player_names_present(self):
        games = normalize_wnba_slate(_WNBA_ODDS, _WNBA_PROPS, TARGET_DATE)
        names = {p["name"] for p in games[0]["players"]}
        assert "A'ja Wilson" in names
        assert "Sabrina Ionescu" in names

    def test_no_props_gives_empty_players(self):
        games = normalize_wnba_slate(_WNBA_ODDS, [], TARGET_DATE)
        assert games[0]["players"] == []

    def test_wrong_date_raises(self):
        with pytest.raises(RuntimeError, match="no games found"):
            normalize_wnba_slate(_WNBA_ODDS, _WNBA_PROPS, "2099-01-01")

    def test_empty_odds_raises(self):
        with pytest.raises(RuntimeError, match="no games found"):
            normalize_wnba_slate([], _WNBA_PROPS, TARGET_DATE)
