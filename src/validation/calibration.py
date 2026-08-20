"""
Forecast calibration metrics.

Implements:
  - Brier Score (mean squared error of probabilities)
  - Log Loss (cross-entropy)
  - CRPS (Continuous Ranked Probability Score)
  - Quantile Loss
  - Randomised Probability Integral Transform (PIT)

All metric definitions follow the scoring-rules literature.
"""

import logging
import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Binary calibration metrics
# ---------------------------------------------------------------------------

def brier_score(
    p_forecast: Sequence[float],
    outcomes: Sequence[float],
) -> float:
    """
    Brier Score = mean((p - o)^2) where o ∈ {0, 1}.

    Lower is better. Perfect calibration = 0.  Climatology = p(1-p).
    """
    ps = np.array(p_forecast, dtype=float)
    os_ = np.array(outcomes, dtype=float)
    if len(ps) != len(os_):
        raise ValueError("p_forecast and outcomes must have the same length.")
    return float(np.mean((ps - os_) ** 2))


def brier_score_decomposed(
    p_forecast: Sequence[float],
    outcomes: Sequence[float],
    n_bins: int = 10,
) -> Dict[str, float]:
    """
    Murphy (1973) decomposition: Brier = Reliability - Resolution + Uncertainty.
    """
    ps = np.array(p_forecast, dtype=float)
    os_ = np.array(outcomes, dtype=float)
    n = len(ps)
    o_bar = float(np.mean(os_))

    bins = np.linspace(0.0, 1.0, n_bins + 1)
    rel, res = 0.0, 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (ps >= lo) & (ps < hi)
        if mask.sum() == 0:
            continue
        f_k = float(np.mean(ps[mask]))
        o_k = float(np.mean(os_[mask]))
        n_k = int(mask.sum())
        rel += n_k * (f_k - o_k) ** 2
        res += n_k * (o_k - o_bar) ** 2

    uncertainty = o_bar * (1.0 - o_bar)
    bs = brier_score(ps, os_)
    return {
        "brier_score": bs,
        "reliability": rel / n,
        "resolution": res / n,
        "uncertainty": uncertainty,
    }


def log_loss(
    p_forecast: Sequence[float],
    outcomes: Sequence[float],
    eps: float = 1e-7,
) -> float:
    """
    Binary cross-entropy log loss.

    Lower is better.
    """
    ps = np.clip(np.array(p_forecast, dtype=float), eps, 1.0 - eps)
    os_ = np.array(outcomes, dtype=float)
    return float(-np.mean(os_ * np.log(ps) + (1.0 - os_) * np.log(1.0 - ps)))


# ---------------------------------------------------------------------------
# Probabilistic forecast metrics (distributions)
# ---------------------------------------------------------------------------

def crps_normal(
    mu: Sequence[float],
    sigma: Sequence[float],
    observations: Sequence[float],
) -> float:
    """
    CRPS for Gaussian predictive distributions.

    CRPS(N(μ,σ), y) = σ [y_norm(Φ(z) - 0.5) - 1/√π]
    where z = (y - μ) / σ.

    Lower is better; CRPS = MAE for deterministic forecasts.
    """
    from scipy.stats import norm  # type: ignore

    mu_ = np.array(mu, dtype=float)
    sig_ = np.maximum(np.array(sigma, dtype=float), 1e-6)
    obs = np.array(observations, dtype=float)

    z = (obs - mu_) / sig_
    crps_vals = sig_ * (
        z * (2.0 * norm.cdf(z) - 1.0)
        + 2.0 * norm.pdf(z)
        - 1.0 / math.sqrt(math.pi)
    )
    return float(np.mean(crps_vals))


def quantile_loss(
    q: float,
    forecasts: Sequence[float],
    observations: Sequence[float],
) -> float:
    """
    Quantile (pinball) loss for quantile q ∈ (0, 1).
    """
    f = np.array(forecasts, dtype=float)
    y = np.array(observations, dtype=float)
    errors = y - f
    loss = np.where(errors >= 0, q * errors, (q - 1.0) * errors)
    return float(np.mean(loss))


# ---------------------------------------------------------------------------
# PIT (Probability Integral Transform)
# ---------------------------------------------------------------------------

def randomised_pit(
    cdf_at_obs: Sequence[float],
    n_bins: int = 10,
    seed: int = 42,
) -> Dict[str, object]:
    """
    Randomised PIT histogram.

    For a perfectly calibrated model the PIT values are i.i.d. Uniform(0,1).
    For discrete distributions a small uniform jitter is applied to the CDF jump.

    Parameters
    ----------
    cdf_at_obs : F(y) evaluated at each observation y
    n_bins : number of histogram bins

    Returns
    -------
    dict with 'pit_values', 'histogram', 'bin_edges', 'uniformity_p'
    """
    from scipy.stats import uniform, kstest  # type: ignore

    rng = np.random.default_rng(seed)
    pit = np.array(cdf_at_obs, dtype=float)
    # Randomise discrete jumps: u ~ Uniform(F(y-), F(y))
    jitter = rng.uniform(0, 1, len(pit))
    pit_r = pit - jitter * (1.0 / max(len(pit), 1))
    pit_r = np.clip(pit_r, 0.0, 1.0)

    counts, bin_edges = np.histogram(pit_r, bins=n_bins, range=(0.0, 1.0))
    ks_stat, p_value = kstest(pit_r, "uniform")

    return {
        "pit_values": pit_r.tolist(),
        "histogram": counts.tolist(),
        "bin_edges": bin_edges.tolist(),
        "ks_statistic": float(ks_stat),
        "uniformity_p": float(p_value),
        "n_forecasts": len(pit),
    }


# ---------------------------------------------------------------------------
# Calibration summary
# ---------------------------------------------------------------------------

def calibration_summary(
    p_forecast: Sequence[float],
    outcomes: Sequence[float],
    label: str = "",
) -> Dict[str, float]:
    """Compute all binary calibration metrics at once."""
    result = {
        "label": label,
        "n": len(list(p_forecast)),
        "brier_score": brier_score(p_forecast, outcomes),
        "log_loss": log_loss(p_forecast, outcomes),
        "mean_forecast": float(np.mean(p_forecast)),
        "actual_rate": float(np.mean(outcomes)),
    }
    logger.info(
        "Calibration [%s] n=%d Brier=%.4f LogLoss=%.4f",
        label, result["n"], result["brier_score"], result["log_loss"],
    )
    return result
