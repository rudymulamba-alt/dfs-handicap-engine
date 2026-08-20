"""
DraftKings Pick6 platform adapter.

Provides:
- Eligible contest lookup
- Correct ΔEV calculation (multiplier × (p_model - p_market))
- Standings Points and contest-field simulation
- $1 contest allocation modeling
- Real Pick6 API integration structure
"""

import logging
import os
from typing import Dict, List, Optional, Any

import numpy as np

from src.pricing.threshold_curves import pick6_delta_ev

logger = logging.getLogger(__name__)

_DK_API_BASE = "https://api.draftkings.com"
_DEFAULT_MULTIPLIERS = {
    "SINGLE": 1.0,
    "2-PICK": 3.0,
    "3-PICK": 6.0,
    "4-PICK": 10.0,
    "5-PICK": 20.0,
    "6-PICK": 25.0,
}


class DraftKingsPick6Adapter:
    """
    DraftKings Pick6 contest adapter.

    Pick6 is a fixed-multiplier format where the player picks 2-6 legs
    and earns a multiplier on their stake if all legs win.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        bankroll: float = 1000.0,
    ):
        self.api_key = api_key or os.environ.get("DK_API_KEY", "")
        self.bankroll = bankroll
        if not self.api_key:
            logger.warning("DK_API_KEY not set; using mock contest data [ASSUMED]")

    # ------------------------------------------------------------------
    # Contest / product lookup
    # ------------------------------------------------------------------

    def get_eligible_contests(self, sport: str, date: str) -> List[Dict]:
        """
        Return eligible Pick6 contests for *sport* and *date*.

        Falls back to mock data when API key is not configured.
        """
        if not self.api_key:
            return self._mock_contests(sport)

        try:
            import requests  # type: ignore
            url = f"{_DK_API_BASE}/lineups/v1/pick6/contests"
            resp = requests.get(
                url,
                params={"sport": sport, "date": date},
                headers={"Authorization": f"******"},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json().get("contests", [])
        except Exception as exc:  # noqa: BLE001
            logger.warning("DK Pick6 contest fetch failed: %s [ASSUMED]", exc)
            return self._mock_contests(sport)

    def _mock_contests(self, sport: str) -> List[Dict]:
        return [
            {
                "contest_id": f"dk_p6_{sport}_001",
                "name": f"Pick6 {sport.upper()} $1 Entry",
                "entry_fee": 1.0,
                "max_entries": 150,
                "field_size": 1000,
                "prize_pool": 1000.0,
                "sport": sport,
                "multiplier_table": _DEFAULT_MULTIPLIERS,
                "source": "MOCK",
                "lineage": "[ASSUMED]",
            }
        ]

    # ------------------------------------------------------------------
    # EV calculation
    # ------------------------------------------------------------------

    def calculate_leg_ev(
        self,
        p_model: float,
        p_market: float,
        n_picks: int,
    ) -> Dict[str, float]:
        """
        Compute ΔEV for a single Pick6 leg.

        Correct DK formula: ΔEV = multiplier × (p_model − p_market)
        NOT: 1 / p_model.

        n_picks : total picks in the slip (2-6)
        """
        # Derive leg multiplier from n-pick table
        key = f"{n_picks}-PICK"
        slip_multiplier = _DEFAULT_MULTIPLIERS.get(key, 3.0)
        # Per-leg contribution: n-th root of slip multiplier
        per_leg_multiplier = slip_multiplier ** (1.0 / n_picks)

        result = pick6_delta_ev(p_model, p_market, per_leg_multiplier)
        result["n_picks"] = n_picks
        result["slip_multiplier"] = slip_multiplier
        result["per_leg_multiplier"] = per_leg_multiplier
        return result

    # ------------------------------------------------------------------
    # Contest-field simulation
    # ------------------------------------------------------------------

    def simulate_contest_field(
        self,
        my_entry: Dict,
        field_size: int = 1000,
        n_sims: int = 5000,
        seed: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Simulate my entry vs a field of *field_size* entries.

        Returns expected rank percentile and expected prize.
        """
        rng = np.random.default_rng(seed)
        p_joint = my_entry.get("p_joint", 0.5)
        stake = my_entry.get("stake", 1.0)
        multiplier = my_entry.get("multiplier", 3.0)

        # My wins
        my_wins = rng.random(n_sims) < p_joint

        # Field uses market probability (no edge)
        p_market_joint = my_entry.get("p_market_joint", p_joint * 0.95)
        field_wins = rng.binomial(field_size, p_market_joint, n_sims)

        # Simple rank: how many field entries win ≥ my entry?
        my_prize = np.where(my_wins, stake * multiplier, 0.0)
        expected_prize = float(np.mean(my_prize))

        # Standings points: approximate
        standings_pts = float(np.mean(my_wins) * 100)

        return {
            "win_probability": float(np.mean(my_wins)),
            "expected_prize": expected_prize,
            "expected_roi": float(expected_prize / stake - 1.0) if stake > 0 else 0.0,
            "field_size": field_size,
            "avg_field_wins": float(np.mean(field_wins)),
            "standings_points": standings_pts,
        }

    # ------------------------------------------------------------------
    # $1 contest allocation
    # ------------------------------------------------------------------

    def allocate_dollar_contests(
        self,
        approved_legs: List[Dict],
        max_entries: int = 20,
        entry_fee: float = 1.0,
    ) -> List[Dict]:
        """
        Build a list of $1 Pick6 entries from approved legs.

        Selects top legs by ΔEV and constructs max-6-leg slips.
        """
        if not approved_legs:
            return []

        # Sort by delta_ev descending (or ev_median if delta_ev not present)
        sorted_legs = sorted(
            approved_legs,
            key=lambda x: x.get("delta_ev", x.get("ev_median", 0.0)),
            reverse=True,
        )

        # Build 6-pick slips from top legs
        entries = []
        for i in range(0, min(len(sorted_legs), max_entries * 6), 6):
            chunk = sorted_legs[i : i + 6]
            if len(chunk) < 2:
                break
            n = len(chunk)
            key = f"{n}-PICK"
            multiplier = _DEFAULT_MULTIPLIERS.get(key, 3.0)
            p_joint = float(np.prod([leg.get("p_fused", 0.5) for leg in chunk]))
            entries.append({
                "platform": "DRAFTKINGS_PICK6",
                "contest_type": key,
                "legs": [leg.get("forecast_id", "") for leg in chunk],
                "n_picks": n,
                "multiplier": multiplier,
                "p_joint": p_joint,
                "stake": entry_fee,
                "ev": multiplier * p_joint - entry_fee,
                "entry_fee": entry_fee,
            })

        logger.info(
            "DK Pick6: allocated %d $%.0f entries from %d legs",
            len(entries), entry_fee, len(approved_legs),
        )
        return entries[:max_entries]
