"""
Paper anchor constants — ground-truth values from the ICAIF 2026 paper.

Every number the pipeline reproduces or verifies against lives here so that
stage scripts, the smoke test, and CI all reference a single source of truth.

Two sets of values are maintained in parallel:

PAPER values  — reported in the ICAIF 2026 paper (test window: 2024-01-02 to 2025-06-30,
                 full 576-company universe, full LLM-scored corpus).

COMPUTED values — reproduced by running compute_from_csv.py on the pre-scored CSV cache
                  (same raw data, but with two known differences from the paper run):

  Difference 1 — Extended test window:
    The repo default extends to 2026-03-31 (latest available data), adding ~9 months
    of 2025–2026 data not in the paper. The Taiwan market was strongly bullish in this
    period, which raises backtest returns (T6: 36.5% vs paper 14.6%) and Sharpe (2.16
    vs 1.12). To reproduce paper T6 numbers: --test-end 2025-06-30.

  Difference 2 — Top-54 vs full-universe for Tier-1 market signal:
    The repo default uses Top-54 stocks for the market-level mean, whereas the paper
    uses all 576. This raises T2 F1 (0.7738 vs 0.7357). To reproduce paper T2:
    run compute_from_csv.py --full-universe.

  T3 Top-50 F1 (0.6142 vs paper 0.6456): The paper reports the best-performing
    operating point; the repo uses the balanced-class threshold (score > 50).
    The gap is a threshold-selection difference, not a data difference.

All PAPER values are taken directly from the submitted manuscript tables.
All COMPUTED values are produced by running the code in this repo on the
pre-scored CSV cache (data/csv/). Neither set is fabricated or simulated.
"""

# ─── Table 2: Tier-1 Market-Level Nowcast/Forecast ──────────────────────────
# Paper values (from ICAIF 2026 Table 2)
TABLE2 = {
    "same_day": {"f1": 0.7357, "acc": 68.13, "auc": 0.7170},
    "next_day": {"f1": 0.6064, "acc": 60.64},
}

# Computed values (from compute_from_csv.py on raw CSV data)
TABLE2_COMPUTED = {
    "same_day": {"f1": 0.7738, "acc": 68.35, "auc": 0.7794},
}

# ─── Table 3: Tier-2 Same-Day F1 (Top-5 + Top-50 average) ─────────────────────
# Paper values (from ICAIF 2026 Table 3)
TABLE3 = {
    "2330": {"name": "TSMC",       "f1_kg": 0.7223, "f1_direct": 0.6327, "f1_wide": 0.5124, "acc": 71.8, "auc": 0.7730},
    "2345": {"name": "Accton",     "f1_kg": 0.7111, "f1_direct": 0.5592, "f1_wide": 0.5087, "acc": 72.4, "auc": 0.7241},
    "3017": {"name": "AVC",        "f1_kg": 0.7157, "f1_direct": 0.5733, "f1_wide": 0.5142, "acc": 70.9, "auc": 0.7118},
    "3711": {"name": "ASE Tech",   "f1_kg": 0.6860, "f1_direct": 0.5843, "f1_wide": 0.5063, "acc": 69.4, "auc": 0.7323},
    "6515": {"name": "Opto.Comm.", "f1_kg": 0.6557, "f1_direct": 0.5356, "f1_wide": 0.5091, "acc": 64.7, "auc": 0.6691},
    "top50_avg": {"f1_kg": 0.6456, "f1_direct": 0.5309, "f1_wide": 0.5040, "acc": 64.6, "auc": 0.6534},
}

# Computed values (from compute_from_csv.py)
TABLE3_COMPUTED = {
    "2330": {"f1": 0.6607, "acc": 50.65, "auc": 0.7088},
    "2345": {"f1": 0.6711, "acc": 53.83, "auc": 0.5790},
    "3017": {"f1": 0.6711, "acc": 53.27, "auc": 0.5583},
    "3711": {"f1": 0.6611, "acc": 54.39, "auc": 0.6273},
    "6515": {"f1": 0.6819, "acc": 58.32, "auc": 0.6058},
    "top50_avg": {"f1": 0.6142, "acc": 49.17, "auc": 0.5854},
}

# ─── Table 4: Coverage Expansion Statistics ──────────────────────────────────
TABLE4 = {
    "raw_articles": 284_925,
    "post_filter":  118_662,
    "post_kg":      352_287,
    "top50_direct":  55_385,
    "top50_kg":      70_590,
    "others_direct": 63_277,
    "others_kg":    281_697,
    "coverage_mult_top50":   1.2745,
    "coverage_mult_others":  4.4517,
    "coverage_mult_overall": 2.9688,
}

# ─── Table 6: Cost-Adjusted Backtest ─────────────────────────────────────────
# Paper values (from ICAIF 2026 Table 6)
TABLE6 = {
    "kg_ls":   {"ann_ret": 14.6, "sharpe": 1.12, "max_dd":  9.6, "turnover": 19},
    "kg_long": {"ann_ret": 21.4, "sharpe": 0.71, "max_dd": 13.1, "turnover": 11, "excess": 6.8, "ir": 0.71},
    "llm_ls":  {"ann_ret":  5.9, "sharpe": 0.47, "max_dd": 14.8, "turnover": 21},
    "taiex":   {"ann_ret": 34.0, "sharpe": 1.38, "max_dd": 27.7, "turnover":  0},
}

# Computed values (from compute_from_csv.py)
TABLE6_COMPUTED = {
    "kg_ls": {"ann_ret": 36.5, "sharpe": 2.16, "max_dd": 9.2},
}

# ─── §5: Ablation Ladder (shuffled-edge control) ─────────────────────────────
ABLATION = {
    "MarketWide": 0.5040,
    "Direct":     0.5309,
    "A1":         0.6138,
    "A2":         0.6175,
    "A3":         0.6060,
    "A4":         0.6296,
    "KG":         0.6456,
}

# Shuffle SDs (from R=20 replicates)
SHUFFLE_SD = {"A1": 0.0028, "A2": 0.0035, "A3": 0.0041}

# ─── Pipeline parameters (fixed ex-ante) ─────────────────────────────────────
PIPELINE_PARAMS = {
    "corpus_window":     "2023-01-01 ~ 2024-06-30",
    "n_firms":           576,
    "n_sectors":         33,
    "kg_edges":          979,
    "mean_degree":       3.40,
    "n_lags":            5,
    "threshold_default": 50,
    "commissions":       {"buy_pct": 0.10, "sell_pct": 0.34},
    "test_window":       "2024-01-02 ~ 2026-03-31",
    # Tier-1 weights
    "beta":              0.25,
    # Tier-2 pool weights
    "tier2_a":           0.18,
    "tier2_b":           0.52,
    "tier2_c":           0.30,
    # KG propagation
    "gamma":             0.5,
    "path_cap":          50,
    # Stale-news discount
    "lambda_s":          0.35,
    "lookback":          15,
    # Time-decay
    "lambda_t":          0.46,
    "decay_window":      5,
    # SprintScore
    "w_event":           0.40,
    # Backtest
    "quintile_n":        10,
    "commission_pct":    0.1425,
    "sales_tax_pct":     0.30,
    "borrow_fee_pct":    2.0,
}

# Convenience: the five tickers with individual Table-3 entries
TOP5_TICKERS = ["2330", "2345", "3017", "3711", "6515"]
