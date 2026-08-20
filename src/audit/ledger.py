"""
Audit & reporting: append-only decision ledger, user-facing output,
stage-by-stage rejection reasoning, discovery logging.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_LEDGER: List[Dict] = []


def append_event(event_type: str, payload: Dict, run_id: str = "") -> Dict:
    """
    Append an immutable event to the in-memory audit ledger.

    Returns the full event record.
    """
    record = {
        "seq": len(_LEDGER) + 1,
        "event_type": event_type,
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "payload": payload,
    }
    _LEDGER.append(record)
    logger.debug("AUDIT [%s] seq=%d run=%s", event_type, record["seq"], run_id)
    return record


def get_ledger_snapshot(run_id: Optional[str] = None) -> List[Dict]:
    """Return a copy of all ledger events, optionally filtered by run_id."""
    if run_id:
        return [e for e in _LEDGER if e.get("run_id") == run_id]
    return list(_LEDGER)


def save_ledger(path: str = "output/audit_ledger.json") -> str:
    """Persist the in-memory ledger to a JSON file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(_LEDGER, f, indent=2, default=str)
    logger.info("Audit ledger saved to %s (%d events)", path, len(_LEDGER))
    return path


def format_final_output(result: Dict) -> str:
    """
    Format the final recommendation for human-readable display.

    Returns a multi-line string.
    """
    lines = [
        "=" * 80,
        f"FINAL RECOMMENDATION  |  Run: {result.get('run_id', '?')}",
        f"Date: {result.get('slate_date', '?')}  |  Generated: {result.get('timestamp', '?')}",
        "=" * 80,
        "",
    ]

    # Tier 1 legs
    t1 = result.get("final_tier_1_legs", [])
    lines.append(f"FINAL T1 LEGS ({len(t1)}):")
    for leg in t1:
        lines.append(
            f"  ✓ {leg.get('forecast_id', '?'):20s}  {leg.get('platform', '?'):20s}"
            f"  p_fused={leg.get('p_fused', 0):.3f}  EV={leg.get('ev_median', 0):.3f}"
        )

    # Tier 2 legs
    t2 = result.get("final_tier_2_legs", [])
    lines.append(f"\nFINAL T2 LEGS ({len(t2)}):")
    for leg in t2:
        lines.append(
            f"  ◆ {leg.get('forecast_id', '?'):20s}  {leg.get('platform', '?'):20s}"
            f"  p_fused={leg.get('p_fused', 0):.3f}  EV={leg.get('ev_median', 0):.3f}"
        )

    # Conditional legs
    cond = result.get("final_conditional_legs", [])
    lines.append(f"\nFINAL CONDITIONAL LEGS ({len(cond)}):")
    for leg in cond:
        lines.append(
            f"  ○ {leg.get('forecast_id', '?'):20s}  {leg.get('platform', '?'):20s}"
            f"  p_fused={leg.get('p_fused', 0):.3f}  EV={leg.get('ev_median', 0):.3f}"
        )

    # Recommended entries
    entries = result.get("recommended_entries", [])
    lines.append(f"\nRECOMMENDED ENTRIES ({len(entries)}):")
    for entry in entries:
        lines.append(
            f"  → {entry.get('entry_id', '?'):20s}  {entry.get('platform', '?'):16s}"
            f"  stake=${entry.get('stake_recommended', 0):.2f}"
            f"  p_joint={entry.get('p_joint', 0):.3f}"
        )

    # Audit summary
    audit = result.get("audit", {})
    lines.append("\nAUDIT SUMMARY:")
    for k, v in audit.items():
        lines.append(f"  {k}: {v}")

    lines.append("=" * 80)
    return "\n".join(lines)


def log_stage_rejection(
    forecast_id: str,
    stage: str,
    reason: str,
    details: Optional[Dict] = None,
    run_id: str = "",
) -> None:
    """Log a stage rejection with full reasoning for discovery reruns."""
    payload = {
        "forecast_id": forecast_id,
        "stage": stage,
        "reason": reason,
        "details": details or {},
    }
    append_event("STAGE_REJECTION", payload, run_id)
    logger.info("REJECTED [%s] %s: %s", stage, forecast_id, reason)


def discovery_log(
    run_id: str,
    markets_considered: List[Dict],
    survivors: List[Dict],
    rejected: List[Dict],
) -> Dict:
    """
    Log discovery-phase results for future reruns.

    Returns summary dict.
    """
    payload = {
        "n_considered": len(markets_considered),
        "n_survivors": len(survivors),
        "n_rejected": len(rejected),
        "survivor_ids": [f.get("forecast_id", "") for f in survivors],
        "rejection_reasons": [
            {"id": f.get("forecast_id", ""), "tier": f.get("sim_tier", "")}
            for f in rejected
        ],
    }
    append_event("DISCOVERY_LOG", payload, run_id)
    logger.info(
        "Discovery [run=%s]: considered=%d survivors=%d rejected=%d",
        run_id, len(markets_considered), len(survivors), len(rejected),
    )
    return payload
