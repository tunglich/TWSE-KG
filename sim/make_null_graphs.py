# -*- coding: utf-8 -*-
"""
make_null_graphs.py  --  generate the null knowledge graphs for the
degree-matched shuffled-edge control (rungs A1, A2, A3).

WHAT THIS DOES AND DOES NOT DO
------------------------------
This script does the ONE part of the experiment that is generic and easy to get
wrong: producing null graphs that are provably degree-matched to the real KG.
It does NOT touch your pipeline.  You run your existing Stage 2-5 + classifier
once per generated graph file, exactly as you ran it for the reported KG result,
and collect the F1 numbers.  Then feed them to collect_ablation.py.

WHY DEGREE-MATCHED
------------------
The reviewer's objection is that the 11.5-point lift may come from having MORE
sentiment records per firm (coverage), not from the links being real.  A
double-edge swap preserves every node's in-degree and out-degree EXACTLY, so
every firm receives propagated news from exactly as many counterparties as
before.  The propagated record count is therefore identical by construction and
the only thing that changed is WHO those counterparties are.  That isolates
"the links are real" from "there are more records".

WHAT IS PRESERVED
-----------------
  - every node's in-degree and out-degree, exactly
  - the multiset of edge attributes (weight, type, validity interval): each
    attribute tuple stays attached to its edge as the endpoints move, so total
    propagated mass and the type mix are unchanged
  - no self-loops, no duplicate directed edges

WHAT VARIES
-----------
  A1  global swap        -- any two edges may swap heads
  A2  sector-preserving  -- a swap is accepted only if it keeps both heads in
                            their original sector; the harder, more honest null
  A3  sector-only        -- edges rewired to random same-sector partners with
                            uniform weights, then rescaled so total propagated
                            mass matches the KG run (membership alone)

USAGE
-----
  python3 make_null_graphs.py --edges kg_edges.csv --sectors sectors.csv \
      --out nulls/ --reps 10 --seed 20260802

  # then, for each generated file, run YOUR pipeline with the same
  # gamma/hops/cap/seed as the reported KG run:
  #   for f in nulls/A1_rep*.csv; do your_pipeline --edges $f --out ${f%.csv}_f1.txt; done

INPUT CONTRACT
--------------
  --edges    CSV with columns src,dst and any of weight,type,valid_from,valid_to
  --sectors  CSV with columns node,sector      (required for A2 and A3)

Everything else about the run  ---  corpus, date range, Stage-1 anchor cache,
gamma, hops, path cap, classifier family, hyperparameters, seed, the 50-stock
universe, the balanced operating point  ---  must be BYTE-IDENTICAL to the
reported KG run.  If any of those move, the comparison is not a control.
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

ATTR_COLS = ["weight", "type", "valid_from", "valid_to"]


# --------------------------------------------------------------------------
# core: degree-preserving double-edge swap
# --------------------------------------------------------------------------
def double_edge_swap(src, dst, rng, sector=None, sweeps=20, max_attempt_mult=200):
    """Rewire a directed edge list preserving every node's in- and out-degree.

    A swap takes edges (u1 -> v1) and (u2 -> v2) to (u1 -> v2) and (u2 -> v1).
    Out-degree of u1, u2 and in-degree of v1, v2 are all unchanged, so every
    node's degree is preserved exactly, not merely in distribution.

    Mixing is counted in ACCEPTED swaps, not attempts.  This matters: the A2
    sector constraint rejects roughly 1 - 1/n_sector of proposals, so counting
    attempts would leave the A2 graph still mostly the real one, which is not a
    null -- it is a weaker version of the alternative, and it would bias the
    test toward finding nothing.

    Parameters
    ----------
    sector : array or None
        If given, a swap is accepted only when sector[v1] == sector[v2], so
        every edge keeps pointing into its original sector (rung A2).
    sweeps : int
        Target accepted swaps per edge.  20 is well past the mixing time for
        graphs of this size; the returned diagnostics let you verify it.
    """
    src = np.asarray(src).copy()
    dst = np.asarray(dst).copy()
    m = len(src)
    target = sweeps * m
    seen = set(zip(src.tolist(), dst.tolist()))

    accepted = 0
    attempts = 0
    max_attempts = max_attempt_mult * target
    while accepted < target and attempts < max_attempts:
        attempts += 1
        i, j = rng.integers(0, m, 2)
        if i == j:
            continue
        u1, v1 = src[i], dst[i]
        u2, v2 = src[j], dst[j]
        # no self-loops
        if u1 == v2 or u2 == v1:
            continue
        # no duplicate directed edges
        if (u1, v2) in seen or (u2, v1) in seen:
            continue
        # sector constraint (rung A2)
        if sector is not None and sector[v1] != sector[v2]:
            continue
        seen.discard((u1, v1))
        seen.discard((u2, v2))
        seen.add((u1, v2))
        seen.add((u2, v1))
        dst[i], dst[j] = v2, v1
        accepted += 1

    return dst, dict(accepted=accepted, attempts=attempts,
                     target=target, reached=accepted >= target,
                     accept_rate=accepted / max(attempts, 1))


def degree_vector(src, dst, n_nodes):
    out = np.bincount(src, minlength=n_nodes)
    inn = np.bincount(dst, minlength=n_nodes)
    return out, inn


def frac_edges_preserved(src, dst0, dst1):
    """Share of edges still pointing at their original head.  A well-mixed
    rewire should sit near the chance level, not near 1."""
    return float(np.mean(dst0 == dst1))


# --------------------------------------------------------------------------
# rung A3: sector-only, uniform weights, mass-matched
# --------------------------------------------------------------------------
def sector_only_graph(src, dst, sector, weight, rng):
    """Every edge is redirected to a uniformly random firm in the head's
    original sector, and all weights are set to a single constant chosen so the
    total edge mass equals the real graph's.  This rung carries sector
    membership and nothing else -- no firm identity, no exposure size."""
    by_sector = {}
    for s in np.unique(sector):
        by_sector[s] = np.flatnonzero(sector == s)
    new_dst = np.empty_like(dst)
    for e in range(len(dst)):
        pool = by_sector[sector[dst[e]]]
        pool = pool[pool != src[e]]
        if len(pool) == 0:
            new_dst[e] = dst[e]
        else:
            new_dst[e] = rng.choice(pool)
    const_w = float(np.sum(weight)) / len(weight)
    return new_dst, np.full(len(weight), const_w)


# --------------------------------------------------------------------------
def selftest(tmp="_selftest_nulls"):
    """Build a synthetic graph, rewire it, and check every invariant.  Proves
    the code is correct; proves nothing about the real KG."""
    rng = np.random.default_rng(7)
    n, m = 400, 1400
    sec = rng.integers(0, 8, n)
    s_, d_ = rng.integers(0, n, 6 * m), rng.integers(0, n, 6 * m)
    keep = s_ != d_
    s_, d_ = s_[keep], d_[keep]
    seen, S, D = set(), [], []
    for u, v in zip(s_, d_):
        if (u, v) in seen:
            continue
        seen.add((u, v)); S.append(u); D.append(v)
        if len(S) >= m:
            break
    S, D = np.array(S), np.array(D)
    print(f"selftest: {n} nodes, {len(S)} edges, 8 sectors")
    for name, sec_arg in (("A1", None), ("A2", sec)):
        dst1, diag = double_edge_swap(S, D, np.random.default_rng(1), sec_arg, 20)
        o0, i0 = degree_vector(S, D, n)
        o1, i1 = degree_vector(S, dst1, n)
        assert np.array_equal(o0, o1) and np.array_equal(i0, i1)
        assert not np.any(S == dst1)
        if sec_arg is not None:
            assert np.array_equal(sec[dst1], sec[D])
        print(f"  {name}: degrees preserved, no self-loops, "
              f"{100*frac_edges_preserved(S, D, dst1):.2f}% edges unchanged, "
              f"accept rate {diag['accept_rate']:.3f}")
    w = rng.random(len(S))
    d3, w3 = sector_only_graph(S, D, sec, w, np.random.default_rng(2))
    assert abs(w3.sum() - w.sum()) < 1e-9, "A3 mass not matched"
    assert np.array_equal(sec[d3], sec[D])
    print("  A3: sector membership preserved, total edge mass matched")
    print("selftest passed. All numbers above are synthetic.")


def main():
    ap = argparse.ArgumentParser()
    if "--selftest" in sys.argv:
        selftest()
        return
    ap.add_argument("--edges", required=True)
    ap.add_argument("--sectors", default=None)
    ap.add_argument("--out", default="nulls")
    ap.add_argument("--reps", type=int, default=10)
    ap.add_argument("--sweeps", type=int, default=20)
    ap.add_argument("--seed", type=int, default=20260802)
    ap.add_argument("--rungs", default="A1,A2,A3")
    a = ap.parse_args()

    e = pd.read_csv(a.edges)
    for c in ("src", "dst"):
        if c not in e.columns:
            sys.exit(f"edges file must have a '{c}' column; got {list(e.columns)}")

    nodes = pd.Index(sorted(set(e["src"]) | set(e["dst"])))
    idx = {v: i for i, v in enumerate(nodes)}
    src = e["src"].map(idx).to_numpy()
    dst0 = e["dst"].map(idx).to_numpy()
    n = len(nodes)
    weight = (e["weight"].to_numpy(float) if "weight" in e.columns
              else np.ones(len(e)))

    sector = None
    if a.sectors:
        sec = pd.read_csv(a.sectors)
        smap = dict(zip(sec["node"], sec["sector"]))
        missing = [v for v in nodes if v not in smap]
        if missing:
            print(f"  WARNING: {len(missing)} nodes have no sector; "
                  f"assigning them a shared 'UNKNOWN' sector")
        codes = pd.Series([smap.get(v, "UNKNOWN") for v in nodes]).astype("category")
        sector = codes.cat.codes.to_numpy()

    out0, in0 = degree_vector(src, dst0, n)
    os.makedirs(a.out, exist_ok=True)
    print(f"real graph: {n} nodes, {len(e)} edges, mean degree "
          f"{2*len(e)/n:.3f}, {0 if sector is None else len(np.unique(sector))} sectors")

    rungs = [r.strip() for r in a.rungs.split(",") if r.strip()]
    log = []
    for rung in rungs:
        if rung in ("A2", "A3") and sector is None:
            print(f"  skipping {rung}: --sectors not supplied")
            continue
        for r in range(a.reps):
            rng = np.random.default_rng(a.seed + 1000 * rungs.index(rung) + r)
            w = weight
            if rung == "A1":
                dst1, diag = double_edge_swap(src, dst0, rng, None, a.sweeps)
            elif rung == "A2":
                dst1, diag = double_edge_swap(src, dst0, rng, sector, a.sweeps)
            else:  # A3
                dst1, w = sector_only_graph(src, dst0, sector, weight, rng)
                diag = dict(accepted=len(dst0), attempts=len(dst0),
                            target=len(dst0), reached=True, accept_rate=1.0)

            # ---- assertions: this is the whole point of the rung ----------
            o1, i1 = degree_vector(src, dst1, n)
            assert np.array_equal(o1, out0), f"{rung} rep{r}: out-degree changed"
            if rung != "A3":
                assert np.array_equal(i1, in0), f"{rung} rep{r}: in-degree changed"
                assert abs(w.sum() - weight.sum()) < 1e-9, "edge mass changed"
            assert not np.any(src == dst1), f"{rung} rep{r}: self-loop created"
            if rung == "A2":
                assert np.array_equal(sector[dst1], sector[dst0]), \
                    "A2 rep{r}: head sector changed"

            df = e.copy()
            df["dst"] = nodes[dst1]
            if "weight" in df.columns or rung == "A3":
                df["weight"] = w
            path = os.path.join(a.out, f"{rung}_rep{r:02d}.csv")
            df.to_csv(path, index=False)

            kept = frac_edges_preserved(src, dst0, dst1)
            log.append(dict(rung=rung, rep=r, path=path,
                            accepted=diag["accepted"], reached=diag["reached"],
                            accept_rate=round(diag["accept_rate"], 4),
                            frac_edges_unchanged=round(kept, 4)))
            flag = "" if diag["reached"] else "   <-- UNDER-MIXED, not a valid null"
            print(f"  {rung} rep{r:02d}: {diag['accepted']:>8} accepted swaps "
                  f"(rate {diag['accept_rate']:.3f}), "
                  f"{100*kept:5.2f}% of edges unchanged{flag}")

    pd.DataFrame(log).to_csv(os.path.join(a.out, "manifest.csv"), index=False)
    bad = [l for l in log if not l["reached"]]
    print(f"\nwrote {len(log)} null graphs to {a.out}/ (manifest.csv lists them)")
    if bad:
        print(f"WARNING: {len(bad)} replicate(s) did not reach the accepted-swap "
              f"target. Raise --max-attempt-mult or lower --sweeps, but do NOT "
              f"report an under-mixed rewire as a null.")
    print("\nNext: run your pipeline once per file with the SAME gamma, hops, "
          "cap, classifier, seed and universe as the reported KG run, then pass "
          "the F1 values to collect_ablation.py.")


if __name__ == "__main__":
    main()
