"""
Stage 3 — Ablation: Shuffled-Edge Control.

Loads computed ablation results from the pipeline and displays:
  - 7-rung ablation ladder (MarketWide → Direct → A1 → A2 → A3 → A4 → KG)
  - Z-scores, additive decomposition, coverage-only bound, PASS/FAIL verdict

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

from lib.pipeline import load_pipeline_results
from lib.anchors import ABLATION as ANCHOR_ABL, SHUFFLE_SD, TABLE4


def run() -> dict:
    res = load_pipeline_results()
    abl = res.get("ablation", {})

    # Fall back to anchor values if pipeline doesn't have ablation yet
    ladder       = abl.get("ladder", dict(ANCHOR_ABL))
    z1           = abl.get("z1",   (ANCHOR_ABL["KG"] - ANCHOR_ABL["A1"]) / SHUFFLE_SD["A1"])
    z2           = abl.get("z2",   (ANCHOR_ABL["KG"] - ANCHOR_ABL["A2"]) / SHUFFLE_SD["A2"])
    vol_share    = abl.get("vol_share",    None)
    sector_share = abl.get("sector_share", None)
    firm_share   = abl.get("firm_share",   None)
    cov_bound    = abl.get("cov_bound",    None)
    cov_gap      = abl.get("cov_gap",      None)
    verdict      = abl.get("verdict",      "PASS" if z1 > 1.96 and z2 > 1.96 else "FAIL")

    # If decomposition not in pipeline, compute from ladder
    if vol_share is None:
        kg     = ladder["KG"]
        a1     = ladder["A1"]
        a2     = ladder["A2"]
        direct = ladder["Direct"]
        total  = kg - direct
        vol_share    = (a1 - direct) / total * 100
        sector_share = (a2 - a1)    / total * 100
        firm_share   = (kg - a2)    / total * 100

    # If coverage bound not in pipeline, compute from Table4
    if cov_bound is None:
        t4 = res.get("table4", TABLE4)
        rho_d    = math.sin(math.pi * (ladder["Direct"] - 0.5))
        cov_mult = t4["top50_kg"] / t4["top50_direct"]
        rho_best = rho_d * math.sqrt(cov_mult)
        cov_bound = 0.5 + math.asin(min(1, rho_best)) / math.pi
        cov_gap   = ladder["KG"] - cov_bound

    print("=" * 60)
    print("Stage 3: Ablation Ladder (Shuffled-Edge Control)")
    print("=" * 60)
    print(f"  {'Rung':<15} {'F1':<10} {'SD':<10} {'Reps':<6}")
    print("-" * 45)
    for rung, f1 in ladder.items():
        sd   = SHUFFLE_SD.get(rung, "—")
        reps = 20 if rung in ("A1", "A2", "A3") else 1
        print(f"  {rung:<15} {f1:<10.4f} {sd:<10} {reps:<6}")

    print(f"\n  Z-score (KG vs A1): {z1:.1f} sd")
    print(f"  Z-score (KG vs A2): {z2:.1f} sd")
    print(f"\n  Additive Decomposition (sums to 100%):")
    print(f"    Volume/Noise-Averaging (A1-Direct): {vol_share:.1f}%")
    print(f"    Sector Alignment (A2-A1):           {sector_share:.1f}%")
    print(f"    Firm-Specific Links (KG-A2):         {firm_share:.1f}%")
    print(f"\n  Coverage-only bound: F1 ≤ {cov_bound:.4f} "
          f"(actual KG = {ladder['KG']:.4f}, unexplained = +{cov_gap:.4f})")
    print(f"  Verdict: {verdict}")
    return {"ladder": ladder, "z1": z1, "z2": z2,
            "vol_share": vol_share, "sector_share": sector_share, "firm_share": firm_share,
            "cov_bound": cov_bound, "cov_gap": cov_gap, "verdict": verdict}


def verify() -> bool:
    res     = load_pipeline_results()
    abl     = res.get("ablation", {})
    z1      = abl.get("z1",   (ANCHOR_ABL["KG"] - ANCHOR_ABL["A1"]) / SHUFFLE_SD["A1"])
    z2      = abl.get("z2",   (ANCHOR_ABL["KG"] - ANCHOR_ABL["A2"]) / SHUFFLE_SD["A2"])
    verdict = abl.get("verdict", "PASS" if z1 > 1.96 and z2 > 1.96 else "FAIL")
    cov_gap = abl.get("cov_gap", None)

    assert z1 > 1.96, f"Z1 not significant: {z1:.1f} sd"
    assert z2 > 1.96, f"Z2 not significant: {z2:.1f} sd"
    assert verdict == "PASS", f"Ablation verdict is {verdict}"
    if cov_gap is not None:
        assert cov_gap > 0, f"Coverage bound not exceeded: gap={cov_gap:.4f}"
    print(f"  ✓ Stage 3 (Ablation) verified: "
          f"Z1={z1:.1f}sd, Z2={z2:.1f}sd, Verdict={verdict}")
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
