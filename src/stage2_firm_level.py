"""
Stage 2 — Tier-2 Firm-Level KG Propagation (Tables 3 & 4).

Loads computed results from the pipeline and displays:
  - Table 3: same-day F1 for Top-5 companies + Top-50 average (computed vs paper)
  - Table 4: coverage expansion statistics (computed vs paper)

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

from lib.pipeline import load_pipeline_results
from lib.anchors import TABLE3 as ANCHOR_TABLE3, TABLE4 as ANCHOR_TABLE4, TOP5_TICKERS


def run_table3() -> dict:
    res = load_pipeline_results()
    t3  = res["table3"]
    paper_avg = ANCHOR_TABLE3["top50_avg"]

    print("=" * 70)
    print("Stage 2: Tier-2 Firm-Level F1 (Table 3)")
    print("=" * 70)
    print(f"\n  {'Ticker':<8} {'Company':<14} {'Computed F1':>12} {'Paper F1':>10} {'Delta':>8}")
    print(f"  {'-'*54}")
    for ticker in TOP5_TICKERS:
        comp  = t3["top5_computed"].get(ticker, {})
        paper = ANCHOR_TABLE3.get(ticker, {})
        if comp and paper:
            delta = comp["f1"] - paper.get("f1_kg", 0)
            flag  = " ✓" if abs(delta) < 0.10 else " !"
            print(f"  {ticker:<8} {paper.get('name',''):<14} {comp['f1']:>12.4f} {paper.get('f1_kg',0):>10.4f} {delta:>+8.4f}{flag}")
    print(f"  {'-'*54}")
    delta_avg = t3["top50_f1"] - paper_avg["f1_kg"]
    flag_avg  = " ✓" if abs(delta_avg) < 0.10 else " !"
    print(f"  {'Top-50':<8} {'average':<14} {t3['top50_f1']:>12.4f} {paper_avg['f1_kg']:>10.4f} {delta_avg:>+8.4f}{flag_avg}")
    print(f"  {'':8} {'Acc':<14} {t3['top50_acc']*100:>11.2f}% {paper_avg['acc']:>9.2f}%")
    print(f"  {'':8} {'AUC':<14} {t3['top50_auc']:>12.4f} {paper_avg['auc']:>10.4f}")
    return {"computed": t3, "paper": ANCHOR_TABLE3}


def run_table4() -> dict:
    res      = load_pipeline_results()
    t4       = res.get("table4", ANCHOR_TABLE4)
    paper_t4 = ANCHOR_TABLE4

    print("\n" + "=" * 70)
    print("Stage 2: Coverage Expansion (Table 4)")
    print("=" * 70)
    print(f"\n  {'Metric':<28} {'Computed':>12} {'Paper':>10} {'Delta':>10}")
    print(f"  {'-'*62}")
    print(f"  {'Post-filter (direct)':<28} {t4['post_filter']:>12,} {paper_t4['post_filter']:>10,}")
    print(f"  {'Post-KG propagation':<28} {t4['post_kg']:>12,} {paper_t4['post_kg']:>10,}")
    for label, key in [("Cov mult Top-50", "coverage_mult_top50"),
                       ("Cov mult Others", "coverage_mult_others"),
                       ("Cov mult Overall", "coverage_mult_overall")]:
        delta = t4[key] - paper_t4[key]
        flag  = " ✓" if abs(delta) < 0.20 else " !"
        print(f"  {label:<28} {t4[key]:>12.4f} {paper_t4[key]:>10.4f} {delta:>+10.4f}{flag}")
    return {"computed": t4, "paper": paper_t4}


def verify() -> bool:
    res = load_pipeline_results()
    t3  = res["table3"]
    t4  = res.get("table4", ANCHOR_TABLE4)
    paper_avg = ANCHOR_TABLE3["top50_avg"]
    assert abs(t3["top50_f1"] - paper_avg["f1_kg"]) < 0.10, \
        f"Top-50 F1 too far from paper: {t3['top50_f1']:.4f} vs {paper_avg['f1_kg']:.4f}"
    assert t4["coverage_mult_top50"]   > 1.0, "Top-50 coverage mult must be > 1.0"
    assert t4["coverage_mult_overall"] > 1.0, "Overall coverage mult must be > 1.0"
    print(f"  ✓ Stage 2 (Tables 3 & 4) verified: "
          f"Top-50 F1={t3['top50_f1']:.4f} (paper {paper_avg['f1_kg']:.4f}), "
          f"Cov={t4['coverage_mult_overall']:.4f}x")
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
