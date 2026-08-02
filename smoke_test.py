#!/usr/bin/env python3
"""
TWSE-KG Smoke Test — quick (< 10 second) sanity check.

Verifies that:
  1. All Python modules import without error
  2. Paper anchor constants are internally consistent
  3. The KG CSV data files exist and have the expected row counts
  4. Every stage script can run --verify without assertion failures
  5. Pipeline cache loads correctly

Exit code 0 = all green, nonzero = something is broken.

Usage:
    python smoke_test.py
"""
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

GREEN = "\033[92m"
RED   = "\033[91m"
RESET = "\033[0m"

passed = 0
failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  {GREEN}✓{RESET} {msg}")


def fail(msg):
    global failed
    failed += 1
    print(f"  {RED}✗{RESET} {msg}")


def section(title):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


def main() -> int:
    t0 = time.time()

    print("TWSE-KG Smoke Test")
    print("=" * 60)

    # ── 1. Import all modules ──────────────────────────────────────
    section("1. Module Imports")
    try:
        from lib.anchors import (TABLE2, TABLE3, TABLE4, TABLE6, ABLATION,
                                  SHUFFLE_SD, PIPELINE_PARAMS, TOP5_TICKERS)
        from lib.data import load_workbook, EXPECTED_SHEETS
        from lib.metrics import run_all_checks, coverage_bound
        from lib.pipeline import load_pipeline_results, CACHE_PATH
        ok("lib.anchors, lib.data, lib.metrics, lib.pipeline imported")
    except Exception as e:
        fail(f"Import error: {e}")
        _print_summary(t0)
        return 1

    # ── 2. Anchor consistency ──────────────────────────────────────
    section("2. Anchor Consistency")
    checks = run_all_checks()
    for name, errs in checks.items():
        if errs:
            for e in errs:
                fail(f"{name}: {e}")
        else:
            ok(name)

    # ── 3. Coverage bound ─────────────────────────────────────────
    section("3. Coverage-Only Bound")
    try:
        bound, gap = coverage_bound()
        assert gap > 0, f"Coverage bound {bound:.4f} >= KG {ABLATION['KG']:.4f}"
        ok(f"Bound = {bound:.4f}, gap = +{gap:.4f}")
    except Exception as e:
        fail(str(e))

    # ── 4. KG data files ──────────────────────────────────────────
    section("4. KG Data Files (data/kg/)")
    kg_dir = REPO_ROOT / "data" / "kg"
    expected_kg = {
        "companies.csv":    100,    # at least 100 rows
        "supplies_to.csv":  1000,   # at least 1000 edges
        "competes_with.csv": 100,   # at least 100 edges
    }
    for fname, min_rows in expected_kg.items():
        fpath = kg_dir / fname
        if fpath.exists():
            try:
                import csv
                with open(fpath, encoding="utf-8") as f:
                    n = sum(1 for _ in csv.reader(f)) - 1  # exclude header
                if n >= min_rows:
                    ok(f"{fname}: {n:,} rows")
                else:
                    fail(f"{fname}: only {n} rows (expected >= {min_rows})")
            except Exception as e:
                fail(f"{fname}: {e}")
        else:
            fail(f"{fname} not found in {kg_dir}")

    # Also check legacy xlsx if present
    xlsx_path = REPO_ROOT / "data" / "Sentiment_score_all.xlsx"
    if xlsx_path.exists():
        try:
            wb = load_workbook()
            missing = set(EXPECTED_SHEETS) - set(wb.sheetnames)
            if missing:
                fail(f"Sentiment_score_all.xlsx missing sheets: {missing}")
            else:
                ok(f"Sentiment_score_all.xlsx: {len(EXPECTED_SHEETS)} sheets "
                   f"({xlsx_path.stat().st_size / 1024:.0f} KB)")
            wb.close()
        except Exception as e:
            fail(str(e))
    else:
        ok("Sentiment_score_all.xlsx not in repo (large file — stored externally, OK)")

    # ── 5. Pipeline cache ─────────────────────────────────────────
    section("5. Pipeline Cache")
    try:
        if CACHE_PATH.exists():
            res = load_pipeline_results()
            t2 = res["table2"]
            t6 = res["table6"]
            assert 0.5 < t2["f1"] < 1.0, f"T2 F1 out of range: {t2['f1']}"
            assert t6["ann_ret"] > 0,      f"T6 ann_ret not positive: {t6['ann_ret']}"
            ok(f"Cache loaded: T2 F1={t2['f1']:.4f}, T6 Ann.Ret={t6['ann_ret']*100:.1f}%")
        else:
            ok(f"Cache not present at {CACHE_PATH} (will be created on first run)")
    except Exception as e:
        fail(f"Pipeline cache error: {e}")

    # ── 6. Stage scripts ──────────────────────────────────────────
    section("6. Stage Script Verification")
    stages = [
        ("Stage 1 (Table 2)",  "src.stage1_market_level"),
        ("Stage 3 (Ablation)", "src.stage3_ablation"),
        ("Stage 4 (Backtest)", "src.stage4_backtest"),
        ("Stage 5 (50-Stock)", "src.stage5_50stock"),
    ]
    for label, module_name in stages:
        try:
            mod = __import__(module_name, fromlist=["verify"])
            if mod.verify():
                ok(label)
            else:
                fail(f"{label} returned False")
        except Exception as e:
            fail(f"{label}: {e}")

    # ── 7. Ablation kit scripts ───────────────────────────────────
    section("7. Ablation Kit Scripts")
    exp_dir = REPO_ROOT / "exp"
    for script in ["shuffle_control.py", "ablation_design.py", "collect_ablation.py"]:
        if (exp_dir / script).exists():
            ok(f"exp/{script}")
        else:
            fail(f"exp/{script} missing")

    _print_summary(t0)
    return 1 if failed else 0


def _print_summary(t0: float):
    elapsed = time.time() - t0
    print(f"\n{'─' * 60}")
    print(f"  {GREEN}Passed: {passed}{RESET}  {RED}Failed: {failed}{RESET}  Time: {elapsed:.1f}s")
    print(f"{'─' * 60}")
    if failed:
        print(f"  {RED}SMOKE TEST FAILED — {failed} issue(s){RESET}")
    else:
        print(f"  {GREEN}SMOKE TEST PASSED — all checks green{RESET}")


if __name__ == "__main__":
    raise SystemExit(main())
