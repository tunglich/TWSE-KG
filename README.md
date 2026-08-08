# TWSE-KG

[![CI](https://github.com/tunglich/TWSE-KG/actions/workflows/verify.yml/badge.svg)](https://github.com/tunglich/TWSE-KG/actions/workflows/verify.yml)

A Proprietary Database and Knowledge Graph for Financial News Analysis and Scoring.

## Overview

This repository contains the experimental code and data for reproducing the results in the ICAIF 2026 paper:
**"Cross-Market Knowledge Graph Propagation for Taiwan Stock Supply Chain Sentiment Scoring"**.

The system uses a two-tier sentiment scoring architecture:
- **Tier-1 (Market-Level):** Cross-market (TW+US) aggregate nowcast/forecast
- **Tier-2 (Firm-Level):** Knowledge-graph-propagated firm-specific sentiment with typed edges, exposure weights, and two-hop propagation

## Web Application

The following screenshots illustrate the anonymised web application built on top of this pipeline.
All pages are publicly accessible without login and contain no author-identifying information.

<table>
  <tr>
    <td align="center" width="50%">
      <img src="docs/screenshots/screenshot_home.png" alt="Home" width="100%"/>
      <br/>
      <sub><b>Fig. A.</b> Home page — full-text company search across 576 TWSE-listed companies with supply-chain statistics summary.</sub>
    </td>
    <td align="center" width="50%">
      <img src="docs/screenshots/screenshot_analysis.png" alt="Analysis" width="100%"/>
      <br/>
      <sub><b>Fig. B.</b> Supply Chain Analysis (TSMC, 2330) — downstream customer revenue-share bar chart and ranked customer table.</sub>
    </td>
  </tr>
  <tr>
    <td align="center" width="50%">
      <img src="docs/screenshots/screenshot_kg.png" alt="Knowledge Graph" width="100%"/>
      <br/>
      <sub><b>Fig. C.</b> Supply Chain Knowledge Graph — interactive force-directed graph with 2-hop propagation (107 nodes, 120 edges for TSMC).</sub>
    </td>
    <td align="center" width="50%">
      <img src="docs/screenshots/screenshot_news_sentiment.png" alt="News Sentiment" width="100%"/>
      <br/>
      <sub><b>Fig. D.</b> News Sentiment Analysis — daily Tier-2 sentiment score overlaid on OHLCV K-line chart (TSMC, 2330, 1-year window).</sub>
    </td>
  </tr>
  <tr>
    <td align="center" colspan="2">
      <img src="docs/screenshots/screenshot_strategy.png" alt="Strategy" width="50%"/>
      <br/>
      <sub><b>Fig. E.</b> Long-Short Sentiment Backtest — configurable quintile-based long-short strategy with commission, slippage, and date-range controls.</sub>
    </td>
  </tr>
</table>

## Pipeline

![Pipeline](docs/pipeline_ieee.png)

For the complete mathematical specification (Equations 1–9, parameter table,
notation summary), see [`docs/methodology.md`](docs/methodology.md).

## Repository Structure

```
TWSE-KG/
├── README.md
├── LICENSE                     # Proprietary license
├── Makefile                    # Pipeline orchestration (make all / verify / smoke)
├── requirements.txt            # Python dependencies
├── smoke_test.py               # Quick sanity check (< 5s)
├── run_experiments.py          # Legacy reproduction script (still works)
├── .github/workflows/
│   └── verify.yml              # CI: auto-verify against paper anchors
├── lib/                        # Reusable library modules
│   ├── anchors.py              #   Paper anchor constants (single source of truth)
│   ├── data.py                  #   Data loading helpers (xlsx accessors)
│   └── metrics.py               #   Verification helpers
├── src/                        # Pipeline stage scripts
│   ├── stage1_market_level.py  #   Tier-1 nowcast/forecast (Table 2)
│   ├── stage2_firm_level.py    #   Tier-2 KG propagation (Tables 3 & 4)
│   ├── stage3_ablation.py      #   Shuffled-edge control ablation (§5)
│   ├── stage4_backtest.py      #   Cost-adjusted backtest (Table 6)
│   └── stage5_50stock.py       #   50-stock F1 gain & coverage (§5)
├── scripts/                    # Utility scripts
│   ├── export_xlsx.py          #   Regenerate Sentiment_score_all.xlsx
│   └── run_ablation_kit.py     #   Run ablation kit selftests
├── data/
│   └── Sentiment_score_all.xlsx  # All experimental data (7 sheets)
├── docs/
│   └── data_schema.md          # Data dictionary for xlsx sheets
└── exp/                        # Ablation kit (shuffled-edge control)
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

# Quick smoke test (< 5 seconds)
python smoke_test.py

# Run full pipeline (all 5 stages)
make all

# Or run individual stages
python src/stage1_market_level.py
python src/stage2_firm_level.py
python src/stage3_ablation.py
python src/stage4_backtest.py
python src/stage5_50stock.py

# Verify all numbers against paper anchors
make verify

# Regenerate the xlsx data file
make data

# Run ablation kit selftests
make ablation
```

## Data Description (Sentiment_score_all.xlsx)

| Sheet | Content | Run Script |
|-------|---------|------------|
| Table3_Prediction | Tier-2 same-day F1 for Top-5 companies + Top-50 average | `python src/stage5_50stock.py` |
| Table4_Coverage | Coverage expansion statistics (raw → post-filter → post-KG) | `python src/stage5_50stock.py` |
| Table6_Backtest | Cost-adjusted backtest results (KG vs LLM-Direct vs TAIEX) | `python src/stage4_backtest.py` |
| Ablation_Ladder | 7-rung shuffled-edge control ablation | `python src/stage3_ablation.py` |
| 50_Stock_F1_Coverage | 50-stock individual F1 gain and coverage multiplier | `python src/stage5_50stock.py` |
| Table2_MarketLevel | Tier-1 market-level nowcast/forecast | `python src/stage1_market_level.py` |
| Pipeline_Params | Fixed ex-ante pipeline parameters | `python src/compute_from_csv.py` |

See [docs/data_schema.md](docs/data_schema.md) for full column descriptions.

## Key Results

- **F1 lift:** 0.5309 (Direct) → 0.6456 (KG) = +0.1147 (11.5 points)
- **Coverage:** 2.97× overall, 1.27× for Top-50, 4.45× for others
- **Backtest:** KG long-short 14.6% annualized return, Sharpe 1.12
- **Ablation:** KG clears both null bands (A1: 11.4σ, A2: 8.0σ), verdict = PASS
- **Coverage-only hypothesis rejected:** R²(gain, coverage) ≈ 0

## License

Proprietary. All rights reserved.
