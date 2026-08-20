"""
Kill-switch: auto-halt on calibration failure or capacity collapse.
"""

import logging
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_HALT_REASONS: Dict[str, str] = {}
_HALTED = False


def _is_halted() -> bool:
    return _HALTED


def check_and_halt(drift_result: Dict, kill_switch_state: Optional[Dict] = None) -> Dict:
    """
    Evaluate drift result and trigger halt if necessary.

    Parameters
    ----------
    drift_result : output of DriftMonitor.check_drift()
    kill_switch_state : optional dict to update in place

    Returns
    -------
    dict with halted (bool), reason, timestamp
    """
    global _HALTED, _HALT_REASONS

    drift_level = drift_result.get("drift_level", "OK")
    if drift_level == "HALT":
        _HALTED = True
        reason = drift_result.get("reason", "Drift threshold exceeded")
        _HALT_REASONS["last_halt"] = reason
        logger.critical("KILL SWITCH TRIGGERED: %s", reason)
        result = {
            "halted": True,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
            "drift_level": drift_level,
        }
        if kill_switch_state is not None:
            kill_switch_state.update(result)
        return result

    return {
        "halted": False,
        "reason": drift_result.get("reason", "OK"),
        "timestamp": datetime.now().isoformat(),
        "drift_level": drift_level,
    }


def reset_kill_switch() -> None:
    """Manually reset kill switch (requires explicit human override)."""
    global _HALTED, _HALT_REASONS
    _HALTED = False
    _HALT_REASONS = {}
    logger.warning("Kill switch manually reset at %s", datetime.now().isoformat())


def capacity_check(
    recommended_stake: float,
    bankroll: float,
    max_stake_fraction: float = 0.5,
) -> Dict:
    """
    Check that recommended stake does not exceed bankroll capacity.

    Returns
    -------
    dict with capacity_ok (bool), stake_fraction, recommendation
    """
    fraction = recommended_stake / bankroll if bankroll > 0 else 1.0
    ok = fraction <= max_stake_fraction
    if not ok:
        logger.warning(
            "Capacity check FAILED: stake fraction %.2f > max %.2f",
            fraction, max_stake_fraction,
        )
    return {
        "capacity_ok": ok,
        "stake_fraction": float(fraction),
        "recommended_stake": recommended_stake,
        "bankroll": bankroll,
        "max_stake_fraction": max_stake_fraction,
        "recommendation": "OK" if ok else "REDUCE_STAKE",
    }
