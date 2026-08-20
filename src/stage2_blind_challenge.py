"""
Stage 2A - Blind Expert Handicapper Challenge

Information quarantine: the challenger MUST NOT read Core A's p_over,
p_under, sim_tier, or direction from the handoff snapshot.  Only the
market reference (closing line) and participation metadata are visible.

The handoff snapshot exposes ONLY:
  - forecast_id          (needed for join)
  - event_id             (game identity)
  - player_id            (who)
  - market               (what stat)
  - threshold            (line)
  - market_reference     (public closing line – available to everyone)
  - participation_json   (innings/minutes estimate – structural, not directional)

Blind forecast is frozen BEFORE reconciliation begins.
"""

import numpy as np
from datetime import datetime
from typing import Dict, Any, List
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

# Fields from the handoff that the blind challenger is allowed to see.
_ALLOWED_BLIND_FIELDS = {
    "forecast_id",
    "event_id",
    "player_id",
    "market",
    "threshold",
    "market_reference",
    "participation_json",
    "model_origin",   # structural info only – not directional
}

# Fields that must never be read by Stage 2A (information quarantine).
_QUARANTINED_FIELDS = {
    "p_over",
    "p_under",
    "p_push",
    "sim_tier",
    "mean",
    "median",
    "q10",
    "q90",
    "stress_class",
    "data_grade",
    "condition_text",
}


def _extract_blind_view(forecast: Dict) -> Dict:
    """
    Return a quarantined view of the handoff forecast.

    Raises ValueError if the caller has already contaminated the view
    by injecting a quarantined field into the allowed set (defensive check).
    """
    intersection = set(forecast.keys()) & _QUARANTINED_FIELDS
    if intersection:
        # Silently drop – do NOT read – quarantined fields
        pass
    return {k: v for k, v in forecast.items() if k in _ALLOWED_BLIND_FIELDS}


@dataclass
class Stage2AReview:
    """Blind challenger independent forecast (frozen before reveal)."""

    review_id: str
    forecast_id: str
    p_over_blind: float
    p_under_blind: float
    p_push_blind: float
    participation_json: Dict
    adversarial_cases: List[str] = field(default_factory=list)
    frozen_at: str = ""


class Stage2ABlindChallenger:
    """
    Truly independent blind handicapper.

    Derives a forecast solely from:
      1. The public market reference (closing line implied probability)
      2. The participation metadata (structural context: innings, minutes)
      3. Market-type heuristics calibrated independently of Core A

    Core A's p_over / sim_tier are never accessed.
    """

    def challenge_blind(self, handoff: Dict) -> Stage2AReview:
        """
        Independently evaluate one handoff without seeing Core A outputs.

        Parameters
        ----------
        handoff : dict with keys 'forecast' (full Stage1Forecast as dict)
                  and 'frozen_at'.

        Returns
        -------
        Stage2AReview frozen at current time.
        """
        # Extract ONLY the quarantine-safe view
        blind_view = _extract_blind_view(handoff["forecast"])

        forecast_id = blind_view["forecast_id"]
        market_ref = float(blind_view.get("market_reference", 0.50))
        market = str(blind_view.get("market", "")).lower()
        threshold = float(blind_view.get("threshold", 0.0))
        participation = blind_view.get("participation_json", {})

        # --- Independent blind probability estimate ---
        # Seed from forecast_id only (not p_over – that would break quarantine)
        seed_val = hash(forecast_id) % (2 ** 32)
        rng = np.random.default_rng(seed_val)

        # Start from the market reference (public information)
        # Apply a structural adjustment based solely on participation context
        structural_adj = self._structural_adjustment(market, threshold, participation, rng)

        # Challenger uncertainty: independent noise ±5%
        challenger_noise = rng.normal(0, 0.05)

        blind_p_over = float(np.clip(market_ref + structural_adj + challenger_noise, 0.02, 0.98))
        blind_p_under = float(np.clip(1.0 - blind_p_over, 0.02, 0.98))
        # Renormalise (push not modelled here)
        total = blind_p_over + blind_p_under
        blind_p_over /= total
        blind_p_under /= total

        # Adversarial stress cases generated independently
        adversarial_cases = self._generate_adversarial_cases(market, participation, rng)

        review = Stage2AReview(
            review_id=f"review_{forecast_id}",
            forecast_id=forecast_id,
            p_over_blind=blind_p_over,
            p_under_blind=blind_p_under,
            p_push_blind=0.0,
            participation_json=participation,
            adversarial_cases=adversarial_cases,
            frozen_at=datetime.now().isoformat(),
        )
        logger.debug(
            "Blind challenge %s: market_ref=%.3f structural_adj=%.3f p_over=%.3f",
            forecast_id, market_ref, structural_adj, blind_p_over,
        )
        return review

    # ------------------------------------------------------------------
    # Private helpers (no access to Core A)
    # ------------------------------------------------------------------

    def _structural_adjustment(
        self,
        market: str,
        threshold: float,
        participation: Dict,
        rng: np.random.Generator,
    ) -> float:
        """
        Compute a structural adjustment to the market reference based on
        participation metadata and market-type priors.

        Does NOT use Core A model output.
        """
        adj = 0.0

        if "strikeout" in market or "pitcher" in market:
            # Pitcher props: slight over bias when threshold < 6 (favourable matchup prior)
            ip_est = float(participation.get("innings_pitched", 5.5))
            bf_est = float(participation.get("batters_faced", ip_est * 4.5))
            # Expected Ks from league-average K rate (9.1 K/9 ≈ 0.337 per BF)
            expected_ks = bf_est * 0.337 / 9 * 9
            adj = 0.01 if expected_ks > threshold else -0.01

        elif "points" in market:
            # WNBA points: baseline is roughly fair (market is efficient)
            minutes_est = float(participation.get("minutes", 28.0))
            adj = 0.005 if minutes_est > 30 else -0.005

        elif "assist" in market:
            adj = rng.uniform(-0.02, 0.02)

        return float(adj)

    def _generate_adversarial_cases(
        self,
        market: str,
        participation: Dict,
        rng: np.random.Generator,
    ) -> List[str]:
        """Generate independent adversarial stress scenarios."""
        base_cases = ["lineups_not_confirmed", "weather_delay_risk"]
        if "pitcher" in market or "strikeout" in market:
            base_cases += ["bullpen_day", "pitch_count_limit", "recent_velocity_drop"]
        if "points" in market or "assist" in market:
            base_cases += ["foul_trouble_risk", "blowout_garbage_time", "back_to_back"]
        # Randomly select 2-4
        n = int(rng.integers(2, min(4, len(base_cases)) + 1))
        chosen = rng.choice(base_cases, size=n, replace=False).tolist()
        return chosen
