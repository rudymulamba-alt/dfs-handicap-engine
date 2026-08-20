"""Tests for WNBA player simulator."""

import numpy as np
import pytest
from src.models.wnba_simulator import WNBAPlayerSimulator


class TestWNBAPlayerSimulator:
    def setup_method(self):
        self.sim = WNBAPlayerSimulator(n_sims=5000, seed=42)

    def test_returns_required_keys(self):
        result = self.sim.simulate("TestPlayer")
        required = {"p_over", "p_under", "p_push", "mean", "median", "q10", "q90",
                    "threshold", "model_origin", "player_name"}
        assert required.issubset(result.keys())

    def test_probabilities_sum_to_one(self):
        result = self.sim.simulate("TestPlayer")
        assert abs(result["p_over"] + result["p_under"] + result["p_push"] - 1.0) < 0.01

    def test_assists_market(self):
        result = self.sim.simulate("TestPlayer", market="player_assists")
        assert result["market"] == "player_assists"
        assert 0.0 <= result["p_over"] <= 1.0

    def test_rebounds_market(self):
        result = self.sim.simulate("TestPlayer", market="player_rebounds")
        assert result["market"] == "player_rebounds"

    def test_high_ppg_player_over_bias(self):
        """Player with high PPG should have higher p_over for low threshold."""
        stats_star = {"ppg": 25.0, "mpg": 35.0, "apg": 5.0, "rpg": 7.0}
        stats_bench = {"ppg": 6.0, "mpg": 15.0, "apg": 1.0, "rpg": 2.0}
        ctx = {"threshold": 10.0}
        r_star = self.sim.simulate("Star", stats_star, ctx, "player_points")
        r_bench = self.sim.simulate("Bench", stats_bench, ctx, "player_points")
        assert r_star["p_over"] > r_bench["p_over"]

    def test_foul_trouble_reduces_minutes(self):
        """High foul rate should reduce expected minutes."""
        ctx_low_fouls = {"foul_rate_per_game": 1.0, "threshold": 20.0}
        ctx_high_fouls = {"foul_rate_per_game": 4.5, "threshold": 20.0}
        r_low = self.sim.simulate("Player", market="player_points", game_context=ctx_low_fouls)
        r_high = self.sim.simulate("Player", market="player_points", game_context=ctx_high_fouls)
        assert r_low["minutes_mean_model"] >= r_high["minutes_mean_model"] - 1.0

    def test_blowout_reduces_stats(self):
        ctx_normal = {"blowout_prob": 0.0, "threshold": 15.0}
        ctx_blowout = {"blowout_prob": 0.9, "threshold": 15.0}
        r_normal = self.sim.simulate("Player", market="player_points", game_context=ctx_normal)
        r_blowout = self.sim.simulate("Player", market="player_points", game_context=ctx_blowout)
        assert r_blowout["minutes_mean_model"] <= r_normal["minutes_mean_model"] + 1.0
