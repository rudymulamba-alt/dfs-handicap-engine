"""
De-vigging utilities: remove the bookmaker margin from raw odds.

Methods
-------
- multiplicative  : scale each implied probability by 1/overround
- power           : iterative power adjustment (Jullien-Salanié)
- shin             : Shin 1993 approximation
- implied          : simple normalization (same as multiplicative for 2-way)
"""

import math
import logging
from typing import Dict, List, Sequence

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core de-vigging functions
# ---------------------------------------------------------------------------

def _american_to_implied(odds: float) -> float:
    """Convert American odds to implied probability."""
    if odds >= 100:
        return 100.0 / (odds + 100.0)
    else:
        return abs(odds) / (abs(odds) + 100.0)


def american_to_implied(prices: Sequence[float]) -> List[float]:
    """Convert list of American prices to raw implied probabilities."""
    return [_american_to_implied(p) for p in prices]


def multiplicative_devig(implied_probs: Sequence[float]) -> List[float]:
    """
    Multiplicative de-vigging: divide each probability by the sum.

    This is the most common method and is unbiased across outcomes.
    """
    total = sum(implied_probs)
    if total <= 0:
        raise ValueError("Sum of implied probs must be positive.")
    return [p / total for p in implied_probs]


def power_devig(implied_probs: Sequence[float], tol: float = 1e-9, max_iter: int = 1000) -> List[float]:
    """
    Power method (Jullien & Salanié 1994):
    Find k such that sum(p_i^(1/k)) = 1.

    Iterative bisection.
    """
    probs = list(implied_probs)
    if any(p <= 0 for p in probs):
        raise ValueError("All implied probabilities must be positive for power method.")

    lo, hi = 0.5, 5.0
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        total = sum(p ** (1.0 / mid) for p in probs)
        if abs(total - 1.0) < tol:
            break
        if total > 1.0:
            lo = mid
        else:
            hi = mid
    k = (lo + hi) / 2.0
    fair = [p ** (1.0 / k) for p in probs]
    # normalize for numerical precision
    s = sum(fair)
    return [f / s for f in fair]


def shin_devig(implied_probs: Sequence[float]) -> List[float]:
    """
    Shin (1993) de-vigging: assumes a fixed fraction of bettors have inside info.

    Uses iterative root-finding for the z (insider fraction) parameter.
    """
    probs = list(implied_probs)
    n = len(probs)
    overround = sum(probs) - 1.0

    # Estimate z (small when vig is small)
    # z ≈ (overround) / (n - 1) for rough initialisation
    z_est = max(0.0, min(0.5, overround / (n - 1) if n > 1 else 0.0))

    def shin_fair(z: float, raw: List[float]) -> List[float]:
        out = []
        for p in raw:
            disc = (z ** 2 + 4 * (1 - z) * p**2) ** 0.5
            fair = (-(z) + disc) / (2 * (1 - z)) if z < 1 else p
            out.append(fair)
        return out

    # Bisect for z that makes fair probs sum to 1
    lo, hi = 0.0, 0.5
    for _ in range(500):
        mid = (lo + hi) / 2.0
        s = sum(shin_fair(mid, probs))
        if abs(s - 1.0) < 1e-9:
            break
        if s > 1.0:
            lo = mid
        else:
            hi = mid
    z = (lo + hi) / 2.0
    fair = shin_fair(z, probs)
    total = sum(fair)
    return [f / total for f in fair]


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------

def devig(
    american_prices: Sequence[float],
    method: str = "multiplicative",
) -> Dict[str, List[float]]:
    """
    Full de-vigging pipeline.

    Parameters
    ----------
    american_prices : list of American odds, e.g. [-110, -110] or [-120, 105]
    method : 'multiplicative' | 'power' | 'shin' | 'implied'

    Returns
    -------
    dict with 'implied_raw', 'fair_probs', 'overround', 'method'
    """
    implied = american_to_implied(american_prices)
    overround = sum(implied) - 1.0

    method = method.lower()
    if method in ("multiplicative", "implied"):
        fair = multiplicative_devig(implied)
    elif method == "power":
        fair = power_devig(implied)
    elif method == "shin":
        fair = shin_devig(implied)
    else:
        raise ValueError(f"Unknown devig method: {method!r}")

    logger.debug("devig method=%s overround=%.4f fair=%s", method, overround, fair)
    return {
        "implied_raw": implied,
        "fair_probs": fair,
        "overround": overround,
        "method": method,
    }
