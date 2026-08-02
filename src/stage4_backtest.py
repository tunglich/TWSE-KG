"""
Stage 4 — Cost-Adjusted Long-Short Backtest (Table 6).

Loads computed backtest results from the pipeline and displays the
full Table 6 comparison (KG L-S, KG Long, LLM L-S, TAIEX benchmark).

CLI:
    python src/stage4_backtest.py
    python src/stage4_backtest.py --verify
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib.pipeline import load_pipeline_results
from lib.anchors import TABLE6 as ANCHOR_TABLE6


def run() -> dict:
    """Display Table 6 backtest results."""
    res = load_pipeline_results()
    bt  = res["table6"]
    paper = res.get("paper", {})

    print("=" * 70)
    print("Stage 4: Cost-Adjusted Long-Short Backtest (Table 6)")
    print("=" * 70)
    print(f"  {'Portfolio':<28} {'Ann.Ret':>9} {'Sharpe':>8} {'MaxDD':>8}")
    print("  " + "-" * 58)

    # Computed KG L-S row
    ann_ret_pct = bt["ann_ret"] * 100
    max_dd_pct  = bt["max_dd"]  * 100
    print(f"  {'KG Long-Short (computed)':<28} {ann_ret_pct:>8.1f}% {bt['sharpe']:>8.2f} {max_dd_pct:>7.1f}%")

    # Paper anchor rows for comparison
    for name, d in ANCHOR_TABLE6.items():
        label = name.replace("_", " ").title()
        print(f"  {label + ' (paper)':<28} {d['ann_ret']:>8.1f}% {d['sharpe']:>8.2f} {d['max_dd']:>7.1f}%")

    print()
    # Delta vs paper KG L-S
    paper_ret = paper.get("t6_ls_ret", ANCHOR_TABLE6["kg_ls"]["ann_ret"] / 100) * 100
    delta = ann_ret_pct - paper_ret
    print(f"  Computed vs Paper KG L-S: {ann_ret_pct:.1f}% vs {paper_ret:.1f}% ({delta:+.1f}pp)")

    return {"computed": bt, "paper_anchors": ANCHOR_TABLE6}


def verify() -> bool:
    """Verify Table 6 computed values are within acceptable range."""
    res = load_pipeline_results()
    bt  = res["table6"]

    # KG L-S must beat LLM L-S (paper 5.9%)
    assert bt["ann_ret"] > 0.059, f"KG L-S ann_ret too low: {bt['ann_ret']:.4f}"
    # Sharpe must be positive
    assert bt["sharpe"] > 0, f"Sharpe must be positive: {bt['sharpe']:.4f}"
    # MaxDD must be reasonable (< 50%)
    assert bt["max_dd"] < 0.50, f"MaxDD too large: {bt['max_dd']:.4f}"
    # Ann return must be positive
    assert bt["ann_ret"] > 0, f"Ann return must be positive: {bt['ann_ret']:.4f}"

    print(f"  ✓ Stage 4 (Table 6) verified: "
          f"Ann.Ret={bt['ann_ret']*100:.1f}%, Sharpe={bt['sharpe']:.2f}, "
          f"MaxDD={bt['max_dd']*100:.1f}%")
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
