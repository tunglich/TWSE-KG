#!/usr/bin/env python3
"""
TWSE-KG Smoke Test — quick (< 5 second) sanity check.

Verifies that:
  1. All Python modules import without error
  2. Paper anchor constants are internally consistent
  3. The xlsx data file exists and has all 7 sheets
  4. Every stage script can run --verify without assertion failures

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
RED = "\033[91m"
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

    # 1. Import all modules
    section("1. Module Imports")
    try:
        from lib.anchors import TABLE2, TABLE3, TABLE4, TABLE6, ABLATION, SHUFFLE_SD, PIPELINE_PARAMS, TOP5_TICKERS
        from lib.data import load_workbook, EXPECTED_SHEETS
        from lib.metrics import run_all_checks, coverage_bound
        ok("lib.anchors, lib.data, lib.metrics imported")
    except Exception as e:
        fail(f"Import error: {e}")
        _print_summary(t0)
        return 1

    # 2. Anchor consistency
    section("2. Anchor Consistency")
    checks = run_all_checks()
    for name, errs in checks.items():
        if errs:
            for e in errs:
                fail(f"{name}: {e}")
        else:
            ok(name)

    # 3. Coverage bound
    section("3. Coverage-Only Bound")
    try:
        bound, gap = coverage_bound()
        assert gap > 0, f"Coverage bound {bound:.4f} >= KG {ABLATION['KG']:.4f}"
        ok(f"Bound = {bound:.4f}, gap = +{gap:.4f}")
    except Exception as e:
        fail(str(e))

    # 4. Data file
    section("4. Data File (Sentiment_score_all.xlsx)")
    xlsx_path = REPO_ROOT / "data" / "Sentiment_score_all.xlsx"
    if xlsx_path.exists():
        try:
            wb = load_workbook()
            missing = set(EXPECTED_SHEETS) - set(wb.sheetnames)
            if missing:
                fail(f"Missing sheets: {missing}")
            else:
                ok(f"All {len(EXPECTED_SHEETS)} sheets present ({xlsx_path.stat().st_size / 1024:.0f} KB)")
            wb.close()
        except Exception as e:
            fail(str(e))
    else:
        fail(f"File not found: {xlsx_path}")

    # 5. Stage scripts
    section("5. Stage Script Verification")
    stages = [
        ("Stage 1 (Table 2)", "src.stage1_market_level"),
        ("Stage 2 (Tables 3&4)", "src.stage2_firm_level"),
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

    # 6. Ablation kit scripts present
    section("6. Ablation Kit Scripts")
    sim_dir = REPO_ROOT / "sim"
    for script in ["shuffle_control.py", "ablation_design.py", "collect_ablation.py"]:
        if (sim_dir / script).exists():
            ok(f"sim/{script}")
        else:
            fail(f"sim/{script} missing")

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
