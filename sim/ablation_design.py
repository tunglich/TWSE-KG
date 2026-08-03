# -*- coding: utf-8 -*-
"""
Design + power simulation for the KG ablations requested in review item 2.

WHAT THIS IS AND IS NOT
-----------------------
This is NOT a substitute for running the ablations on the real corpus, and no
number produced here may be reported in the paper as an experimental result.
Its purpose is to answer three questions BEFORE spending compute:

  Q1  If the 11.5-point lift is genuinely structural, what F1 should each
      ablation return?  If it is pure coverage expansion, what then?
  Q2  Are those two predictions far enough apart to be distinguishable with
      551 held-out days and 50 stocks, given cross-sectional correlation?
  Q3  How many shuffle replicates are needed for a credible null band?

DESIGN RULE (inherited from calibrated_sim.py): every free parameter is pinned
to a quantity already reported in the paper.  Exactly two parameters are fitted
(own-news strength kappa, graph-transmission strength theta) against exactly two
targets (F1_Direct = 0.5309, F1_KG = 0.6456).  F1_MarketWide = 0.5040 is held
back as an out-of-sample check, as the AUC check was in calibrated_sim.py.

THE ABLATION LADDER
-------------------
The review asks for shuffled-edge, sector-only, unweighted-one-hop.  A global
degree-matched shuffle destroys sector alignment as well as firm-specific links,
so on its own it cannot separate "supply-chain link" from "same industry".  We
therefore simulate a four-rung ladder that decomposes the lift additively:

  Direct                       no propagation                    (in paper)
  A1  global shuffle           volume + degree, no structure     <- new
  A2  sector-preserving shuffle volume + degree + sector         <- new
  A3  sector-only propagation  sector membership, uniform wts    <- new
  A4  unweighted one-hop       true topology, no wts, no hop-2   <- new
  KG  full                     typed, weighted, two-hop          (in paper)

  F1(A1) - F1(Direct)  =  pure volume / noise-averaging
  F1(A2) - F1(A1)      =  sector alignment
  F1(KG) - F1(A2)      =  firm-specific link information   <- the contested term
  F1(KG) - F1(A4)      =  value of exposure weights and the second hop

COST NOTE: all four ablations are LLM-free.  Stage-1 anchor scores are cached
per (item, prompt-version); propagation is deterministic post-processing over
that cache.  An ablation re-runs stages 2-5 plus the downstream classifier only.
"""
import numpy as np
from scipy import optimize, stats

RNG_MASTER = np.random.default_rng(20260801)

NFIRM, NSECT, NDAY, NTOP = 576, 12, 551, 50

# ---- anchors taken from the paper ------------------------------------------
F1_DIRECT, F1_KG, F1_WIDE = 0.5309, 0.6456, 0.5040
COV_MULT_TOP50 = 70590 / 55385          # Table 5: 1.2745
COV_MULT_OTHER = 281697 / 63277         # Table 5: 4.4518
TOP50_SHARE_PRE = 55385 / 118662        # Table 5: 0.4667
GAMMA, HOPS = 0.5, 2                    # Section 3.2: fixed ex ante
MEAN_DEG = 2 * 15542 / 9146             # KG: 9,146 nodes, 15,542 relations

f1_of_rho = lambda r: 0.5 + np.arcsin(np.clip(r, -1, 1)) / np.pi
rho_of_f1 = lambda f: np.sin(np.pi * (f - 0.5))


# ============================================================================
# 1.  Analytic bound: can a 1.275x record increase carry 11.5 F1 points?
# ============================================================================
def coverage_only_bound():
    """Pure noise-averaging bound on the Top-50.

    Under the coverage-only hypothesis the extra propagated records carry no
    firm-specific information; they can only sharpen the estimate of whatever
    the direct records already measure.  The most generous version of that
    story is that firm j's score is a mean of n_j i.i.d. noisy readings of the
    same firm-specific quantity, so latent skill scales as

        rho(n) = rho_max * sqrt(n / (n + c))

    Even granting the propagated records the SAME information content per
    record as a direct mention -- which is the most favourable assumption the
    hypothesis can make -- the Top-50 record count rises only 1.275x.
    """
    rho_d, rho_k = rho_of_f1(F1_DIRECT), rho_of_f1(F1_KG)
    # best case: signal-to-noise grows with sqrt(record count), no ceiling
    rho_best = rho_d * np.sqrt(COV_MULT_TOP50)
    f1_best = f1_of_rho(rho_best)
    print("=== 1. coverage-only analytic bound (Top-50) ===")
    print(f"  rho_Direct = {rho_d:.4f}   rho_KG = {rho_k:.4f}")
    print(f"  Top-50 record multiplier from Table 5      : {COV_MULT_TOP50:.4f}x")
    print(f"  best-case F1 from sqrt(n) noise averaging  : {f1_best:.4f}")
    print(f"  F1 actually reported for the KG            : {F1_KG:.4f}")
    print(f"  unexplained by the most generous coverage story: "
          f"{F1_KG - f1_best:+.4f} F1 points")
    print(f"  (non-Top-50 multiplier is {COV_MULT_OTHER:.2f}x, but F1 is not "
          f"measured there)")
    return f1_best


# ============================================================================
# 2.  Structural simulation
# ============================================================================
def build_world(rng):
    """576 firms, 12 sectors, a preferential-attachment KG with the paper's
    mean degree, and a capitalisation-skewed news arrival process."""
    cap = np.sort(rng.lognormal(0, 1.1, NFIRM))[::-1]      # firm 0 = largest
    cap /= cap.sum()
    sector = rng.integers(0, NSECT, NFIRM)
    sector[:NTOP] = rng.integers(0, NSECT, NTOP)

    # preferential attachment, sector-homophilic: real supply chains are
    # denser within a sector but not confined to it
    n_edge = int(round(MEAN_DEG * NFIRM / 2))
    src = rng.choice(NFIRM, n_edge, p=cap)
    pref = cap ** 0.5
    dst = np.empty(n_edge, dtype=int)
    for e in range(n_edge):
        w = pref * np.where(sector == sector[src[e]], 3.0, 1.0)
        w[src[e]] = 0.0
        dst[e] = rng.choice(NFIRM, p=w / w.sum())
    # edge weights: revenue / customer shares, right-skewed and bounded
    alpha = rng.beta(1.6, 4.0, n_edge)
    return dict(cap=cap, sector=sector, src=src, dst=dst, alpha=alpha,
                n_edge=n_edge)


def adjacency(w, src, dst, alpha):
    A = np.zeros((NFIRM, NFIRM))
    np.add.at(A, (src, dst), alpha)
    np.add.at(A, (dst, src), alpha)          # relations are bidirectional
    return A


def prop_matrix(A, hops=HOPS, gamma=GAMMA, cap=50.0):
    """Two-hop propagation with hop decay and a per-path cap, per Section 3.2."""
    P = gamma * A.copy()
    if hops >= 2:
        P += (gamma ** 2) * (A @ A)
    np.fill_diagonal(P, 0.0)
    return np.clip(P, 0, cap)


def degree_matched_shuffle(w, rng, within_sector=False):
    """Double-edge swap preserving each node's degree and the multiset of edge
    weights.  With within_sector=True, swaps are restricted to edge pairs whose
    endpoints share a sector, so sector alignment survives the shuffle."""
    src, dst, sec = w["src"].copy(), w["dst"].copy(), w["sector"]
    ne = len(src)
    for _ in range(20 * ne):                 # 20 sweeps: well past mixing
        i, j = rng.integers(0, ne, 2)
        if i == j:
            continue
        if within_sector and not (sec[dst[i]] == sec[dst[j]]):
            continue
        if src[i] == dst[j] or src[j] == dst[i]:
            continue
        dst[i], dst[j] = dst[j], dst[i]
    return src, dst


def make_scorers(w, rng):
    """The propagation operators for every rung of the ladder."""
    A_true = adjacency(w, w["src"], w["dst"], w["alpha"])
    P = {}
    P["KG"] = prop_matrix(A_true)

    s1, d1 = degree_matched_shuffle(w, rng, within_sector=False)
    P["A1_shuffle_global"] = prop_matrix(adjacency(w, s1, d1, w["alpha"]))

    s2, d2 = degree_matched_shuffle(w, rng, within_sector=True)
    P["A2_shuffle_sector"] = prop_matrix(adjacency(w, s2, d2, w["alpha"]))

    # sector-only: uniform propagation to every same-sector firm, rescaled to
    # carry the same total propagated mass as the true KG so that the contrast
    # is structure, not volume
    S = (w["sector"][:, None] == w["sector"][None, :]).astype(float)
    np.fill_diagonal(S, 0.0)
    P["A3_sector_only"] = S * (P["KG"].sum() / S.sum())

    # unweighted one-hop: true topology, alpha = 1, no second hop
    A_unw = adjacency(w, w["src"], w["dst"], np.ones(w["n_edge"]))
    P["A4_unweighted_1hop"] = prop_matrix(np.minimum(A_unw, 1.0), hops=1)
    return P


def simulate(w, P, kappa, theta, rng, nday=NDAY, n_event_day=190):
    """Generate one held-out window and return macro-F1 on the Top-50 for
    every scorer.  The TRUE return-generating process transmits along the TRUE
    graph; ablations differ only in the operator the SCORER uses."""
    # --- news arrival: anchor drawn with capitalisation skew ---------------
    D = np.zeros((nday, NFIRM))
    n_ev = rng.poisson(n_event_day, nday)
    for t in range(nday):
        a = rng.choice(NFIRM, n_ev[t], p=w["cap"])
        shock = rng.standard_normal(n_ev[t])
        np.add.at(D[t], a, shock)
    covered = D != 0.0

    # --- returns: market + sector + own news + graph-transmitted news ------
    m = rng.standard_normal((nday, 1))
    fs = rng.standard_normal((nday, NSECT))[:, w["sector"]]
    transmitted = D @ P["KG"]
    r = (0.55 * m + 0.45 * fs
         + kappa * D
         + theta * transmitted
         + 1.0 * rng.standard_normal((nday, NFIRM)))
    y = r > 0

    # --- scorers ----------------------------------------------------------
    obs = 0.35                                # scoring noise on the anchor read
    Dn = D + obs * np.abs(D).mean() * rng.standard_normal(D.shape)
    scores = {"Direct": np.where(covered, Dn, 0.0)}
    for k, Pk in P.items():
        scores[k] = np.where(covered, Dn, 0.0) + Dn @ Pk
    scores["MarketWide"] = np.repeat(Dn.sum(1, keepdims=True), NFIRM, axis=1)

    out = {}
    for k, s in scores.items():
        thr = np.median(s[:, :NTOP], axis=0, keepdims=True)   # balanced point
        pred = s[:, :NTOP] > thr
        yt = y[:, :NTOP]
        tp = (pred & yt).sum(0)
        f1 = 2 * tp / np.maximum(2 * tp + (pred & ~yt).sum(0)
                                 + (~pred & yt).sum(0), 1)
        out[k] = f1                                            # per-stock, 50
    return out


def calibrate(w, P, rng):
    """Fit (kappa, theta) so the simulated Direct and KG macro-F1 reproduce the
    two reported anchors.  Two parameters, two targets: exactly identified."""
    def resid(p):
        kappa, theta = np.exp(p)
        acc = []
        for s in range(4):                     # average out MC noise
            o = simulate(w, P, kappa, theta,
                         np.random.default_rng(9000 + s))
            acc.append((o["Direct"].mean(), o["KG"].mean()))
        d, k = np.mean(acc, axis=0)
        return [d - F1_DIRECT, k - F1_KG]

    sol = optimize.root(resid, np.log([0.35, 0.30]), method="hybr",
                        options={"xtol": 1e-4})
    return np.exp(sol.x), sol.success


# ============================================================================
# 3.  Power: can 551 days x 50 stocks separate the two hypotheses?
# ============================================================================
def power(w, P, kappa, theta, reps=40):
    rows = {}
    for s in range(reps):
        o = simulate(w, P, kappa, theta, np.random.default_rng(31000 + s))
        for k, v in o.items():
            rows.setdefault(k, []).append(v.mean())
    return {k: (np.mean(v), np.std(v, ddof=1)) for k, v in rows.items()}


# ============================================================================
def main():
    f1_cov = coverage_only_bound()

    rng = RNG_MASTER
    w = build_world(rng)
    P = make_scorers(w, rng)
    print(f"\n  KG built: {w['n_edge']} edges, mean degree "
          f"{2*w['n_edge']/NFIRM:.2f} (paper: {MEAN_DEG:.2f})")

    print("\n=== 2. calibrating (kappa, theta) to the two reported anchors ===")
    (kappa, theta), ok = calibrate(w, P, rng)
    print(f"  kappa (own-news) = {kappa:.4f}   theta (graph) = {theta:.4f}"
          f"   converged={ok}")

    print("\n=== 3. predicted ablation ladder (mean +- MC sd over 40 windows) ===")
    res = power(w, P, kappa, theta)
    order = ["MarketWide", "Direct", "A1_shuffle_global", "A2_shuffle_sector",
             "A3_sector_only", "A4_unweighted_1hop", "KG"]
    for k in order:
        mu, sd = res[k]
        tag = ""
        if k == "Direct":
            tag = f"   <- paper {F1_DIRECT}"
        if k == "KG":
            tag = f"   <- paper {F1_KG}"
        if k == "MarketWide":
            tag = f"   <- paper {F1_WIDE} (held-out check)"
        print(f"  {k:22s} F1 = {mu:.4f} +- {sd:.4f}{tag}")

    print("\n=== 4. additive decomposition of the 11.5-point lift ===")
    d = lambda a, b: res[a][0] - res[b][0]
    tot = d("KG", "Direct")
    parts = [("pure volume / degree      (A1 - Direct)", d("A1_shuffle_global", "Direct")),
             ("sector alignment          (A2 - A1)    ", d("A2_shuffle_sector", "A1_shuffle_global")),
             ("firm-specific links       (KG - A2)    ", d("KG", "A2_shuffle_sector")),
             ("of which weights + hop 2  (KG - A4)    ", d("KG", "A4_unweighted_1hop"))]
    for name, v in parts[:3]:
        print(f"  {name}  {v:+.4f}   ({100*v/tot:5.1f}% of the lift)")
    print(f"  {parts[3][0]}  {parts[3][1]:+.4f}   (subset of the above)")
    print(f"  {'total  (KG - Direct)':38s}  {tot:+.4f}")

    print("\n=== 5. is the experiment powered? ===")
    sd_kg, sd_a1 = res["KG"][1], res["A1_shuffle_global"][1]
    sep = d("KG", "A1_shuffle_global")
    se_diff = np.hypot(sd_kg, sd_a1)
    print(f"  KG - A1 separation           : {sep:+.4f} F1")
    print(f"  sd of a single-window estimate: {se_diff:.4f}")
    print(f"  implied z on ONE window       : {sep/se_diff:.1f}")
    for R in (1, 5, 10, 20, 50):
        print(f"    R={R:2d} shuffle replicates -> null-band half-width "
              f"{1.96*sd_a1/np.sqrt(R):.4f} F1")
    print("  the held-out window is fixed, so replicates randomise the SHUFFLE,")
    print("  not the data; R is chosen for a stable null band, not for power.")

    print("\n=== 6. free pre-experiment: gain vs coverage regression ===")
    o = simulate(w, P, kappa, theta, np.random.default_rng(777))
    gain = o["KG"] - o["Direct"]
    # per-stock coverage multiplier implied by the propagation operator
    covmult = 1.0 + (P["KG"][:, :NTOP] > 0).sum(0) / np.maximum(
        (P["KG"][:, :NTOP] > 0).sum(0).mean(), 1) * (COV_MULT_TOP50 - 1)
    sl, ic, rv, pv, se = stats.linregress(covmult, gain)
    print(f"  slope {sl:+.4f} (se {se:.4f})  R^2 = {rv**2:.3f}  p = {pv:.3f}")
    print("  Under the coverage hypothesis R^2 should be high and the residual")
    print("  gain near zero.  This regression needs NO new inference: it uses")
    print("  the 50 per-stock gains already reported plus per-stock record")
    print("  counts the pipeline already writes.  Run it first.")


if __name__ == "__main__":
    main()
