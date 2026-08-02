# Paper 3 — KG ablation experiment: executable specification

Prepared in response to review item 2 ("missing shuffled-edge / sector baseline",
the reviewer's largest single gap). This document is the protocol to run on the
real corpus. The accompanying `ablation_design.py` is a **design study
only** — none of its numbers may appear in the paper as a result.

## 0. Why this experiment is cheap

All rungs are **LLM-free**. Stage-1 anchor sentiment is cached per
(item, prompt-version); propagation is deterministic post-processing over that
cache. An ablation re-runs stages 2–5 plus the downstream classifier. No new
inference calls, no new corpus, no re-labelling. If the pipeline code exists,
one rung is a matter of minutes-to-hours, not days.

## 1. What is held fixed across every rung

Frozen, identical to the reported KG run:

- corpus, date range, and the 551-day held-out window
- Stage-1 anchor scores (read from cache, never recomputed)
- decay `gamma = 0.5`, `hops = 2`, magnitude/confidence handling, staleness rule
- feature construction, classifier family, hyperparameters, seed
- the 50-stock evaluation universe and the balanced-class operating point

The **only** thing that varies is the propagation operator `P`.

## 2. The ladder

| Rung | Propagation operator | What it contains |
|---|---|---|
| Direct | none | own-firm news only (already in paper) |
| A1 | global degree-matched edge shuffle | volume + degree, no real structure |
| A2 | sector-preserving degree-matched shuffle | volume + degree + sector alignment |
| A3 | sector-only, uniform weights, mass-matched | sector membership alone |
| A4 | true topology, unweighted, one hop | real links, no weights, no 2nd hop |
| KG | typed, weighted, two-hop | full method (already in paper) |

Shuffles use double-edge swaps (20 sweeps over the edge list), which preserve
every node's degree exactly, so the **number of propagated records is identical**
to the KG run by construction. A3 is rescaled so total propagated mass equals
the KG run's. This is what makes the comparison clean: no rung gets an advantage
from having more sentiment records than another.

## 3. Decomposition (the reason for four rungs, not one)

A single global shuffle destroys sector alignment *and* firm-specific links at
once, so it cannot answer the reviewer's actual question. The ladder is additive:

```
F1(A1) - F1(Direct)  = pure volume / noise-averaging
F1(A2) - F1(A1)      = sector alignment
F1(KG) - F1(A2)      = firm-specific link information   <-- the contested term
F1(KG) - F1(A4)      = value of exposure weights + second hop
```

## 4. Test statistic and falsification criterion

**Primary statistic:** `F1(KG) - F1(A1)` on the fixed held-out window.

**Null band:** run `R` independent shuffles; the null distribution is the spread
of `F1(A1)` across replicates. The held-out window is fixed, so replicates
randomise the *shuffle*, not the data — `R` is chosen for a stable band, not for
power. **R = 10** gives a half-width of roughly 0.003 F1 in the model; R = 20
if the run is cheap. Report the band, not a p-value from an i.i.d. assumption
that does not hold cross-sectionally.

**Falsification:** if `F1(KG)` falls inside the A1 null band, the structural
claim is refuted and the paper's Discussion must say so. Pre-commit to this
before running.

**Secondary:** report `F1(KG) - F1(A2)` as the headline structural term, since
A2 is the harder and more honest baseline.

## 5. Experiment 0 — free, run this first

Regress the 50 already-reported per-stock F1 gains on per-stock coverage
multipliers (propagated records / direct records), which the pipeline already
writes to disk. Zero new inference, zero new runs.

- Coverage hypothesis predicts high R² and near-zero residual gain.
- Structural hypothesis predicts low R² and a large intercept.

This can be done today and is worth reporting either way.

## 6. Arithmetic that already exists in the paper

From Table 5, without any new experiment: overall coverage grows
118,662 → 352,287 (2.97×), but that expansion is almost entirely outside the
Top-50 (non-Top-50 63,277 → 281,697 = **4.45×**). The 11.5-point F1 lift is
measured **on the Top-50**, where coverage grows only 55,385 → 70,590 =
**1.27×**, and where only ~21.5% of records are propagated. The coverage
hypothesis therefore has to produce 11.5 F1 points out of a 27% record
increase. A generous sqrt(n) noise-averaging bound on that increase yields at
most ~0.535 F1 against the reported 0.6456 — leaving ~11 points unexplained.

This paragraph can go into the paper **now**; it needs no new run.

---

## 7. Shuffle-specific design study (`shuffle_test.py`, `shuffle_mechanism.py`)

Added after a focused re-run of the A1/A2 rungs. Two corrections to §4 above.

### 7.1 The null band must randomise the shuffle, not the window

`ablation_design.py` used one shuffle and 40 resampled windows. That is the
wrong variance. In the real experiment the held-out window is **fixed** and only
the shuffle is random, so the null band is the spread of `F1(A1)` across `R`
independent shuffle realisations on that one window. Re-measured that way the
band is much tighter: sd ≈ 0.003 F1 at R = 20, giving

```
KG - A1 = +0.0369   ->  12.7 shuffle-sd above the null
KG - A2 = +0.0324   ->   9.3 shuffle-sd above the null
```

**R = 10 is enough; R = 20 costs little.** The experiment is decisively powered
*if* the real data behaves like the calibrated model.

### 7.2 The outcome is NOT robust — pre-check before committing

The share of the lift a *random* degree-matched graph already captures is
**60-106%** across plausible world configurations. It is flat in the
market-factor loading (66-68% from beta_m = 0.15 to 0.95), so the common market
factor is not the driver. It is governed instead by how much of the transmitted
signal survives a degree-preserving rewire:

| configuration | corr(true, rewired) | A1 share of lift | KG - A1 |
|---|---|---|---|
| flat capitalisations | +0.03 | 106% | **-0.005 (fails)** |
| baseline | +0.17 | 65% | +0.041 |
| strong preferential attachment | +0.45 | 72% | +0.032 |
| steep capitalisations | +0.82 | 88% | +0.015 |

A steep capitalisation distribution is the Taiwan case (TSMC alone is a large
fraction of TAIEX), and it is the regime where separation is **weakest**.

### 7.3 The cheap pre-check — run this before the full ablation

On the cached Stage-1 anchors only, no classifier, minutes not hours:

```
S_true = anchors @ P_KG
S_rand = anchors @ P_shuffled        (R = 5 shuffles)
report the per-stock correlation corr(S_true[:, j], S_rand[:, j]) over the Top 50
```

- correlation **low (< ~0.3)**: run the full ablation, it will separate cleanly.
- correlation **high (> ~0.7)**: the shuffle baseline will absorb most of the
  lift. Lead with `F1(KG) - F1(A2)` and with the §6 coverage arithmetic instead,
  and report A1 as a secondary, honestly-framed number.

Either way the pre-check is worth running first, because it forecasts the
experiment's outcome at a fraction of the cost.

**Implemented in `precheck_shuffle.py`.** Sparse throughout (a dense
9,146 x 9,146 operator is 669 MB and is not needed). Verify it runs with
`python3 precheck_shuffle.py --selftest` (synthetic data, ~9 s), then point
it at the real files:

```
python3 precheck_shuffle.py \
    --edges kg_edges.csv --anchors stage1_cache.csv \
    --universe top50.csv --sectors sectors.csv \
    --gamma 0.5 --hops 2 --reps 5 --out precheck_out.csv
```

Input contract: `edges` = `src,dst[,weight]`; `anchors` = long format
`date,node,score` straight from the Stage-1 cache; `universe` = the 50
evaluation tickers; `sectors` optional and only needed for the A2 rung.
`--gamma/--hops/--cap` must match the reported KG run or the pre-check
does not describe the experiment you are about to run.

Mixing is counted in **accepted** swaps per edge, not attempts: the A2
sector constraint rejects about `1 - 1/n_sector` of attempts, and an
under-mixed rewire is not a valid null, it is a graph that is still partly
the real one.

### 7.4  The pre-check statistic is NOT monotone (correction, 2026-08-01)

`shuffle_control.py` calibrates the world to Table 4 rather than guessing it:
news arrival is capitalisation-weighted, so the reported Top-50 share of
pre-propagation records (55,385 / 118,662 = 46.67%) pins the size distribution.
Solving gives lognormal sigma = 1.29.  In that world the ladder reads

    MarketWide 0.5442 | Direct 0.5344 | A1 0.6138 (sd 0.0028)
    A2 0.6175 (sd 0.0035) | A4 0.6296 | KG 0.6507
    KG - A1 = +0.0369 (13.1 sd)   KG - A2 = +0.0332 (9.5 sd)

Sweeping sigma and recording both the pre-check correlation and the separation
gives an INVERTED U, not the monotone relation section 7.3 assumed:

    corr    0.04   0.10   0.17   0.35   0.66   0.91   0.95
    KG-A1  0.011  0.032  0.041  0.038  0.025  0.008  0.009
    A1 sh   90%    72%    65%    68%    78%    93%   109%

Low correlation means the shuffled graph produces a DIFFERENT transmitted
signal, not a WORSE one.  When news is spread evenly the propagated term is an
average of many small items whichever graph carries it, so the shuffle collects
~90% of the lift while being decorrelated from the truth.  Both tails are bad;
the verdict bands in `precheck_shuffle.py` have been corrected accordingly
(<0.10 weak, 0.10-0.55 best, 0.55-0.75 ambiguous, >0.75 do not lead with A1).

Caveat on the calibration: the held-back anchor misses.  F1_MarketWide comes
out at 0.5442 against the reported 0.5040, so the world is only roughly right
and the lookup table should be read as an ordering, not as point predictions.
