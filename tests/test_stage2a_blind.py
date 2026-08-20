"""Tests for Stage 2A blind challenge (information quarantine)."""

import pytest
from src.stage2_blind_challenge import (
    Stage2ABlindChallenger,
    Stage2AReview,
    _extract_blind_view,
    _QUARANTINED_FIELDS,
    _ALLOWED_BLIND_FIELDS,
)


def _make_full_forecast(forecast_id: str = "fc_001") -> dict:
    """Build a full Stage1Forecast dict including quarantined fields."""
    return {
        "forecast_id": forecast_id,
        "event_id": "mlb_1",
        "player_id": "Skenes",
        "market": "pitcher_strikeouts",
        "threshold": 7.5,
        "p_over": 0.72,          # QUARANTINED
        "p_under": 0.28,          # QUARANTINED
        "p_push": 0.0,            # QUARANTINED
        "mean": 8.1,              # QUARANTINED
        "median": 8.0,            # QUARANTINED
        "q10": 4.0,               # QUARANTINED
        "q90": 12.0,              # QUARANTINED
        "sim_tier": "SIM-T1",     # QUARANTINED
        "stress_class": "ROBUST", # QUARANTINED
        "data_grade": "A",        # QUARANTINED
        "market_reference": 0.50,
        "participation_json": {"innings_pitched": 6.5, "batters_faced": 28},
        "model_origin": "INDEPENDENT",
    }


class TestBlindViewExtraction:
    def test_quarantined_fields_excluded(self):
        fc = _make_full_forecast()
        blind = _extract_blind_view(fc)
        for field in _QUARANTINED_FIELDS:
            assert field not in blind, f"Quarantined field {field!r} leaked into blind view"

    def test_allowed_fields_present(self):
        fc = _make_full_forecast()
        blind = _extract_blind_view(fc)
        assert "forecast_id" in blind
        assert "market_reference" in blind
        assert "threshold" in blind


class TestStage2ABlindChallenger:
    def setup_method(self):
        self.challenger = Stage2ABlindChallenger()

    def _make_handoff(self, forecast_id: str = "fc_001") -> dict:
        return {
            "handoff_id": f"handoff_{forecast_id}",
            "forecast": _make_full_forecast(forecast_id),
            "frozen_at": "2026-08-19T10:00:00",
        }

    def test_returns_stage2a_review(self):
        review = self.challenger.challenge_blind(self._make_handoff())
        assert isinstance(review, Stage2AReview)

    def test_probabilities_sum_to_one(self):
        review = self.challenger.challenge_blind(self._make_handoff())
        total = review.p_over_blind + review.p_under_blind + review.p_push_blind
        assert abs(total - 1.0) < 0.01

    def test_probabilities_in_range(self):
        review = self.challenger.challenge_blind(self._make_handoff())
        assert 0.0 <= review.p_over_blind <= 1.0
        assert 0.0 <= review.p_under_blind <= 1.0

    def test_forecast_id_preserved(self):
        review = self.challenger.challenge_blind(self._make_handoff("fc_42"))
        assert review.forecast_id == "fc_42"

    def test_blind_p_over_does_not_equal_core_a(self):
        """Blind p_over must not simply copy Core A's p_over (0.72)."""
        review = self.challenger.challenge_blind(self._make_handoff())
        # The blind estimate starts from market_reference (0.50), not Core A (0.72)
        # It should not land exactly on 0.72
        assert abs(review.p_over_blind - 0.72) > 0.01, (
            "Blind challenger appears to be reading Core A p_over (0.72); "
            f"got {review.p_over_blind}"
        )

    def test_adversarial_cases_generated(self):
        review = self.challenger.challenge_blind(self._make_handoff())
        assert isinstance(review.adversarial_cases, list)
        assert len(review.adversarial_cases) >= 2

    def test_deterministic_per_forecast_id(self):
        """Same forecast_id should produce same blind estimate (seeded)."""
        h = self._make_handoff("fc_999")
        r1 = self.challenger.challenge_blind(h)
        r2 = self.challenger.challenge_blind(h)
        assert r1.p_over_blind == r2.p_over_blind

    def test_different_forecasts_different_estimates(self):
        """Different forecast_ids should produce different estimates."""
        r1 = self.challenger.challenge_blind(self._make_handoff("fc_001"))
        r2 = self.challenger.challenge_blind(self._make_handoff("fc_002"))
        # Very unlikely to be identical
        assert r1.p_over_blind != r2.p_over_blind
