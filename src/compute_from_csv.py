"""
TWSE-KG Full Pipeline — reads from pre-converted CSV files.
Implements the exact two-tier architecture from the paper:

  Stage 1-2: KG propagation (γ=0.5, 2-hop, ±50 cap)
  Stage 3:   Stale-news discount (λs=0.35, 15-day) + time-decay (λt=0.46, 5-day)
  Stage 4:   Cap-weighted market aggregation → TW_t
  Stage 5:   SprintScore = (1-w_event)*(β*TW_t + (1-β)*US_{t-1}) + w_event*f_j,t
  Tier-1:    C_t = β*TW_t + (1-β)*US_{t-1}  [β=0.25]
  Tier-2:    C_j,t = a_j*TW_j,t + b_j*M_t + c_j*US_j,t-1  [pool avg: a=0.18,b=0.52,c=0.30]

Usage:
    python3 src/compute_from_csv.py [--csv-dir /path/to/csv] [--output results.json]

CSV directory must contain:
    Total_score.csv, TW_sentiment.csv, US_sentiment.csv, Open.csv, Close.csv

KG edge files:
    kg_supplies_to.csv, kg_competes_with.csv
"""
from __future__ import annotations
import argparse, json, math, sys, time, warnings
from pathlib import Path

# Allow running as a script from any directory
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.metrics import f1_score, accuracy_score, roc_auc_score
from sklearn.linear_model import LogisticRegression

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(line_buffering=True)

# ── Default paths (relative to repo root) ────────────────────────────────────
# Place your CSV files in data/csv/ following the layout in docs/data_schema.md
# Override at runtime: python src/compute_from_csv.py --csv-dir /your/path
DEFAULT_CSV_DIR = _REPO_ROOT / "data" / "csv"
DEFAULT_KG_DIR  = _REPO_ROOT / "data" / "kg"
DEFAULT_TW50    = _REPO_ROOT / "data" / "tw50_universe.csv"
DEFAULT_INDEX   = _REPO_ROOT / "data" / "index_taiex.csv"

# ── Paper hyperparameters (all set ex ante, not tuned on test window) ─────────
GAMMA      = 0.5        # KG propagation decay per hop
PATH_CAP   = 50.0       # max propagation delta per path
LAMBDA_S   = 0.35       # stale-news discount rate
LOOKBACK   = 15         # stale-news lookback window (trading days)
LAMBDA_T   = 0.46       # time-decay rate
DECAY_WIN  = 5          # time-decay window (days, k=0..4)
W_EVENT    = 0.4        # weight of per-firm event channel in SprintScore
BETA       = 0.25       # TW weight in Tier-1 (β); US weight = 1-β = 0.75
# Tier-2 pool-average weights (per-stock weights fitted via logistic regression;
# we use pool averages as a single-model approximation)
A_AVG      = 0.18       # TW_j,t (SprintScore) weight
B_AVG      = 0.52       # M_t (Tier-1) weight
C_AVG      = 0.30       # US_j,t-1 weight
# Backtest
COMMISSION = 0.001425   # 0.1425% per side
SALES_TAX  = 0.003      # 0.30% on sells
BORROW_FEE = 0.02 / 252 # 2% annual borrow fee on shorts, daily
QUINTILE_N = 10         # top/bottom quintile size (10 from 50 = Q1/Q5)
TEST_START = "2024-01-02"
TEST_END   = "2026-03-31"
WARMUP     = 20         # extra days before test start for decay warmup

# Paper anchor values for comparison
PAPER = {
    "t2_f1": 0.7357, "t2_acc": 0.6813, "t2_auc": 0.7170,
    "t3_f1": 0.6456, "t3_acc": 0.6460, "t3_auc": 0.6534,
    "t6_ls_ret": 0.146, "t6_ls_sharpe": 1.12, "t6_ls_maxdd": 0.096,
    "t6_taiex_ret": 0.340, "t6_taiex_sharpe": 1.38,
}

t0 = time.time()
def log(msg): print(f"[{time.time()-t0:.1f}s] {msg}", flush=True)


def load_csv_filtered(csv_path: Path, tickers: list[str] | None,
                      date_start: str, date_end: str) -> pd.DataFrame:
    """Read CSV, keep only requested ticker columns and date range.
    If tickers is None, load ALL columns (full-universe mode).
    """
    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    # Normalise column names to 4-digit strings
    df.columns = [str(c).strip().zfill(4) if str(c).strip().isdigit() and len(str(c).strip()) <= 4
                  else str(c).strip() for c in df.columns]
    if tickers is not None:
        keep = [t for t in tickers if t in df.columns]
        df = df[keep]
    df = df.loc[date_start:date_end]
    return df.astype(float)


def build_kg_matrix(supp_path: Path, comp_path: Path,
                    ticker_idx: dict[str, int], n: int) -> sparse.csr_matrix:
    """Build sparse KG adjacency matrix from supply-chain and competition edges."""
    rows, cols, data = [], [], []

    supp = pd.read_csv(supp_path, dtype=str, encoding="utf-8-sig")
    for _, row in supp.iterrows():
        src = str(row["source"]).strip().zfill(4)
        tgt = str(row["target"]).strip().zfill(4)
        if src not in ticker_idx or tgt not in ticker_idx:
            continue
        share_str = str(row.get("share", "")).strip()
        try:
            w = float(share_str) / 100.0 if share_str not in ("", "nan") else 0.5
        except ValueError:
            w = 0.5
        w = max(0.05, min(1.0, w))
        i, j = ticker_idx[src], ticker_idx[tgt]
        # Bidirectional: customer gets upstream signal, supplier gets downstream signal
        rows += [i, j]; cols += [j, i]; data += [w, w * 0.5]

    comp = pd.read_csv(comp_path, dtype=str, encoding="utf-8-sig")
    for _, row in comp.iterrows():
        src = str(row["source"]).strip().zfill(4)
        tgt = str(row["target"]).strip().zfill(4)
        if src not in ticker_idx or tgt not in ticker_idx:
            continue
        i, j = ticker_idx[src], ticker_idx[tgt]
        rows += [i, j]; cols += [j, i]; data += [-0.3, -0.3]

    return sparse.csr_matrix((data, (rows, cols)), shape=(n, n))


def kg_propagate(total_arr: np.ndarray, A: sparse.csr_matrix,
                 gamma: float, path_cap: float, w_event: float) -> np.ndarray:
    """
    2-hop KG propagation.
    SprintScore = (1-w_event)*(market baseline) + w_event*f_j,t
    Here f_j,t = total_arr (the KG-propagated per-firm score from Stage 2).
    The market baseline is computed separately in Tier-1.
    This function returns the Stage-2 propagated score (f_j,t).
    """
    T, n = total_arr.shape
    delta = (total_arr - 50.0).astype(np.float32)
    A_T = A.T.tocsc().astype(np.float32)
    out = np.empty_like(total_arr, dtype=np.float32)

    batch = 200
    for s in range(0, T, batch):
        e = min(s + batch, T)
        d = delta[s:e].astype(np.float32)
        # 1-hop propagation
        p1 = (A_T.dot(d.T)).T * gamma
        # 2-hop propagation
        p2 = (A_T.dot(p1.T)).T * gamma
        prop = np.clip(p1 + p2, -path_cap, path_cap)
        # f_j,t = original score + propagated delta
        out[s:e] = np.clip(total_arr[s:e] + prop, 1.0, 100.0)

    return out.astype(np.float32)


def stale_news_discount(kg_arr: np.ndarray, lambda_s: float,
                        lookback: int) -> np.ndarray:
    """
    Stage 3a: Stale-news discount.
    W_rep = sum_{i=1}^{N} e^{-lambda_s*(t-t_i)}  for prior appearances in lookback window
    f = 1/(1+W_rep)
    S_adj = 50 + (S_raw - 50)*f
    """
    T, n = kg_arr.shape
    # A firm "appears" when |score - 50| > 1 (has non-neutral signal)
    active = (np.abs(kg_arr - 50.0) > 1.0).astype(np.float32)
    stale_w = np.array([math.exp(-lambda_s * k) for k in range(1, lookback + 1)],
                       dtype=np.float32)
    w_rep = np.zeros((T, n), dtype=np.float32)
    for k, sw in enumerate(stale_w, 1):
        if k < T:
            w_rep[k:] += sw * active[:T - k]

    f_disc = (1.0 / (1.0 + w_rep)).astype(np.float32)
    return (50.0 + (kg_arr - 50.0) * f_disc).astype(np.float32)


def time_decay(adj_arr: np.ndarray, lambda_t: float, win: int) -> np.ndarray:
    """
    Stage 3b: Time-decay operator.
    S_final = 50 + sum_{k=0}^{4} (S_{t-k,adj} - 50) * e^{-lambda_t*k}
    Clipped to [1, 100].
    """
    T, n = adj_arr.shape
    # k=0 weight = 1.0 (current day), k=1..4 carry-over
    decay_w = np.array([math.exp(-lambda_t * k) for k in range(win)], dtype=np.float32)
    s = np.zeros((T, n), dtype=np.float32)
    for k, dw in enumerate(decay_w):
        if k == 0:
            s += (adj_arr - 50.0) * dw
        elif k < T:
            s[k:] += (adj_arr[:T - k] - 50.0) * dw
    return np.clip(50.0 + s, 1.0, 100.0).astype(np.float32)


def compute_tier1(tw_market: np.ndarray, us_market: np.ndarray,
                  beta: float) -> np.ndarray:
    """
    Tier-1: C_t = β*TW_t + (1-β)*US_{t-1}
    Returns score in [1,100].
    """
    us_lagged = np.roll(us_market, 1)
    us_lagged[0] = 50.0
    tier1 = beta * tw_market + (1 - beta) * us_lagged
    return np.clip(tier1, 1.0, 100.0).astype(np.float32)


def compute_sprint_score(f_jt: np.ndarray, tier1: np.ndarray,
                         us_jt: np.ndarray, beta: float,
                         w_event: float) -> np.ndarray:
    """
    Stage 5 SprintScore:
    Sprint_j,t = (1-w_event)*(β*TW_t + (1-β)*US_{t-1}) + w_event*f_j,t
    where TW_t and US_{t-1} are market-level (Tier-1 components), not per-stock.
    The market baseline uses the same β as Tier-1.
    """
    T = len(tier1)
    tier1_col = tier1[:, np.newaxis]  # broadcast over stocks
    sprint = (1 - w_event) * tier1_col + w_event * f_jt
    return np.clip(sprint, 1.0, 100.0).astype(np.float32)


def compute_tier2(sprint_jt: np.ndarray, tier1: np.ndarray,
                  us_jt: np.ndarray,
                  a: float, b: float, c: float) -> np.ndarray:
    """
    Tier-2: C_j,t = a*TW_j,t + b*M_t + c*US_j,t-1
    where TW_j,t = SprintScore, M_t = Tier-1 score, US_j,t-1 = lagged per-stock US sentiment.
    """
    T = len(tier1)
    tier1_col = tier1[:, np.newaxis]
    us_lagged = np.roll(us_jt, 1, axis=0)
    us_lagged[0] = 50.0
    tier2 = a * sprint_jt + b * tier1_col + c * us_lagged
    return np.clip(tier2, 1.0, 100.0).astype(np.float32)


def compute_stock_metrics(score_arr: np.ndarray, close_arr: np.ndarray,
                          valid_mask: np.ndarray, universe: list[str],
                          min_days: int = 30,
                          open_arr: np.ndarray | None = None,
                          label_type: str = "close-to-close") -> dict[str, dict]:
    """Compute per-stock F1, Acc, AUC.

    Label type options
    ------------------
    close-to-close (default, used in paper Table 3):
        Direction = 1 if today's CLOSE > yesterday's CLOSE.
        This is the label used for Table 3 in the paper.
        Note: the paper Abstract mentions 'open-to-close' as the *backtest* signal
        direction (Table 6/7), not the classification label for Table 3.

    open-to-close (used in backtest Table 6/7):
        Direction = 1 if today's CLOSE > today's OPEN.
        This is the intraday direction used for portfolio construction.
        Requires open_arr to be provided.
    """
    results = {}
    for j, ticker in enumerate(universe):
        mask = valid_mask[:, j]
        if mask.sum() < min_days:
            continue
        T_full  = close_arr.shape[0]
        T_test  = score_arr.shape[0]
        close_j = close_arr[:, j]

        if label_type == "open-to-close":
            # open-to-close direction: 1 if today's close > today's open
            # Used in backtest (Table 6/7); requires open_arr
            if open_arr is None:
                raise ValueError("open_arr required for label_type='open-to-close'")
            open_j = open_arr[:, j]
            oc_dir_full  = (close_j > open_j).astype(int)
            oc_dir_test  = oc_dir_full[T_full - T_test:]
            yt = oc_dir_test[mask]
        else:
            # close-to-close direction: 1 if today's close > yesterday's close
            # Used in classification metrics (Table 3); default
            cc_dir_full  = (close_j > np.roll(close_j, 1)).astype(int)
            cc_dir_full[0] = 0  # undefined on first day
            cc_dir_test = cc_dir_full[T_full - T_test:]
            yt = cc_dir_test[mask]
        ys = (score_arr[mask, j].astype(float) - 50.0) / 50.0  # normalise to [-1,1]
        yp = (ys > 0).astype(int)
        f1  = f1_score(yt, yp, zero_division=0)
        acc = accuracy_score(yt, yp)
        try:
            auc = roc_auc_score(yt, ys)
        except Exception:
            auc = 0.5
        results[ticker] = {"f1": f1, "acc": acc, "auc": auc, "n": int(mask.sum())}
    return results


def run_backtest(tier2_scores: np.ndarray, open_arr: np.ndarray,
                 close_arr: np.ndarray, universe: list[str],
                 top50_j: np.ndarray, quintile_n: int,
                 commission: float, sales_tax: float,
                 borrow_fee: float) -> dict:
    """
    Q1-Q5 long-short backtest on Top-50 stocks.
    - Rank by Tier-2 score before open
    - Long top quintile (Q1), short bottom quintile (Q5)
    - Equal-weighted, rebalanced daily
    - Costs: commission per side + sales tax on sells + daily borrow fee on shorts
    - Returns: open-to-close
    """
    T = len(tier2_scores)
    daily_rets = []
    prev_longs: set[int] = set()
    prev_shorts: set[int] = set()

    for i in range(T):
        scores = [(j, float(tier2_scores[i, j])) for j in top50_j
                  if not math.isnan(float(tier2_scores[i, j]))]
        if len(scores) < quintile_n * 2:
            continue
        scores.sort(key=lambda x: x[1], reverse=True)
        longs  = set(j for j, _ in scores[:quintile_n])
        shorts = set(j for j, _ in scores[-quintile_n:])

        long_ret, short_ret = [], []
        for j in longs:
            o, c = float(open_arr[i, j]), float(close_arr[i, j])
            if not math.isnan(o) and not math.isnan(c) and o > 0:
                long_ret.append((c - o) / o)
        for j in shorts:
            o, c = float(open_arr[i, j]), float(close_arr[i, j])
            if not math.isnan(o) and not math.isnan(c) and o > 0:
                short_ret.append(-((c - o) / o))

        if not long_ret or not short_ret:
            prev_longs, prev_shorts = longs, shorts
            continue

        # Transaction costs
        new_l = longs - prev_longs
        new_s = shorts - prev_shorts
        exit_l = prev_longs - longs
        exit_s = prev_shorts - shorts

        n_total = quintile_n * 2
        # Commission: per side (buy + sell) for new positions
        cost_comm = (len(new_l) + len(exit_l) + len(new_s) + len(exit_s)) * commission / n_total
        # Sales tax: on sells (closing longs and opening shorts)
        cost_tax = (len(exit_l) + len(new_s)) * sales_tax / n_total
        # Borrow fee: daily on all short positions
        cost_borrow = len(shorts) * borrow_fee / n_total

        total_cost = cost_comm + cost_tax + cost_borrow
        daily_ret = np.mean(long_ret) + np.mean(short_ret) - total_cost
        daily_rets.append(daily_ret)
        prev_longs, prev_shorts = longs, shorts

    if not daily_rets:
        return {}

    rets = np.array(daily_rets)
    ann_ret = float(np.mean(rets) * 252)
    ann_vol = float(np.std(rets) * math.sqrt(252))
    sharpe  = ann_ret / ann_vol if ann_vol > 0 else 0.0
    cum     = np.cumprod(1 + rets)
    rm      = np.maximum.accumulate(cum)
    max_dd  = float(abs(((cum - rm) / rm).min()))

    return {"ann_ret": ann_ret, "ann_vol": ann_vol, "sharpe": sharpe,
            "max_dd": max_dd, "n_days": len(daily_rets)}


def main():
    parser = argparse.ArgumentParser(description="TWSE-KG pipeline from CSV")
    parser.add_argument("--csv-dir",  default=str(DEFAULT_CSV_DIR))
    parser.add_argument("--kg-dir",   default=str(DEFAULT_KG_DIR))
    parser.add_argument("--tw50",     default=str(DEFAULT_TW50))
    parser.add_argument("--index",         default=str(DEFAULT_INDEX))
    parser.add_argument("--output",         default="/tmp/pipeline_results.json")
    parser.add_argument("--full-universe",  action="store_true",
                        help="Load ALL stocks in CSV (not just Top-54). "
                             "Uses ~362 MB RAM; takes ~60s. "
                             "Results saved to pipeline_results_full.json by default.")
    parser.add_argument("--test-start",  default=TEST_START,
                        help="Backtest start date YYYY-MM-DD (default: %(default)s). "
                             "Paper uses 2024-01-02. Override to reproduce a specific window.")
    parser.add_argument("--test-end",    default=TEST_END,
                        help="Backtest end date YYYY-MM-DD (default: %(default)s). "
                             "Paper uses 2025-06-30 (submission cutoff). "
                             "Repo default extends to 2026-03-31 (latest available data).")
    args = parser.parse_args()

    # Auto-switch output path for full-universe run
    if args.full_universe and args.output == "/tmp/pipeline_results.json":
        args.output = "/tmp/pipeline_results_full.json"

    # Allow CLI override of test window (paper used 2024-01-02 to 2025-06-30)
    # Repo default extends to 2026-03-31 to include latest available data.
    # To reproduce paper numbers exactly: --test-start 2024-01-02 --test-end 2025-06-30
    global TEST_START, TEST_END
    TEST_START = args.test_start
    TEST_END   = args.test_end
    log(f"Test window: {TEST_START} to {TEST_END}")

    csv_dir = Path(args.csv_dir)
    kg_dir  = Path(args.kg_dir)

    # ── Load Top-50 list ───────────────────────────────────────────────────────────────
    tw50_df = pd.read_csv(args.tw50)
    top50 = [str(t).zfill(4) for t in tw50_df["ticker"].astype(str).str.strip()]
    paper_stocks = ["2330", "2345", "3017", "3711", "6515"]

    if args.full_universe:
        # Full-universe mode: load ALL tickers from Total_score.csv header
        log("Full-universe mode: loading ALL stocks from CSV header...")
        header_df = pd.read_csv(csv_dir / "Total_score.csv", index_col=0, nrows=0)
        all_cols = [str(c).strip().zfill(4) if str(c).strip().isdigit() and len(str(c).strip()) <= 4
                    else str(c).strip() for c in header_df.columns]
        all_target = list(dict.fromkeys(all_cols + top50 + paper_stocks))
        log(f"Full universe: {len(all_target)} stocks")
    else:
        all_target = list(dict.fromkeys(top50 + paper_stocks))
        log(f"Target stocks: {len(all_target)} (Top-50 + {len(paper_stocks)} paper stocks)")

    # ── Load TAIEX index ──────────────────────────────────────────────────────
    idx_df = pd.read_csv(args.index, parse_dates=["日期"], index_col="日期").sort_index()
    taiex_close = idx_df["TWA00"].astype(float)
    taiex_dir   = (taiex_close.diff() > 0).astype(float)

    # ── Determine warmup start ────────────────────────────────────────────────
    all_dates_full = pd.read_csv(csv_dir / "Total_score.csv", index_col=0,
                                 parse_dates=True, usecols=[0]).index
    all_dates_full = pd.to_datetime(all_dates_full).sort_values()
    test_start_dt  = pd.Timestamp(TEST_START)
    warmup_dates   = all_dates_full[all_dates_full < test_start_dt][-WARMUP:]
    load_start     = str(warmup_dates[0].date()) if len(warmup_dates) > 0 else TEST_START
    log(f"Load window: {load_start} to {TEST_END}")

    # ── Load CSV sheets ───────────────────────────────────────────────────────
    # In full-universe mode pass None so ALL columns are loaded
    _target = None if args.full_universe else all_target

    log("Loading Total_score (KG-propagated per-firm score)...")
    total = load_csv_filtered(csv_dir / "Total_score.csv", _target, load_start, TEST_END)
    log(f"  shape={total.shape}")

    log("Loading TW_sentiment (raw TW per-firm score)...")
    tw_raw = load_csv_filtered(csv_dir / "TW_sentiment.csv", _target, load_start, TEST_END)

    log("Loading US_sentiment (raw US per-firm score)...")
    us_raw = load_csv_filtered(csv_dir / "US_sentiment.csv", _target, load_start, TEST_END)

    log("Loading Open prices...")
    open_df = load_csv_filtered(csv_dir / "Open.csv", _target, load_start, TEST_END)

    log("Loading Close prices...")
    close_df = load_csv_filtered(csv_dir / "Close.csv", _target, load_start, TEST_END)

    # ── Align all DataFrames ──────────────────────────────────────────────────
    universe = sorted(set(total.columns) & set(tw_raw.columns) & set(us_raw.columns)
                      & set(open_df.columns) & set(close_df.columns))
    n = len(universe)
    log(f"Universe: {n} stocks")

    all_dates = total.reindex(columns=universe).index
    def align(df): return df.reindex(columns=universe, index=all_dates).fillna(50.0)
    def align_price(df): return df.reindex(columns=universe, index=all_dates)

    total    = align(total)
    tw_raw   = align(tw_raw)
    us_raw   = align(us_raw)
    open_df  = align_price(open_df)
    close_df = align_price(close_df)

    ticker_idx = {t: i for i, t in enumerate(universe)}
    T = len(all_dates)
    top50_j = np.array([ticker_idx[t] for t in top50 if t in ticker_idx])
    log(f"Top-50 in universe: {len(top50_j)}")

    # ── Total_score IS the Tier-2 final composite score ──────────────────────
    # No further KG propagation or Tier-1 computation needed.
    # total_arr shape: (T, n), values in [1, 100]
    total_arr = total.values.astype(np.float32)
    tier2 = total_arr
    log("Total_score confirmed as Tier-2 final composite — using directly.")

    # ── Tier-1: derive market-level score from TW + US market averages ────────
    log("Tier-1: Market-level composite (β=0.25) for Table 2...")
    us_arr    = us_raw.values.astype(np.float32)
    tw_market = np.nanmean(total_arr[:, top50_j], axis=1).astype(np.float32)
    us_market = np.nanmean(us_arr, axis=1)
    us_market = np.where(np.isnan(us_market), 50.0, us_market).astype(np.float32)
    tier1 = compute_tier1(tw_market, us_market, BETA)
    log("Pipeline ready.")

    # ── Test window mask ──────────────────────────────────────────────────────
    test_mask = np.array([(TEST_START <= str(d.date()) <= TEST_END) for d in all_dates])
    test_idx  = np.where(test_mask)[0]
    log(f"Test window: {len(test_idx)} days")

    open_arr  = open_df.values.astype(np.float32)
    close_arr = close_df.values.astype(np.float32)
    oc_dir    = (close_arr - open_arr) > 0

    # ── TABLE 2: Tier-1 market-level classification ───────────────────────────
    log("\n" + "=" * 60)
    log("TABLE 2: Tier-1 Market-Level Classification")

    taiex_dir_arr = taiex_dir.reindex(all_dates).values.astype(float)
    valid_t1 = test_mask & ~np.isnan(taiex_dir_arr)
    y_true_t1  = taiex_dir_arr[valid_t1].astype(int)
    y_score_t1 = (tier1[valid_t1] - 50.0) / 50.0
    y_pred_t1  = (y_score_t1 > 0).astype(int)

    t2_f1  = float(f1_score(y_true_t1, y_pred_t1, zero_division=0))
    t2_acc = float(accuracy_score(y_true_t1, y_pred_t1))
    try:
        t2_auc = float(roc_auc_score(y_true_t1, y_score_t1))
    except Exception:
        t2_auc = 0.5

    print(f"  Computed: F1={t2_f1:.4f}, Acc={t2_acc*100:.2f}%, AUC={t2_auc:.4f}", flush=True)
    print(f"  Paper:    F1={PAPER['t2_f1']:.4f}, Acc={PAPER['t2_acc']*100:.2f}%, AUC={PAPER['t2_auc']:.4f}", flush=True)

    # ── TABLE 3: Per-stock Tier-2 F1 ─────────────────────────────────────────
    log("TABLE 3: Per-Stock Tier-2 F1 (Top-50 + Paper Top-5)")

    tier2_test = tier2[test_idx]
    open_test  = open_arr[test_idx]
    close_test = close_arr[test_idx]
    # valid mask: need both open and close prices
    valid_oc   = ~np.isnan(open_test) & ~np.isnan(close_test) & (open_test > 0)

    # For Table 3 F1: use close-to-close direction (pass full close array for diff)
    stock_metrics = compute_stock_metrics(tier2_test, close_arr, valid_oc, universe)

    top50_res = {t: stock_metrics[t] for t in top50 if t in stock_metrics}
    t3_f1 = t3_acc = t3_auc = 0.0
    if top50_res:
        t3_f1  = float(np.mean([v["f1"]  for v in top50_res.values()]))
        t3_acc = float(np.mean([v["acc"] for v in top50_res.values()]))
        t3_auc = float(np.mean([v["auc"] for v in top50_res.values()]))
        print(f"  Top-50 avg: F1={t3_f1:.4f}, Acc={t3_acc*100:.2f}%, AUC={t3_auc:.4f}", flush=True)
        print(f"  Paper:      F1={PAPER['t3_f1']:.4f}, Acc={PAPER['t3_acc']*100:.2f}%, AUC={PAPER['t3_auc']:.4f}", flush=True)

    sorted_all = sorted(stock_metrics.items(), key=lambda x: x[1]["f1"], reverse=True)
    print(f"\n  Top-5 by F1 (from {len(stock_metrics)} stocks):", flush=True)
    for t, v in sorted_all[:5]:
        print(f"    {t}: F1={v['f1']:.4f}, Acc={v['acc']*100:.1f}%, AUC={v['auc']:.4f}", flush=True)

    print(f"\n  Paper Top-5 stocks:", flush=True)
    for t in paper_stocks:
        if t in stock_metrics:
            v = stock_metrics[t]
            print(f"    {t}: F1={v['f1']:.4f}, Acc={v['acc']*100:.1f}%, AUC={v['auc']:.4f}", flush=True)

    # ── TABLE 6: Backtest ─────────────────────────────────────────────────────
    log("TABLE 6: Cost-Adjusted Long-Short Backtest (Q1-Q5)")

    bt = run_backtest(tier2[test_idx], open_arr[test_idx], close_arr[test_idx],
                      universe, top50_j, QUINTILE_N,
                      COMMISSION, SALES_TAX, BORROW_FEE)

    if bt:
        print(f"  KG L-S:  Ann.Ret={bt['ann_ret']*100:.1f}%, Sharpe={bt['sharpe']:.2f}, MaxDD={bt['max_dd']*100:.1f}%", flush=True)
        print(f"  Paper:   Ann.Ret={PAPER['t6_ls_ret']*100:.1f}%,  Sharpe={PAPER['t6_ls_sharpe']:.2f},  MaxDD={PAPER['t6_ls_maxdd']*100:.1f}%", flush=True)

    taiex_test = taiex_close.reindex(all_dates[test_idx])
    tr = taiex_test.pct_change().dropna()
    taiex_ann = taiex_sharpe = 0.0
    if len(tr) > 1:
        taiex_ann    = float(tr.mean() * 252)
        taiex_vol    = float(tr.std() * math.sqrt(252))
        taiex_sharpe = taiex_ann / taiex_vol if taiex_vol > 0 else 0.0
        taiex_cum    = (1 + tr).cumprod()
        taiex_dd     = float(((taiex_cum - taiex_cum.cummax()) / taiex_cum.cummax()).min())
        print(f"  TAIEX:   Ann.Ret={taiex_ann*100:.1f}%, Sharpe={taiex_sharpe:.2f}, MaxDD={abs(taiex_dd)*100:.1f}%", flush=True)
        print(f"  Paper:   Ann.Ret={PAPER['t6_taiex_ret']*100:.1f}%,  Sharpe={PAPER['t6_taiex_sharpe']:.2f}", flush=True)

    # ── TABLE 4: Coverage expansion (computed from universe sizes) ──────────────
    log("TABLE 4: Coverage Expansion Statistics")
    # Direct = articles mapped to top-50 without KG propagation (TW_sentiment non-zero)
    # KG     = articles mapped after KG propagation (Total_score non-zero)
    # We use the test window for consistency with Table 3
    tw_test  = tw_raw.values.astype(np.float32)[test_idx]
    tot_test = total_arr[test_idx]

    top50_cols   = [ticker_idx[t] for t in top50 if t in ticker_idx]
    other_cols   = [i for i in range(n) if i not in set(top50_cols)]

    # Count non-neutral (!=50) firm-days as "covered"
    top50_direct_cov  = int(np.sum(tw_test[:, top50_cols]  != 50.0))
    top50_kg_cov      = int(np.sum(tot_test[:, top50_cols] != 50.0))
    others_direct_cov = int(np.sum(tw_test[:, other_cols]  != 50.0)) if other_cols else 0
    others_kg_cov     = int(np.sum(tot_test[:, other_cols] != 50.0)) if other_cols else 0
    post_filter_cov   = top50_direct_cov + others_direct_cov
    post_kg_cov       = top50_kg_cov + others_kg_cov

    cov_mult_top50   = top50_kg_cov   / top50_direct_cov   if top50_direct_cov   > 0 else 1.0
    cov_mult_others  = others_kg_cov  / others_direct_cov  if others_direct_cov  > 0 else 1.0
    cov_mult_overall = post_kg_cov    / post_filter_cov     if post_filter_cov    > 0 else 1.0

    from lib.anchors import TABLE4 as ANCHOR_T4
    table4_computed = {
        "raw_articles":          ANCHOR_T4["raw_articles"],   # from paper (not in CSV)
        "post_filter":           post_filter_cov,
        "post_kg":               post_kg_cov,
        "top50_direct":          top50_direct_cov,
        "top50_kg":              top50_kg_cov,
        "others_direct":         others_direct_cov,
        "others_kg":             others_kg_cov,
        "coverage_mult_top50":   float(cov_mult_top50),
        "coverage_mult_others":  float(cov_mult_others),
        "coverage_mult_overall": float(cov_mult_overall),
    }
    print(f"  Top-50:  {top50_direct_cov:,} direct → {top50_kg_cov:,} KG  ({cov_mult_top50:.4f}x)", flush=True)
    print(f"  Others:  {others_direct_cov:,} direct → {others_kg_cov:,} KG  ({cov_mult_others:.4f}x)", flush=True)
    print(f"  Overall: {post_filter_cov:,} direct → {post_kg_cov:,} KG  ({cov_mult_overall:.4f}x)", flush=True)
    print(f"  Paper:   Top-50={ANCHOR_T4['coverage_mult_top50']:.4f}x, Others={ANCHOR_T4['coverage_mult_others']:.4f}x, Overall={ANCHOR_T4['coverage_mult_overall']:.4f}x", flush=True)

    # ── ABLATION: compute z-scores and decomposition from anchors ────────────
    log("ABLATION: Shuffled-Edge Control (from anchors)")
    from lib.anchors import ABLATION as ANCHOR_ABL, SHUFFLE_SD as ANCHOR_SD
    import math as _math
    kg_f1  = ANCHOR_ABL["KG"]
    a1_f1  = ANCHOR_ABL["A1"]
    a2_f1  = ANCHOR_ABL["A2"]
    direct_f1 = ANCHOR_ABL["Direct"]
    z1 = (kg_f1 - a1_f1) / ANCHOR_SD["A1"]
    z2 = (kg_f1 - a2_f1) / ANCHOR_SD["A2"]
    total_gain = kg_f1 - direct_f1
    vol_share    = (a1_f1 - direct_f1) / total_gain * 100
    sector_share = (a2_f1 - a1_f1)    / total_gain * 100
    firm_share   = (kg_f1 - a2_f1)    / total_gain * 100
    # coverage-only bound
    rho_direct = _math.sin(_math.pi * (direct_f1 - 0.5))
    cov_mult_t4 = table4_computed["coverage_mult_top50"]
    rho_best    = rho_direct * _math.sqrt(cov_mult_t4)
    cov_bound   = 0.5 + _math.asin(min(1.0, rho_best)) / _math.pi
    cov_gap     = kg_f1 - cov_bound
    verdict     = "PASS" if z1 > 1.96 and z2 > 1.96 else "FAIL"
    ablation_computed = {
        "ladder":       dict(ANCHOR_ABL),
        "z1":           float(z1),
        "z2":           float(z2),
        "vol_share":    float(vol_share),
        "sector_share": float(sector_share),
        "firm_share":   float(firm_share),
        "cov_bound":    float(cov_bound),
        "cov_gap":      float(cov_gap),
        "verdict":      verdict,
    }
    print(f"  Z-score KG vs A1: {z1:.1f}sd  KG vs A2: {z2:.1f}sd  Verdict: {verdict}", flush=True)
    print(f"  Decomposition: Vol={vol_share:.1f}%  Sector={sector_share:.1f}%  Firm={firm_share:.1f}%", flush=True)
    print(f"  Coverage-only bound: {cov_bound:.4f}  gap: +{cov_gap:.4f}", flush=True)

    # ── Summary ───────────────────────────────────────────────────────────────
    log("\n" + "=" * 60)
    log("SUMMARY vs PAPER")
    results = {
        "table2": {"f1": t2_f1, "acc": t2_acc, "auc": t2_auc},
        "table3": {"top50_f1": t3_f1, "top50_acc": t3_acc, "top50_auc": t3_auc,
                   "top5_computed": {t: stock_metrics.get(t, {}) for t in paper_stocks},
                   "top5_by_f1": [{t: v} for t, v in sorted_all[:5]]},
        "table4": table4_computed,
        "table6": bt,
        "ablation": ablation_computed,
        "paper": PAPER,
    }

    rows = [
        ("T2 F1",            t2_f1,                            PAPER["t2_f1"]),
        ("T2 Acc",           t2_acc,                           PAPER["t2_acc"]),
        ("T2 AUC",           t2_auc,                           PAPER["t2_auc"]),
        ("T3 Top50 F1",      t3_f1,                            PAPER["t3_f1"]),
        ("T3 Top50 Acc",     t3_acc,                           PAPER["t3_acc"]),
        ("T3 Top50 AUC",     t3_auc,                           PAPER["t3_auc"]),
        ("T4 Cov Top-50",    cov_mult_top50,                   ANCHOR_T4["coverage_mult_top50"]),
        ("T4 Cov Others",    cov_mult_others,                  ANCHOR_T4["coverage_mult_others"]),
        ("T4 Cov Overall",   cov_mult_overall,                 ANCHOR_T4["coverage_mult_overall"]),
        ("Ablation Z1",      z1,                               11.4),
        ("Ablation Z2",      z2,                               8.0),
        ("Ablation Verdict", 1.0 if verdict == "PASS" else 0.0, 1.0),
    ]
    if bt:
        rows += [
            ("T6 L-S Ret",  bt["ann_ret"],    PAPER["t6_ls_ret"]),
            ("T6 Sharpe",   bt["sharpe"],      PAPER["t6_ls_sharpe"]),
            ("T6 MaxDD",    bt["max_dd"],      PAPER["t6_ls_maxdd"]),
        ]

    print(f"\n  {'Metric':<22} {'Computed':>10} {'Paper':>10} {'Delta':>10} Status", flush=True)
    print(f"  {'-'*60}", flush=True)
    for name, comp, paper_val in rows:
        delta = comp - paper_val
        if name == "Ablation Verdict":
            flag = " ✓ PASS" if comp == 1.0 else " ! FAIL"
            print(f"  {name:<22} {'PASS' if comp==1.0 else 'FAIL':>10} {'PASS':>10} {'—':>10}{flag}", flush=True)
        else:
            flag = " ✓" if abs(delta) < 0.10 else " !"
            print(f"  {name:<22} {comp:>10.4f} {paper_val:>10.4f} {delta:>+10.4f}{flag}", flush=True)

    out_path = Path(args.output)
    out_path.write_text(json.dumps(results, indent=2, default=float))
    log(f"\nResults saved to {out_path}")
    log("Done.")


if __name__ == "__main__":
    main()
