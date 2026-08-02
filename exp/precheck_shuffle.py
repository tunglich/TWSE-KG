#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PRE-CHECK for the degree-matched shuffled-edge ablation (review item 2).

Run this BEFORE committing to the full ablation.  It touches only the cached
Stage-1 anchor scores and the KG edge list.  No LLM calls, no propagation
re-run of stages 3-5, no classifier, no re-labelling.  Minutes, not hours.

WHAT IT MEASURES
----------------
    S_true = anchors @ P_KG                     (true typed weighted 2-hop)
    S_rand = anchors @ P_shuffled               (degree-matched random rewire)

and reports, for each of the 50 evaluation stocks, corr(S_true[:,j], S_rand[:,j])
over the held-out window.  That correlation forecasts the whole experiment:

    mean corr < 0.30   ->  run the full ablation.  A degree-matched random graph
                           carries little of the true transmitted signal, so
                           F1(KG) - F1(A1) should separate cleanly.
    0.30 - 0.70        ->  ambiguous.  Run the full ladder but pre-commit to
                           reporting F1(KG) - F1(A2) as the headline term.
    mean corr > 0.70   ->  the shuffle baseline will absorb most of the lift.
                           Do NOT lead with A1.  Lead with F1(KG) - F1(A2) and
                           with the coverage arithmetic (ABLATION_SPEC section 6),
                           and report A1 as a secondary, honestly-framed number.

Reasoning: a degree-matched shuffle preserves every node's degree, so hub firms
stay hubs.  If the transmitted signal is hub-dominated, a random graph loads on
the same news and inherits most of the signal regardless of who is wired to whom.
The design study (shuffle_mechanism.py) found the A1 share of the lift
ranges 60-106% across plausible worlds, tracking exactly this correlation.
This script measures the real value instead of guessing it.

USAGE
-----
    python3 precheck_shuffle.py --selftest          # verify it runs, synthetic data
    python3 precheck_shuffle.py \
        --edges    kg_edges.csv \
        --anchors  stage1_cache.csv \
        --universe top50.csv \
        --sectors  sectors.csv          # optional; enables the A2 rung
        --out      precheck_out.csv

INPUT CONTRACT (all CSV, header required, ids may be strings or ints)
    --edges     src,dst[,weight]        one row per KG relation
                                        weight defaults to 1.0 if absent
    --anchors   date,node,score         LONG format, one row per scored item-day
                                        (aggregate duplicates by mean; see --agg)
    --universe  node                    the 50 evaluation tickers, one per row
    --sectors   node,sector             optional

Nodes present in --anchors or --universe but absent from --edges are added as
isolated nodes, which is the correct treatment: they receive no propagation.

NOTE ON PARAMETERS: --gamma, --hops and --cap must be set to the SAME values the
reported KG run used (the paper fixes gamma = 0.5, hops = 2 ex ante).  If they
differ, this pre-check does not describe the experiment you are going to run.
"""
import argparse
import sys

import numpy as np

try:
    import pandas as pd
except ImportError:
    sys.exit("pandas required:  pip install pandas")
try:
    import scipy.sparse as sp
except ImportError:
    sys.exit("scipy required:  pip install scipy")


# ---------------------------------------------------------------------------
# graph construction
# ---------------------------------------------------------------------------
def build_adjacency(src, dst, wgt, n):
    """Symmetric weighted adjacency.  Relations are bidirectional; parallel
    edges accumulate, matching the propagation used in the reported run."""
    A = sp.coo_matrix((np.concatenate([wgt, wgt]),
                       (np.concatenate([src, dst]),
                        np.concatenate([dst, src]))), shape=(n, n)).tocsr()
    A.setdiag(0.0)
    A.eliminate_zeros()
    return A


def prop_matrix(A, gamma, hops, cap):
    """P = gamma*A + gamma^2*A@A, zero diagonal, capped.  Sparse throughout:
    a dense 9,146 x 9,146 float64 matrix is 669 MB and is not needed."""
    P = (gamma * A).tocsr()
    if hops >= 2:
        P = (P + (gamma ** 2) * (A @ A)).tocsr()
    P.setdiag(0.0)
    P.eliminate_zeros()
    if cap is not None:
        P.data = np.clip(P.data, -cap, cap)
    return P


def degree_matched_shuffle(src, dst, rng, sector=None, sweeps=20,
                           max_try_mult=400):
    """Double-edge swap.  Preserves every node's degree EXACTLY and preserves
    the multiset of edge weights, so the propagated record count is identical to
    the true-KG run by construction.  With `sector` given, a swap is accepted
    only when the two destination endpoints share a sector, so sector alignment
    survives the rewire (rung A2).

    Mixing is measured in ACCEPTED swaps per edge, not in attempts.  The sector
    constraint rejects roughly (1 - 1/n_sector) of attempts, so a fixed attempt
    budget would leave A2 badly under-mixed -- an under-mixed shuffle is not a
    valid null, it is a graph that is still partly the real one.  We therefore
    keep drawing until `sweeps` accepted swaps per edge are reached, subject to
    a hard attempt cap."""
    s, d = src.copy(), dst.copy()
    ne = len(s)
    target = sweeps * ne
    hard_cap = max_try_mult * ne
    swaps = tries = 0
    while swaps < target and tries < hard_cap:
        batch = min(4 * ne, hard_cap - tries)
        ii = rng.integers(0, ne, batch)
        jj = rng.integers(0, ne, batch)
        tries += batch
        for k in range(batch):
            i, j = ii[k], jj[k]
            if i == j:
                continue
            if sector is not None and sector[d[i]] != sector[d[j]]:
                continue
            # forbid self-loops created by the swap
            if s[i] == d[j] or s[j] == d[i]:
                continue
            d[i], d[j] = d[j], d[i]
            swaps += 1
            if swaps >= target:
                break
    if swaps < target:
        print(f"    WARNING: only {swaps:,}/{target:,} accepted swaps "
              f"({swaps/ne:.1f} per edge) before the attempt cap. The rewire "
              f"may be under-mixed; raise --max-try-mult or lower --sweeps.")
    return s, d, swaps


# ---------------------------------------------------------------------------
def per_stock_corr(S_true, S_rand, cols):
    """corr(S_true[:,j], S_rand[:,j]) for each evaluation stock j."""
    out = np.full(len(cols), np.nan)
    for k, j in enumerate(cols):
        a = np.asarray(S_true[:, j]).ravel()
        b = np.asarray(S_rand[:, j]).ravel()
        if a.std() > 1e-12 and b.std() > 1e-12:
            out[k] = np.corrcoef(a, b)[0, 1]
    return out


def herfindahl(x):
    x = np.asarray(x, dtype=float)
    if x.sum() <= 0:
        return np.nan
    p = x / x.sum()
    return float((p ** 2).sum() * len(p))      # 1.0 = uniform, higher = hubbier


def verdict(c):
    """Map the pre-check correlation to a recommendation.

    CORRECTED 2026-08-01 after shuffle_control.py.  The first version of this
    function assumed the mapping was MONOTONE -- low correlation good, high
    correlation bad.  A calibrated sweep of the size distribution falsified
    that: KG - A1 is an INVERTED U in this statistic.

        pre-check corr   0.04   0.10   0.17   0.35   0.66   0.91   0.95
        KG - A1        0.011  0.032  0.041  0.038  0.025  0.008  0.009
        A1 share        90%    72%    65%    68%    78%    93%   109%

    Low correlation means the random graph produces a DIFFERENT signal, not a
    WORSE one.  In a flat world the propagated term is an average of many small
    items either way, so the shuffle collects nearly the whole lift (90%) even
    though its signal is decorrelated from the true one.  Both tails are bad
    for the paper; the middle is where the true topology earns its place.
    """
    if c < 0.10:
        return ("WEAK SEPARATION EXPECTED - do not lead with A1",
                "Near-zero correlation is NOT the good case.  It means the "
                "propagated term is diffuse enough that counterparty identity "
                "barely matters, and the shuffle absorbs ~90% of the lift.  "
                "Lead with the coverage arithmetic (SPEC section 6).")
    if c < 0.55:
        return ("RUN THE FULL ABLATION - best expected separation",
                "The shuffle retains part of the signal but misses the "
                "firm-specific part.  This is the regime where KG - A1 is "
                "largest relative to its null band.")
    if c < 0.75:
        return ("AMBIGUOUS - run the ladder, pre-commit to KG - A2",
                "Separation is shrinking.  Report F1(KG) - F1(A2) as the "
                "headline structural term and A1 as a secondary number.")
    return ("DO NOT LEAD WITH A1",
            "The shuffle baseline will absorb nearly all of the lift.  Lead "
            "with F1(KG) - F1(A2) and the coverage arithmetic (SPEC section "
            "6); report A1 honestly as a secondary number.")


# ---------------------------------------------------------------------------
def load_real(a):
    ed = pd.read_csv(a.edges)
    if not {"src", "dst"} <= set(ed.columns):
        sys.exit("--edges needs columns src,dst[,weight]")
    wgt = ed["weight"].to_numpy(float) if "weight" in ed.columns \
        else np.ones(len(ed))

    an = pd.read_csv(a.anchors)
    if not {"date", "node", "score"} <= set(an.columns):
        sys.exit("--anchors needs columns date,node,score (long format)")
    an = an.groupby(["date", "node"], as_index=False)["score"].agg(a.agg)

    uni = pd.read_csv(a.universe)
    ucol = "node" if "node" in uni.columns else uni.columns[0]
    universe = uni[ucol].astype(str).tolist()

    nodes = pd.Index(sorted(set(ed["src"].astype(str))
                            | set(ed["dst"].astype(str))
                            | set(an["node"].astype(str))
                            | set(universe)))
    idx = {v: i for i, v in enumerate(nodes)}
    n = len(nodes)

    src = ed["src"].astype(str).map(idx).to_numpy()
    dst = ed["dst"].astype(str).map(idx).to_numpy()

    dates = pd.Index(sorted(an["date"].unique()))
    didx = {v: i for i, v in enumerate(dates)}
    rows = an["date"].map(didx).to_numpy()
    cols = an["node"].astype(str).map(idx).to_numpy()
    anchors = sp.coo_matrix((an["score"].to_numpy(float), (rows, cols)),
                            shape=(len(dates), n)).tocsr()

    missing = [u for u in universe if u not in idx]
    if missing:
        sys.exit(f"universe ids absent everywhere: {missing[:5]}")
    ucols = np.array([idx[u] for u in universe])

    sector = None
    if a.sectors:
        sc = pd.read_csv(a.sectors)
        m = dict(zip(sc["node"].astype(str), sc["sector"].astype(str)))
        codes = pd.Index(sorted(set(m.values())))
        cmap = {v: i for i, v in enumerate(codes)}
        sector = np.full(n, -1)
        for k, v in m.items():
            if k in idx:
                sector[idx[k]] = cmap[v]
        if (sector < 0).any():
            print(f"  note: {(sector<0).sum()} nodes have no sector; they are "
                  f"placed in a single residual bucket")
            sector[sector < 0] = len(codes)
    return dict(n=n, src=src, dst=dst, wgt=wgt, anchors=anchors,
                ucols=ucols, universe=universe, sector=sector,
                ndate=len(dates))


def load_selftest(a):
    """Synthetic data with the paper's scale, so the script can be verified end
    to end before it is pointed at real files.  Nothing here is a result."""
    rng = np.random.default_rng(20260801)
    n, ne, nd = 9146, 15542, 551
    cap = np.sort(rng.lognormal(0, 1.4, n))[::-1]
    cap /= cap.sum()
    src = rng.choice(n, ne, p=cap)
    dst = rng.choice(n, ne, p=cap ** 0.5 / (cap ** 0.5).sum())
    keep = src != dst
    src, dst = src[keep], dst[keep]
    wgt = rng.beta(1.6, 4.0, len(src))
    nz = 120_000
    r = rng.integers(0, nd, nz)
    c = rng.choice(n, nz, p=cap)
    anchors = sp.coo_matrix((rng.standard_normal(nz), (r, c)),
                            shape=(nd, n)).tocsr()
    sector = rng.integers(0, 12, n)
    return dict(n=n, src=src, dst=dst, wgt=wgt, anchors=anchors,
                ucols=np.arange(50), universe=[f"S{i}" for i in range(50)],
                sector=sector, ndate=nd)


# ---------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--edges"); p.add_argument("--anchors")
    p.add_argument("--universe"); p.add_argument("--sectors")
    p.add_argument("--out", default="precheck_out.csv")
    p.add_argument("--gamma", type=float, default=0.5)
    p.add_argument("--hops", type=int, default=2)
    p.add_argument("--cap", type=float, default=50.0)
    p.add_argument("--reps", type=int, default=5)
    p.add_argument("--sweeps", type=int, default=20,
                   help="ACCEPTED double-edge swaps per edge (mixing target)")
    p.add_argument("--max-try-mult", type=int, default=400,
                   dest="max_try_mult", help="attempt cap = this x n_edges")
    p.add_argument("--seed", type=int, default=20260801)
    p.add_argument("--agg", default="mean", choices=["mean", "sum", "last"])
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args()

    if a.selftest:
        print("*** SELFTEST: synthetic data, no result may be reported ***\n")
        w = load_selftest(a)
    else:
        if not (a.edges and a.anchors and a.universe):
            p.error("--edges, --anchors and --universe are required "
                    "(or use --selftest)")
        w = load_real(a)

    print(f"nodes {w['n']}   edges {len(w['src'])}   days {w['ndate']}   "
          f"universe {len(w['ucols'])}")
    print(f"propagation: gamma={a.gamma} hops={a.hops} cap={a.cap}   "
          f"(must match the reported KG run)")

    deg = np.bincount(np.concatenate([w["src"], w["dst"]]), minlength=w["n"])
    print(f"mean degree {deg.mean():.3f}   degree Herfindahl "
          f"{herfindahl(deg):.2f}  (1.0 = uniform; high = hub-dominated)")

    A = build_adjacency(w["src"], w["dst"], w["wgt"], w["n"])
    P_kg = prop_matrix(A, a.gamma, a.hops, a.cap)
    print(f"P_KG nnz {P_kg.nnz:,}   density {P_kg.nnz/w['n']**2:.2e}")

    S_true = np.asarray((w["anchors"] @ P_kg).todense())
    rng = np.random.default_rng(a.seed)

    res = {}
    for tag, sec in (("A1_global", None),
                     ("A2_sector", w["sector"] if w["sector"] is not None else None)):
        if tag == "A2_sector" and w["sector"] is None:
            print("\nA2 skipped (--sectors not supplied)")
            continue
        cors = []
        for r in range(a.reps):
            s, d, nsw = degree_matched_shuffle(
                w["src"], w["dst"], rng, sector=sec, sweeps=a.sweeps,
                max_try_mult=a.max_try_mult)
            Ps = prop_matrix(build_adjacency(s, d, w["wgt"], w["n"]),
                             a.gamma, a.hops, a.cap)
            S_rand = np.asarray((w["anchors"] @ Ps).todense())
            cors.append(per_stock_corr(S_true, S_rand, w["ucols"]))
            print(f"  {tag} rep {r+1}/{a.reps}: {nsw:,} accepted swaps, "
                  f"mean corr {np.nanmean(cors[-1]):+.3f}")
        res[tag] = np.array(cors)

    print("\n=== per-stock correlation between true and rewired signal ===")
    for tag, C in res.items():
        m = np.nanmean(C, axis=0)
        q = np.nanpercentile(m, [10, 50, 90])
        print(f"  {tag}: mean {np.nanmean(m):+.3f}  median {q[1]:+.3f}  "
              f"p10 {q[0]:+.3f}  p90 {q[2]:+.3f}  "
              f"across-shuffle sd {np.nanstd(np.nanmean(C, axis=1), ddof=1):.4f}")

    key = np.nanmean(res["A1_global"])
    v, why = verdict(key)
    print(f"\n=== VERDICT (on A1 mean corr = {key:+.3f}) ===")
    print(f"  {v}\n  {why}")
    if "A2_sector" in res:
        print(f"  A2 mean corr = {np.nanmean(res['A2_sector']):+.3f} "
              f"(always >= A1; A2 is the harder, more honest baseline)")

    out = pd.DataFrame({"node": w["universe"]})
    for tag, C in res.items():
        out[f"corr_{tag}"] = np.nanmean(C, axis=0)
    out.to_csv(a.out, index=False)
    print(f"\nper-stock values written to {a.out}")
    print("This is a PRE-CHECK, not an experimental result. It forecasts the "
          "ablation outcome; it does not substitute for running it.")


if __name__ == "__main__":
    main()
