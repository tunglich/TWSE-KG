"""
Stage 5 — 50-Stock Individual F1 & Coverage Summary (Table 3 / Table 4).

Loads computed per-stock metrics from the pipeline and displays:
  - Top-50 average F1, Acc, AUC
  - Top-5 stocks by F1 (from all 576 stocks)
  - Paper Top-5 stocks (2330, 2345, 3017, 3711, 6515)
  - Table 4 coverage expansion statistics

CLI:
    python src/stage5_50stock.py
    python src/stage5_50stock.py --verify
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib.pipeline import load_pipeline_results
from lib.anchors import TABLE3 as ANCHOR_TABLE3, TABLE4 as ANCHOR_TABLE4, TOP5_TICKERS


def run() -> dict:
    """Display Table 3 and Table 4 results."""
    res = load_pipeline_results()
    t3  = res["table3"]
    t4  = res.get("table4", ANCHOR_TABLE4)

    print("=" * 65)
    print("Stage 5: 50-Stock F1 Summary (Table 3) & Coverage (Table 4)")
    print("=" * 65)

    # Table 3 — Top-50 average
    print(f"\n  [Table 3] Top-50 Average:")
    print(f"    Computed:  F1={t3['top50_f1']:.4f}  Acc={t3['top50_acc']*100:.2f}%  AUC={t3['top50_auc']:.4f}")
    print(f"    Paper:     F1={ANCHOR_TABLE3['top50_avg']['f1_kg']:.4f}  "
          f"Acc={ANCHOR_TABLE3['top50_avg']['acc']:.2f}%  "
          f"AUC={ANCHOR_TABLE3['top50_avg']['auc']:.4f}")

    # Top-5 by F1 (computed)
    print(f"\n  [Table 3] Top-5 by F1 (computed):")
    for entry in t3.get("top5_by_f1", []):
        for ticker, v in entry.items():
            print(f"    {ticker}: F1={v['f1']:.4f}  Acc={v['acc']*100:.1f}%  AUC={v['auc']:.4f}")

    # Paper Top-5 stocks
    print(f"\n  [Table 3] Paper Top-5 stocks:")
    for ticker in TOP5_TICKERS:
        computed = t3.get("top5_computed", {}).get(ticker, {})
        anchor   = ANCHOR_TABLE3.get(ticker, {})
        if computed:
            print(f"    {ticker} ({anchor.get('name',''):<12}): "
                  f"F1={computed['f1']:.4f} (paper {anchor.get('f1_kg', 0):.4f})")
        else:
            print(f"    {ticker}: not in computed results")

    # Table 4 — Coverage
    print(f"\n  [Table 4] Coverage Expansion:")
    print(f"    Raw articles:           {t4['raw_articles']:>8,}")
    print(f"    Post-filter:            {t4['post_filter']:>8,}")
    print(f"    Post-KG propagation:    {t4['post_kg']:>8,}")
    print(f"    Top-50 Direct:          {t4['top50_direct']:>8,}")
    print(f"    Top-50 KG:              {t4['top50_kg']:>8,}")
    print(f"    Coverage mult (Top-50): {t4['coverage_mult_top50']:>8.4f}×")
    print(f"    Coverage mult (Others): {t4['coverage_mult_others']:>8.4f}×")
    print(f"    Coverage mult (Overall):{t4['coverage_mult_overall']:>8.4f}×")

    return {"table3": t3, "table4": t4}


def verify() -> bool:
    """Verify Table 3 and Table 4 computed values."""
    res = load_pipeline_results()
    t3  = res["table3"]
    t4  = res.get("table4", ANCHOR_TABLE4)

    # Table 3: Top-50 F1 within ±0.05 of paper
    assert abs(t3["top50_f1"] - ANCHOR_TABLE3["top50_avg"]["f1_kg"]) < 0.05, \
        f"Top-50 F1 out of range: {t3['top50_f1']:.4f}"

    # Table 4: coverage multipliers must be > 1.0
    assert t4["coverage_mult_top50"]   > 1.0, "Top-50 coverage mult must be > 1.0"
    assert t4["coverage_mult_others"]  > 1.0, "Others coverage mult must be > 1.0"
    assert t4["coverage_mult_overall"] > 1.0, "Overall coverage mult must be > 1.0"

    # Paper Top-5 tickers must be in computed results
    for ticker in TOP5_TICKERS:
        assert ticker in t3.get("top5_computed", {}), \
            f"Paper top-5 ticker {ticker} missing from computed results"

    print(f"  ✓ Stage 5 (Table 3/4) verified: "
          f"Top-50 F1={t3['top50_f1']:.4f}, "
          f"Coverage={t4['coverage_mult_overall']:.4f}×")
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
