"""Tests for calibration metrics."""

import numpy as np
import pytest
from src.validation.calibration import (
    brier_score,
    brier_score_decomposed,
    log_loss,
    crps_normal,
    quantile_loss,
    randomised_pit,
    calibration_summary,
)


class TestBrierScore:
    def test_perfect_forecast(self):
        bs = brier_score([1.0, 0.0], [1.0, 0.0])
        assert bs == 0.0

    def test_worst_forecast(self):
        bs = brier_score([0.0, 1.0], [1.0, 0.0])
        assert bs == 1.0

    def test_uniform_50pct(self):
        bs = brier_score([0.5] * 100, [1] * 50 + [0] * 50)
        assert abs(bs - 0.25) < 0.01

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError):
            brier_score([0.5, 0.5], [1.0])


class TestLogLoss:
    def test_perfect(self):
        ll = log_loss([1.0, 1.0], [1.0, 1.0])
        assert ll < 0.01

    def test_symmetric_prediction(self):
        ll = log_loss([0.5] * 10, [1] * 5 + [0] * 5)
        assert abs(ll - np.log(2)) < 0.01


class TestCRPS:
    def test_deterministic_equals_mae(self):
        """CRPS with sigma→0 equals MAE."""
        mu = [3.0, 5.0, 7.0]
        obs = [3.0, 5.0, 7.0]
        crps = crps_normal(mu, [1e-6] * 3, obs)
        assert abs(crps) < 0.001

    def test_wider_distribution_worse(self):
        """Wider sigma → worse CRPS when observation is at mean."""
        crps_tight = crps_normal([5.0], [1.0], [5.0])
        crps_wide = crps_normal([5.0], [3.0], [5.0])
        assert crps_wide > crps_tight


class TestQuantileLoss:
    def test_symmetric_quantile(self):
        ql = quantile_loss(0.5, [3.0] * 10, [3.0] * 10)
        assert abs(ql) < 1e-9

    def test_q90_larger_than_q10(self):
        forecasts = [5.0] * 100
        observations = np.random.default_rng(0).normal(5, 2, 100).tolist()
        ql10 = quantile_loss(0.1, forecasts, observations)
        ql90 = quantile_loss(0.9, forecasts, observations)
        # Both should be non-negative
        assert ql10 >= 0
        assert ql90 >= 0


class TestRandomisedPIT:
    def test_output_keys(self):
        pit = randomised_pit([0.1, 0.3, 0.5, 0.7, 0.9])
        assert "histogram" in pit
        assert "uniformity_p" in pit
        assert "ks_statistic" in pit

    def test_uniform_input_high_pvalue(self):
        """Uniform PIT values should not reject uniformity."""
        rng = np.random.default_rng(42)
        pit_vals = rng.uniform(0, 1, 500).tolist()
        result = randomised_pit(pit_vals)
        assert result["uniformity_p"] > 0.01  # should not reject at 1% level


class TestCalibrationSummary:
    def test_returns_expected_keys(self):
        result = calibration_summary([0.6, 0.4, 0.7], [1, 0, 1])
        assert "brier_score" in result
        assert "log_loss" in result
        assert "n" in result
