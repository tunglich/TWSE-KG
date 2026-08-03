# -*- coding: utf-8 -*-
"""
Addendum to shuffle_test.py: WHY does a degree-matched random graph already
capture ~2/3 of the simulated lift, and what does that imply for the real run?

The sweep in shuffle_test.py section 4 falsified my first explanation: the A1
share is flat (~66-68%) across market-factor loadings from 0.15 to 0.95, so the
common market factor is NOT the driver.  The remaining candidate is HUB
DOMINANCE: a degree-matched shuffle preserves every node's degree, so the hub
firms stay hubs.  If the true transmitted signal (D @ P_KG) is dominated by news
originating at a handful of high-degree, high-capitalisation firms, then a
random graph with the same degree sequence loads on the SAME news and inherits
most of the signal, regardless of who is wired to whom.

Two tests:
  A  measure corr( (D @ P_KG)[:, j] , (D @ P_A1)[:, j] ) across the Top 50
  B  vary hub concentration (the capitalisation dispersion and the preferential-
     attachment exponent) and see whether the A1 share tracks it

DESIGN SIMULATION ONLY.  No number here may be reported as a result.
"""
import numpy as np
from scipy import optimize

import ablation_design as AD
from ablation_design import (NFIRM, NSECT, NTOP, F1_DIRECT, F1_KG,
                             adjacency, prop_matrix, degree_matched_shuffle)
from shuffle_test import gen_window, f1_of, calibrate, shuffled_ops

MEAN_DEG = AD.MEAN_DEG


def build_world_cfg(rng, sigma_cap=1.1, pa_exp=0.5, homoph=3.0):
    """build_world with the hub-concentration knobs exposed."""
    cap = np.sort(rng.lognormal(0, sigma_cap, NFIRM))[::-1]
    cap /= cap.sum()
    sector = rng.integers(0, NSECT, NFIRM)
    n_edge = int(round(MEAN_DEG * NFIRM / 2))
    src = rng.choice(NFIRM, n_edge, p=cap)
    pref = cap ** pa_exp
    dst = np.empty(n_edge, dtype=int)
    for e in range(n_edge):
        wgt = pref * np.where(sector == sector[src[e]], homoph, 1.0)
        wgt[src[e]] = 0.0
        dst[e] = rng.choice(NFIRM, p=wgt / wgt.sum())
    alpha = rng.beta(1.6, 4.0, n_edge)
    return dict(cap=cap, sector=sector, src=src, dst=dst, alpha=alpha,
                n_edge=n_edge)


def herfindahl(x):
    p = x / x.sum()
    return float((p ** 2).sum() * len(p))      # 1 = uniform, higher = concentrated


def run(sigma_cap, pa_exp, homoph, label, R=8, verbose=False):
    rng = np.random.default_rng(20260801)
    w = build_world_cfg(rng, sigma_cap, pa_exp, homoph)
    P_kg = prop_matrix(adjacency(w, w["src"], w["dst"], w["alpha"]))
    (kp, th), ok = calibrate(w, P_kg, 0.55, 0.45)
    win = gen_window(w, P_kg, kp, th, np.random.default_rng(4242), 0.55, 0.45)
    fd, fk = f1_of(win).mean(), f1_of(win, P_kg).mean()

    rr = np.random.default_rng(555)
    Ps = list(shuffled_ops(w, rr, R, False))
    aa = np.array([f1_of(win, P).mean() for P in Ps])

    # test A: how much of the TRUE transmitted signal survives a random rewire?
    T_true = win["Dn"] @ P_kg
    cors = []
    for P in Ps:
        T_rand = win["Dn"] @ P
        for j in range(NTOP):
            a, b = T_true[:, j], T_rand[:, j]
            if a.std() > 0 and b.std() > 0:
                cors.append(np.corrcoef(a, b)[0, 1])
    cor = float(np.mean(cors))

    deg = np.bincount(np.concatenate([w["src"], w["dst"]]), minlength=NFIRM)
    hh_deg, hh_cap = herfindahl(deg.astype(float) + 1e-9), herfindahl(w["cap"])
    share = (aa.mean() - fd) / (fk - fd)
    print(f"  {label:26s} HH_cap={hh_cap:5.1f} HH_deg={hh_deg:5.1f} "
          f"corr={cor:+.3f}  Direct={fd:.4f} A1={aa.mean():.4f} KG={fk:.4f}"
          f"  A1share={100*share:5.1f}%  KG-A1={fk-aa.mean():+.4f}")
    return share, cor, hh_deg


def main():
    print("=== A/B. hub concentration vs the A1 share (design simulation) ===")
    print("  HH = normalised Herfindahl (1 = uniform).  corr = mean per-stock")
    print("  correlation between the TRUE transmitted signal and the signal a")
    print("  degree-matched RANDOM graph produces on the same news stream.\n")

    rows = []
    rows.append(run(1.1, 0.5, 3.0, "baseline (as in paper sim)"))
    rows.append(run(0.4, 0.5, 3.0, "flat caps  sigma=0.4"))
    rows.append(run(1.8, 0.5, 3.0, "steep caps sigma=1.8"))
    rows.append(run(1.1, 0.0, 3.0, "no pref. attachment"))
    rows.append(run(1.1, 1.0, 3.0, "strong pref. attachment"))
    rows.append(run(1.1, 0.5, 1.0, "no sector homophily"))
    rows.append(run(1.1, 0.5, 8.0, "strong sector homophily"))

    sh = np.array([r[0] for r in rows])
    co = np.array([r[1] for r in rows])
    hd = np.array([r[2] for r in rows])
    print(f"\n  A1 share range across configurations: "
          f"{100*sh.min():.1f}% - {100*sh.max():.1f}%")
    print(f"  corr(A1 share, transmitted-signal correlation) = "
          f"{np.corrcoef(sh, co)[0,1]:+.3f}")
    print(f"  corr(A1 share, degree Herfindahl)              = "
          f"{np.corrcoef(sh, hd)[0,1]:+.3f}")
    print("\n  READ: the A1 share is governed by how much of the transmitted")
    print("  signal a degree-preserving rewire reproduces.  In the real KG the")
    print("  analogous quantity is measurable BEFORE running the classifier:")
    print("  compute S_true = A_scores @ P_KG and S_rand = A_scores @ P_shuf on")
    print("  the cached Stage-1 anchors and correlate them per stock.  That is a")
    print("  minutes-long check and it forecasts the outcome of the whole")
    print("  experiment.  Run it before committing to the full ablation.")
    print("\nDESIGN SIMULATION ONLY -- no number here is an experimental result.")


if __name__ == "__main__":
    main()
