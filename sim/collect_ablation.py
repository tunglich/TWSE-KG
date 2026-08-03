# -*- coding: utf-8 -*-
"""
collect_ablation.py  --  turn the raw F1 numbers from the ablation ladder into
the reporting table, the null band, the additive decomposition, and the
pre-registered verdict.

INPUT
-----
One CSV, `results.csv`, with columns:

    rung,rep,f1

  rung : Direct | A1 | A2 | A3 | A4 | KG
  rep  : replicate index; 0 for the deterministic rungs (Direct, A4, KG)
  f1   : Top-50 macro-averaged F1 at the balanced operating point

Example:

    rung,rep,f1
    Direct,0,0.5309
    A1,0,0.5921
    A1,1,0.5948
    ...
    A2,0,0.6002
    ...
    A4,0,0.6301
    KG,0,0.6456

USAGE
-----
    python3 collect_ablation.py --results results.csv
    python3 collect_ablation.py --selftest        # synthetic, verifies the maths

WHAT IT PRINTS
--------------
  1. per-rung mean, sd, and replicate count
  2. the primary statistic  F1(KG) - F1(A1)  in units of shuffle sd
  3. the secondary statistic F1(KG) - F1(A2)  (the harder, more honest baseline)
  4. the additive decomposition of the 11.5-point lift
  5. the pre-registered verdict (PASS / AMBIGUOUS / REFUTED)
  6. a ready-to-paste LaTeX table body

THE VERDICT IS PRE-REGISTERED
-----------------------------
It is fixed here, in code, BEFORE the numbers exist, exactly so that it cannot
be tuned to whatever comes out.  The falsification rule from ABLATION_SPEC.md
section 4:

  REFUTED     F1(KG) lies inside the A1 null band (<= 2 sd above its mean).
              The structural claim does not survive; the Discussion must say
              so and the contribution must be reframed as a coverage result.
  AMBIGUOUS   2-4 sd above.  Report the gap with the band; do not lead with it.
  PASS        > 4 sd above AND the A2 gap is also positive beyond 2 sd.
              Report KG - A2 as the headline structural term.

A large KG - A1 with a null or negative KG - A2 means sector alignment, not
firm-level links, is doing the work.  That is a real and reportable finding,
but it is NOT the paper's current claim, so it is called out separately.
"""
import argparse
import sys

import numpy as np
import pandas as pd

RUNGS = ["Direct", "A1", "A2", "A3", "A4", "KG"]
LABEL = {
    "Direct": "LLM-Direct (no propagation)",
    "A1": "A1  global degree-matched shuffle",
    "A2": "A2  sector-preserving shuffle",
    "A3": "A3  sector-only, mass-matched",
    "A4": "A4  true topology, unweighted, 1 hop",
    "KG": "KG  typed, weighted, two-hop (full)",
}
TEX_LABEL = {
    "Direct": r"LLM-Direct (no propagation)",
    "A1": r"A1: degree-matched shuffle",
    "A2": r"A2: sector-preserving shuffle",
    "A3": r"A3: sector-only, mass-matched",
    "A4": r"A4: true topology, unweighted, 1 hop",
    "KG": r"KG (full method)",
}


def summarise(df):
    out = {}
    for r in RUNGS:
        v = df.loc[df["rung"] == r, "f1"].to_numpy(float)
        if len(v) == 0:
            continue
        # ddof=1 is the right sd for a finite set of shuffle replicates; with a
        # single deterministic run there is no sampling spread to report.
        sd = float(np.std(v, ddof=1)) if len(v) > 1 else float("nan")
        out[r] = dict(mean=float(np.mean(v)), sd=sd, n=len(v))
    return out


def sd_units(point, band):
    """How far `point` sits above a null band, in band standard deviations."""
    if band is None or not np.isfinite(band["sd"]) or band["sd"] <= 0:
        return float("nan")
    return (point - band["mean"]) / band["sd"]


def verdict(z1, z2):
    if not np.isfinite(z1):
        return "INCONCLUSIVE", ("A1 has fewer than two replicates, so there is "
                               "no null band. Run at least R = 10.")
    if z1 <= 2:
        return "REFUTED", (
            "F1(KG) lies inside the A1 null band. A degree-matched random graph "
            "reproduces the lift, so the gain is coverage/volume, not real "
            "links. Reframe the contribution and say so in the Discussion.")
    if z1 <= 4:
        return "AMBIGUOUS", (
            "F1(KG) is above the A1 band but not decisively. Report the gap "
            "together with the band and do not lead with it; lead with the "
            "coverage arithmetic of section 6 instead.")
    if np.isfinite(z2) and z2 <= 2:
        return "PASS (sector-driven)", (
            "KG beats the global shuffle decisively but not the "
            "sector-preserving one. Sector alignment, not firm-specific links, "
            "carries the signal. This is reportable, but it is NOT the paper's "
            "current claim -- the claim must be narrowed to sector-level "
            "propagation.")
    return "PASS", (
        "KG clears both null bands. Report KG - A2 as the headline structural "
        "term; A1 is the volume control.")


def report(df):
    s = summarise(df)
    missing = [r for r in ("Direct", "A1", "KG") if r not in s]
    if missing:
        sys.exit(f"results file is missing required rung(s): {missing}")

    print("=" * 74)
    print("ABLATION LADDER  --  Top-50 macro-averaged F1, balanced operating point")
    print("=" * 74)
    print(f"{'rung':<40}{'F1':>9}{'sd':>9}{'R':>5}")
    for r in RUNGS:
        if r not in s:
            continue
        sd = "  --   " if not np.isfinite(s[r]["sd"]) else f"{s[r]['sd']:.4f}"
        print(f"{LABEL[r]:<40}{s[r]['mean']:>9.4f}{sd:>9}{s[r]['n']:>5}")

    kg = s["KG"]["mean"]
    direct = s["Direct"]["mean"]
    z1 = sd_units(kg, s["A1"])
    z2 = sd_units(kg, s.get("A2"))

    print("\n" + "-" * 74)
    print("TEST STATISTICS")
    print("-" * 74)
    print(f"  primary    F1(KG) - F1(A1) = {kg - s['A1']['mean']:+.4f}"
          f"   ({z1:.1f} shuffle-sd above the A1 null band)")
    if "A2" in s:
        print(f"  secondary  F1(KG) - F1(A2) = {kg - s['A2']['mean']:+.4f}"
              f"   ({z2:.1f} shuffle-sd above the A2 null band)")

    print("\n" + "-" * 74)
    print("ADDITIVE DECOMPOSITION of the reported lift")
    print("-" * 74)
    total = kg - direct
    rows = []
    if "A1" in s:
        rows.append(("volume / noise-averaging", s["A1"]["mean"] - direct))
    if "A2" in s and "A1" in s:
        rows.append(("sector alignment", s["A2"]["mean"] - s["A1"]["mean"]))
        rows.append(("firm-specific link information  <-- contested",
                     kg - s["A2"]["mean"]))
    else:
        rows.append(("everything above degree-matched volume",
                     kg - s["A1"]["mean"]))
    for name, v in rows:
        share = 100 * v / total if total else float("nan")
        print(f"  {name:<48}{v:+.4f}  ({share:5.1f}% of the lift)")
    print(f"  {'TOTAL  F1(KG) - F1(Direct)':<48}{total:+.4f}")
    if "A4" in s:
        print(f"\n  exposure weights + second hop (KG - A4): "
              f"{kg - s['A4']['mean']:+.4f}")

    v, why = verdict(z1, z2)
    print("\n" + "=" * 74)
    print(f"PRE-REGISTERED VERDICT: {v}")
    print("=" * 74)
    print("  " + why.replace(". ", ".\n  "))

    print("\n" + "-" * 74)
    print("LaTeX table body (paste into the ablation table)")
    print("-" * 74)
    for r in RUNGS:
        if r not in s:
            continue
        if np.isfinite(s[r]["sd"]):
            cell = f"{s[r]['mean']:.4f} $\\pm$ {s[r]['sd']:.4f}"
            rep = f"{s[r]['n']}"
        else:
            cell = f"{s[r]['mean']:.4f}"
            rep = "1"
        print(f"{TEX_LABEL[r]} & {cell} & {rep} \\\\")
    print("\nband note for the caption:")
    if np.isfinite(z1):
        print(f"  A1 null band: {s['A1']['mean']:.4f} $\\pm$ "
              f"{s['A1']['sd']:.4f} over {s['A1']['n']} rewirings of the fixed "
              f"held-out window; the reported KG score sits {z1:.1f} sd above it.")
    return v


def selftest():
    """Synthetic numbers only -- verifies the arithmetic, proves nothing about
    the real graph. These values must never be quoted as a result."""
    rng = np.random.default_rng(0)
    rows = [("Direct", 0, 0.5309), ("KG", 0, 0.6456), ("A4", 0, 0.6301)]
    for i in range(10):
        rows.append(("A1", i, 0.6087 + 0.0028 * rng.standard_normal()))
    for i in range(10):
        rows.append(("A2", i, 0.6124 + 0.0035 * rng.standard_normal()))
    for i in range(10):
        rows.append(("A3", i, 0.5602 + 0.0041 * rng.standard_normal()))
    df = pd.DataFrame(rows, columns=["rung", "rep", "f1"])
    print("*** SELFTEST: synthetic inputs. Not a result. ***\n")
    report(df)
    print("\n*** SELFTEST complete. The numbers above are synthetic. ***")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=None)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return
    if not a.results:
        sys.exit("give --results results.csv, or --selftest")
    df = pd.read_csv(a.results)
    for c in ("rung", "rep", "f1"):
        if c not in df.columns:
            sys.exit(f"results file must have a '{c}' column; got {list(df.columns)}")
    bad = sorted(set(df["rung"]) - set(RUNGS))
    if bad:
        sys.exit(f"unknown rung label(s) {bad}; expected a subset of {RUNGS}")
    report(df)


if __name__ == "__main__":
    main()
