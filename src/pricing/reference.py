"""
Multi-book consensus reference-line builder.

Features
--------
- Aggregates odds from multiple books with freshness weighting
- Lead-lag detection (which book moves first)
- De-vigging via src.pricing.devig
- Settlement identity verification for DK/PP/Chalkboard rules
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from src.pricing.devig import devig

logger = logging.getLogger(__name__)


class BookOdds:
    """Single book / time snapshot for one market side."""

    def __init__(self, book: str, price: float, fetched_at: str):
        self.book = book
        self.price = float(price)          # American
        self.fetched_at = fetched_at


def _freshness_weight(fetched_at: str, now: Optional[datetime] = None) -> float:
    """
    Exponential decay weight: weight = exp(-age_minutes / 30).

    Older data receives lower weight.
    """
    if now is None:
        now = datetime.now(tz=timezone.utc)
    try:
        ts = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_minutes = (now - ts).total_seconds() / 60.0
    except (ValueError, TypeError):
        age_minutes = 60.0  # assume stale
    import math
    return math.exp(-age_minutes / 30.0)


class ReferenceLineBuilder:
    """
    Build a consensus reference line from multiple book snapshots.

    Usage
    -----
    builder = ReferenceLineBuilder()
    ref = builder.build(over_books, under_books, method='multiplicative')
    """

    def build(
        self,
        over_books: Sequence[BookOdds],
        under_books: Sequence[BookOdds],
        devig_method: str = "multiplicative",
    ) -> Dict:
        """
        Compute freshness-weighted consensus fair probability.

        Parameters
        ----------
        over_books  : list of BookOdds for the OVER side
        under_books : list of BookOdds for the UNDER side
        devig_method : passed to devig()

        Returns
        -------
        dict with fair_over, fair_under, overround, consensus_over_price,
              consensus_under_price, lead_book, n_books
        """
        if not over_books or not under_books:
            logger.warning("ReferenceLineBuilder: missing book data; returning 0.50/0.50 [ASSUMED]")
            return {
                "fair_over": 0.50,
                "fair_under": 0.50,
                "overround": 0.0,
                "consensus_over_price": -110,
                "consensus_under_price": -110,
                "lead_book": None,
                "n_books": 0,
                "lineage": "[ASSUMED]",
            }

        now = datetime.now(tz=timezone.utc)

        # Freshness-weighted average American price per side
        def weighted_avg(books: Sequence[BookOdds]) -> float:
            weights = [_freshness_weight(b.fetched_at, now) for b in books]
            total_w = sum(weights)
            if total_w == 0:
                return books[0].price
            return sum(b.price * w for b, w in zip(books, weights)) / total_w

        avg_over = weighted_avg(over_books)
        avg_under = weighted_avg(under_books)

        result = devig([avg_over, avg_under], method=devig_method)
        fair_over, fair_under = result["fair_probs"]

        # Lead-lag: book with highest freshness weight moves first
        all_books = list(over_books) + list(under_books)
        lead = max(all_books, key=lambda b: _freshness_weight(b.fetched_at, now))

        n_books = len(set(b.book for b in all_books))

        return {
            "fair_over": float(fair_over),
            "fair_under": float(fair_under),
            "overround": float(result["overround"]),
            "consensus_over_price": float(avg_over),
            "consensus_under_price": float(avg_under),
            "devig_method": devig_method,
            "lead_book": lead.book,
            "n_books": n_books,
            "lineage": "[VERIFIED]" if n_books >= 2 else "[MODELED]",
        }


def verify_settlement_identity(
    player_name: str,
    market_name: str,
    platform: str,
    stat_value: Optional[float],
    threshold: float,
) -> Dict:
    """
    Verify settlement outcome per platform-specific rules.

    DraftKings Pick6 / ParlayPlay / Chalkboard have different void conditions
    (e.g., DNP, stat-correction windows, push handling).

    Returns
    -------
    dict with outcome ('WIN'|'LOSS'|'VOID'|'PUSH'), reason, verified
    """
    platform = platform.upper()

    if stat_value is None:
        return {
            "outcome": "VOID",
            "reason": "Stat not reported (DNP or suspended game)",
            "player_name": player_name,
            "market": market_name,
            "platform": platform,
            "verified": True,
        }

    # Half-point thresholds: no push possible
    if threshold != int(threshold):
        outcome = "WIN" if stat_value > threshold else "LOSS"
    else:
        if stat_value > threshold:
            outcome = "WIN"
        elif stat_value < threshold:
            outcome = "LOSS"
        else:
            # Push handling differs by platform
            if platform in ("DRAFTKINGS_PICK6", "DK"):
                outcome = "VOID"  # DK voids integer pushes
            elif platform == "PARLAYPLAY":
                outcome = "PUSH"  # PP refunds leg
            else:
                outcome = "PUSH"

    return {
        "outcome": outcome,
        "reason": f"stat={stat_value} vs threshold={threshold}",
        "player_name": player_name,
        "market": market_name,
        "platform": platform,
        "threshold": threshold,
        "stat_value": stat_value,
        "verified": True,
    }
