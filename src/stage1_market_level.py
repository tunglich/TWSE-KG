"""
Stage 1 — Tier-1 Market-Level Nowcast/Forecast (Table 2).

Loads computed Tier-1 results from the pipeline and displays
same-day nowcast vs next-day forecast F1/Acc/AUC, with computed vs paper comparison.

CLI:
    python src/stage1_market_level.py
    python src/stage1_market_level.py --verify
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as a script: add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib.pipeline import load_pipeline_results
from lib.anchors import TABLE2 as ANCHOR_TABLE2


def run() -> dict:
    """Display Table 2 computed vs paper values."""
    res = load_pipeline_results()
    sd  = res["table2"]
    paper_sd = ANCHOR_TABLE2["same_day"]
    paper_nd = ANCHOR_TABLE2["next_day"]

    print("=" * 65)
    print("Stage 1: Tier-1 Market-Level Nowcast/Forecast (Table 2)")
    print("=" * 65)
    print(f"\n  {'Metric':<22} {'Computed':>10} {'Paper':>10} {'Delta':>10}")
    print(f"  {'-'*54}")
    print(f"  {'Same-day F1':<22} {sd['f1']:>10.4f} {paper_sd['f1']:>10.4f} {sd['f1']-paper_sd['f1']:>+10.4f}")
    print(f"  {'Same-day Acc':<22} {sd['acc']*100:>9.2f}% {paper_sd['acc']:>9.2f}% {(sd['acc']*100-paper_sd['acc']):>+9.2f}pp")
    print(f"  {'Same-day AUC':<22} {sd['auc']:>10.4f} {paper_sd['auc']:>10.4f} {sd['auc']-paper_sd['auc']:>+10.4f}")
    print(f"\n  Next-day forecast (paper only):")
    print(f"    F1={paper_nd['f1']:.4f}  Acc={paper_nd['acc']:.2f}%")
    gain_f1  = sd["f1"]  - paper_nd["f1"]
    gain_acc = sd["acc"] * 100 - paper_nd["acc"]
    print(f"\n  Computed same-day vs paper next-day: +{gain_f1:.4f} F1, +{gain_acc:.2f}pp Acc")
    return {"computed": sd, "paper_same_day": paper_sd, "paper_next_day": paper_nd}


def verify() -> bool:
    """Verify Table 2 computed values are within acceptable range of paper."""
    res = load_pipeline_results()
    sd  = res["table2"]
    paper = ANCHOR_TABLE2["same_day"]
    assert abs(sd["f1"] - paper["f1"]) < 0.10, \
        f"Same-day F1 too far from paper: computed={sd['f1']:.4f}, paper={paper['f1']:.4f}"
    assert sd["auc"] > 0.5, f"Same-day AUC below 0.5: {sd['auc']:.4f}"
    assert sd["acc"] > 0.50, f"Same-day Acc below 50%: {sd['acc']*100:.2f}%"
    print(f"  ✓ Stage 1 (Table 2) verified: "
          f"F1={sd['f1']:.4f} (paper {paper['f1']:.4f}), "
          f"Acc={sd['acc']*100:.2f}%, AUC={sd['auc']:.4f}")
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
