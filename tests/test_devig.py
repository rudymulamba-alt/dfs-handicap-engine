"""Tests for de-vigging utilities."""

import pytest
from src.pricing.devig import (
    american_to_implied,
    multiplicative_devig,
    power_devig,
    shin_devig,
    devig,
)


class TestAmericanToImplied:
    def test_minus_110(self):
        imp = american_to_implied([-110])[0]
        assert abs(imp - 110 / 210) < 0.001

    def test_plus_100(self):
        imp = american_to_implied([100])[0]
        assert abs(imp - 0.5) < 0.001

    def test_plus_110(self):
        imp = american_to_implied([110])[0]
        assert abs(imp - 100 / 210) < 0.001


class TestMultiplicativeDevig:
    def test_symmetric_juice(self):
        implied = american_to_implied([-110, -110])
        fair = multiplicative_devig(implied)
        assert abs(fair[0] - 0.5) < 0.001
        assert abs(sum(fair) - 1.0) < 1e-9

    def test_overround_removed(self):
        implied = [0.55, 0.55]  # overround = 0.10
        fair = multiplicative_devig(implied)
        assert abs(sum(fair) - 1.0) < 1e-9

    def test_three_way(self):
        implied = [0.40, 0.35, 0.35]
        fair = multiplicative_devig(implied)
        assert abs(sum(fair) - 1.0) < 1e-9


class TestPowerDevig:
    def test_sums_to_one(self):
        implied = american_to_implied([-110, -110])
        fair = power_devig(implied)
        assert abs(sum(fair) - 1.0) < 1e-6

    def test_symmetric(self):
        implied = american_to_implied([-110, -110])
        fair = power_devig(implied)
        assert abs(fair[0] - fair[1]) < 0.001


class TestShinDevig:
    def test_sums_to_one(self):
        implied = american_to_implied([-110, -110])
        fair = shin_devig(implied)
        assert abs(sum(fair) - 1.0) < 1e-6


class TestDevigWrapper:
    def test_multiplicative(self):
        result = devig([-110, -110], method="multiplicative")
        assert "fair_probs" in result
        assert "overround" in result
        assert abs(sum(result["fair_probs"]) - 1.0) < 1e-9

    def test_power(self):
        result = devig([-110, -110], method="power")
        assert abs(sum(result["fair_probs"]) - 1.0) < 1e-6

    def test_shin(self):
        result = devig([-110, -110], method="shin")
        assert abs(sum(result["fair_probs"]) - 1.0) < 1e-6

    def test_unknown_method_raises(self):
        with pytest.raises(ValueError):
            devig([-110, -110], method="unknown")
