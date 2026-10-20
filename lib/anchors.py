"""
Paper anchor constants — ground-truth values from the ICAIF 2026 paper.

Every number the pipeline reproduces or verifies against lives here so that
stage scripts, the smoke test, and CI all reference a single source of truth.

Two sets of values are maintained in parallel:

PAPER values  — reported in the final ICAIF 2026 paper (Chen & Jang, "Cross-Market Sentiment
                 Propagation via Firm-Level Knowledge Graphs", doi:10.1145/3858063.3858704):
                 held-out window 2024-01-02 to 2026-09-30 (2024–2026Q3), 1,179-firm universe,
                 corpus January 2015 – September 2026.  Updated 2026-10-20 from the camera-ready
                 version; the earlier submitted-version values (e.g. Top-50 F1(KG) 0.6456,
                 576 firms, test end 2025-06-30) are kept in git history.

COMPUTED values — reproduced by running compute_from_csv.py on the pre-scored CSV cache
                  (same raw data, but with two known differences from the paper run):

  Difference 1 — Test window:
    The repo default test window now matches the final paper (2024-01-02 to 2026-09-30).
    Computed numbers on an older CSV cache that ends earlier will cover a shorter window;
    override with --test-start / --test-end to compare a specific period.

  Difference 2 — Top-54 vs full-universe for Tier-1 market signal:
    The repo default uses Top-54 stocks for the market-level mean, whereas the paper
    uses the full scoring universe. To reproduce paper T2: run compute_from_csv.py --full-universe.

  T3 Top-50 F1: the repo uses the balanced-class threshold (score > 50); any gap to the
    paper's operating point is a threshold-selection difference, not a data difference.

All PAPER values are taken directly from the final (camera-ready) paper tables.
All COMPUTED values are produced by running the code in this repo on the
pre-scored CSV cache (data/csv/). Neither set is fabricated or simulated.
"""

# ─── Table 2: Tier-1 Market-Level Nowcast/Forecast ──────────────────────────
# Paper values (from ICAIF 2026 Table 2)
TABLE2 = {
    "same_day": {"f1": 0.7357, "acc": 68.13, "auc": 0.7170},
    "next_day": {"f1": 0.6064, "acc": 60.64},
}
# Label-only references (paper Table 3 Panel C): always-up and training-majority baselines
TABLE2_LABEL_BASELINES = {
    "tier1": {"up": 371, "not_up": 286, "always_up_f1": 0.7218, "always_up_acc": 56.47},
    "tier2_top50": {"up": 14_338, "not_up": 18_849, "always_up_f1": 0.6018, "always_up_acc": 43.20,
                    "majority_acc": 56.80},
}

# Computed values (from compute_from_csv.py on raw CSV data)
TABLE2_COMPUTED = {
    "same_day": {"f1": 0.7738, "acc": 68.35, "auc": 0.7794},
}

# ─── Table 3: Tier-2 Same-Day F1 (Top-5 + Top-50 average) ─────────────────────
# Paper values (from ICAIF 2026 Table 3)
TABLE3 = {
    "2330": {"name": "TSMC",       "f1_kg": 0.7281, "f1_direct": 0.6360, "f1_wide": 0.5140, "acc": 72.2, "auc": 0.7790, "a": 0.125, "b": 0.375, "c": 0.500},
    "3017": {"name": "AVC",        "f1_kg": 0.7219, "f1_direct": 0.5772, "f1_wide": 0.5158, "acc": 71.4, "auc": 0.7186, "a": 0.100, "b": 0.100, "c": 0.800},
    "2345": {"name": "Accton",     "f1_kg": 0.7184, "f1_direct": 0.5630, "f1_wide": 0.5100, "acc": 73.0, "auc": 0.7315, "a": 0.400, "b": 0.000, "c": 0.600},
    "3711": {"name": "ASE Tech",   "f1_kg": 0.6918, "f1_direct": 0.5875, "f1_wide": 0.5072, "acc": 69.9, "auc": 0.7380, "a": 0.250, "b": 0.750, "c": 0.000},
    "6515": {"name": "Opto.Comm.", "f1_kg": 0.6612, "f1_direct": 0.5381, "f1_wide": 0.5102, "acc": 65.2, "auc": 0.6745, "a": 0.333, "b": 0.667, "c": 0.000},
    "top50_avg": {"f1_kg": 0.6524, "f1_direct": 0.5348, "f1_wide": 0.5053, "acc": 65.1, "auc": 0.6590},
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
    # Paper §3.5: raw Taiwan articles Jan 2015 – Sep 2026 → post-filter → KG-propagated firm-level impact records
    "raw_articles": 308_994,
    "post_filter":  125_714,
    "post_kg":      383_434,
    "post_kg_share_top50":  19.3,   # % of post-KG records on Top-50 constituents
    "post_kg_share_others": 80.7,
    "coverage_mult_overall": 3.0501,   # 383,434 / 125,714 (paper: "3.05x")
    # The final paper does not break direct vs KG records down by Top-50 / others; these stay None.
    "top50_direct":  None,
    "top50_kg":      None,
    "others_direct": None,
    "others_kg":     None,
    "coverage_mult_top50":   None,
    "coverage_mult_others":  None,
}

# ─── Table 6: Cost-Adjusted Backtest ─────────────────────────────────────────
# Paper values (from ICAIF 2026 Table 6)
TABLE6 = {
    "kg_ls":   {"ann_ret": 15.4, "sharpe": 1.18, "max_dd":  9.4, "turnover": 19},
    "kg_long": {"ann_ret": None, "sharpe": None, "max_dd": 12.8, "turnover": 11, "excess": 7.2, "ir": 0.76},
    "llm_ls":  {"ann_ret":  6.2, "sharpe": 0.49, "max_dd": 14.5, "turnover": 21},
    "taiex":   {"ann_ret": 34.0, "sharpe": 1.38, "max_dd": 27.7, "turnover":  0},
}
# Regression of daily long-short excess returns on TAIEX TR (paper §4.6)
TABLE6_MARKET_REGRESSION = {"beta_mkt": 0.08, "alpha_ann_pct": 11.4, "t_alpha": 1.3}

# Computed values (from compute_from_csv.py)
TABLE6_COMPUTED = {
    "kg_ls": {"ann_ret": 36.5, "sharpe": 2.16, "max_dd": 9.2},
}

# ─── §5: Ablation Ladder (shuffled-edge control) ─────────────────────────────
ABLATION = {
    "MarketWide": 0.5053,
    "Direct":     0.5348,
    "A1":         0.6138,
    "A2":         0.6175,
    "A3":         0.6060,   # submitted-version rung; not reported in the final paper
    "A4":         0.6296,   # submitted-version rung; not reported in the final paper
    "KG":         0.6524,
}

# Shuffle SDs (from R=20 replicates)
SHUFFLE_SD = {"A1": 0.0028, "A2": 0.0035, "A3": 0.0041}   # final paper: five randomized runs per design (A1, A2)

# ─── Pipeline parameters (fixed ex-ante) ─────────────────────────────────────
PIPELINE_PARAMS = {
    "corpus_window":     "2015-01-01 ~ 2026-09-30",
    "n_firms":           1179,
    "n_sectors":         33,
    "kg_edges":          40237,   # de-duplicated edges in the 2026Q3 KG snapshot (paper Table 1(b))
    "kg_nodes":          8127,
    "mean_degree":       None,    # submitted version reported 3.40 on a 979-edge Taiwan-only graph; not reported in the final paper
    "n_lags":            5,
    "threshold_default": 50,
    "commissions":       {"buy_pct": 0.10, "sell_pct": 0.34},
    "test_window":       "2024-01-02 ~ 2026-09-30",
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
TOP5_TICKERS = ["2330", "3017", "2345", "3711", "6515"]   # paper Table 3 Panel B order (by KG F1)
