#!/usr/bin/env python3
"""
CALIBRATION TIMELINE ANALYSIS
Calculate time-to-statistical-significance for v9.0 engine
"""

import json
import math
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s')
logger = logging.getLogger(__name__)

class CalibrationTimeline:
    """Calculate calibration requirements and timelines"""
    
    def __init__(self):
        self.min_sample_size = 50  # Brier score reliability threshold
        self.min_edph_confidence = 20  # entries for CLV/ROI confidence
        self.high_precision_threshold = 200  # for formal statistical validation
        
    def calculate_entry_velocity(self):
        """Estimate entries per day based on slate frequency"""
        
        logger.info("\n" + "="*80)
        logger.info("ENTRY VELOCITY ANALYSIS")
        logger.info("="*80)
        
        scenarios = {
            "Conservative (MLB only, selective)": {
                "entries_per_day": 3,
                "description": "1 slate/day, 3 approved entries per slate",
                "basis": "15 MLB games × 2 pitchers = 30 markets; ~10% approval rate",
            },
            "Moderate (MLB + WNBA, balanced)": {
                "entries_per_day": 6,
                "description": "2 slates/day, 3 approved entries per slate",
                "basis": "MLB + WNBA coverage; ~20% approval rate combined",
            },
            "Aggressive (Multi-sport, 24hr coverage)": {
                "entries_per_day": 10,
                "description": "Multiple slates/day (MLB, WNBA, late games, other sports)",
                "basis": "Expanded coverage; ~25% approval rate",
            }
        }
        
        for scenario_name, scenario_data in scenarios.items():
            logger.info(f"\n{scenario_name}")
            logger.info(f"  Daily Entry Volume: {scenario_data['entries_per_day']} entries/day")
            logger.info(f"  Rationale: {scenario_data['basis']}")
            logger.info(f"  Description: {scenario_data['description']}")
        
        return scenarios

    def calculate_timelines(self, scenarios):
        """Calculate days-to-calibration for each scenario"""
        
        logger.info("\n" + "="*80)
        logger.info("CALIBRATION TIMELINES")
        logger.info("="*80)
        
        calibration_gates = {
            "Minimal Validation": {
                "sample_size": 20,
                "metrics": ["Win rate", "Gross P&L"],
                "confidence_level": "LOW - high variance",
            },
            "Basic Calibration": {
                "sample_size": 50,
                "metrics": ["Brier score", "Win rate", "CLV estimate"],
                "confidence_level": "MODERATE - can distinguish signal from noise",
            },
            "Strong Calibration": {
                "sample_size": 100,
                "metrics": ["Brier score", "Log loss", "CRPS", "Calibration slope"],
                "confidence_level": "HIGH - reliable predictions",
            },
            "Formal Validation": {
                "sample_size": 200,
                "metrics": ["All above + Drift detection", "Prospective registry", "Rollover effect"],
                "confidence_level": "VERY HIGH - publishable quality",
            }
        }
        
        results = {}
        
        for scenario_name, scenario_data in scenarios.items():
            entries_per_day = scenario_data["entries_per_day"]
            
            logger.info(f"\n{'='*80}")
            logger.info(f"SCENARIO: {scenario_name}")
            logger.info(f"Assumption: {entries_per_day} entries/day")
            logger.info(f"{'='*80}")
            
            scenario_timeline = {}
            
            for gate_name, gate_data in calibration_gates.items():
                sample_size = gate_data["sample_size"]
                days_required = math.ceil(sample_size / entries_per_day)
                date_ready = datetime.now() + timedelta(days=days_required)
                
                scenario_timeline[gate_name] = {
                    "sample_size": sample_size,
                    "days": days_required,
                    "ready_date": date_ready.strftime("%Y-%m-%d"),
                    "confidence": gate_data["confidence_level"],
                    "metrics": gate_data["metrics"],
                }
                
                logger.info(f"\n{gate_name}")
                logger.info(f"  Required Sample Size: {sample_size} entries")
                logger.info(f"  Days to Complete: {days_required} days")
                logger.info(f"  Ready Date: {date_ready.strftime('%A, %B %d, %Y')}")
                logger.info(f"  Confidence Level: {gate_data['confidence_level']}")
                logger.info(f"  Metrics Computed: {', '.join(gate_data['metrics'][:2])}...")
            
            results[scenario_name] = scenario_timeline
        
        return results

    def calculate_critical_path(self):
        """Identify critical path: what must happen first"""
        
        logger.info("\n" + "="*80)
        logger.info("CRITICAL PATH TO PROFITABILITY VALIDATION")
        logger.info("="*80)
        
        milestones = [
            {
                "milestone": "Current Status",
                "entries": 3,
                "days_from_now": 0,
                "action": "LIVE - Jobe/Bradley, Stock, Holmes conditionals deployed",
                "priority": "N/A",
            },
            {
                "milestone": "Immediate Feedback",
                "entries": 5,
                "days_from_now": 1,
                "action": "Collect CLV, settlement, realize P&L from first 5 entries",
                "priority": "HIGH",
                "reason": "Detect systematic model errors early (overshooting/undershooting)",
            },
            {
                "milestone": "Basic Validation",
                "entries": 20,
                "days_from_now": 7,
                "action": "Win rate, gross P&L, coverage rate",
                "priority": "HIGH",
                "reason": "Falsify if EDPH_q20 < $0 or win rate < 40%",
            },
            {
                "milestone": "Calibration Ready",
                "entries": 50,
                "days_from_now": 17,
                "action": "Brier score, log loss, CRPS, CLV distribution",
                "priority": "CRITICAL",
                "reason": "Model calibration achieves statistical power; confidence in P&L estimate",
            },
            {
                "milestone": "Drift Detection",
                "entries": 100,
                "days_from_now": 33,
                "action": "Split sample: first 50 vs last 50; test for significant drift",
                "priority": "CRITICAL",
                "reason": "Detect if model degrades over time (sportsbook market adaptation)",
            },
            {
                "milestone": "Formal Validation",
                "entries": 200,
                "days_from_now": 67,
                "action": "Prospective registry lock; publish calibration results",
                "priority": "MEDIUM",
                "reason": "Ready for investor/stakeholder review; defensible claims",
            }
        ]
        
        for i, milestone in enumerate(milestones, 1):
            logger.info(f"\n[{i}] {milestone['milestone']}")
            logger.info(f"    Entries Needed: {milestone['entries']}")
            logger.info(f"    Timeline: {milestone['days_from_now']} days from now")
            logger.info(f"    Action: {milestone['action']}")
            logger.info(f"    Priority: {milestone['priority']}")
            if 'reason' in milestone:
                logger.info(f"    Why: {milestone['reason']}")
        
        return milestones

    def calculate_risks_and_gates(self):
        """Identify kill-switch scenarios"""
        
        logger.info("\n" + "="*80)
        logger.info("RISK GATES & KILL SWITCHES")
        logger.info("="*80)
        
        gates = [
            {
                "gate": "IMMEDIATE LOSS HALT",
                "trigger": "After entry 5: EDPH_q20 < -$50 (i.e., losing money)",
                "action": "PAUSE - Investigate model error (overfitting, bad data, etc.)",
                "timeline": "Day 1-2",
            },
            {
                "gate": "COVERAGE FAILURE",
                "trigger": "After entry 20: k_exec < 15% (too few viable markets)",
                "action": "HALT - Insufficient opportunity density; model too selective",
                "timeline": "Week 1",
            },
            {
                "gate": "CALIBRATION COLLAPSE",
                "trigger": "After entry 50: Brier score > 0.30 (worse than random)",
                "action": "HALT - Model fundamentally miscalibrated",
                "timeline": "Week 3",
            },
            {
                "gate": "DRIFT DETECTION",
                "trigger": "After entry 100: Significant statistical drift (first 50 vs last 50)",
                "action": "RETRAIN or HALT - Market has adapted, model no longer valid",
                "timeline": "Week 5",
            },
            {
                "gate": "PROFITABILITY VALIDATION",
                "trigger": "After entry 200: EDPH_q20 > $0 AND Brier < 0.22",
                "action": "APPROVE - Ready for real-money deployment at scale",
                "timeline": "Week 10",
            }
        ]
        
        for gate in gates:
            logger.info(f"\n{gate['gate']}")
            logger.info(f"  Trigger Point: {gate['trigger']}")
            logger.info(f"  Expected Timeline: {gate['timeline']}")
            logger.info(f"  Response: {gate['action']}")
        
        return gates

    def summary_table(self, scenarios, timelines):
        """Create summary table of all scenarios"""
        
        logger.info("\n" + "="*80)
        logger.info("QUICK REFERENCE TABLE")
        logger.info("="*80)
        
        logger.info("\n┌─ DAYS TO KEY MILESTONES ─────────────────────────────────┐")
        logger.info("│")
        logger.info("│  Scenario                          │ 20 entries │ 50 entries │ 200 entries")
        logger.info("├────────────────────────────────────┼────────────┼────────────┼─────────────")
        
        for scenario_name, scenario_data in scenarios.items():
            entries_per_day = scenario_data["entries_per_day"]
            
            days_20 = math.ceil(20 / entries_per_day)
            days_50 = math.ceil(50 / entries_per_day)
            days_200 = math.ceil(200 / entries_per_day)
            
            logger.info(f"│  {scenario_name:<33} │ {days_20:>9} │ {days_50:>10} │ {days_200:>11}")
        
        logger.info("│")
        logger.info("└──────────────────────────────────────────────────────────┘")

    def detailed_breakdown(self):
        """Deep dive: what happens at each milestone"""
        
        logger.info("\n" + "="*80)
        logger.info("DETAILED BREAKDOWN: WHAT WE'RE MEASURING")
        logger.info("="*80)
        
        metrics = {
            "Entries 1-5 (Days 0-2)": {
                "name": "Immediate Feedback",
                "checks": [
                    "Settlement completeness (did all entries resolve?)",
                    "CLV calculation (are we beating the closing line?)",
                    "Realized payout vs model prediction (lucky or accurate?)",
                    "Early drift signals (are markets already adapting?)",
                ],
                "pass_criteria": "No systematic errors detected; EDPH not catastrophically negative",
                "fail_criteria": "EDPH_q20 < -$50; repeated misses on same market type",
            },
            "Entries 6-20 (Days 2-7)": {
                "name": "Basic Validation",
                "checks": [
                    "Win rate (target: 45-55% on first sample)",
                    "Gross P&L (positive or negative trend?)",
                    "Coverage rate k_exec (% of scanned markets that got approved)",
                    "Participation model validation (did players get minutes we predicted?)",
                ],
                "pass_criteria": "Win rate 40-60%; EDPH_q20 > -$5; coverage k_exec > 20%",
                "fail_criteria": "Win rate <30% or >70%; EDPH_q20 < -$25; systematic bias in one market",
            },
            "Entries 21-50 (Days 7-17)": {
                "name": "Calibration Readiness",
                "checks": [
                    "Brier score (should be 0.15-0.25 for good model)",
                    "Log loss (entropy: lower = better probability estimates)",
                    "CRPS (continuous rank probability score)",
                    "Quantile calibration (are our Q10/Q90 estimates accurate?)",
                    "CLV tracking (average daily edge vs closing line)",
                ],
                "pass_criteria": "Brier 0.15-0.25; Log loss 0.40-0.60; EDPH_q20 > $0",
                "fail_criteria": "Brier > 0.30; Log loss > 0.70; EDPH trending negative",
            },
            "Entries 51-100 (Days 17-33)": {
                "name": "Drift Detection",
                "checks": [
                    "Split-sample test: Calibration(entries 1-50) vs Holdout(entries 51-100)",
                    "Slope regression (should be ~1.0 for perfect calibration)",
                    "Intercept bias (are predictions systematically over/under?)",
                    "Temporal correlation (is recent performance worse than early?)",
                    "Market adaptation (are closing lines incorporating our edges?)",
                ],
                "pass_criteria": "Slope 0.90-1.10; No significant split-sample drift; CLV stable",
                "fail_criteria": "Slope <0.80 or >1.20; Significant degradation; CLV trending to zero",
            },
            "Entries 101-200 (Days 33-67)": {
                "name": "Formal Validation",
                "checks": [
                    "Prospective registry lock (freeze all decisions made pre-entry-101)",
                    "Long-term calibration (does Brier still hold on new data?)",
                    "Seasonal effects (did summer→fall change market dynamics?)",
                    "Volatility analysis (stable EDPH or high variance?)",
                    "Real-world constraints (can we actually execute at this rate?)",
                ],
                "pass_criteria": "Brier maintained; EDPH_q20 > $2/hour; no hidden biases",
                "fail_criteria": "Model degrades; EDPH collapses; systematic prediction errors",
            }
        ]
        
        for stage_name, stage_data in metrics.items():
            logger.info(f"\n{stage_name}")
            logger.info(f"  Goal: {stage_data['name']}")
            logger.info(f"  Checks:")
            for check in stage_data['checks']:
                logger.info(f"    • {check}")
            logger.info(f"  ✓ Pass if: {stage_data['pass_criteria']}")
            logger.info(f"  ✗ Fail if: {stage_data['fail_criteria']}")

def main():
    logger.info("\n\n")
    logger.info("╔" + "="*78 + "╗")
    logger.info("║" + "CALIBRATION TIMELINE & STATISTICAL POWER ANALYSIS".center(78) + "║")
    logger.info("║" + "v9.0 DFS Engine - Time to Profitability Validation".center(78) + "║")
    logger.info("╚" + "="*78 + "╝")
    
    analyzer = CalibrationTimeline()
    
    # Entry velocity analysis
    scenarios = analyzer.calculate_entry_velocity()
    
    # Timeline calculation
    timelines = analyzer.calculate_timelines(scenarios)
    
    # Critical path
    milestones = analyzer.calculate_critical_path()
    
    # Risk gates
    gates = analyzer.calculate_risks_and_gates()
    
    # Summary
    analyzer.summary_table(scenarios, timelines)
    
    # Deep dive
    analyzer.detailed_breakdown()
    
    # Final recommendation
    logger.info("\n" + "="*80)
    logger.info("RECOMMENDATION")
    logger.info("="*80)
    
    logger.info("\n✅ MOST LIKELY SCENARIO: Moderate (MLB + WNBA, 6 entries/day)")
    logger.info("  • Realistic: covers 2 sports, ~20% approval rate")
    logger.info("  • Timeline: 50 entries in ~8 days, 200 entries in ~33 days")
    logger.info("  • Checkpoint: Basic validation by end of week (Aug 26)")
    logger.info("  • Checkpoint: Calibration ready by Sept 5")
    logger.info("  • Checkpoint: Formal validation by Sept 21")
    
    logger.info("\n⚠️  CRITICAL ASSUMPTION")
    logger.info("  The timeline assumes consistent entry flow.")
    logger.info("  REALITY: Some days will have 0 approved entries (weak market edge)")
    logger.info("  REALITY: Some days will have 10+ entries (hot markets)")
    logger.info("  → Actual timeline will be +/- 30% from estimate")
    
    logger.info("\n🎯 DECISION POINT: Day 7 (Aug 26)")
    logger.info("  At 20 entries, we'll know:")
    logger.info("    1. Is EDPH positive or negative?")
    logger.info("    2. Are we beating closing lines (CLV positive)?")
    logger.info("    3. Should we CONTINUE, PIVOT, or HALT?")
    logger.info("  → After this point, commitment becomes clearer")
    
    logger.info("\n" + "="*80 + "\n")

if __name__ == "__main__":
    main()
