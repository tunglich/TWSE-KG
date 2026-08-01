# TWSE-KG

[![Verify Paper Anchors](https://github.com/tunglich/TWSE-KG/actions/workflows/verify.yml/badge.svg)](https://github.com/tunglich/TWSE-KG/actions/workflows/verify.yml)

A Proprietary Database and Knowledge Graph for Financial News Analysis and Scoring.

## Overview

This repository contains the experimental code and data for reproducing the results in the ICAIF 2026 paper:
**"Cross-Market Knowledge Graph Propagation for Taiwan Stock Supply Chain Sentiment Scoring"**.

The system uses a two-tier sentiment scoring architecture:
- **Tier-1 (Market-Level):** Cross-market (TW+US) aggregate nowcast/forecast
- **Tier-2 (Firm-Level):** Knowledge-graph-propagated firm-specific sentiment with typed edges, exposure weights, and two-hop propagation

## Repository Structure

```
TWSE-KG/
├── README.md
├── LICENSE                     # Proprietary license
├── requirements.txt            # Python dependencies
├── run_experiments.py          # Reproduction script for all paper tables
├── .github/workflows/
│   └── verify.yml              # CI: auto-verify against paper anchors
├── data/
│   └── Sentiment_score_all.xlsx  # All experimental data (7 sheets)
└── sim/                        # Ablation kit (shuffled-edge control)
    ├── ABLATION_SPEC.md
    ├── RUNBOOK_SHUFFLED_EDGE.md
    ├── shuffle_control.py
    ├── ablation_design.py
    ├── collect_ablation.py
    └── ...
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run all experiments
python run_experiments.py

# Run specific table
python run_experiments.py --table 3

# Verify against paper anchors
python run_experiments.py --verify

# Run ablation kit selftest
cd sim && python shuffle_control.py --selftest
```

## Data Description (Sentiment_score_all.xlsx)

| Sheet | Content |
|-------|---------|
| Table3_Prediction | Tier-2 same-day F1 for Top-5 companies + Top-50 average |
| Table4_Coverage | Coverage expansion statistics (raw → post-filter → post-KG) |
| Table6_Backtest | Cost-adjusted backtest results (KG vs LLM-Direct vs TAIEX) |
| Ablation_Ladder | 7-rung shuffled-edge control ablation |
| 50_Stock_F1_Coverage | 50-stock individual F1 gain and coverage multiplier |
| Table2_MarketLevel | Tier-1 market-level nowcast/forecast |
| Pipeline_Params | Fixed ex-ante pipeline parameters |

## Key Results

- **F1 lift:** 0.5309 (Direct) → 0.6456 (KG) = +0.1147 (11.5 points)
- **Coverage:** 2.97× overall, 1.27× for Top-50, 4.45× for others
- **Backtest:** KG long-short 14.6% annualized return, Sharpe 1.12
- **Ablation:** KG clears both null bands (A1: 11.4σ, A2: 8.0σ), verdict = PASS
- **Coverage-only hypothesis rejected:** R²(gain, coverage) ≈ 0

## License

Proprietary. All rights reserved.
