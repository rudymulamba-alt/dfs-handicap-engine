#!/usr/bin/env python3
"""
UNIFIED DUAL-CORE DFS HANDICAPPING ENGINE v9.0
Complete end-to-end execution: Stage 1 → Stage 2A → Stage 2B → Portfolio Optimization
"""

import argparse
import json
import os
from datetime import datetime, date as _date
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import logging

from src.stage1_core_a import Stage1CoreA, reconcile_forecasts
from src.stage2_blind_challenge import Stage2ABlindChallenger
from src.stage2_product_validator import Stage2BProductValidator
from src.portfolio_optimizer import PortfolioOptimizer
from src.data.point_in_time import PointInTimeCapture, PointInTimeState

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Engine:
    """Main v9.0 engine orchestrator"""
    
    def __init__(self, api_key: str, bankroll: float = 1000.0):
        self.api_key = api_key
        self.bankroll = bankroll
        self.run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.mode = "DEEP"
        self.model_state = "PRODUCTION"
        self.validation_class = "P"
        
        logger.info(f"✓ Engine v9.0 initialized | Run ID: {self.run_id} | Bankroll: ${bankroll}")

    def run_slate(self, sports: List[str], date: str, platforms: List[str]) -> Dict[str, Any]:
        """Execute full pipeline"""
        logger.info(f"\n{'='*80}")
        logger.info(f"UNIFIED DUAL-CORE DFS HANDICAPPING ENGINE v9.0")
        logger.info(f"{'='*80}")
        logger.info(f"Mode: {self.mode} | Sport: {', '.join(sports)} | Date: {date}")
        logger.info(f"Platforms: {', '.join(platforms)} | Bankroll: ${self.bankroll}")
        
        # STEP 1: Capture PIT state
        logger.info(f"\n[T-180m] CAPTURING POINT-IN-TIME STATE...")
        pit_state = PointInTimeCapture().capture_slate_state(sports, date, self.api_key)
        logger.info(f"✓ State captured | Hash: {pit_state.information_state_hash[:16]}...")
        
        # STEP 2: Stage 1 - Core A
        logger.info(f"\n[T-165m] STAGE 1: CORE A STRUCTURAL SIMULATION...")
        stage1_candidates = Stage1CoreA(pit_state).scan_and_shortlist(sports, self.mode)
        logger.info(f"✓ Markets scanned: {len(stage1_candidates['all_markets'])}")
        logger.info(f"✓ Stage 1 survivors (T1/T2/COND): {len(stage1_candidates['live_survivors'])}")
        logger.info(f"✓ Rejected (WATCH/PASS): {len(stage1_candidates['rejected'])}")
        
        # STEP 3: Freeze handoff
        logger.info(f"\n[T-135m] FREEZING HANDOFF SNAPSHOT...")
        handoff_snapshots = [
            {
                "handoff_id": f"handoff_{f.forecast_id}",
                "forecast": asdict(f),
                "frozen_at": datetime.now().isoformat(),
            } for f in stage1_candidates['live_survivors']
        ]
        logger.info(f"✓ {len(handoff_snapshots)} handoff snapshots frozen")
        
        # STEP 4: Stage 2A - Blind Challenge
        logger.info(f"\n[T-110m] STAGE 2A: BLIND EXPERT HANDICAPPER CHALLENGE...")
        stage2a_reviews = [Stage2ABlindChallenger().challenge_blind(h) for h in handoff_snapshots]
        logger.info(f"✓ Blind reviews completed for {len(stage2a_reviews)} candidates")
        
        # STEP 5: Reconciliation
        logger.info(f"\n[T-100m] RECONCILING CORE A + CORE B (SHARED ERROR FUSION)...")
        fused_forecasts = reconcile_forecasts(
            stage1_candidates['live_survivors'],
            stage2a_reviews
        )
        logger.info(f"✓ Fused probabilities computed | Covariance: explicit")
        
        # STEP 6: Stage 2B - Product Validation
        logger.info(f"\n[T-90m] STAGE 2B: DFS PRODUCT VALIDATION...")
        validator = Stage2BProductValidator(pit_state)
        stage2b_validations = []
        for forecast in fused_forecasts:
            for platform in platforms:
                val = validator.validate_product(forecast, platform)
                stage2b_validations.append(val)
        
        logger.info(f"✓ Product validations completed")
        logger.info(f"✓ Platforms checked: {len(set(v['platform'] for v in stage2b_validations))}")
        
        # Extract approved
        final_approved = [v for v in stage2b_validations if v['final_tier'] in ['FINAL-T1', 'FINAL-T2', 'FINAL-CONDITIONAL']]
        logger.info(f"✓ Final approved legs: {len(final_approved)}")
        
        # STEP 7: Portfolio
        logger.info(f"\n[T-60m] ENTRY CONSTRUCTION & PORTFOLIO OPTIMIZATION...")
        final_entries = PortfolioOptimizer(self.bankroll).build_and_optimize(final_approved, pit_state, platforms)
        logger.info(f"✓ Feasible entries: {len(final_entries['all_entries'])}")
        logger.info(f"✓ Recommended entries: {len(final_entries['recommended'])}")
        
        # STEP 8: Output
        logger.info(f"\n[T-30m] COMPILING FINAL OUTPUT...")
        final_output = self._compile_output(stage1_candidates, stage2b_validations, final_entries, pit_state)
        
        # Audit
        logger.info(f"\n{'='*80}")
        logger.info(f"AUDIT SUMMARY")
        logger.info(f"{'='*80}")
        for k, v in final_output['audit'].items():
            logger.info(f"{k}: {v}")
        logger.info(f"{'='*80}\n")
        
        return final_output

    def _compile_output(self, stage1: Dict, stage2b: List[Dict], entries: Dict, pit_state: PointInTimeState) -> Dict:
        """Compile final output"""
        final_t1 = [v for v in stage2b if v['final_tier'] == 'FINAL-T1']
        final_t2 = [v for v in stage2b if v['final_tier'] == 'FINAL-T2']
        final_cond = [v for v in stage2b if v['final_tier'] == 'FINAL-CONDITIONAL']
        
        return {
            "run_id": self.run_id,
            "timestamp": datetime.now().isoformat(),
            "slate_date": pit_state.slate_date,
            "final_tier_1_legs": final_t1,
            "final_tier_2_legs": final_t2,
            "final_conditional_legs": final_cond,
            "recommended_entries": entries['recommended'],
            "audit": {
                "markets_scanned": len(stage1['all_markets']),
                "stage1_survivors": len(stage1['live_survivors']),
                "stage2_vetoes": len([v for v in stage2b if v['final_tier'] == 'PASS']),
                "stage2_downgrades": len([v for v in stage2b if v['final_tier'] == 'FINAL-T2']),
                "final_approved_legs": len(final_t1) + len(final_t2) + len(final_cond),
                "feasible_entries": len(entries['all_entries']),
                "portfolio_exclusions": len(entries['all_entries']) - len(entries['recommended']),
                "recommended_entries": len(entries['recommended'])
            }
        }


def resolve_run_date(cli_date: Optional[str] = None) -> str:
    """
    Determine the slate date using the following precedence (highest first):

    1. ``cli_date`` — value supplied via ``--date`` on the command line.
    2. ``MODEL_DATE`` environment variable.
    3. Today's date (UTC) formatted as ``YYYY-MM-DD``.

    The resolved value must be a valid date string in ``YYYY-MM-DD`` format.
    A ``ValueError`` is raised if the supplied string cannot be parsed.
    """
    raw = cli_date or os.environ.get("MODEL_DATE", "").strip() or None
    if raw:
        # Validate format — raises ValueError on bad input.
        datetime.strptime(raw, "%Y-%m-%d")
        return raw
    return _date.today().strftime("%Y-%m-%d")


def main(argv: Optional[List[str]] = None) -> Dict:
    """Execute full pipeline"""
    parser = argparse.ArgumentParser(
        description="Unified Dual-Core DFS Handicapping Engine v9.0"
    )
    parser.add_argument(
        "--date",
        default=None,
        metavar="YYYY-MM-DD",
        help=(
            "Slate date to run (YYYY-MM-DD). "
            "Falls back to MODEL_DATE env var, then today's date."
        ),
    )
    args = parser.parse_args(argv)

    # PARLAY_API2 is the sole required credential.  The legacy PARLAY_API_KEY
    # name is accepted as a fallback so that existing CI setups are not broken.
    api_key = (
        os.getenv('PARLAY_API2', '').strip()
        or os.getenv('PARLAY_API_KEY', '').strip()
    )
    if not api_key:
        raise RuntimeError(
            "PARLAY_API2 is required. "
            "Set your Parlay API token as PARLAY_API2."
        )
    bankroll = float(os.getenv('ENGINE_BANKROLL', '1000.0'))
    sports = ['mlb', 'wnba']
    date = resolve_run_date(args.date)
    platforms = ['DRAFTKINGS_PICK6', 'PARLAYPLAY', 'CHALKBOARD']
    
    logger.info(f"Slate date: {date}")

    # Initialize database
    try:
        from src.db.models import create_all_tables
        create_all_tables()
        logger.info("✓ Database tables initialized")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Database initialization skipped: %s", exc)

    engine = Engine(api_key=api_key, bankroll=bankroll)
    result = engine.run_slate(sports=sports, date=date, platforms=platforms)
    
    # Audit ledger
    try:
        from src.audit.ledger import save_ledger, format_final_output
        print(format_final_output(result))
        save_ledger(f"output/audit_ledger_{engine.run_id}.json")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Audit ledger write skipped: %s", exc)
        # Fallback output
        print("\n" + "="*80)
        print("FINAL RECOMMENDATION")
        print("="*80)
        print(json.dumps(result, indent=2, default=str))
    
    # Save JSON
    os.makedirs('output', exist_ok=True)
    output_file = f"output/final_recommendation_{engine.run_id}.json"
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    logger.info(f"✓ Output saved to {output_file}")
    
    return result


if __name__ == "__main__":
    main()
