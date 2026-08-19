"""Entry Construction and Scenario-Level Portfolio Optimization"""

import numpy as np
from datetime import datetime
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)


class PortfolioOptimizer:
    """Scenario-level joint portfolio optimization"""
    
    def __init__(self, bankroll: float):
        self.bankroll = bankroll
    
    def build_and_optimize(self, final_approved: List[Dict], pit_state: Any, platforms: List[str]) -> Dict[str, Any]:
        """Build feasible entries and optimize stakes"""
        
        # Generate legal entry combinations
        entries = []
        for i, leg1 in enumerate(final_approved[:5]):
            for leg2 in final_approved[i+1:6]:
                if leg1["platform"] == leg2["platform"]:
                    entry = {
                        "entry_id": f"entry_{i}_{final_approved.index(leg2)}",
                        "platform": leg1["platform"],
                        "legs": [leg1, leg2],
                        "p_joint": leg1["p_fused"] * leg2["p_fused"],
                        "multiplier": 1.5 * 1.6,
                    }
                    
                    entry["ev"] = entry["multiplier"] * entry["p_joint"] - 1.0
                    entries.append(entry)
        
        # Filter negative EV
        positive_ev_entries = [e for e in entries if e["ev"] > 0]
        
        # Kelly sizing with 1/4 fractional
        recommended = []
        total_stake = 0
        
        for entry in positive_ev_entries[:5]:
            kelly_frac = entry["ev"] / (entry["multiplier"] - 1) if entry["multiplier"] > 1 else 0.01
            kelly_frac = max(0.01, min(0.25, kelly_frac))
            
            stake = self.bankroll * kelly_frac / 4
            if stake > 2 and total_stake + stake <= self.bankroll * 0.5:
                entry["stake_recommended"] = float(stake)
                entry["stake_requested"] = float(stake)
                entry["stake_accepted"] = float(stake)
                recommended.append(entry)
                total_stake += stake
        
        logger.info(f"Entry Construction: {len(entries)} feasible → {len(positive_ev_entries)} positive EV → {len(recommended)} recommended")
        
        return {
            "all_entries": entries,
            "positive_ev_entries": positive_ev_entries,
            "recommended": recommended,
            "total_recommended_stake": total_stake,
        }
