"""
Threshold curve utilities: map continuous probability to DFS EV curves.

Functions
---------
- pchip_interpolate   : monotone cubic (PCHIP) threshold curve
- logit_linear        : logit-linear probability → EV map
- integer_push_mass   : compute push probability for integer thresholds
- ev_curve            : full EV curve for a range of model probabilities
"""

import logging
from typing import Dict, List, Sequence, Tuple

import numpy as np
from scipy.interpolate import PchipInterpolator  # type: ignore

logger = logging.getLogger(__name__)


def pchip_interpolate(
    x_known: Sequence[float],
    y_known: Sequence[float],
    x_query: Sequence[float],
) -> np.ndarray:
    """
    Monotone-preserving cubic interpolation (PCHIP).

    Parameters
    ----------
    x_known : control-point x values (e.g., model probabilities)
    y_known : control-point y values (e.g., EV multipliers)
    x_query : points at which to evaluate the curve

    Returns
    -------
    np.ndarray of interpolated values, clipped to [min(y_known), max(y_known)]
    """
    xs = np.array(x_known, dtype=float)
    ys = np.array(y_known, dtype=float)
    xq = np.array(x_query, dtype=float)

    interp = PchipInterpolator(xs, ys, extrapolate=False)
    out = interp(xq)
    # Fill NaNs (outside knot range) with boundary values
    out = np.where(xq < xs[0], ys[0], out)
    out = np.where(xq > xs[-1], ys[-1], out)
    return np.clip(out, min(ys), max(ys))


def logit_linear(
    p: float,
    intercept: float = 0.0,
    slope: float = 1.0,
) -> float:
    """
    Logit-linear transformation: logit(p) * slope + intercept → probability.

    Useful for calibration adjustments on model probabilities.
    """
    p = float(np.clip(p, 1e-6, 1 - 1e-6))
    logit_p = np.log(p / (1.0 - p))
    adj_logit = intercept + slope * logit_p
    return float(1.0 / (1.0 + np.exp(-adj_logit)))


def integer_push_mass(
    mean: float,
    std: float,
    threshold: float,
    dist: str = "normal",
) -> float:
    """
    Estimate push probability at an integer threshold.

    For continuous distributions push mass is zero; for half-integer
    thresholds this is always zero.  For integer thresholds with discrete
    underlying distributions use Poisson approximation.

    Parameters
    ----------
    mean, std : distribution parameters
    threshold : the line (e.g. 6.5 → no push; 6.0 → possible push)
    dist : 'normal' | 'poisson'

    Returns
    -------
    float : push probability
    """
    if threshold != int(threshold):
        return 0.0  # half-integer threshold: push is impossible

    t = int(threshold)
    if dist == "poisson":
        lam = max(0.01, mean)
        from scipy.stats import poisson  # type: ignore
        return float(poisson.pmf(t, lam))
    else:
        from scipy.stats import norm  # type: ignore
        # For normal, treat P(X==t) as P(t-0.5 < X < t+0.5)
        return float(norm.cdf(t + 0.5, mean, std) - norm.cdf(t - 0.5, mean, std))


def ev_curve(
    multiplier: float,
    p_grid: Sequence[float],
    cost: float = 1.0,
) -> Dict[str, List[float]]:
    """
    Compute EV curve: EV = multiplier * p_win - cost.

    Returns dict with 'p_grid', 'ev', 'breakeven_p'.
    """
    ps = np.array(p_grid, dtype=float)
    ev = multiplier * ps - cost
    breakeven = cost / multiplier if multiplier > 0 else float("nan")
    logger.debug("ev_curve multiplier=%.2f breakeven=%.4f", multiplier, breakeven)
    return {
        "p_grid": ps.tolist(),
        "ev": ev.tolist(),
        "breakeven_p": breakeven,
        "multiplier": multiplier,
        "cost": cost,
    }


def pick6_delta_ev(
    p_model: float,
    p_market: float,
    multiplier: float,
    cost: float = 1.0,
) -> Dict[str, float]:
    """
    DraftKings Pick6 ΔEV calculation.

    ΔEV = EV(model) - EV(market)
         = multiplier * (p_model - p_market)

    This is the *correct* DK Pick6 edge metric (not 1/probability).

    Returns
    -------
    dict with ev_model, ev_market, delta_ev
    """
    ev_model = multiplier * p_model - cost
    ev_market = multiplier * p_market - cost
    delta_ev = ev_model - ev_market
    return {
        "ev_model": float(ev_model),
        "ev_market": float(ev_market),
        "delta_ev": float(delta_ev),
        "p_model": float(p_model),
        "p_market": float(p_market),
        "multiplier": float(multiplier),
    }
