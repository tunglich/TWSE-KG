# -*- coding: utf-8 -*-
"""
Focused design simulation for ONE experiment: the degree-matched random edge
shuffle (rung A1) and its sector-preserving variant (rung A2).

WHAT THIS IS AND IS NOT
-----------------------
A design study run BEFORE the real ablation, to answer three questions that
determine whether the experiment is worth running and how to pre-register it.
No number produced here may be reported in the paper as a result.

  Q1  What is the correct null band?  In the real experiment the held-out
      window is FIXED and only the shuffle is random, so the null band must be
      the spread of F1(A1) across R independent shuffle realisations on that
      one window -- not the spread across resampled windows.  ablation_design.py
      used a single shuffle and 40 windows, which answers a different question.

  Q2  How large is KG - A1 relative to that band?

  Q3  Under what conditions does A1 look like a WEAK baseline (good for the
      paper) versus a STRONG one (bad for the paper)?  The driver is how much
      of the return variance is common factor: a random graph still aggregates
      market-wide news, so the more common-factor structure the real returns
      carry, the more of the lift a random graph reproduces.  We sweep the
      market-factor loading and report the A1 share of the lift at each level.

DESIGN RULE: unchanged from calibrated_sim.py / ablation_design.py.  Two free
parameters (kappa, theta) fitted to two reported anchors (F1_Direct = 0.5309,
F1_KG = 0.6456); F1_MarketWide = 0.5040 held back as an out-of-sample check.
"""
import time
import numpy as np
from scipy import optimize

import ablation_design as AD
from ablation_design import (NFIRM, NSECT, NDAY, NTOP, F1_DIRECT, F1_KG,
                             F1_WIDE, build_world, adjacency, prop_matrix,
                             degree_matched_shuffle)

BETA_M_BASE, BETA_S_BASE = 0.55, 0.45      # market and sector loadings
R_SHUFFLE = 20                             # replicate shuffles per condition


# ---------------------------------------------------------------------------
# data generation and scoring, separated so the window can be held fixed
# ---------------------------------------------------------------------------
def gen_window(w, P_kg, kappa, theta, rng, beta_m=BETA_M_BASE,
               beta_s=BETA_S_BASE, nday=NDAY, n_event_day=190):
    """One held-out window.  Returns transmit along the TRUE graph."""
    D = np.zeros((nday, NFIRM))
    n_ev = rng.poisson(n_event_day, nday)
    for t in range(nday):
        a = rng.choice(NFIRM, n_ev[t], p=w["cap"])
        np.add.at(D[t], a, rng.standard_normal(n_ev[t]))
    covered = D != 0.0

    m = rng.standard_normal((nday, 1))
    fs = rng.standard_normal((nday, NSECT))[:, w["sector"]]
    r = (beta_m * m + beta_s * fs + kappa * D + theta * (D @ P_kg)
         + rng.standard_normal((nday, NFIRM)))
    y = r > 0

    obs = 0.35
    Dn = D + obs * np.abs(D).mean() * rng.standard_normal(D.shape)
    Dn = np.where(covered, Dn, 0.0)
    return dict(Dn=Dn, y=y)


def f1_of(win, P=None):
    """Macro-F1 over the Top-50 at the balanced operating point."""
    s = win["Dn"] if P is None else win["Dn"] + win["Dn"] @ P
    s = s[:, :NTOP]
    thr = np.median(s, axis=0, keepdims=True)
    pred, yt = s > thr, win["y"][:, :NTOP]
    tp = (pred & yt).sum(0)
    return 2 * tp / np.maximum(2 * tp + (pred & ~yt).sum(0)
                               + (~pred & yt).sum(0), 1)


def calibrate(w, P_kg, beta_m, beta_s, nseed=3):
    def resid(p):
        kappa, theta = np.exp(p)
        acc = []
        for s in range(nseed):
            win = gen_window(w, P_kg, kappa, theta,
                             np.random.default_rng(9000 + s), beta_m, beta_s)
            acc.append((f1_of(win).mean(), f1_of(win, P_kg).mean()))
        d, k = np.mean(acc, axis=0)
        return [d - F1_DIRECT, k - F1_KG]
    sol = optimize.root(resid, np.log([0.35, 0.30]), method="hybr",
                        options={"xtol": 2e-4})
    return np.exp(sol.x), sol.success


def shuffled_ops(w, rng, R, within_sector):
    for _ in range(R):
        s, d = degree_matched_shuffle(w, rng, within_sector=within_sector)
        yield prop_matrix(adjacency(w, s, d, w["alpha"]))


# ---------------------------------------------------------------------------
def main():
    t0 = time.time()
    rng = AD.RNG_MASTER
    w = build_world(rng)
    P_kg = prop_matrix(adjacency(w, w["src"], w["dst"], w["alpha"]))
    print(f"world: {w['n_edge']} edges, mean degree "
          f"{2*w['n_edge']/NFIRM:.2f}, {NFIRM} firms, {NSECT} sectors")

    # ---- 1. calibrate at the base loadings --------------------------------
    (kappa, theta), ok = calibrate(w, P_kg, BETA_M_BASE, BETA_S_BASE)
    print(f"\n=== 1. calibration (beta_m={BETA_M_BASE}) ===")
    print(f"  kappa={kappa:.4f}  theta={theta:.4f}  converged={ok}")

    # ---- 2. THE null band: fixed window, R independent shuffles -----------
    print(f"\n=== 2. null band on a FIXED window, R={R_SHUFFLE} shuffles ===")
    win = gen_window(w, P_kg, kappa, theta, np.random.default_rng(4242),
                     BETA_M_BASE, BETA_S_BASE)
    f_direct = f1_of(win).mean()
    f_kg = f1_of(win, P_kg).mean()
    f_wide = f1_of({"Dn": np.repeat(win["Dn"].sum(1, keepdims=True), NFIRM, 1),
                    "y": win["y"]}).mean()

    rs = np.random.default_rng(555)
    a1 = np.array([f1_of(win, P).mean()
                   for P in shuffled_ops(w, rs, R_SHUFFLE, False)])
    a2 = np.array([f1_of(win, P).mean()
                   for P in shuffled_ops(w, rs, R_SHUFFLE, True)])

    print(f"  Direct                 {f_direct:.4f}   (paper {F1_DIRECT})")
    print(f"  MarketWide             {f_wide:.4f}   (paper {F1_WIDE}, held out)")
    print(f"  A1 global shuffle      {a1.mean():.4f}  sd {a1.std(ddof=1):.4f}"
          f"   range [{a1.min():.4f}, {a1.max():.4f}]")
    print(f"  A2 sector shuffle      {a2.mean():.4f}  sd {a2.std(ddof=1):.4f}"
          f"   range [{a2.min():.4f}, {a2.max():.4f}]")
    print(f"  KG (true graph)        {f_kg:.4f}   (paper {F1_KG})")

    hi1 = a1.mean() + 1.96 * a1.std(ddof=1)
    hi2 = a2.mean() + 1.96 * a2.std(ddof=1)
    print(f"\n  A1 null band upper edge (mean+1.96sd) : {hi1:.4f}")
    print(f"  KG - A1  = {f_kg - a1.mean():+.4f}  -> "
          f"{(f_kg - a1.mean())/a1.std(ddof=1):.1f} shuffle-sd above the null")
    print(f"  A2 null band upper edge               : {hi2:.4f}")
    print(f"  KG - A2  = {f_kg - a2.mean():+.4f}  -> "
          f"{(f_kg - a2.mean())/a2.std(ddof=1):.1f} shuffle-sd above the null")
    print(f"  verdict: KG {'CLEARS' if f_kg > hi2 else 'DOES NOT CLEAR'} the "
          f"harder (A2) null band.")

    # ---- 3. what fraction of the lift does a random graph already buy? ----
    tot = f_kg - f_direct
    print(f"\n=== 3. share of the {tot:+.4f} lift captured by each rung ===")
    print(f"  A1 - Direct (volume only)   {a1.mean()-f_direct:+.4f}"
          f"   {100*(a1.mean()-f_direct)/tot:5.1f}% of the lift")
    print(f"  A2 - A1     (sector)        {a2.mean()-a1.mean():+.4f}"
          f"   {100*(a2.mean()-a1.mean())/tot:5.1f}%")
    print(f"  KG - A2     (firm links)    {f_kg-a2.mean():+.4f}"
          f"   {100*(f_kg-a2.mean())/tot:5.1f}%  <- the contested term")

    # ---- 4. sensitivity: how common-factor structure drives A1 ------------
    print("\n=== 4. sensitivity of the A1 share to the common-factor loading ===")
    print("  A random graph still aggregates market-wide news.  The more of the")
    print("  return variance is common factor, the stronger the A1 baseline and")
    print("  the worse the experiment looks for the paper.")
    print(f"  {'beta_m':>7} {'R2_common':>10} {'Direct':>8} {'A1':>8} {'KG':>8}"
          f" {'KG-A1':>8} {'A1 share':>9} {'z_shuf':>7}")
    for bm in (0.15, 0.35, 0.55, 0.75, 0.95):
        (kp, th), _ = calibrate(w, P_kg, bm, BETA_S_BASE)
        wn = gen_window(w, P_kg, kp, th, np.random.default_rng(4242),
                        bm, BETA_S_BASE)
        fd, fk = f1_of(wn).mean(), f1_of(wn, P_kg).mean()
        rr = np.random.default_rng(555)
        aa = np.array([f1_of(wn, P).mean()
                       for P in shuffled_ops(w, rr, 8, False)])
        share = (aa.mean() - fd) / (fk - fd)
        r2 = (bm**2 + BETA_S_BASE**2) / (bm**2 + BETA_S_BASE**2 + 1.0)
        print(f"  {bm:7.2f} {r2:10.2f} {fd:8.4f} {aa.mean():8.4f} {fk:8.4f}"
              f" {fk-aa.mean():+8.4f} {100*share:8.1f}% "
              f"{(fk-aa.mean())/max(aa.std(ddof=1),1e-6):7.1f}")

    print(f"\n[elapsed {time.time()-t0:.0f}s]  DESIGN SIMULATION ONLY -- "
          f"no number here is an experimental result.")


if __name__ == "__main__":
    main()
