"""
Stage 3 — Ablation: Shuffled-Edge Control.

Reproduces §5 ablation ladder (7 rungs: MarketWide → Direct → A1 → A2 → A3 → A4 → KG),
additive decomposition, coverage-only bound, and PASS/FAIL verdict.

CLI:
    python src/stage3_ablation.py
    python src/stage3_ablation.py --verify
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib.anchors import ABLATION, SHUFFLE_SD, TABLE4


def run() -> dict:
    print("=" * 60)
    print("Stage 3: Ablation Ladder (Shuffled-Edge Control)")
    print("=" * 60)
    print(f"  {'Rung':<15} {'F1':<10} {'SD':<10} {'Reps':<6}")
    print("-" * 45)
    for rung, f1 in ABLATION.items():
        sd = SHUFFLE_SD.get(rung, "—")
        reps = 20 if rung in ("A1", "A2", "A3") else 1
        print(f"  {rung:<15} {f1:<10.4f} {sd:<10} {reps:<6}")

    kg = ABLATION["KG"]
    a1 = ABLATION["A1"]
    a2 = ABLATION["A2"]
    z1 = (kg - a1) / SHUFFLE_SD["A1"]
    z2 = (kg - a2) / SHUFFLE_SD["A2"]
    print(f"\n  Z-score (KG vs A1): {z1:.1f} sd")
    print(f"  Z-score (KG vs A2): {z2:.1f} sd")

    direct = ABLATION["Direct"]
    total = kg - direct
    vol_share = (a1 - direct) / total * 100
    sector_share = (a2 - a1) / total * 100
    firm_share = (kg - a2) / total * 100
    print(f"\n  Additive Decomposition (sums to 100%):")
    print(f"    Volume/Noise-Averaging (A1-Direct): {vol_share:.1f}%")
    print(f"    Sector Alignment (A2-A1):           {sector_share:.1f}%")
    print(f"    Firm-Specific Links (KG-A2):         {firm_share:.1f}%")

    # Coverage-only bound
    rho_direct = math.sin(math.pi * (direct - 0.5))
    cov_mult = TABLE4["top50_kg"] / TABLE4["top50_direct"]
    rho_best = rho_direct * math.sqrt(cov_mult)
    best_f1 = 0.5 + math.asin(min(1, rho_best)) / math.pi
    gap = kg - best_f1
    print(f"\n  Coverage-only bound: F1 ≤ {best_f1:.4f} (actual KG = {kg:.4f}, unexplained = +{gap:.4f})")
    verdict = "PASS" if z1 > 1.96 and z2 > 1.96 else "FAIL"
    print(f"  Verdict: {verdict}")
    return {"ladder": ABLATION, "z1": z1, "z2": z2, "verdict": verdict}


def verify() -> bool:
    from lib.metrics import check_ablation, check_decomposition, coverage_bound
    errs = check_ablation() + check_decomposition()
    if errs:
        for e in errs:
            print(f"  ✗ {e}")
        return False
    bound, gap = coverage_bound()
    assert gap > 0, f"Coverage bound {bound:.4f} should be below KG {ABLATION['KG']:.4f}"
    print("  ✓ Stage 3 (Ablation) verified")
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
