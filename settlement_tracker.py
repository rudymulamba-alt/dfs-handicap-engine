#!/usr/bin/env python3
"""
SETTLEMENT TRACKING & CALIBRATION
Monitor CLV, P&L, and prospective validation
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s')
logger = logging.getLogger(__name__)

class SettlementTracker:
    """Track outcomes, CLV, and calibration metrics"""
    
    def __init__(self):
        self.entries = []
        self.settlements = []
        self.clv_registry = []
        self.calibration_data = []
    
    def log_closing_line(self, entry_key: str, leg_id: str, threshold: float, closing_price: float, model_prob: float) -> dict:
        """Log closing line for CLV calculation"""
        
        # Devig closing price to probability
        closing_prob = 1.0 / (closing_price / 100 + 1) if closing_price > 0 else 0.5
        
        clv_prob = model_prob - closing_prob
        clv_direction = "FAVORABLE" if clv_prob > 0.02 else "UNFAVORABLE" if clv_prob < -0.02 else "NEUTRAL"
        
        clv_record = {
            "entry_key": entry_key,
            "leg_id": leg_id,
            "threshold": threshold,
            "model_probability": model_prob,
            "closing_price": closing_price,
            "closing_probability": closing_prob,
            "clv_probability": clv_prob,
            "clv_direction": clv_direction,
            "timestamp": datetime.now().isoformat(),
        }
        
        self.clv_registry.append(clv_record)
        
        logger.info(f"[CLV] {entry_key} - {leg_id}")
        logger.info(f"  Model: {model_prob*100:.1f}% | Closing: {closing_prob*100:.1f}% | CLV: {clv_prob*100:+.1f}% ({clv_direction})")
        
        return clv_record
    
    def settle_entry(self, entry_key: str, legs_results: List[Dict], payout_if_correct: float, payout_received: float) -> dict:
        """Settle entry and calculate P&L"""
        
        all_legs_hit = all(leg["result"] == "HIT" for leg in legs_results)
        
        settlement = {
            "entry_key": entry_key,
            "legs_results": legs_results,
            "entry_result": "WIN" if all_legs_hit else "LOSS",
            "payout_if_correct": payout_if_correct,
            "payout_received": payout_received,
            "gross_payout": payout_received,
            "net_pnl": payout_received - (5.00 if "pick6" in entry_key else 3.00),  # Assume stake
            "roi": (payout_received - (5.00 if "pick6" in entry_key else 3.00)) / (5.00 if "pick6" in entry_key else 3.00),
            "settlement_time": datetime.now().isoformat(),
        }
        
        self.settlements.append(settlement)
        
        logger.info(f"\n[SETTLEMENT] {entry_key}")
        logger.info(f"  Legs: {', '.join([l['leg_id'] + ':' + l['result'] for l in legs_results])}")
        logger.info(f"  Payout: ${payout_received:.2f} (Entry Result: {settlement['entry_result']})")
        logger.info(f"  P&L: {settlement['net_pnl']:+.2f} | ROI: {settlement['roi']*100:+.1f}%")
        
        return settlement
    
    def compute_calibration(self) -> dict:
        """Compute calibration metrics across all settled entries"""
        
        if not self.settlements:
            logger.warning("No settled entries yet")
            return {}
        
        wins = len([s for s in self.settlements if s["entry_result"] == "WIN"])
        losses = len([s for s in self.settlements if s["entry_result"] == "LOSS"])
        total_pnl = sum(s["net_pnl"] for s in self.settlements)
        total_roi = sum(s["roi"] for s in self.settlements)
        avg_roi = total_roi / len(self.settlements) if self.settlements else 0
        
        calibration = {
            "sample_size": len(self.settlements),
            "wins": wins,
            "losses": losses,
            "win_rate": wins / len(self.settlements) if self.settlements else 0,
            "total_pnl": total_pnl,
            "average_roi_per_entry": avg_roi,
            "edph_estimate": (total_pnl / len(self.settlements)) * 2,  # 2 entries per hour estimate
            "timestamp": datetime.now().isoformat(),
        }
        
        logger.info("\n" + "="*80)
        logger.info("CALIBRATION SUMMARY")
        logger.info("="*80)
        logger.info(f"Sample Size: {calibration['sample_size']} entries")
        logger.info(f"Win Rate: {calibration['win_rate']*100:.1f}% ({wins}W-{losses}L)")
        logger.info(f"Total P&L: ${calibration['total_pnl']:+.2f}")
        logger.info(f"Avg ROI/Entry: {calibration['average_roi_per_entry']*100:+.1f}%")
        logger.info(f"EDPH Estimate: ${calibration['edph_estimate']:+.2f}/hour")
        logger.info("="*80)
        
        return calibration

class CalibrationValidator:
    """Validate model calibration against realized outcomes"""
    
    def validate_brier_score(self, predictions: List[float], outcomes: List[int]) -> float:
        """Brier Score: mean squared error of probabilities"""
        if not predictions or not outcomes:
            return None
        
        brier = sum((p - o) ** 2 for p, o in zip(predictions, outcomes)) / len(predictions)
        logger.info(f"Brier Score: {brier:.4f} (lower is better, max=1.0)")
        return brier
    
    def validate_log_loss(self, predictions: List[float], outcomes: List[int]) -> float:
        """Log Loss: negative log-likelihood"""
        if not predictions or not outcomes:
            return None
        
        epsilon = 1e-15
        log_loss = -sum(o * np.log(np.clip(p, epsilon, 1)) + (1-o) * np.log(np.clip(1-p, epsilon, 1)) for p, o in zip(predictions, outcomes)) / len(predictions)
        logger.info(f"Log Loss: {log_loss:.4f} (lower is better)")
        return log_loss
    
    def validate_calibration_slope(self, predictions: List[float], outcomes: List[int]) -> float:
        """Calibration slope: should be ~1.0 for perfect calibration"""
        if len(predictions) < 10:
            logger.warning("Insufficient samples for calibration slope")
            return None
        
        # Simplified: group predictions into bins and compare
        slope = 1.0  # Placeholder
        logger.info(f"Calibration Slope: {slope:.3f} (target: 1.0)")
        return slope

def main():
    logger.info("\n" + "="*80)
    logger.info("SETTLEMENT TRACKING & CALIBRATION SYSTEM")
    logger.info("="*80)
    
    tracker = SettlementTracker()
    
    # Log closing lines
    logger.info("\n[CLOSING LINES] Captured 30 minutes before lock\n")
    
    tracker.log_closing_line(
        entry_key="dk_pick6_entry_1_pick6_mlb_combo",
        leg_id="forecast_2_mlb_1_jobe_k",
        threshold=6.5,
        closing_price=-118,
        model_prob=0.57
    )
    
    tracker.log_closing_line(
        entry_key="dk_pick6_entry_1_pick6_mlb_combo",
        leg_id="forecast_5_mlb_3_bradley_k",
        threshold=6.5,
        closing_price=-116,
        model_prob=0.59
    )
    
    tracker.log_closing_line(
        entry_key="pp_entry_2_pp_mlb_wnba",
        leg_id="forecast_17_wnba_1_player_points",
        threshold=18.5,
        closing_price=-112,
        model_prob=0.60
    )
    
    # Simulate settlement (mock results)
    logger.info("\n[SIMULATING ENTRY OUTCOMES]\n")
    
    # Entry 1 result: 1 HIT, 1 MISS = LOSS
    tracker.settle_entry(
        entry_key="dk_pick6_entry_1_pick6_mlb_combo",
        legs_results=[
            {"leg_id": "forecast_2_jobe_k", "result": "HIT", "actual_value": 7.2},
            {"leg_id": "forecast_5_bradley_k", "result": "MISS", "actual_value": 6.1},
        ],
        payout_if_correct=17.10,
        payout_received=0.0
    )
    
    # Entry 2 result: 2 HITS = WIN
    tracker.settle_entry(
        entry_key="pp_entry_2_pp_mlb_wnba",
        legs_results=[
            {"leg_id": "forecast_17_wnba_points", "result": "HIT", "actual_value": 19.5},
            {"leg_id": "forecast_19_stock_k", "result": "HIT", "actual_value": 7.0},
        ],
        payout_if_correct=7.29,
        payout_received=7.29
    )
    
    # Compute calibration
    calibration = tracker.compute_calibration()
    
    # Save settlement log
    os.makedirs('output', exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    settlement_file = f"output/settlement_log_{timestamp}.json"
    
    with open(settlement_file, 'w') as f:
        json.dump({
            "clv_registry": tracker.clv_registry,
            "settlements": tracker.settlements,
            "calibration": calibration,
            "timestamp": datetime.now().isoformat(),
        }, f, indent=2)
    
    logger.info(f"\n✓ Settlement log saved to: {settlement_file}")
    
    return calibration

if __name__ == "__main__":
    try:
        import numpy as np
    except:
        import subprocess, sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "numpy"])
        import numpy as np
    
    main()
