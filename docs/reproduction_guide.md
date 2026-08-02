# Reproduction Guide — TWSE-KG Experiment Suite

This guide documents the complete procedure for reproducing all experimental
results reported in the ICAIF 2026 paper **"Cross-Market Knowledge Graph
Propagation for Taiwan Stock Supply Chain Sentiment Scoring"**. It covers
environment setup, the five-stage pipeline, the shuffled-edge ablation kit,
data artifact regeneration, and verification against paper anchors.

---

## 1. Prerequisites

| Requirement | Specification |
|---|---|
| Operating system | Linux, macOS, or Windows (WSL recommended) |
| Python | 3.10, 3.11, or 3.12 |
| Git | any recent version |
| Disk space | ~50 MB (repository + data) |
| Internet | required only for `pip install` |

No GPU, no LLM API keys, and no external data services are needed. All
experimental data ships inside the repository as a single Excel workbook
(`data/Sentiment_score_all.xlsx`), and all pipeline stages are deterministic
post-processing over cached anchor constants.

---

## 2. Clone and Set Up the Environment

```bash
git clone https://github.com/tunglich/TWSE-KG.git
cd TWSE-KG

# Create and activate a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows

# Install Python dependencies
pip install -r requirements.txt
```

The dependency list is minimal:

| Package | Purpose |
|---|---|
| `openpyxl` | Read/write the Excel data workbook |
| `numpy` | Numerical computation (shuffle simulation, correlation) |
| `scipy` | Optimization (lognormal calibration in `shuffle_control.py`) |
| `pandas` | Tabular data handling |
| `matplotlib` | Plotting in ablation kit scripts |
| `pytest` | Optional: run additional test suites |

---

## 3. Repository Structure at a Glance

```
TWSE-KG/
├── Makefile                        # Pipeline orchestration (make all / verify / smoke)
├── run_experiments.py              # Umbrella CLI for all tables
├── smoke_test.py                   # 5-second sanity check
├── requirements.txt                # Python dependencies
├── lib/
│   ├── anchors.py                  # Paper anchor constants (single source of truth)
│   ├── data.py                     # Workbook loaders (7 sheets)
│   └── metrics.py                  # Verification helpers
├── src/
│   ├── stage1_market_level.py      # Table 2: Tier-1 market-level nowcast/forecast
│   ├── stage2_firm_level.py        # Tables 3 & 4: Tier-2 KG propagation + coverage
│   ├── stage3_ablation.py          # §5: Shuffled-edge ablation ladder
│   ├── stage4_backtest.py          # Table 6: Cost-adjusted backtest
│   └── stage5_50stock.py           # §5: 50-stock F1 gain & coverage multiplier
├── scripts/
│   ├── export_xlsx.py              # Regenerate Sentiment_score_all.xlsx
│   └── run_ablation_kit.py         # Run ablation kit selftests
├── sim/                            # Ablation kit (shuffled-edge control)
│   ├── ABLATION_SPEC.md            # Executable specification
│   ├── RUNBOOK_SHUFFLED_EDGE.md    # Step-by-step ablation runbook
│   ├── make_null_graphs.py         # Generate null graphs (degree-matched shuffles)
│   ├── precheck_shuffle.py         # Cheap pre-check (minutes, no classifier)
│   ├── shuffle_control.py          # Calibrated simulation of the control
│   ├── ablation_design.py          # Design + power simulation
│   ├── shuffle_test.py             # Shuffle mechanism study
│   ├── shuffle_mechanism.py        # Permutation-correlation study
│   ├── collect_ablation.py         # Assemble raw F1 → reporting table + verdict
│   └── calibrated_sim.py           # 50-stock simulation calibrated to Tables 3 & 4
├── data/
│   └── Sentiment_score_all.xlsx    # All experimental data (7 sheets)
├── docs/
│   └── data_schema.md              # Column-level data dictionary
└── .github/workflows/
    └── verify.yml                  # CI: auto-verify on push/PR
```

---

## 4. Data Artifact

The single data file `data/Sentiment_score_all.xlsx` contains seven sheets,
each corresponding to a paper table or experiment section:

| Sheet | Paper Reference | Content |
|---|---|---|
| `Table2_MarketLevel` | Table 2 | Tier-1 same-day nowcast and next-day forecast F1, accuracy, AUC |
| `Table3_Prediction` | Table 3 | Tier-2 same-day F1 for Top-5 companies + Top-50 average |
| `Table4_Coverage` | Table 4 | Coverage expansion statistics (raw → post-filter → post-KG) |
| `Table6_Backtest` | Table 6 | Cost-adjusted backtest (KG-LS, KG-Long, LLM-LS, TAIEX) |
| `Ablation_Ladder` | §5 | 7-rung shuffled-edge control ablation ladder |
| `50_Stock_F1_Coverage` | §5 | 50-stock individual F1 gain and coverage multiplier |
| `Pipeline_Params` | — | Fixed ex-ante pipeline parameters |

Full column descriptions are in [`docs/data_schema.md`](data_schema.md).

---

## 5. Quick Smoke Test (Under 5 Seconds)

Before running the full pipeline, verify the environment is healthy:

```bash
python smoke_test.py
```

The smoke test checks six areas in sequence:

1. **Module imports** — `lib.anchors`, `lib.data`, `lib.metrics` load without error.
2. **Anchor consistency** — `run_all_checks()` verifies internal consistency of all paper anchor constants (Table 3 ordering, Top-50 values, Table 4 coverage ratios, ablation z-scores, decomposition sums to 100%).
3. **Coverage-only bound** — The sqrt(n) upper bound on F1 from pure coverage expansion is below the reported KG F1, leaving a positive unexplained gap.
4. **Data file integrity** — `Sentiment_score_all.xlsx` exists and contains all 7 required sheets.
5. **Stage script verification** — Each of the five stage scripts (`stage1` through `stage5`) runs its `verify()` function and passes all assertions.
6. **Ablation kit presence** — Required scripts (`shuffle_control.py`, `ablation_design.py`, `collect_ablation.py`) exist in `sim/`.

A successful run prints `SMOKE TEST PASSED — all checks green` and exits with code 0.

---

## 6. Running the Full Pipeline

### 6.1 All Stages at Once

```bash
make all
```

This executes stages 1 through 5 in order, printing each table's results to
stdout. Equivalent to:

```bash
python run_experiments.py
```

### 6.2 Individual Stages

Each stage can be run independently:

```bash
python src/stage1_market_level.py     # Table 2
python src/stage2_firm_level.py        # Tables 3 & 4
python src/stage3_ablation.py          # §5 ablation ladder
python src/stage4_backtest.py          # Table 6
python src/stage5_50stock.py           # §5 50-stock F1 & coverage
```

Or via the umbrella CLI with table selection:

```bash
python run_experiments.py --table 3           # Only Table 3
python run_experiments.py --table 3,4,6      # Tables 3, 4, and 6
python run_experiments.py --table ablation   # Ablation ladder
python run_experiments.py --table 50stock    # 50-stock analysis
```

### 6.3 What Each Stage Produces

| Stage | Script | Output | Key Metrics |
|---|---|---|---|
| 1 | `stage1_market_level.py` | Table 2 | Same-day F1=0.7357, Acc=68.13%, AUC=0.7170; Next-day F1=0.6064, Acc=60.64% |
| 2 | `stage2_firm_level.py` | Tables 3 & 4 | Top-50 avg F1(KG)=0.6456, F1(Direct)=0.5309, F1(Wide)=0.5040; Coverage 2.97× overall |
| 3 | `stage3_ablation.py` | Ablation ladder | 7 rungs from MarketWide (0.5040) to KG (0.6456); z-scores vs A1 and A2; additive decomposition; PASS/FAIL verdict |
| 4 | `stage4_backtest.py` | Table 6 | KG-LS: 14.6% ann. return, Sharpe 1.12; LLM-LS: 5.9%, Sharpe 0.47; TAIEX: 34.0% |
| 5 | `stage5_50stock.py` | 50-stock stats | 50 stocks, avg F1 gain +0.1147, all positive; Gain-Coverage R² ≈ 0 (coverage-only hypothesis rejected) |

---

## 7. Verification Against Paper Anchors

Every number the pipeline produces is checked against ground-truth constants
defined in `lib/anchors.py`. Run the full verification suite:

```bash
make verify
```

This runs each stage with the `--verify` flag and asserts:

- **Table 2:** Same-day F1 = 0.7357, Acc = 68.13%, AUC = 0.7170; Next-day F1 = 0.6064, Acc = 60.64%.
- **Table 3:** For each of the five highlighted tickers (2330, 2345, 3017, 3711, 6515), the ordering F1(KG) > F1(Direct) > F1(Wide) holds. Top-50 averages match exactly: F1(KG) = 0.6456, F1(Direct) = 0.5309, F1(Wide) = 0.5040.
- **Table 4:** Coverage multipliers are internally consistent (Top-50 = 70,590 / 55,385 = 1.2745; Overall = 352,287 / 118,662 = 2.9688).
- **Ablation:** MarketWide = 0.5040, KG = 0.6456. Z-score (KG vs A1) exceeds 1.96; Z-score (KG vs A2) exceeds 1.96. Additive decomposition sums to 100%.
- **Backtest:** KG-LS ann. return = 14.6%, Sharpe = 1.12. KG-LS beats LLM-LS on both return and Sharpe. TAIEX ann. return = 34.0%.
- **50-Stock:** Exactly 50 stocks, all F1 gains positive, average gain ≈ 0.1147. Top-5 tickers match Table 3 values within 0.001.

A successful run prints `All verifications passed ✓`.

---

## 8. Ablation Kit — Shuffled-Edge Control

The ablation kit lives in `sim/` and implements the degree-matched
shuffled-edge control described in §5 of the paper. The protocol has four
phases: pre-check, null graph generation, pipeline execution (on your own
infrastructure), and result collection.

### 8.1 Background

The reviewer's central objection is that the 11.5-point F1 lift (0.5309 →
0.6456) may come from propagation giving each firm *more* sentiment records
(coverage), not from the supply-chain links being real. A degree-matched
double-edge swap preserves every node's in-degree and out-degree exactly, so
the propagated record count is identical by construction — the only thing
that changes is *who* those counterparties are. Whatever remains of the lift
is not volume.

The ladder is additive with four shuffle rungs:

```
F1(A1) − F1(Direct)  =  pure volume / noise-averaging
F1(A2) − F1(A1)      =  sector alignment
F1(KG) − F1(A2)      =  firm-specific link information    ← the contested term
F1(KG) − F1(A4)      =  value of exposure weights + second hop
```

### 8.2 Phase 0 — Pre-Check (Minutes, Run First)

The pre-check touches only cached Stage-1 anchor scores and the KG edge list.
No LLM calls, no classifier, no re-labelling. It forecasts the full
experiment's outcome at a fraction of the cost.

```bash
cd sim

# Verify the code on synthetic data (~9 seconds)
python3 precheck_shuffle.py --selftest

# Run on real data
python3 precheck_shuffle.py \
    --edges kg_edges.csv --anchors stage1_cache.csv \
    --universe top50.csv --sectors sectors.csv \
    --gamma 0.5 --hops 2 --reps 5 --out precheck_out.csv
```

**Input contract:**

| File | Format | Description |
|---|---|---|
| `kg_edges.csv` | `src,dst[,weight]` | Knowledge graph edge list |
| `stage1_cache.csv` | `date,node,score` (long format) | Cached Stage-1 anchor scores |
| `top50.csv` | One ticker per line | 50 evaluation tickers |
| `sectors.csv` | `ticker,sector` | Sector membership (needed for A2 rung only) |

The `--gamma` and `--hops` flags must match the reported KG run (γ = 0.5,
hops = 2) or the pre-check does not describe the actual experiment.

**Interpreting the output:** The pre-check reports the mean per-stock
correlation between true and shuffled transmitted signals. Consult the
verdict bands from `ABLATION_SPEC.md` §7.4 (corrected 2026-08-01 — the
statistic is non-monotone, an inverted U):

| Mean Correlation | Interpretation |
|---|---|
| < 0.10 | Weak — shuffle produces a different signal; full ablation will separate cleanly |
| 0.10 – 0.55 | Best case — run the full ladder, lead with KG − A1 |
| 0.55 – 0.75 | Ambiguous — run the full ladder but lead with KG − A2 |
| > 0.75 | Do not lead with A1 — the shuffle baseline absorbs most of the lift; lead with KG − A2 and the coverage arithmetic |

### 8.3 Phase 1 — Generate Null Graphs (Seconds)

```bash
cd sim

# Verify degree preservation on synthetic data
python3 make_null_graphs.py --selftest

# Generate null graphs for the real experiment
python3 make_null_graphs.py \
    --edges kg_edges.csv --sectors sectors.csv \
    --out nulls/ --reps 10 --sweeps 20 --seed 20260802
```

This writes `nulls/A1_rep00.csv` through `nulls/A3_rep09.csv` (for R = 10)
plus `nulls/manifest.csv`. Every replicate is asserted to be:

- Degree-preserving (every node's in-degree and out-degree matches the real graph exactly)
- Self-loop-free
- Mass-matched (total propagated mass equals the KG run)
- Sector-preserving (for A2 rungs only)

Mixing is counted in **accepted** swaps, not attempts. The A2 sector
constraint rejects roughly `1 − 1/n_sector` of proposals, so counting
attempts would leave A2 mostly the real graph — not a valid null.

`--reps 10` gives a null band half-width of about 0.003 F1. Use R = 20 if
a run is cheap. R is chosen for a stable band, not for statistical power:
the held-out window is fixed, so replicates randomise the *shuffle*, not
the data.

### 8.4 Phase 2 — Run Your Pipeline Once Per Null Graph

This step runs on your own infrastructure and cannot be automated from this
repository. For each generated null graph, run your existing Stage 2–5
pipeline + classifier exactly as you ran it for the reported KG result:

```bash
for f in nulls/A1_rep*.csv nulls/A2_rep*.csv nulls/A3_rep*.csv; do
  your_pipeline --edges "$f" --out "${f%.csv}_f1.txt"
done
```

**Critical:** Everything except the edge file must be byte-identical to the
reported KG run:

- Corpus, date range, and the 551-day held-out window
- Stage-1 anchor scores (read from cache, never recomputed)
- Decay γ = 0.5, hops = 2, path cap ±50, staleness rule
- Feature construction, classifier family, hyperparameters, seed
- The 50-stock evaluation universe and the balanced-class operating point

All rungs are LLM-free — Stage-1 sentiment is cached per (item,
prompt-version) and propagation is deterministic post-processing over that
cache. No new inference calls, no re-labelling. A1 + A2 + A3 at R = 10 is 30
propagation-and-classify runs, plus one each for A4, Direct, and KG.

### 8.5 Phase 3 — Collect and Report

Assemble a single `results.csv` with columns `rung,rep,f1` (`rep = 0` for
deterministic rungs), then:

```bash
cd sim

# Verify the arithmetic on synthetic data
python3 collect_ablation.py --selftest

# Run on real results
python3 collect_ablation.py --results results.csv
```

The script prints:

1. Per-rung mean, standard deviation, and replicate count
2. Primary statistic: F1(KG) − F1(A1) in shuffle-sd units
3. Secondary statistic: F1(KG) − F1(A2) (the harder, more honest baseline)
4. Additive decomposition of the 11.5-point lift (volume share, sector share, firm-specific share)
5. Pre-registered verdict (PASS / AMBIGUOUS / REFUTED)
6. Ready-to-paste LaTeX table body

### 8.6 Pre-Registered Verdict

The verdict is hard-coded in `collect_ablation.py` so it cannot be tuned to
the result:

| Verdict | Criterion | Action |
|---|---|---|
| **PASS** | F1(KG) > 4 sd above A1 **and** > 2 sd above A2 | Lead with KG − A2 |
| **PASS (sector-driven)** | Clears A1 decisively but not A2 | Narrow claim to sector-level propagation |
| **AMBIGUOUS** | 2–4 sd above A1 | Report the gap with the band; do not lead with it |
| **REFUTED** | F1(KG) within 2 sd of A1 | Reframe as a coverage result |

### 8.7 Ablation Kit Selftests

Run all ablation kit selftests from the repository root:

```bash
make ablation
```

This invokes `--selftest` on `shuffle_control.py`, `ablation_design.py`,
and `collect_ablation.py`, verifying the simulation and collection
arithmetic on synthetic data.

### 8.8 Design Simulations (Optional)

Two calibrated simulations provide design insight before running the real
experiment:

| Script | Purpose |
|---|---|
| `ablation_design.py` | Answers Q1–Q3: predicted F1 for each rung under structural vs. coverage hypotheses; whether the predictions are distinguishable with 551 days and 50 stocks; how many shuffle replicates are needed |
| `shuffle_control.py` | Calibrates the world to Table 4 (news arrival is capitalisation-weighted, pinned by the reported Top-50 share of pre-propagation records = 46.67%); produces the reporting table, decomposition, and a lookup table mapping pre-check correlation to predicted KG − A1 separation |

**These are design simulations only.** No number produced by these scripts
may be reported in the paper as an experimental result.

---

## 9. Regenerating the Data Workbook

To rebuild `data/Sentiment_score_all.xlsx` from the anchor constants in
`lib/anchors.py`:

```bash
make data
# or equivalently:
python scripts/export_xlsx.py
```

This reconstructs all seven sheets from the Python constants. One caveat:
the `50_Stock_F1_Coverage` sheet is copied from the existing workbook if
present (it contains 50 rows of per-stock data that are not fully encoded
in `anchors.py`). If the source workbook is deleted before regeneration,
only the Top-5 rows are written as a fallback. To preserve the full 50-stock
sheet, keep the existing workbook or provide a replacement before running
`export_xlsx.py`.

---

## 10. Continuous Integration

The GitHub Actions workflow (`.github/workflows/verify.yml`) runs on every
push to `main` or `develop` and on every pull request to `main`. It tests
across Python 3.10, 3.11, and 3.12 on `ubuntu-latest`:

```yaml
steps:
  - uses: actions/checkout@v4
  - uses: actions/setup-python@v5
  - run: pip install -r requirements.txt
  - run: python run_experiments.py           # Run all experiments
  - run: python run_experiments.py --verify  # Verify against paper anchors
  - run: cd sim && python shuffle_control.py --selftest
  - run: cd sim && python ablation_design.py --selftest
```

A green badge on the repository README confirms all anchors pass in CI.

---

## 11. Troubleshooting

### Missing Data File

If `smoke_test.py` reports `File not found: data/Sentiment_score_all.xlsx`,
regenerate it:

```bash
python scripts/export_xlsx.py
```

### Missing Sheets

If the smoke test reports `Missing sheets`, the workbook is corrupted or
incomplete. Delete it and regenerate:

```bash
rm data/Sentiment_score_all.xlsx
python scripts/export_xlsx.py
```

### Import Errors

Ensure the virtual environment is activated and dependencies are installed:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Stage Verification Failure

If `make verify` fails at a specific stage, run that stage individually with
`--verify` for a focused error message:

```bash
python src/stage3_ablation.py --verify
```

### Ablation Kit Selftest Failure

Run the failing script's selftest directly for details:

```bash
cd sim
python shuffle_control.py --selftest
python ablation_design.py --selftest
python collect_ablation.py --selftest
```

### Cleaning Cached Files

```bash
make clean
```

This removes `__pycache__` directories, `.pyc` files, and `.pytest_cache`.

---

## 12. Paper Anchor Reference

All ground-truth values are defined in `lib/anchors.py` as a single source
of truth. The key anchors:

| Anchor | Value | Paper Reference |
|---|---|---|
| Same-day F1 | 0.7357 | Table 2 |
| Same-day Accuracy | 68.13% | Table 2 |
| Same-day AUC | 0.7170 | Table 2 |
| Next-day F1 | 0.6064 | Table 2 |
| Next-day Accuracy | 60.64% | Table 2 |
| Top-50 F1(KG) | 0.6456 | Table 3, Ablation KG |
| Top-50 F1(Direct) | 0.5309 | Table 3, Ablation Direct |
| Top-50 F1(Wide) | 0.5040 | Table 3, Ablation MarketWide |
| F1 Gain | +0.1147 | Table 3 |
| Coverage Multiplier (Overall) | 2.9688 | Table 4 |
| Coverage Multiplier (Top-50) | 1.2745 | Table 4 |
| Coverage Multiplier (Others) | 4.4517 | Table 4 |
| KG-LS Annualized Return | 14.6% | Table 6 |
| KG-LS Sharpe | 1.12 | Table 6 |
| LLM-LS Annualized Return | 5.9% | Table 6 |
| TAIEX Annualized Return | 34.0% | Table 6 |
| Ablation A1 F1 | 0.6138 (sd 0.0028) | §5 |
| Ablation A2 F1 | 0.6175 (sd 0.0035) | §5 |
| Ablation A4 F1 | 0.6296 | §5 |
| Z-score (KG vs A1) | 11.4 | §5 |
| Z-score (KG vs A2) | 8.0 | §5 |
| Verdict | PASS | §5 |
| Gain-Coverage R² | ≈ 0 | §5 |

---

## 13. Fixed Pipeline Parameters

The following ex-ante parameters are frozen across every rung of the
ablation ladder and the reported KG run. They are recorded in
`lib/anchors.py` under `PIPELINE_PARAMS`:

| Parameter | Value |
|---|---|
| Corpus window | 2023-01-01 to 2024-06-30 |
| Number of firms | 576 |
| Number of sectors | 33 |
| KG edges | 979 |
| Mean degree | 3.40 |
| Number of lags | 5 |
| Default threshold | 50 |
| Buy commission | 0.10% |
| Sell commission | 0.34% |
| Test window | 2024-01-02 to 2024-06-30 |
| Decay (γ) | 0.5 |
| Hops | 2 |
| Path cap | ±50 |
| Shuffle replicates (R) | 20 (or 10 if runs are expensive) |
| Shuffle sweeps | 20 |
| Seed | 20260802 (for reproducible null graph generation) |

---

## 14. Citation

If you use this code or data in your research, please cite:

> *Cross-Market Knowledge Graph Propagation for Taiwan Stock Supply Chain
> Sentiment Scoring.* ICAIF 2026.

---

## 15. License

Proprietary. All rights reserved. See [`LICENSE`](../LICENSE) for details.
