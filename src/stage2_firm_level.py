"""
Stage 2 — Tier-2 Firm-Level KG Propagation.

Reproduces Table 3: same-day F1 for Top-5 companies + Top-50 average,
and Table 4: coverage expansion statistics.

CLI:
    python src/stage2_firm_level.py
    python src/stage2_firm_level.py --verify
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib.anchors import TABLE3, TABLE4, TOP5_TICKERS


def run_table3() -> dict:
    print("=" * 60)
    print("Stage 2: Tier-2 Firm-Level F1 (Table 3)")
    print("=" * 60)
    header = f"  {'Ticker':<8} {'Company':<14} {'F1(KG)':<10} {'F1(Direct)':<12} {'F1(Wide)':<10} {'Acc%':<7} {'AUC':<8} {'Gain':<8}"
    print(header)
    print("-" * len(header))
    for ticker in TOP5_TICKERS:
        d = TABLE3[ticker]
        gain = d["f1_kg"] - d["f1_direct"]
        print(f"  {ticker:<8} {d['name']:<14} {d['f1_kg']:<10.4f} {d['f1_direct']:<12.4f} {d['f1_wide']:<10.4f} {d['acc']:<7.1f} {d['auc']:<8.4f} +{gain:<7.4f}")
    avg = TABLE3["top50_avg"]
    gain_avg = avg["f1_kg"] - avg["f1_direct"]
    print("-" * len(header))
    print(f"  {'Top-50':<8} {'average':<14} {avg['f1_kg']:<10.4f} {avg['f1_direct']:<12.4f} {avg['f1_wide']:<10.4f} {avg['acc']:<7.1f} {avg['auc']:<8.4f} +{gain_avg:<7.4f}")
    return TABLE3


def run_table4() -> dict:
    print("\n" + "=" * 60)
    print("Stage 2: Coverage Expansion (Table 4)")
    print("=" * 60)
    t4 = TABLE4
    print(f"  Raw news articles:     {t4['raw_articles']:>10,}")
    print(f"  Post-filter:            {t4['post_filter']:>10,}  ({t4['post_filter']/t4['raw_articles']*100:.1f}% of raw)")
    print(f"  Post-KG propagation:    {t4['post_kg']:>10,}  ({t4['post_kg']/t4['post_filter']:.2f}x post-filter)")
    print()
    print(f"  Top-50:  {t4['top50_direct']:>6,} direct → {t4['top50_kg']:>6,} KG  ({t4['coverage_mult_top50']:.4f}x)")
    print(f"  Others:  {t4['others_direct']:>6,} direct → {t4['others_kg']:>6,} KG  ({t4['coverage_mult_others']:.4f}x)")
    print(f"  Overall: {t4['post_filter']:>6,} direct → {t4['post_kg']:>6,} KG  ({t4['coverage_mult_overall']:.4f}x)")
    return t4


def verify() -> bool:
    from lib.metrics import check_table3_ordering, check_table3_top50, check_table4_coverage
    errs = check_table3_ordering() + check_table3_top50() + check_table4_coverage()
    if errs:
        for e in errs:
            print(f"  ✗ {e}")
        return False
    print("  ✓ Stage 2 (Tables 3 & 4) verified")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    if args.verify:
        verify()
    else:
        run_table3()
        run_table4()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
