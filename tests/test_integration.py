"""Integration test: full pipeline runs end-to-end."""

import os
import pytest


def test_full_pipeline_runs():
    """Run the full engine pipeline and verify output structure."""
    os.environ.setdefault("PARLAY_API_KEY", "test_key")
    os.environ.setdefault("DATABASE_URL", "sqlite:///test_integration.db")

    from src.stage1_core_a import Stage1CoreA, reconcile_forecasts
    from src.stage2_blind_challenge import Stage2ABlindChallenger
    from src.stage2_product_validator import Stage2BProductValidator
    from src.portfolio_optimizer import PortfolioOptimizer
    from src.data.point_in_time import PointInTimeCapture
    from dataclasses import asdict

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
    from src.data.point_in_time import PointInTimeCapture
    from src.stage2_product_validator import Stage2BProductValidator

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
