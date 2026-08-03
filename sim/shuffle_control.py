# -*- coding: utf-8 -*-
"""
Full simulation of the shuffled-edge CONTROL exactly as the paper pre-registers
it, in a world calibrated to Taiwan's news concentration.

WHY THIS RUN EXISTS
-------------------
shuffle_mechanism.py established that the outcome of the control hinges on one
quantity: how much of the transmitted signal a degree-preserving rewire
reproduces.  It also showed the risky regime is a STEEP size distribution, which
is the Taiwan case.  But that run guessed the steepness.  This one does not.

CALIBRATION ANCHOR (no guessing): Table 4 of the paper reports that 55,385 of
118,662 pre-propagation records accrue to the Top 50 of 576 firms  ---  46.67%.
News arrival in the model is capitalisation-weighted, so that single reported
number pins the size distribution.  We solve for the lognormal sigma that
reproduces it instead of choosing one.

WHAT IT PRODUCES
----------------
  1. the reporting table the paper would print, with fixed-window null bands
  2. the additive decomposition of the lift
  3. a LOOKUP TABLE mapping the pre-check statistic (transmitted-signal
     correlation, which precheck_shuffle.py measures on the real data in
     minutes) to the predicted KG - A1 separation.  That converts the three
     coarse verdict bands into a quantitative forecast.

DESIGN SIMULATION ONLY.  No number here may be reported as a result.  Its role
is to decide whether to run the real control and how to frame it.
"""
import numpy as np
from scipy import optimize

import ablation_design as AD
from ablation_design import (NFIRM, NSECT, NTOP, F1_DIRECT, F1_KG, F1_WIDE,
                             adjacency, prop_matrix, degree_matched_shuffle)
from shuffle_test import gen_window, f1_of, calibrate

TOP50_SHARE_PRE = 55385 / 118662          # Table 4: 0.4667  <- the anchor
MEAN_DEG = AD.MEAN_DEG
R = 20                                    # shuffle replicates for the null band


def sigma_for_top50_share(target=TOP50_SHARE_PRE, n=NFIRM, k=NTOP):
    """Lognormal sigma such that the largest k of n firms carry `target` of the
    news mass.  Solved, not chosen."""
    def share(sig):
        rng = np.random.default_rng(11)
        acc = []
        for _ in range(12):
            c = np.sort(rng.lognormal(0, sig, n))[::-1]
            acc.append(c[:k].sum() / c.sum())
        return np.mean(acc) - target
    return optimize.brentq(share, 0.05, 4.0, xtol=1e-3)


def build(rng, sigma_cap, pa_exp=0.5, homoph=3.0):
    cap = np.sort(rng.lognormal(0, sigma_cap, NFIRM))[::-1]
    cap /= cap.sum()
    sector = rng.integers(0, NSECT, NFIRM)
    ne = int(round(MEAN_DEG * NFIRM / 2))
    src = rng.choice(NFIRM, ne, p=cap)
    pref = cap ** pa_exp
    dst = np.empty(ne, dtype=int)
    for e in range(ne):
        wg = pref * np.where(sector == sector[src[e]], homoph, 1.0)
        wg[src[e]] = 0.0
        dst[e] = rng.choice(NFIRM, p=wg / wg.sum())
    return dict(cap=cap, sector=sector, src=src, dst=dst,
                alpha=rng.beta(1.6, 4.0, ne), n_edge=ne)


def ladder(w, seed_shuf=555, reps=R):
    """Every rung of the pre-registered control, plus the pre-check statistic."""
    P_kg = prop_matrix(adjacency(w, w["src"], w["dst"], w["alpha"]))
    (kp, th), ok = calibrate(w, P_kg, 0.55, 0.45)
    win = gen_window(w, P_kg, kp, th, np.random.default_rng(4242), 0.55, 0.45)

    out = {"Direct": np.array([f1_of(win).mean()]),
           "KG": np.array([f1_of(win, P_kg).mean()])}
    out["MarketWide"] = np.array([f1_of(
        {"Dn": np.repeat(win["Dn"].sum(1, keepdims=True), NFIRM, 1),
         "y": win["y"]}).mean()])

    rng = np.random.default_rng(seed_shuf)
    T_true = win["Dn"] @ P_kg
    cors = []
    for tag, sec in (("A1_shuffle_global", None),
                     ("A2_shuffle_sector", w["sector"])):
        vals = []
        for _ in range(reps):
            s, d = degree_matched_shuffle(w, rng, within_sector=(sec is not None))
            Ps = prop_matrix(adjacency(w, s, d, w["alpha"]))
            vals.append(f1_of(win, Ps).mean())
            if sec is None:
                T_r = win["Dn"] @ Ps
                cors += [np.corrcoef(T_true[:, j], T_r[:, j])[0, 1]
                         for j in range(NTOP)
                         if T_true[:, j].std() > 0 and T_r[:, j].std() > 0]
        out[tag] = np.array(vals)

    # A4: true topology, unweighted, one hop -- weights and hop 2 removed
    A_unw = adjacency(w, w["src"], w["dst"], np.ones(w["n_edge"]))
    out["A4_unweighted_1hop"] = np.array(
        [f1_of(win, prop_matrix(np.minimum(A_unw, 1.0), hops=1)).mean()])
    return out, float(np.mean(cors)), (kp, th, ok)


def main():
    sig = sigma_for_top50_share()
    print("=== 0. calibrating the size distribution to Table 4 ===")
    print(f"  target Top-50 share of pre-propagation records : "
          f"{100*TOP50_SHARE_PRE:.2f}%  (55,385 / 118,662)")
    print(f"  solved lognormal sigma                          : {sig:.3f}")

    w = build(np.random.default_rng(20260801), sig)
    deg = np.bincount(np.concatenate([w["src"], w["dst"]]), minlength=NFIRM)
    print(f"  world: {w['n_edge']} edges, mean degree "
          f"{2*w['n_edge']/NFIRM:.2f}, degree Herfindahl "
          f"{(lambda p: (p**2).sum()*len(p))(deg/deg.sum()):.2f}")

    res, cor, (kp, th, ok) = ladder(w)
    print(f"  fitted kappa={kp:.4f} theta={th:.4f} converged={ok}")

    print(f"\n=== 1. the reporting table (null bands over R={R} rewirings of a "
          f"FIXED window) ===")
    print(f"  {'rung':22s} {'F1':>8} {'shuffle sd':>11} {'95% band':>18}")
    for k in ["MarketWide", "Direct", "A1_shuffle_global", "A2_shuffle_sector",
              "A4_unweighted_1hop", "KG"]:
        v = res[k]
        if len(v) > 1:
            sd = v.std(ddof=1)
            band = f"[{v.mean()-1.96*sd:.4f}, {v.mean()+1.96*sd:.4f}]"
            print(f"  {k:22s} {v.mean():8.4f} {sd:11.4f} {band:>18}")
        else:
            note = {"Direct": f"paper {F1_DIRECT}", "KG": f"paper {F1_KG}",
                    "MarketWide": f"paper {F1_WIDE}, held out"}.get(k, "")
            print(f"  {k:22s} {v.mean():8.4f} {'--':>11} {'--':>18}   {note}")

    a1, a2 = res["A1_shuffle_global"], res["A2_shuffle_sector"]
    fk, fd = res["KG"].mean(), res["Direct"].mean()
    print(f"\n  KG - A1 = {fk-a1.mean():+.4f}  "
          f"({(fk-a1.mean())/a1.std(ddof=1):.1f} shuffle-sd)   "
          f"KG {'OUTSIDE' if fk > a1.mean()+1.96*a1.std(ddof=1) else 'INSIDE'} "
          f"the A1 band")
    print(f"  KG - A2 = {fk-a2.mean():+.4f}  "
          f"({(fk-a2.mean())/a2.std(ddof=1):.1f} shuffle-sd)   "
          f"KG {'OUTSIDE' if fk > a2.mean()+1.96*a2.std(ddof=1) else 'INSIDE'} "
          f"the A2 band")

    tot = fk - fd
    print(f"\n=== 2. decomposition of the {tot:+.4f} lift ===")
    print(f"  volume / degree     (A1 - Direct) {a1.mean()-fd:+.4f}"
          f"  {100*(a1.mean()-fd)/tot:5.1f}%")
    print(f"  sector alignment    (A2 - A1)     {a2.mean()-a1.mean():+.4f}"
          f"  {100*(a2.mean()-a1.mean())/tot:5.1f}%")
    print(f"  firm-specific links (KG - A2)     {fk-a2.mean():+.4f}"
          f"  {100*(fk-a2.mean())/tot:5.1f}%   <- the contested term")
    print(f"  weights + 2nd hop   (KG - A4)     "
          f"{fk-res['A4_unweighted_1hop'].mean():+.4f}  (subset of the above)")
    print(f"\n  pre-check statistic in this world: mean transmitted-signal "
          f"correlation = {cor:+.3f}")

    # ---- 3. lookup table: pre-check correlation -> predicted separation ----
    print("\n=== 3. lookup: pre-check correlation -> predicted KG - A1 ===")
    print("  Sweeping the size distribution moves both quantities together.")
    print("  Run precheck_shuffle.py on the real data, find your correlation in")
    print("  the left column, read the expected separation on the right.")
    print(f"  {'sigma':>6} {'Top50 share':>12} {'pre-check corr':>15} "
          f"{'KG-A1':>8} {'A1 share':>9} {'shuffle-sd':>11}")
    for s in (0.6, 0.9, 1.1, sig, 1.6, 2.0, 2.5):
        ww = build(np.random.default_rng(20260801), s)
        rr, cc, _ = ladder(ww, reps=8)
        aa, kk, dd = rr["A1_shuffle_global"], rr["KG"].mean(), rr["Direct"].mean()
        z = (kk - aa.mean()) / max(aa.std(ddof=1), 1e-9)
        mark = "  <- calibrated" if abs(s - sig) < 1e-6 else ""
        print(f"  {s:6.2f} {100*ww['cap'][:NTOP].sum():11.1f}% {cc:+15.3f} "
              f"{kk-aa.mean():+8.4f} {100*(aa.mean()-dd)/(kk-dd):8.1f}% "
              f"{z:11.1f}{mark}")

    print("\nDESIGN SIMULATION ONLY -- no number here is an experimental result.")


if __name__ == "__main__":
    main()
