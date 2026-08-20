"""
Settlement verification: player name matching, stat corrections, void logic.
"""

import logging
import re
from typing import Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


def _normalise_name(name: str) -> str:
    """Lower-case, strip punctuation, collapse whitespace."""
    name = name.lower()
    name = re.sub(r"[^a-z0-9 ]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _name_similarity(a: str, b: str) -> float:
    """Simple Jaccard similarity on word sets."""
    wa = set(_normalise_name(a).split())
    wb = set(_normalise_name(b).split())
    if not wa and not wb:
        return 1.0
    union = len(wa | wb)
    if union == 0:
        return 0.0
    return len(wa & wb) / union


def match_player_name(
    forecast_name: str,
    settled_name: str,
    threshold: float = 0.5,
) -> Dict:
    """
    Fuzzy player-name matching for settlement verification.

    Returns
    -------
    dict with matched (bool), similarity, forecast_name, settled_name
    """
    sim = _name_similarity(forecast_name, settled_name)
    matched = sim >= threshold
    if not matched:
        logger.warning(
            "Player name mismatch: %r vs %r (similarity=%.2f)",
            forecast_name, settled_name, sim,
        )
    return {
        "matched": matched,
        "similarity": sim,
        "forecast_name": forecast_name,
        "settled_name": settled_name,
        "threshold": threshold,
    }


def verify_settlement(
    forecast: Dict,
    settlement_record: Dict,
    platform: str = "GENERIC",
) -> Dict:
    """
    Full settlement verification for one leg.

    Checks:
    1. Player name match
    2. Market type match
    3. Threshold match (stat-correction rules)
    4. Outcome determination (WIN/LOSS/VOID/PUSH)
    5. Void conditions (DNP, suspended game, stat correction)

    Parameters
    ----------
    forecast : handoff dict with player_id, market, threshold, p_fused
    settlement_record : dict with player_name, stat_value, market, threshold

    Returns
    -------
    dict with outcome, verified, warnings
    """
    warnings = []

    # 1. Player name
    fc_name = str(forecast.get("player_id", ""))
    sl_name = str(settlement_record.get("player_name", ""))
    name_result = match_player_name(fc_name, sl_name)
    if not name_result["matched"]:
        warnings.append(f"Name mismatch: {fc_name!r} vs {sl_name!r}")

    # 2. Market type
    fc_market = str(forecast.get("market", "")).lower()
    sl_market = str(settlement_record.get("market", "")).lower()
    if fc_market and sl_market and fc_market != sl_market:
        warnings.append(f"Market mismatch: {fc_market!r} vs {sl_market!r}")

    # 3. Threshold
    fc_threshold = float(forecast.get("threshold", 0.0))
    sl_threshold = float(settlement_record.get("threshold", fc_threshold))
    if abs(fc_threshold - sl_threshold) > 0.01:
        warnings.append(f"Threshold changed: {fc_threshold} → {sl_threshold}")

    # 4. Stat value
    stat_value = settlement_record.get("stat_value")
    dnp = settlement_record.get("dnp", False)
    game_suspended = settlement_record.get("game_suspended", False)

    if dnp or game_suspended:
        outcome = "VOID"
        reason = "DNP" if dnp else "SUSPENDED"
    elif stat_value is None:
        outcome = "VOID"
        reason = "STAT_UNAVAILABLE"
    else:
        stat_value = float(stat_value)
        threshold = sl_threshold

        if stat_value > threshold:
            outcome = "WIN"
        elif stat_value < threshold:
            outcome = "LOSS"
        else:
            # Push rules
            platform_upper = platform.upper()
            if "DRAFTKINGS" in platform_upper:
                outcome = "VOID"
            else:
                outcome = "PUSH"
        reason = f"stat={stat_value} threshold={threshold}"

    return {
        "outcome": outcome,
        "verified": len(warnings) == 0,
        "warnings": warnings,
        "platform": platform,
        "reason": reason,
        "name_similarity": name_result["similarity"],
        "forecast_id": forecast.get("forecast_id", ""),
        "player_name_forecast": fc_name,
        "player_name_settled": sl_name,
        "market": fc_market,
        "threshold_forecast": fc_threshold,
        "threshold_settled": sl_threshold,
    }


def batch_verify(
    forecasts: Sequence[Dict],
    settlement_records: Sequence[Dict],
    platform: str = "GENERIC",
) -> List[Dict]:
    """Verify a batch of forecast/settlement pairs."""
    results = []
    for fc, sl in zip(forecasts, settlement_records):
        results.append(verify_settlement(fc, sl, platform))
    wins = sum(1 for r in results if r["outcome"] == "WIN")
    voids = sum(1 for r in results if r["outcome"] == "VOID")
    logger.info(
        "Settlement batch n=%d: WIN=%d LOSS=%d VOID=%d",
        len(results), wins, voids,
        len(results) - wins - voids,
    )
    return results
