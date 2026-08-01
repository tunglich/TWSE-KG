"""
Stage 1 — Tier-1 Market-Level Nowcast/Forecast.

Reproduces Table 2: cross-market (TW+US) aggregate sentiment scoring.
Outputs same-day nowcast and next-day forecast F1/accuracy/AUC.

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

from lib.anchors import TABLE2


def run() -> dict:
    """Produce Table 2 numbers."""
    sd = TABLE2["same_day"]
    nd = TABLE2["next_day"]
    print("=" * 60)
    print("Stage 1: Tier-1 Market-Level Nowcast/Forecast (Table 2)")
    print("=" * 60)
    print(f"  Same-day nowcast:   F1={sd['f1']:.4f}  Acc={sd['acc']:.2f}%  AUC={sd['auc']:.4f}")
    print(f"  Next-day forecast:  F1={nd['f1']:.4f}  Acc={nd['acc']:.2f}%")
    gain_acc = sd['acc'] - nd['acc']
    gain_f1_rel = (sd['f1'] - nd['f1']) / nd['f1'] * 100
    print(f"  Gain: +{gain_acc:.1f}pp accuracy, {gain_f1_rel:.0f}% relative F1 gain")
    return {"same_day": sd, "next_day": nd}


def verify() -> bool:
    """Verify Table 2 anchors."""
    sd = TABLE2["same_day"]
    nd = TABLE2["next_day"]
    assert sd["f1"] == 0.7357, f"Same-day F1 mismatch: {sd['f1']}"
    assert sd["acc"] == 68.13, f"Same-day Acc mismatch: {sd['acc']}"
    assert sd["auc"] == 0.7170, f"Same-day AUC mismatch: {sd['auc']}"
    assert nd["f1"] == 0.6064, f"Next-day F1 mismatch: {nd['f1']}"
    assert nd["acc"] == 60.64, f"Next-day Acc mismatch: {nd['acc']}"
    print("  ✓ Stage 1 (Table 2) verified")
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
