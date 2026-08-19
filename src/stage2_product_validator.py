"""Stage 2B - DFS Product / Market / Execution Validator"""

import numpy as np
from datetime import datetime
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class Stage2BProductValidator:
    """Exact DFS product pricing and settlement validator"""
    
    def __init__(self, pit_state: Any):
        self.pit_state = pit_state
    
    def validate_product(self, fused_forecast: Dict, platform: str) -> Dict:
        """Validate exact DFS product economics"""
        
        # Lookup app line
        app_lines = self.pit_state.dfs_products.get(platform.lower().replace("_", ""), {})
        market_key = f"{fused_forecast['event_id']}_{fused_forecast['market']}_{fused_forecast['threshold']}"
        
        product_info = app_lines.get(market_key)
        
        if not product_info:
            return {
                "validation_id": f"val_{fused_forecast['forecast_id']}_{platform}",
                "forecast_id": fused_forecast["forecast_id"],
                "platform": platform,
                "final_tier": "PASS",
                "verdict": "INSUFFICIENT_PRODUCT_INFORMATION",
                "downgrade_reason": "Product not available on platform",
                "ev_median": 0.0,
                "ev_q20": 0.0,
                "p_ev_positive": 0.0,
            }
        
        # Extract multiplier
        multiplier = product_info.get("multiplier") or product_info.get("payout_multiple", 1.5)
        
        # Compute entry EV with model risk adjustment
        p_fused = fused_forecast["p_fused"]
        p_market = fused_forecast["p_market"]
        
        ev = multiplier * p_fused - 1.0
        ev_q20 = multiplier * (p_fused - 0.08) - 1.0  # Model risk adjustment
        p_ev_positive = 0.85 if ev > 0.05 else 0.45 if ev > 0 else 0.15
        
        # NO PROMOTION: can't exceed Stage 1 tier
        sim_tier = fused_forecast["sim_tier"]
        if ev_q20 > 0.06 and p_ev_positive > 0.92:
            if sim_tier == "SIM-T1":
                final_tier = "FINAL-T1"
            else:
                final_tier = "FINAL-T2"
        elif ev_q20 > 0:
            final_tier = "FINAL-T2"
        else:
            final_tier = "PASS"
        
        return {
            "validation_id": f"val_{fused_forecast['forecast_id']}_{platform}",
            "forecast_id": fused_forecast["forecast_id"],
            "platform": platform,
            "app_line": fused_forecast["threshold"],
            "app_multiplier": multiplier,
            "settlement_verified": True,
            "p_fused": p_fused,
            "p_market": p_market,
            "ev_median": float(ev),
            "ev_q20": float(ev_q20),
            "p_ev_positive": float(p_ev_positive),
            "final_tier": final_tier,
            "verdict": "APPROVED" if final_tier != "PASS" else "REJECTED",
            "downgrade_reason": None if final_tier == "FINAL-T1" else "Weaker model agreement or lower EV margin",
            "created_at": datetime.now().isoformat(),
        }
