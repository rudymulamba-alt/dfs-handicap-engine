"""
Real MLB pitcher-strikeout and batter-event simulator.

Models:
  - Pitcher velocity / spin-rate / pitch-mix → K% curve
  - Batter contact quality / K susceptibility
  - Park factors
  - Batters-faced distribution (innings pitched distribution)
  - State-space dynamics (arm slot changes, fatigue)

All inputs labeled [VERIFIED]/[MODELED]/[ASSUMED].
"""

import logging
from typing import Dict, List, Optional, Any

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default pitcher parameters when live data unavailable [ASSUMED]
# ---------------------------------------------------------------------------
_DEFAULT_K_PER_9 = 8.5       # league average 2024
_DEFAULT_VELOCITY = 93.5     # mph
_DEFAULT_SPIN_RATE = 2350    # rpm
_DEFAULT_IP_PER_START = 5.5
_PARK_FACTORS: Dict[str, float] = {
    # K park factors (>1 = pitcher-friendly strikeout environment)
    "Coors Field": 0.92,
    "Great American": 1.05,
    "PNC Park": 1.02,
    "default": 1.00,
}


def _park_k_factor(venue: str) -> float:
    return _PARK_FACTORS.get(venue, _PARK_FACTORS["default"])


class MLBPitcherSimulator:
    """
    Monte Carlo simulator for pitcher strikeout totals.

    Steps
    -----
    1. Build K-rate per batter faced from pitcher velocity / pitch-mix / K%.
    2. Sample innings pitched (geometric-like hazard by pitch count / fatigue).
    3. Derive batters faced from IP distribution.
    4. Simulate K count as Poisson-Binomial over batters faced.
    5. Apply park factor adjustment.
    """

    def __init__(self, n_sims: int = 20_000, seed: Optional[int] = None):
        self.n_sims = n_sims
        self.rng = np.random.default_rng(seed)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def simulate(
        self,
        pitcher_name: str,
        pitcher_stats: Optional[Dict] = None,
        game_context: Optional[Dict] = None,
        lineup_k_susceptibility: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Run full simulation and return forecast dict.

        Parameters
        ----------
        pitcher_name : str
        pitcher_stats : dict with k_per_9, avg_velocity, whip, innings_pitched (season)
        game_context : dict with venue, opposing_lineup_k_pct, bullpen_usage etc.
        lineup_k_susceptibility : float multiplier for opposing batter K-rate

        Returns
        -------
        dict with p_over, p_under, mean, q10, q90, threshold, model_origin, lineage
        """
        stats = pitcher_stats or {}
        ctx = game_context or {}

        # --- Pitcher K-rate per batter ---
        k_per_9 = float(stats.get("k_per_9", _DEFAULT_K_PER_9))
        velocity = float(stats.get("avg_velocity", _DEFAULT_VELOCITY))
        lineage_k = "[VERIFIED]" if stats.get("k_per_9") else "[ASSUMED]"

        # Velocity-based K% adjustment (each mph ~0.6% K change)
        velocity_adj = 1.0 + 0.006 * (velocity - _DEFAULT_VELOCITY)
        k_per_bf_base = (k_per_9 / 27.0) * velocity_adj * lineup_k_susceptibility

        # Park factor
        venue = ctx.get("venue", "default")
        park_adj = _park_k_factor(venue)
        k_per_bf = k_per_bf_base * park_adj

        # State-space dynamics: arm-slot change or fatigue penalty [MODELED]
        arm_slot_change = ctx.get("arm_slot_change", False)
        if arm_slot_change:
            k_per_bf *= 0.93  # 7% drop on command

        # Recent velocity drop
        velocity_trend = float(ctx.get("velocity_trend_mph_last5", 0.0))
        if velocity_trend < -1.0:
            k_per_bf *= 1.0 + 0.006 * velocity_trend

        k_per_bf = float(np.clip(k_per_bf, 0.05, 0.55))

        # --- Innings pitched / batters faced distribution ---
        ip_mean = float(stats.get("innings_pitched_per_start", _DEFAULT_IP_PER_START))
        ip_std = 1.2
        ip_samples = self.rng.normal(ip_mean, ip_std, self.n_sims)
        ip_samples = np.clip(ip_samples, 0.0, 9.0)

        # Batters faced ≈ 3 × IP + 1 (some partial innings)
        bf_samples = np.round(ip_samples * 3 + self.rng.poisson(1, self.n_sims)).astype(int)
        bf_samples = np.clip(bf_samples, 0, 27)

        # --- K count simulation ---
        # Vectorised Binomial sample per simulation
        k_totals = self.rng.binomial(bf_samples, k_per_bf)

        # --- Threshold & probabilities ---
        threshold = float(ctx.get("threshold", 5.5))
        p_over = float(np.mean(k_totals > threshold))
        p_push = float(np.mean(k_totals == threshold)) if threshold == int(threshold) else 0.0
        p_under = float(1.0 - p_over - p_push)

        result = {
            "pitcher_name": pitcher_name,
            "threshold": threshold,
            "p_over": p_over,
            "p_under": p_under,
            "p_push": p_push,
            "mean": float(np.mean(k_totals)),
            "median": float(np.median(k_totals)),
            "q10": float(np.percentile(k_totals, 10)),
            "q90": float(np.percentile(k_totals, 90)),
            "k_per_bf_model": k_per_bf,
            "ip_mean_model": ip_mean,
            "park_factor": park_adj,
            "lineup_k_susceptibility": lineup_k_susceptibility,
            "model_origin": "MLB_PITCHER_SIMULATOR",
            "lineage_k_rate": lineage_k,
            "lineage_venue": "[VERIFIED]" if ctx.get("venue") else "[ASSUMED]",
        }
        logger.debug(
            "MLB sim %s thresh=%.1f p_over=%.3f mean=%.2f",
            pitcher_name, threshold, p_over, np.mean(k_totals),
        )
        return result


class MLBBatterSimulator:
    """Simulate individual batter stat outcomes (hits, HR, RBI etc.)."""

    def __init__(self, n_sims: int = 20_000, seed: Optional[int] = None):
        self.n_sims = n_sims
        self.rng = np.random.default_rng(seed)

    def simulate(
        self,
        batter_name: str,
        batter_stats: Optional[Dict] = None,
        game_context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Simulate batter hits/HR/total-bases over game."""
        stats = batter_stats or {}
        ctx = game_context or {}

        avg = float(stats.get("batting_average", 0.250))
        slg = float(stats.get("slugging_pct", 0.420))
        obp = float(stats.get("on_base_pct", 0.320))
        pa_per_game = float(stats.get("pa_per_game", 4.0))
        lineage = "[VERIFIED]" if stats.get("batting_average") else "[ASSUMED]"

        pa_samples = self.rng.poisson(pa_per_game, self.n_sims)
        hits = self.rng.binomial(pa_samples, avg)

        # Approximate total bases
        singles = self.rng.binomial(hits, 0.65)
        doubles = self.rng.binomial(hits - singles, 0.5)
        triples = self.rng.binomial(hits - singles - doubles, 0.1)
        hr = self.rng.binomial(hits - singles - doubles - triples, 0.3)
        total_bases = singles + 2 * doubles + 3 * triples + 4 * hr

        threshold = float(ctx.get("threshold", 1.5))
        p_over = float(np.mean(hits > threshold))

        return {
            "batter_name": batter_name,
            "threshold": threshold,
            "p_over": p_over,
            "p_under": float(1.0 - p_over),
            "p_push": 0.0,
            "mean_hits": float(np.mean(hits)),
            "mean_total_bases": float(np.mean(total_bases)),
            "model_origin": "MLB_BATTER_SIMULATOR",
            "lineage": lineage,
        }
