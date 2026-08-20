"""
ParlayPlay platform adapter.

Supports:
- More/Less (binary) product pricing
- Insurance variant (partial refund on near-miss)
- Payout / void enumeration across slip outcomes
"""

import logging
import os
from typing import Dict, List, Optional, Any

import numpy as np

logger = logging.getLogger(__name__)

_PP_API_BASE = "https://api.parlayplay.io"

# ParlayPlay standard payout table (n-pick, no insurance)
_PP_PAYOUTS = {
    2: 3.0,
    3: 6.0,
    4: 10.0,
    5: 20.0,
    6: 40.0,
}

# Insurance payout table: full win, and one-miss partial refund
_PP_INSURANCE_PAYOUTS = {
    # (n_picks): (full_win_multiplier, one_miss_refund_fraction)
    2: (3.0, 0.0),     # no insurance on 2-pick
    3: (5.0, 0.5),     # full win × 5, one miss → 50% refund
    4: (8.0, 0.5),
    5: (15.0, 0.5),
    6: (25.0, 0.5),
}


class ParlayPlayAdapter:
    """
    ParlayPlay More/Less DFS adapter.

    More/Less: pick direction (over/under) on player props.
    Binary: all legs must be correct.
    Insurance: one incorrect leg → partial refund.
    """

    def __init__(self, api_key: Optional[str] = None, bankroll: float = 1000.0):
        self.api_key = api_key or os.environ.get("PP_API_KEY", "")
        self.bankroll = bankroll
        if not self.api_key:
            logger.warning("PP_API_KEY not set; using mock data [ASSUMED]")

    # ------------------------------------------------------------------
    # Product pricing
    # ------------------------------------------------------------------

    def price_slip(
        self,
        legs: List[Dict],
        product_type: str = "binary",
        entry_fee: float = 5.0,
    ) -> Dict[str, Any]:
        """
        Price a ParlayPlay slip.

        Parameters
        ----------
        legs : list of leg dicts with p_fused, p_market, market, threshold
        product_type : 'binary' | 'insurance'
        entry_fee : stake in dollars

        Returns
        -------
        dict with ev_model, ev_market, p_win, payout, expected_value
        """
        n = len(legs)
        if n < 2:
            raise ValueError("ParlayPlay requires at least 2 legs.")

        p_joint_model = float(np.prod([leg.get("p_fused", 0.5) for leg in legs]))
        p_joint_market = float(np.prod([leg.get("p_market", 0.5) for leg in legs]))

        if product_type == "binary":
            multiplier = _PP_PAYOUTS.get(n, 3.0)
            ev_model = multiplier * p_joint_model * entry_fee - entry_fee
            ev_market = multiplier * p_joint_market * entry_fee - entry_fee

            return {
                "product_type": "binary",
                "n_picks": n,
                "multiplier": multiplier,
                "p_win_model": p_joint_model,
                "p_win_market": p_joint_market,
                "ev_model": float(ev_model),
                "ev_market": float(ev_market),
                "delta_ev": float(ev_model - ev_market),
                "entry_fee": entry_fee,
                "platform": "PARLAYPLAY",
            }

        elif product_type == "insurance":
            full_mult, refund_frac = _PP_INSURANCE_PAYOUTS.get(n, (3.0, 0.0))
            # p_exactly_one_miss
            per_leg_probs = [leg.get("p_fused", 0.5) for leg in legs]
            p_all_win = float(np.prod(per_leg_probs))
            one_miss_evs = []
            for i, pi in enumerate(per_leg_probs):
                others = [per_leg_probs[j] for j in range(n) if j != i]
                p_one_miss_i = (1.0 - pi) * float(np.prod(others))
                one_miss_evs.append(p_one_miss_i)
            p_one_miss = sum(one_miss_evs)

            ev_model = (
                full_mult * p_all_win * entry_fee
                + refund_frac * p_one_miss * entry_fee
                - entry_fee
            )

            return {
                "product_type": "insurance",
                "n_picks": n,
                "full_multiplier": full_mult,
                "refund_fraction": refund_frac,
                "p_all_win": p_all_win,
                "p_one_miss": p_one_miss,
                "ev_model": float(ev_model),
                "entry_fee": entry_fee,
                "platform": "PARLAYPLAY",
            }
        else:
            raise ValueError(f"Unknown ParlayPlay product type: {product_type!r}")

    # ------------------------------------------------------------------
    # Payout / void enumeration
    # ------------------------------------------------------------------

    def enumerate_outcomes(self, legs: List[Dict], entry_fee: float = 5.0) -> List[Dict]:
        """
        Enumerate all 2^n outcome states for a slip.

        Returns a list of outcome dicts with probability, payout, and void flag.
        """
        n = len(legs)
        probs = [leg.get("p_fused", 0.5) for leg in legs]
        outcomes = []
        for mask in range(2 ** n):
            bits = [(mask >> i) & 1 for i in range(n)]
            wins = sum(bits)
            losses = n - wins
            prob = float(np.prod([
                probs[i] if bits[i] else 1.0 - probs[i]
                for i in range(n)
            ]))
            if wins == n:
                payout = _PP_PAYOUTS.get(n, 3.0) * entry_fee
                void = False
            elif losses == 0:
                payout = 0.0
                void = False
            else:
                payout = 0.0
                void = False

            outcomes.append({
                "bits": bits,
                "wins": wins,
                "losses": losses,
                "probability": prob,
                "payout": payout,
                "void": void,
            })
        return outcomes
