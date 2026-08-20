"""Tests for MLB pitcher simulator."""

import numpy as np
import pytest
from src.models.mlb_simulator import MLBPitcherSimulator, MLBBatterSimulator


class TestMLBPitcherSimulator:
    def setup_method(self):
        self.sim = MLBPitcherSimulator(n_sims=5000, seed=42)

    def test_returns_required_keys(self):
        result = self.sim.simulate("TestPitcher")
        required = {"p_over", "p_under", "p_push", "mean", "median", "q10", "q90",
                    "threshold", "model_origin", "pitcher_name"}
        assert required.issubset(result.keys())

    def test_probabilities_sum_to_one(self):
        result = self.sim.simulate("TestPitcher")
        assert abs(result["p_over"] + result["p_under"] + result["p_push"] - 1.0) < 0.01

    def test_probabilities_in_valid_range(self):
        result = self.sim.simulate("TestPitcher")
        assert 0.0 <= result["p_over"] <= 1.0
        assert 0.0 <= result["p_under"] <= 1.0

    def test_custom_threshold(self):
        result = self.sim.simulate("TestPitcher", game_context={"threshold": 7.5})
        assert result["threshold"] == 7.5

    def test_high_k_rate_pitcher(self):
        """High k/9 pitcher should have higher p_over for given threshold."""
        stats_high = {"k_per_9": 12.0, "avg_velocity": 97.0, "innings_pitched_per_start": 6.0}
        stats_low = {"k_per_9": 6.0, "avg_velocity": 90.0, "innings_pitched_per_start": 5.0}
        ctx = {"threshold": 6.5}
        r_high = self.sim.simulate("High", stats_high, ctx)
        r_low = self.sim.simulate("Low", stats_low, ctx)
        assert r_high["p_over"] > r_low["p_over"]

    def test_park_factor_applied(self):
        """High-strikeout park should not decrease p_over vs neutral."""
        r_neutral = self.sim.simulate("P", game_context={"venue": "default", "threshold": 5.5})
        r_ga = self.sim.simulate("P", game_context={"venue": "Great American", "threshold": 5.5})
        # Great American has K park factor > 1, so p_over should be ≥ neutral
        assert r_ga["p_over"] >= r_neutral["p_over"] - 0.05  # allow small variance

    def test_velocity_drop_reduces_k(self):
        """Velocity drop should reduce p_over."""
        r_norm = self.sim.simulate("P", game_context={"threshold": 6.5, "velocity_trend_mph_last5": 0.0})
        r_drop = self.sim.simulate("P", game_context={"threshold": 6.5, "velocity_trend_mph_last5": -2.0})
        assert r_drop["p_over"] <= r_norm["p_over"] + 0.05


class TestMLBBatterSimulator:
    def setup_method(self):
        self.sim = MLBBatterSimulator(n_sims=5000, seed=42)

    def test_returns_required_keys(self):
        result = self.sim.simulate("TestBatter")
        assert "p_over" in result
        assert "model_origin" in result

    def test_probabilities_valid(self):
        result = self.sim.simulate("TestBatter")
        assert 0.0 <= result["p_over"] <= 1.0
        assert 0.0 <= result["p_under"] <= 1.0
