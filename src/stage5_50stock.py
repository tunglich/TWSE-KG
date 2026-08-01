"""
Stage 5 — 50-Stock Individual F1 Gain & Coverage Multiplier.

Reads the 50_Stock_F1_Coverage sheet from Sentiment_score_all.xlsx,
computes summary statistics, and tests the gain-vs-coverage decoupling
(R² ≈ 0 → coverage-only hypothesis rejected).

CLI:
    python src/stage5_50stock.py
    python src/stage5_50stock.py --verify
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib.data import load_50_stock
from lib.anchors import TABLE3


def run() -> dict:
    print("=" * 60)
    print("Stage 5: 50-Stock F1 Gain & Coverage Multiplier")
    print("=" * 60)
    stocks = load_50_stock()
    n = len(stocks)
    gains = [s["F1_Gain"] for s in stocks]
    covs = [s["Coverage_Mult"] for s in stocks]

    avg_kg = sum(s["F1(KG)"] for s in stocks) / n
    avg_direct = sum(s["F1(Direct)"] for s in stocks) / n
    avg_gain = sum(gains) / n
    median_gain = sorted(gains)[n // 2]
    iqr_lo = sorted(gains)[n // 4]
    iqr_hi = sorted(gains)[3 * n // 4]
    avg_cov = sum(covs) / n

    print(f"  Stocks: {n}")
    print(f"  Avg F1(KG):       {avg_kg:.4f}")
    print(f"  Avg F1(Direct):   {avg_direct:.4f}")
    print(f"  Avg F1 Gain:      {avg_gain:.4f}")
    print(f"  Median F1 Gain:   {median_gain:.4f}")
    print(f"  IQR:              [{iqr_lo:.4f}, {iqr_hi:.4f}]")
    print(f"  Min gain:         {min(gains):.4f}  (all positive: {all(g > 0 for g in gains)})")
    print(f"  Avg Coverage Mult: {avg_cov:.4f}")

    # Gain vs coverage correlation
    mean_g = sum(gains) / n
    mean_c = sum(covs) / n
    num = sum((g - mean_g) * (c - mean_c) for g, c in zip(gains, covs))
    den_g = sum((g - mean_g) ** 2 for g in gains)
    den_c = sum((c - mean_c) ** 2 for c in covs)
    corr = num / math.sqrt(den_g * den_c) if den_g > 0 and den_c > 0 else 0
    r2 = corr * corr
    print(f"  Gain-Coverage R²:  {r2:.4f}")
    print(f"  → Coverage-only hypothesis {'rejected' if r2 < 0.05 else 'NOT rejected'} (R² ≈ {r2:.3f})")

    return {"n": n, "avg_gain": avg_gain, "r_squared": r2, "all_positive": all(g > 0 for g in gains)}


def verify() -> bool:
    stocks = load_50_stock()
    n = len(stocks)
    assert n == 50, f"Expected 50 stocks, got {n}"
    gains = [s["F1_Gain"] for s in stocks]
    assert all(g > 0 for g in gains), "All F1 gains must be positive"
    avg_gain = sum(gains) / n
    assert abs(avg_gain - 0.1147) < 0.01, f"Avg gain {avg_gain:.4f}, expected ≈0.1147"
    # Check Top-5 tickers match Table 3
    for ticker in ["2330", "2345", "3017", "3711", "6515"]:
        match = [s for s in stocks if str(s["Ticker"]) == ticker]
        assert match, f"Ticker {ticker} not found in 50-stock sheet"
        t3 = TABLE3[ticker]
        assert abs(match[0]["F1(KG)"] - t3["f1_kg"]) < 0.001, f"{ticker} F1(KG) mismatch"
    print("  ✓ Stage 5 (50-Stock) verified")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    if args.verify:
        verify()
    else:
        run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
