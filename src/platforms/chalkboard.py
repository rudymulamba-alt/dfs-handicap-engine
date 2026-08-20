"""
Chalkboard platform adapter.

Supports:
- Showdown payout states
- Shield (insurance) payouts
- Peer-to-peer correlation checks
- Leaderboard mechanics (when applicable)
"""

import logging
import os
from typing import Dict, List, Optional, Any

import numpy as np

logger = logging.getLogger(__name__)

_CB_API_BASE = "https://api.chalkboard.io"

# Chalkboard Showdown payout table
_CB_SHOWDOWN_PAYOUTS = {
    2: 2.5,
    3: 5.0,
    4: 9.0,
    5: 17.0,
    6: 30.0,
}

# Chalkboard Shield payout states (partial-win refund)
_CB_SHIELD_PAYOUTS = {
    # n_picks: {all_correct: mult, one_wrong: refund_frac}
    3: {"all_correct": 4.5, "one_wrong": 0.4},
    4: {"all_correct": 7.5, "one_wrong": 0.4},
    5: {"all_correct": 14.0, "one_wrong": 0.4},
    6: {"all_correct": 22.0, "one_wrong": 0.4},
}


class ChalkboardAdapter:
    """
    Chalkboard DFS platform adapter.

    Showdown: fixed-multiplier, all-or-nothing.
    Shield:   one wrong pick returns 40% of stake.
    """

    def __init__(self, api_key: Optional[str] = None, bankroll: float = 1000.0):
        self.api_key = api_key or os.environ.get("CB_API_KEY", "")
        self.bankroll = bankroll
        if not self.api_key:
            logger.warning("CB_API_KEY not set; using mock data [ASSUMED]")

    # ------------------------------------------------------------------
    # Showdown pricing
    # ------------------------------------------------------------------

    def price_showdown(
        self,
        legs: List[Dict],
        entry_fee: float = 5.0,
    ) -> Dict[str, Any]:
        """
        Price a Chalkboard Showdown slip.
        """
        n = len(legs)
        multiplier = _CB_SHOWDOWN_PAYOUTS.get(n, 2.5)
        p_joint = float(np.prod([leg.get("p_fused", 0.5) for leg in legs]))
        p_market_joint = float(np.prod([leg.get("p_market", 0.5) for leg in legs]))

        ev_model = multiplier * p_joint * entry_fee - entry_fee
        ev_market = multiplier * p_market_joint * entry_fee - entry_fee

        return {
            "product_type": "showdown",
            "n_picks": n,
            "multiplier": multiplier,
            "p_win_model": p_joint,
            "p_win_market": p_market_joint,
            "ev_model": float(ev_model),
            "ev_market": float(ev_market),
            "delta_ev": float(ev_model - ev_market),
            "entry_fee": entry_fee,
            "platform": "CHALKBOARD",
        }

    # ------------------------------------------------------------------
    # Shield pricing
    # ------------------------------------------------------------------

    def price_shield(
        self,
        legs: List[Dict],
        entry_fee: float = 5.0,
    ) -> Dict[str, Any]:
        """
        Price a Chalkboard Shield slip.
        One wrong pick → refund_frac × entry_fee returned.
        """
        n = len(legs)
        config = _CB_SHIELD_PAYOUTS.get(n, {"all_correct": 4.5, "one_wrong": 0.4})
        full_mult = config["all_correct"]
        refund_frac = config["one_wrong"]

        per_leg_probs = [leg.get("p_fused", 0.5) for leg in legs]
        p_all_win = float(np.prod(per_leg_probs))

        # One miss
        p_one_miss = 0.0
        for i, pi in enumerate(per_leg_probs):
            others = [per_leg_probs[j] for j in range(n) if j != i]
            p_one_miss += (1.0 - pi) * float(np.prod(others))

        ev_model = (
            full_mult * p_all_win * entry_fee
            + refund_frac * p_one_miss * entry_fee
            - entry_fee
        )

        return {
            "product_type": "shield",
            "n_picks": n,
            "full_multiplier": full_mult,
            "refund_fraction": refund_frac,
            "p_all_win": p_all_win,
            "p_one_miss": p_one_miss,
            "ev_model": float(ev_model),
            "entry_fee": entry_fee,
            "platform": "CHALKBOARD",
        }

    # ------------------------------------------------------------------
    # Peer-to-peer correlation check
    # ------------------------------------------------------------------

    def correlation_check(self, legs: List[Dict]) -> Dict[str, Any]:
        """
        Check for correlated legs that may violate Chalkboard rules or
        reduce effective diversification.

        Returns a dict with correlation_flag, correlated_pairs.
        """
        correlated_pairs = []
        for i in range(len(legs)):
            for j in range(i + 1, len(legs)):
                l1, l2 = legs[i], legs[j]
                # Same game or same player → flag as correlated
                same_game = l1.get("event_id") == l2.get("event_id")
                same_player = l1.get("player_id") == l2.get("player_id")
                if same_game or same_player:
                    correlated_pairs.append({
                        "leg_a": l1.get("forecast_id", i),
                        "leg_b": l2.get("forecast_id", j),
                        "reason": "same_game" if same_game else "same_player",
                    })

        return {
            "correlation_flag": len(correlated_pairs) > 0,
            "correlated_pairs": correlated_pairs,
            "n_legs": len(legs),
            "recommendation": "REVIEW" if correlated_pairs else "OK",
        }

    # ------------------------------------------------------------------
    # Leaderboard simulation
    # ------------------------------------------------------------------

    def simulate_leaderboard(
        self,
        my_slip: Dict,
        field_size: int = 500,
        n_sims: int = 5000,
        seed: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Simulate leaderboard standing for a Chalkboard Showdown contest.
        """
        rng = np.random.default_rng(seed)
        p_win = float(my_slip.get("p_win_model", 0.5))
        p_market = float(my_slip.get("p_win_market", p_win * 0.95))
        stake = float(my_slip.get("entry_fee", 5.0))
        multiplier = float(my_slip.get("multiplier", 3.0))

        my_wins = rng.random(n_sims) < p_win
        field_wins = rng.binomial(field_size, p_market, n_sims)

        my_prize = np.where(my_wins, stake * multiplier, 0.0)
        rank_pct = 1.0 - (field_wins / field_size)  # higher is better

        return {
            "win_probability": float(np.mean(my_wins)),
            "expected_prize": float(np.mean(my_prize)),
            "expected_rank_pct": float(np.mean(rank_pct)),
            "field_size": field_size,
        }
