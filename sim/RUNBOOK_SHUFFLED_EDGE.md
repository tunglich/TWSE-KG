# Degree-matched shuffled-edge control — runbook

This is the experiment the reviewer named as the paper's largest gap, and the
one §5 already pre-registers ("a shuffled-edge control specified in advance").
Everything generic is built and tested here. The one part that cannot be done
in this workspace is the pipeline run itself, because the corpus, the KG, and
the Stage 2–5 code live on your machine.

**Nothing in this directory produces a number that may be printed in the paper.**
The scripts here generate *inputs* (null graphs) and *report* outputs your own
pipeline produces. The simulations in `ablation_design.py`, `shuffle_test.py`,
`shuffle_mechanism.py`, and `shuffle_control.py` are design studies only.

---

## The claim under test

The reported lift is `F1: 0.5309 (LLM-Direct) → 0.6456 (KG)`, +0.1147 on the
Top 50. A reviewer can say: propagation gives each firm *more* sentiment
records, and more records means less noise, so the lift is volume, not real
supply-chain links.

A degree-matched shuffle kills that objection or confirms it. A double-edge
swap takes edges `(u1→v1)` and `(u2→v2)` to `(u1→v2)` and `(u2→v1)`. Every
node's in-degree and out-degree is preserved **exactly** — not in distribution,
exactly. So each firm receives propagated news from exactly as many
counterparties as before, the propagated record count is identical by
construction, and the only thing that changed is *who* those counterparties
are. Whatever remains of the lift is not volume.

---

## The ladder

| Rung | Propagation operator | Carries |
|---|---|---|
| Direct | none | own-firm news (already in the paper) |
| A1 | global degree-matched shuffle | volume + degree, no real structure |
| A2 | sector-preserving degree-matched shuffle | + sector alignment |
| A3 | sector-only, uniform weights, mass-matched | sector membership alone |
| A4 | true topology, unweighted, one hop | real links, no weights, no 2nd hop |
| KG | typed, weighted, two-hop | full method (already in the paper) |

The ladder is additive, which is why there are four rungs and not one:

```
F1(A1) − F1(Direct)  = pure volume / noise-averaging
F1(A2) − F1(A1)      = sector alignment
F1(KG) − F1(A2)      = firm-specific link information   ← the contested term
F1(KG) − F1(A4)      = value of exposure weights + second hop
```

A single global shuffle destroys sector alignment *and* firm identity at once,
so on its own it cannot answer the reviewer's actual question.

---

## Step 0 — the cheap pre-check (minutes, do this first)

Cached Stage-1 anchors only, no classifier. It forecasts the full experiment's
outcome at a fraction of the cost.

```bash
python3 precheck_shuffle.py --selftest          # ~9 s, verifies the code
python3 precheck_shuffle.py \
    --edges kg_edges.csv --anchors stage1_cache.csv \
    --universe top50.csv --sectors sectors.csv \
    --gamma 0.5 --hops 2 --reps 5 --out precheck_out.csv
```

Read the verdict bands from `ABLATION_SPEC.md` §7.4, **not** §7.3 — the
statistic is non-monotone (an inverted U), and §7.3's monotone reading was
wrong. Corrected: `<0.10` weak, `0.10–0.55` best case, `0.55–0.75` ambiguous,
`>0.75` do not lead with A1.

---

## Step 1 — generate the null graphs (seconds)

```bash
python3 make_null_graphs.py --selftest          # verifies degree preservation
python3 make_null_graphs.py \
    --edges kg_edges.csv --sectors sectors.csv \
    --out nulls/ --reps 10 --sweeps 20 --seed 20260802
```

Writes `nulls/A1_rep00.csv … A3_rep09.csv` plus `nulls/manifest.csv`. Every
replicate is asserted degree-preserving, self-loop-free, mass-matched, and (for
A2) sector-preserving before it is written; a replicate that fails to mix is
flagged loudly rather than written silently.

Mixing is counted in **accepted** swaps, not attempts. This matters: the A2
sector constraint rejects roughly `1 − 1/n_sector` of proposals, so counting
attempts would leave A2 mostly the real graph — not a null, but a weakened copy
of the alternative, biased toward finding nothing.

`--reps 10` gives a null band half-width of about 0.003 F1. R = 20 if a run is
cheap. R is chosen for a stable band, not for power: the held-out window is
fixed, so replicates randomise the *shuffle*, not the data.

## Step 2 — run your pipeline once per file

```bash
for f in nulls/A1_rep*.csv nulls/A2_rep*.csv nulls/A3_rep*.csv; do
  your_pipeline --edges "$f" --out "${f%.csv}_f1.txt"
done
```

Everything except the edge file must be **byte-identical** to the reported KG
run: corpus, date range, the 551-day held-out window, the Stage-1 anchor cache
(read, never recomputed), `gamma = 0.5`, `hops = 2`, path cap ±50, staleness
rule, feature construction, classifier family, hyperparameters, seed, the
50-stock universe, and the balanced operating point. If any of those move, the
comparison is not a control.

All rungs are **LLM-free** — Stage-1 sentiment is cached per (item,
prompt-version) and propagation is deterministic post-processing over that
cache. No new inference calls, no re-labelling. A1 + A2 + A3 at R = 10 is 30
propagation-and-classify runs, plus one each for A4 and the already-computed
Direct and KG.

## Step 3 — collect and report

Assemble one `results.csv` with columns `rung,rep,f1` (`rep = 0` for the
deterministic rungs), then:

```bash
python3 collect_ablation.py --selftest          # verifies the arithmetic
python3 collect_ablation.py --results results.csv
```

It prints the per-rung table, `KG − A1` and `KG − A2` in shuffle-sd units, the
additive decomposition, the pre-registered verdict, and a ready-to-paste LaTeX
table body.

---

## The verdict is pre-registered — fix it before you look

Written into `collect_ablation.py` so it cannot be tuned to the result.

- **REFUTED** — `F1(KG)` within 2 sd of the A1 band. A random degree-matched
  graph reproduces the lift. The structural reading fails; the paper must say
  so and be reframed as a coverage result.
- **AMBIGUOUS** — 2–4 sd above. Report the gap with the band, don't lead with it.
- **PASS** — >4 sd above A1 *and* >2 sd above A2. Lead with `KG − A2`.
- **PASS (sector-driven)** — clears A1 decisively but not A2. Sector alignment,
  not firm-level links, carries the signal. Real and reportable, but it is
  **not** the paper's current claim, which would have to narrow to sector-level
  propagation.

---

## Ready-to-paste LaTeX for each outcome

The paper currently hedges in two places. §5 ¶1 (`main.tex` line ~326) ends:

> …though the subtractive design does not separate typed graph structure from
> the coverage expansion it induces; a degree-matched shuffled-edge control is
> the decisive test and is not run here.

and §5 ¶4 (line ~332) lists the control among "the remedies are concrete".
Both must change together, or the paper will claim a result in one paragraph
and promise it as future work in another.

**Page budget: free_lines is 5.1 (≈ 5 spare column-lines).** Branch A is the
only one that fits without a compensating trim; B and C need one. Recompile and
re-measure with `python3 /tmp/slack.py <dir>` before packaging — 8 pages is a
hard limit and over-length is a desk reject.

### Branch A — PASS (replace the line-326 clause)

```latex
and a degree-matched shuffled-edge control separates the two: rewiring the
graph while preserving every firm's in- and out-degree exactly, so the
propagated record count is unchanged by construction, gives
$F_1 = \NULLA \pm \NULLASD$ over ten rewirings, leaving
$+\GAPA$ attributable to real link identity rather than to record volume.
```

and in ¶4 delete "and a shuffled-edge control specified in advance ---
double-edge swaps ... If the reported $F_1$ falls inside that band, the
structural reading is refuted." (that sentence is now a result, not a remedy).

### Branch B — PASS (sector-driven)

```latex
and a degree-matched shuffled-edge control locates the gain: a global rewiring
preserving every firm's degree reaches $F_1 = \NULLA \pm \NULLASD$, but a
sector-preserving rewiring reaches $\NULLB \pm \NULLBSD$, within
$\GAPB$ of the full graph. The propagated signal is therefore carried by
sector-level co-movement rather than by individual customer and supplier
identity, and we narrow the claim accordingly.
```

### Branch C — REFUTED or AMBIGUOUS

```latex
and a degree-matched shuffled-edge control does not separate them: a rewiring
that preserves every firm's degree, and hence the propagated record count,
reaches $F_1 = \NULLA \pm \NULLASD$ against $0.6456$ for the true graph. On
this corpus the lift is therefore attributable to the coverage expansion
propagation induces rather than to the identity of the links, and we report the
method as a coverage mechanism rather than a structural one.
```

If Branch C is the outcome, the abstract's framing also needs a pass: the
coverage arithmetic in §5 ¶2 (2.97× overall, 1.27× on the Top 50, and the
latent-Gaussian bound that puts pure volume at $F_1 \approx 0.535$) becomes the
paper's defence, and it stands on its own — it needs no new run.

---

## What this does not fix

- The control tests whether link *identity* matters. It does not test whether
  the *typed* semantics (supplier vs. customer vs. competitor) matter; that is
  a separate edge-type-permutation rung not specified here.
- A2 preserves sector but not size. A firm rewired onto a same-sector
  counterparty of very different capitalisation is still a large perturbation,
  and §7.4 of `ABLATION_SPEC.md` shows the separation depends on the size
  distribution, which for Taiwan is steep.
- One market, one corpus, one window. The control makes the causal reading
  defensible on this data; it does not make it general.
