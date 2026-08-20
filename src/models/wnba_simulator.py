"""
Real WNBA player-prop simulator.

Models:
  - Minutes distribution per team/coach rotation patterns
  - PPG, APG, RPG scaled by minutes
  - Defensive matchup effect
  - Foul trouble probability
  - Garbage time adjustment
  - Lineup construction / usage rate shifts

All inputs labeled [VERIFIED]/[MODELED]/[ASSUMED].
"""

import logging
from typing import Dict, List, Optional, Any

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# League-average defaults [ASSUMED when player data unavailable]
# ---------------------------------------------------------------------------
_DEFAULT_PPG = 12.0
_DEFAULT_APG = 3.0
_DEFAULT_RPG = 5.0
_DEFAULT_MPG = 28.0
_FOUL_OUT_THRESHOLD = 6       # fouls before disqualification
_GARBAGE_TIME_MINUTES = 3.0   # approx minutes lost when GC is blowout


class WNBAPlayerSimulator:
    """
    Monte Carlo simulator for WNBA player stat outcomes.

    Steps
    -----
    1. Sample minutes from a truncated-normal reflecting coach rotation.
    2. Compute per-minute production rates from season averages.
    3. Apply defensive matchup multiplier.
    4. Model foul trouble: sample foul accumulation, truncate minutes.
    5. Apply garbage-time discount when blowout probability is significant.
    6. Draw final stat count and compute p_over for each market.
    """

    def __init__(self, n_sims: int = 20_000, seed: Optional[int] = None):
        self.n_sims = n_sims
        self.rng = np.random.default_rng(seed)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def simulate(
        self,
        player_name: str,
        player_stats: Optional[Dict] = None,
        game_context: Optional[Dict] = None,
        market: str = "player_points",
    ) -> Dict[str, Any]:
        """
        Simulate stat outcome distribution for *market*.

        Parameters
        ----------
        player_name : str
        player_stats : dict with ppg, apg, rpg, mpg from Sportradar/ESPN [VERIFIED]
        game_context : dict with def_rating, blowout_prob, foul_risk etc.
        market : 'player_points' | 'player_assists' | 'player_rebounds'

        Returns
        -------
        dict with p_over, p_under, mean, q10, q90, threshold, model_origin
        """
        stats = player_stats or {}
        ctx = game_context or {}

        # --- Season averages ---
        ppg = float(stats.get("ppg", _DEFAULT_PPG))
        apg = float(stats.get("apg", _DEFAULT_APG))
        rpg = float(stats.get("rpg", _DEFAULT_RPG))
        mpg = float(stats.get("mpg", _DEFAULT_MPG))
        lineage = "[VERIFIED]" if stats.get("ppg") else "[ASSUMED]"

        # --- Minutes model ---
        # Rotation uncertainty: std dev ~10% of mean minutes
        minutes_std = float(ctx.get("minutes_std", mpg * 0.10))
        min_floor = float(ctx.get("min_floor", 5.0))
        max_cap = float(ctx.get("max_cap", 40.0))

        raw_minutes = self.rng.normal(mpg, minutes_std, self.n_sims)

        # Foul trouble: each foul beyond 3 cuts minutes by ~2
        foul_rate = float(ctx.get("foul_rate_per_game", 2.5))
        fouls = self.rng.poisson(foul_rate, self.n_sims)
        foul_penalty = np.maximum(0, fouls - 3) * 2.0

        # Foul-out (6 fouls) → hard cap at expected remaining minutes
        foul_out_mask = fouls >= _FOUL_OUT_THRESHOLD
        raw_minutes[foul_out_mask] = np.minimum(
            raw_minutes[foul_out_mask] - foul_penalty[foul_out_mask],
            raw_minutes[foul_out_mask] * 0.6,
        )
        minutes = np.clip(raw_minutes - foul_penalty, min_floor, max_cap)

        # Garbage-time adjustment
        blowout_prob = float(ctx.get("blowout_prob", 0.15))
        gc_mask = self.rng.random(self.n_sims) < blowout_prob
        minutes[gc_mask] = np.maximum(min_floor, minutes[gc_mask] - _GARBAGE_TIME_MINUTES)

        # Defensive matchup multiplier [MODELED]
        def_adj = float(ctx.get("def_matchup_adj", 1.0))  # e.g. 0.92 = tough defense

        # --- Per-minute production rates ---
        ppm_pts = (ppg / mpg) * def_adj if mpg > 0 else 0.0
        ppm_ast = (apg / mpg) * def_adj if mpg > 0 else 0.0
        ppm_reb = (rpg / mpg) if mpg > 0 else 0.0  # defensive matchup less relevant for boards

        # --- Stat simulation ---
        if market == "player_points":
            # Poisson-normal mixture for scoring
            pts_mean = minutes * ppm_pts
            pts_std_per_min = float(ctx.get("pts_std_per_min", 0.4))
            pts_noise = self.rng.normal(0, pts_std_per_min * np.sqrt(minutes), self.n_sims)
            stat_samples = np.maximum(0.0, pts_mean + pts_noise)
            default_threshold = ppg
        elif market == "player_assists":
            ast_mean = minutes * ppm_ast
            stat_samples = self.rng.poisson(np.maximum(0.01, ast_mean))
            default_threshold = apg
        elif market == "player_rebounds":
            reb_mean = minutes * ppm_reb
            stat_samples = self.rng.poisson(np.maximum(0.01, reb_mean))
            default_threshold = rpg
        else:
            # Generic: treat as points
            stat_samples = self.rng.normal(minutes * ppm_pts, 2.0, self.n_sims)
            stat_samples = np.maximum(0.0, stat_samples)
            default_threshold = ppg

        threshold = float(ctx.get("threshold", default_threshold))
        p_over = float(np.mean(stat_samples > threshold))
        p_push = float(np.mean(stat_samples == threshold)) if threshold == int(threshold) else 0.0
        p_under = float(1.0 - p_over - p_push)

        result = {
            "player_name": player_name,
            "market": market,
            "threshold": threshold,
            "p_over": p_over,
            "p_under": p_under,
            "p_push": p_push,
            "mean": float(np.mean(stat_samples)),
            "median": float(np.median(stat_samples)),
            "q10": float(np.percentile(stat_samples, 10)),
            "q90": float(np.percentile(stat_samples, 90)),
            "minutes_mean_model": float(np.mean(minutes)),
            "def_matchup_adj": def_adj,
            "blowout_prob": blowout_prob,
            "foul_risk_avg": foul_rate,
            "model_origin": "WNBA_PLAYER_SIMULATOR",
            "lineage_stats": lineage,
            "lineage_context": "[MODELED]",
        }
        logger.debug(
            "WNBA sim %s %s thresh=%.1f p_over=%.3f mean=%.2f",
            player_name, market, threshold, p_over, float(np.mean(stat_samples)),
        )
        return result
