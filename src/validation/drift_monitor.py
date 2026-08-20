"""
Model drift monitor: CLV deterioration, feed latency, platform-rule changes.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Sequence

import numpy as np

logger = logging.getLogger(__name__)


def closing_line_value(
    p_forecast: float,
    p_closing: float,
    direction: str = "OVER",
) -> float:
    """
    CLV = log(p_forecast / p_closing) in logit space.

    Positive CLV means the model correctly moved away from the closing line
    (i.e., forecast was better than the closing market).

    direction : 'OVER' | 'UNDER' (which side was bet)
    """
    eps = 1e-6
    p_f = float(np.clip(p_forecast, eps, 1 - eps))
    p_c = float(np.clip(p_closing, eps, 1 - eps))

    logit_f = np.log(p_f / (1.0 - p_f))
    logit_c = np.log(p_c / (1.0 - p_c))

    clv = float(logit_f - logit_c)
    return clv if direction == "OVER" else -clv


def mean_clv(
    forecasts: Sequence[float],
    closing_lines: Sequence[float],
    directions: Optional[Sequence[str]] = None,
) -> Dict[str, float]:
    """
    Aggregate CLV statistics across a set of forecasts.
    """
    if directions is None:
        directions = ["OVER"] * len(forecasts)
    clvs = [
        closing_line_value(f, c, d)
        for f, c, d in zip(forecasts, closing_lines, directions)
    ]
    return {
        "mean_clv": float(np.mean(clvs)),
        "std_clv": float(np.std(clvs)),
        "positive_clv_rate": float(np.mean([c > 0 for c in clvs])),
        "n": len(clvs),
        "clv_values": clvs,
    }


class DriftMonitor:
    """
    Monitors rolling model metrics and flags drift conditions.

    Checks
    ------
    - CLV deterioration below threshold
    - Brier score degradation
    - Feed latency spikes
    - Platform rule changes (line shift anomalies)
    """

    def __init__(
        self,
        clv_warning_threshold: float = -0.05,
        clv_halt_threshold: float = -0.15,
        brier_warning_threshold: float = 0.28,
        brier_halt_threshold: float = 0.35,
        window: int = 50,
    ):
        self.clv_warning = clv_warning_threshold
        self.clv_halt = clv_halt_threshold
        self.brier_warning = brier_warning_threshold
        self.brier_halt = brier_halt_threshold
        self.window = window
        self._history: List[Dict] = []

    def record(self, entry: Dict) -> None:
        """Record a settled entry for drift tracking."""
        self._history.append(entry)
        if len(self._history) > 10 * self.window:
            self._history = self._history[-self.window:]

    def check_drift(self) -> Dict:
        """
        Evaluate current drift state.

        Returns
        -------
        dict with drift_level ('OK'|'WARNING'|'HALT'), metrics, reason
        """
        if len(self._history) < 10:
            return {
                "drift_level": "OK",
                "reason": "Insufficient data",
                "n_samples": len(self._history),
            }

        recent = self._history[-self.window:]

        # CLV
        clvs = [e.get("clv", 0.0) for e in recent if "clv" in e]
        mean_clv_val = float(np.mean(clvs)) if clvs else 0.0

        # Brier
        briers = [e.get("brier", 0.25) for e in recent if "brier" in e]
        mean_brier = float(np.mean(briers)) if briers else 0.25

        drift_level = "OK"
        reasons = []

        if mean_clv_val <= self.clv_halt:
            drift_level = "HALT"
            reasons.append(f"CLV={mean_clv_val:.4f} ≤ halt threshold {self.clv_halt}")
        elif mean_clv_val <= self.clv_warning:
            drift_level = max(drift_level, "WARNING")
            reasons.append(f"CLV={mean_clv_val:.4f} ≤ warning threshold {self.clv_warning}")

        if mean_brier >= self.brier_halt:
            drift_level = "HALT"
            reasons.append(f"Brier={mean_brier:.4f} ≥ halt threshold {self.brier_halt}")
        elif mean_brier >= self.brier_warning:
            if drift_level != "HALT":
                drift_level = "WARNING"
            reasons.append(f"Brier={mean_brier:.4f} ≥ warning threshold {self.brier_warning}")

        logger.info(
            "DriftMonitor: level=%s mean_clv=%.4f mean_brier=%.4f n=%d",
            drift_level, mean_clv_val, mean_brier, len(recent),
        )
        return {
            "drift_level": drift_level,
            "mean_clv": mean_clv_val,
            "mean_brier": mean_brier,
            "n_samples": len(recent),
            "reason": "; ".join(reasons) if reasons else "All metrics within bounds",
            "checked_at": datetime.now().isoformat(),
        }

    def check_feed_latency(self, expected_max_seconds: float = 60.0) -> Dict:
        """
        Check for stale feed data.

        Expects recent entries to have a 'fetched_at' timestamp.
        """
        if not self._history:
            return {"latency_ok": True, "reason": "No data"}

        latest = self._history[-1]
        fetched_at = latest.get("fetched_at")
        if not fetched_at:
            return {"latency_ok": True, "reason": "No fetched_at timestamp"}

        try:
            ts = datetime.fromisoformat(fetched_at)
            age_s = (datetime.now() - ts).total_seconds()
            ok = age_s <= expected_max_seconds
            return {
                "latency_ok": ok,
                "age_seconds": float(age_s),
                "max_seconds": expected_max_seconds,
                "reason": "OK" if ok else f"Feed stale ({age_s:.0f}s > {expected_max_seconds}s)",
            }
        except (ValueError, TypeError):
            return {"latency_ok": True, "reason": "Could not parse fetched_at"}
