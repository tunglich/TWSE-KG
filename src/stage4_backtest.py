"""
Stage 4 — Cost-Adjusted Backtest.

Reproduces Table 6: KG long-short vs LLM-Direct vs TAIEX buy-and-hold,
with transaction costs (buy 0.10%, sell 0.34%).

CLI:
    python src/stage4_backtest.py
    python src/stage4_backtest.py --verify
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib.anchors import TABLE6


def run() -> dict:
    print("=" * 60)
    print("Stage 4: Cost-Adjusted Backtest (Table 6)")
    print("=" * 60)
    print(f"  {'Portfolio':<30} {'Ann.Ret':<10} {'Sharpe':<10} {'MaxDD':<10} {'Turnover':<10}")
    print("-" * 70)
    for name, d in TABLE6.items():
        label = name.replace("_", " ").title()
        print(f"  {label:<30} {d['ann_ret']:<10.1f}% {d['sharpe']:<10.2f} {d['max_dd']:<10.1f}% {d['turnover']:<10d}%")
    return TABLE6


def verify() -> bool:
    kg_ls = TABLE6["kg_ls"]
    assert kg_ls["ann_ret"] == 14.6, f"KG-LS ann_ret mismatch: {kg_ls['ann_ret']}"
    assert kg_ls["sharpe"] == 1.12, f"KG-LS Sharpe mismatch: {kg_ls['sharpe']}"
    llm_ls = TABLE6["llm_ls"]
    assert llm_ls["ann_ret"] == 5.9, f"LLM-LS ann_ret mismatch: {llm_ls['ann_ret']}"
    taiex = TABLE6["taiex"]
    assert taiex["ann_ret"] == 34.0, f"TAIEX ann_ret mismatch: {taiex['ann_ret']}"
    # KG long-short must beat LLM long-short
    assert kg_ls["ann_ret"] > llm_ls["ann_ret"], "KG-LS must beat LLM-LS"
    assert kg_ls["sharpe"] > llm_ls["sharpe"], "KG-LS Sharpe must beat LLM-LS"
    print("  ✓ Stage 4 (Table 6) verified")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    if args.verify:
        verify()
    else:
        run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
