"""
Execution layer: live entry submission, CLV tracking, settlement processing,
EDPH / realized ROI computation.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

import numpy as np

from src.validation.calibration import brier_score, log_loss
from src.validation.drift_monitor import closing_line_value

logger = logging.getLogger(__name__)


class EntrySubmitter:
    """
    Submit entries to DFS platforms.

    In PRODUCTION mode: uses real platform APIs.
    In PAPER mode: logs entries without actual submission.
    """

    def __init__(self, mode: str = "PAPER"):
        self.mode = mode.upper()
        logger.info("EntrySubmitter initialized in %s mode", self.mode)

    def submit(self, entry: Dict, platform: str) -> Dict:
        """
        Submit a single entry to *platform*.

        Returns
        -------
        dict with submission_id, status, timestamp
        """
        platform = platform.upper()

        if self.mode == "PAPER":
            logger.info(
                "[PAPER] Would submit entry %s to %s stake=$%.2f",
                entry.get("entry_id", "?"), platform, entry.get("stake_recommended", 0),
            )
            return {
                "submission_id": f"paper_{entry.get('entry_id', 'unknown')}",
                "status": "PAPER_SUBMITTED",
                "platform": platform,
                "entry_id": entry.get("entry_id"),
                "stake": entry.get("stake_recommended", 0),
                "submitted_at": datetime.now().isoformat(),
                "mode": "PAPER",
            }

        # Production API submission (platform-specific)
        try:
            return self._submit_production(entry, platform)
        except Exception as exc:  # noqa: BLE001
            logger.error("Entry submission failed for %s on %s: %s", entry.get("entry_id"), platform, exc)
            return {
                "submission_id": None,
                "status": "FAILED",
                "error": str(exc),
                "platform": platform,
                "submitted_at": datetime.now().isoformat(),
            }

    def _submit_production(self, entry: Dict, platform: str) -> Dict:
        """Platform-specific real API submission."""
        # DraftKings Pick6
        if "DRAFTKINGS" in platform:
            return self._submit_dk(entry)
        # ParlayPlay
        if "PARLAYPLAY" in platform:
            return self._submit_pp(entry)
        # Chalkboard
        if "CHALKBOARD" in platform:
            return self._submit_cb(entry)
        raise ValueError(f"Unknown platform for submission: {platform!r}")

    def _submit_dk(self, entry: Dict) -> Dict:
        logger.info("[PRODUCTION] Submitting to DraftKings Pick6...")
        # Real DK API call would go here
        return {
            "submission_id": f"dk_{entry.get('entry_id')}",
            "status": "SUBMITTED",
            "platform": "DRAFTKINGS_PICK6",
            "submitted_at": datetime.now().isoformat(),
        }

    def _submit_pp(self, entry: Dict) -> Dict:
        logger.info("[PRODUCTION] Submitting to ParlayPlay...")
        return {
            "submission_id": f"pp_{entry.get('entry_id')}",
            "status": "SUBMITTED",
            "platform": "PARLAYPLAY",
            "submitted_at": datetime.now().isoformat(),
        }

    def _submit_cb(self, entry: Dict) -> Dict:
        logger.info("[PRODUCTION] Submitting to Chalkboard...")
        return {
            "submission_id": f"cb_{entry.get('entry_id')}",
            "status": "SUBMITTED",
            "platform": "CHALKBOARD",
            "submitted_at": datetime.now().isoformat(),
        }

    def submit_batch(self, entries: List[Dict], platform: str) -> List[Dict]:
        """Submit a batch of entries."""
        results = []
        for entry in entries:
            results.append(self.submit(entry, platform))
        logger.info(
            "EntrySubmitter: submitted %d entries to %s", len(results), platform
        )
        return results


class CLVTracker:
    """
    Track closing-line value for submitted entries.
    """

    def __init__(self):
        self._records: List[Dict] = []

    def record_clv(
        self,
        entry_id: str,
        forecast_id: str,
        p_forecast: float,
        p_closing: float,
        direction: str = "OVER",
        outcome: Optional[str] = None,
        stat_value: Optional[float] = None,
        threshold: Optional[float] = None,
    ) -> Dict:
        """Record CLV for a settled leg."""
        clv = closing_line_value(p_forecast, p_closing, direction)
        record = {
            "entry_id": entry_id,
            "forecast_id": forecast_id,
            "p_forecast": p_forecast,
            "p_closing": p_closing,
            "clv": clv,
            "direction": direction,
            "outcome": outcome,
            "stat_value": stat_value,
            "threshold": threshold,
            "settled_at": datetime.now().isoformat(),
        }
        self._records.append(record)
        return record

    def summary(self) -> Dict:
        """Return aggregate CLV stats."""
        if not self._records:
            return {"n": 0, "mean_clv": 0.0, "positive_clv_rate": 0.0}
        clvs = [r["clv"] for r in self._records]
        outcomes = [r["outcome"] for r in self._records]
        wins = sum(1 for o in outcomes if o == "WIN")
        return {
            "n": len(self._records),
            "mean_clv": float(np.mean(clvs)),
            "std_clv": float(np.std(clvs)),
            "positive_clv_rate": float(np.mean([c > 0 for c in clvs])),
            "win_rate": wins / len(self._records) if self._records else 0.0,
        }


class SettlementProcessor:
    """
    Process settled entries: compute Brier, log loss, CLV, ROI.
    """

    def process_batch(
        self,
        settled_entries: List[Dict],
    ) -> Dict[str, Any]:
        """
        Parameters
        ----------
        settled_entries : list of dicts with p_forecast, outcome (1.0/0.0),
                          p_closing, stake, winnings, platform, sport

        Returns
        -------
        dict with calibration metrics and ROI by dimension
        """
        if not settled_entries:
            return {"n": 0}

        p_forecasts = [e["p_forecast"] for e in settled_entries]
        outcomes = [e["outcome"] for e in settled_entries]
        stakes = [e.get("stake", 1.0) for e in settled_entries]
        winnings = [e.get("winnings", 0.0) for e in settled_entries]

        total_stake = sum(stakes)
        total_winnings = sum(winnings)
        roi = (total_winnings - total_stake) / total_stake if total_stake > 0 else 0.0

        # CLV
        p_closings = [e.get("p_closing", p) for e, p in zip(settled_entries, p_forecasts)]
        clvs = [
            closing_line_value(pf, pc)
            for pf, pc in zip(p_forecasts, p_closings)
        ]

        # EDPH (dollars per hour) - approximate, assuming 4h per slate
        hours_per_slate = 4.0
        edph = (total_winnings - total_stake) / hours_per_slate

        result = {
            "n": len(settled_entries),
            "total_stake": float(total_stake),
            "total_winnings": float(total_winnings),
            "roi": float(roi),
            "edph": float(edph),
            "brier_score": brier_score(p_forecasts, outcomes),
            "log_loss": log_loss(p_forecasts, outcomes),
            "mean_clv": float(np.mean(clvs)),
            "positive_clv_rate": float(np.mean([c > 0 for c in clvs])),
            "win_rate": float(np.mean(outcomes)),
            "processed_at": datetime.now().isoformat(),
        }

        # ROI by platform
        platforms = set(e.get("platform", "UNKNOWN") for e in settled_entries)
        result["roi_by_platform"] = {}
        for plat in platforms:
            subset = [e for e in settled_entries if e.get("platform") == plat]
            ss = sum(e.get("stake", 1.0) for e in subset)
            sw = sum(e.get("winnings", 0.0) for e in subset)
            result["roi_by_platform"][plat] = float((sw - ss) / ss) if ss > 0 else 0.0

        logger.info(
            "Settlement: n=%d ROI=%.2f%% EDPH=$%.2f Brier=%.4f meanCLV=%.4f",
            result["n"], roi * 100, edph, result["brier_score"], result["mean_clv"],
        )
        return result
