# Unified Dual-Core DFS Handicapping Engine v9.0

**Architecture Quality: RESEARCH-AUDITED | IMPLEMENTATION-READY**  
**Profit Engine Status: UNVALIDATED**

A two-stage sports forecasting and DFS product validation engine built to the v9.0 specification.

## Core Architecture

- **Stage 1 (Core A):** Sport-specific structural simulation and slate shortlisting
- **Stage 2A (Blind Challenge):** Independent expert handicapper validation
- **Stage 2B (Product Validator):** Exact DFS product economics and execution gate
- **Portfolio Engine:** Scenario-level joint optimization and sizing

## Current Configuration

- **Sports:** MLB, WNBA
- **Date:** August 19, 2026
- **Platforms:** DraftKings Pick6, ParlayPlay, Chalkboard
- **Data Source:** Parlay API
- **Bankroll:** $1,000

## Quick Start

```bash
pip install -r requirements.txt
export PARLAY_API_KEY=14559e0db9853f9d4ac8211f25d042b0
python main.py
```

## Project Structure

```
dfs-handicap-engine/
├── main.py                          # Entry point - full pipeline
├── requirements.txt                 # Python dependencies
├── config.yaml                      # API keys and configuration
├── src/
│   ├── stage1_core_a.py            # Structural simulation engine
│   ├── stage2_blind_challenge.py    # Independent handicapper
│   ├── stage2_product_validator.py  # DFS product pricing
│   ├── portfolio_optimizer.py       # Entry construction and sizing
│   ├── models/
│   │   ├── mlb_simulator.py         # Pitcher x Batter x Park model
│   │   └── wnba_simulator.py        # WNBA lineup x minutes model
│   ├── platforms/
│   │   ├── draftkings_pick6.py      # DraftKings Pick6 adapter
│   │   ├── parlayplay.py            # ParlayPlay adapter
│   │   └── chalkboard.py            # Chalkboard adapter
│   ├── data/
│   │   ├── parlay_api.py            # Parlay API client
│   │   ├── point_in_time.py         # Point-in-time data capture
│   │   └── sources.py               # Data lineage and verification
│   ├── pricing/
│   │   ├── devig.py                 # Devigging (multiplicative, power)
│   │   ├── threshold_curves.py      # Monotonic threshold interpolation
│   │   └── reference.py             # Multi-book consensus building
│   ├── validation/
│   │   ├── calibration.py           # Brier, log loss, CRPS, PIT
│   │   ├── settlement_verify.py     # Settlement identity checks
│   │   └── drift_monitor.py         # Drift and kill-switch detection
│   └── audit/
│       ├── ledger.py                # Append-only decision log
│       └── reporting.py             # User-facing output and audit counts
├── data/
│   ├── mlb_lineups_08_19.json       # Captured lineups
│   ├── parlay_odds_snapshot.json    # Point-in-time odds capture
│   └── dfs_product_state.json       # DFS app state (Pick6, ParlayPlay, Chalkboard)
└── output/
    └── final_recommendation.json    # FINAL T1/T2/CONDITIONAL + entries
```

## Execution Flow

1. **Capture Point-in-Time State** → odds, lineups, injuries, product rules
2. **Stage 1:** Full-slate structural simulation (sport-specific models)
3. **Handoff Freeze:** Immutable snapshot before Stage 2 sees economics
4. **Stage 2A:** Blind independent challenge
5. **Reconcile:** Fused probability with shared-error covariance
6. **Stage 2B:** Exact DFS product validation
7. **No Promotion:** Final tier cannot exceed Stage 1 tier
8. **Entry Construction:** Build feasible combinations from approved legs
9. **Portfolio Optimization:** Scenario-level joint sizing under Kelly + constraints
10. **Output:** FINAL T1/T2/CONDITIONAL legs + recommended entries

## Key Rules

- **Honesty First:** Never invent odds, lines, injuries, or model performance
- **Point-in-Time Integrity:** Freeze forecasts before seeing target-product economics
- **Stage Independence:** No backward leakage from product price to sporting forecast
- **No Promotion Doctrine:** Stage 2 confirms, downgrades, conditions, or vetoes; never promotes
- **Blind Challenger:** Core B sees no Core A direction/tier/probability until after freeze
- **Shared Error Explicit:** Model agreement is not independence; covariance is mandatory

## Validation & Calibration

- Brier Score, Log Loss, CRPS, Quantile Loss
- Randomized PIT for discrete outcomes
- Calibration intercept/slope and reliability buckets
- Edge monotonicity and realized ROI tracking
- Drift monitoring and auto-halt triggers

## Falsification Criteria

The model succeeds by concluding when there is no edge:
- ❌ Coverage below preregistered k_exec / q_feasible thresholds
- ❌ Probability CLV indistinguishable from zero
- ❌ Calibration non-monotonic or badly overconfident
- ❌ Execution/capacity insufficient
- ❌ Realized EDPH lower bound nonpositive after costs

---

**Version:** August 2026 | **Status:** Production Ready | **Last Updated:** 2026-08-19