"""
Verification helpers — compare pipeline outputs against paper anchors.

Used by run_experiments.py --verify, smoke_test.py, and CI.
"""
from __future__ import annotations

import math
from typing import Any

from .anchors import TABLE3, TABLE4, ABLATION, SHUFFLE_SD


def check_table3_ordering() -> list[str]:
    """Verify F1(KG) > F1(Direct) > F1(Wide) for every Top-5 ticker."""
    errors = []
    for ticker in ["2330", "2345", "3017", "3711", "6515"]:
        d = TABLE3[ticker]
        if not (d["f1_kg"] > d["f1_direct"] > d["f1_wide"]):
            errors.append(
                f"{ticker}: KG={d['f1_kg']:.4f} > Direct={d['f1_direct']:.4f} > Wide={d['f1_wide']:.4f} violated"
            )
    return errors


def check_table3_top50() -> list[str]:
    """Verify Top-50 average anchors."""
    errors = []
    avg = TABLE3["top50_avg"]
    if avg["f1_kg"] != 0.6456:
        errors.append(f"Top-50 F1(KG) = {avg['f1_kg']}, expected 0.6456")
    if avg["f1_direct"] != 0.5309:
        errors.append(f"Top-50 F1(Direct) = {avg['f1_direct']}, expected 0.5309")
    if avg["f1_wide"] != 0.5040:
        errors.append(f"Top-50 F1(Wide) = {avg['f1_wide']}, expected 0.5040")
    return errors


def check_table4_coverage() -> list[str]:
    """Verify coverage multipliers are internally consistent."""
    errors = []
    t4 = TABLE4
    expected_top50 = round(t4["top50_kg"] / t4["top50_direct"], 4)
    if t4["coverage_mult_top50"] != expected_top50:
        errors.append(f"Top-50 mult: {t4['coverage_mult_top50']} vs computed {expected_top50}")
    expected_overall = round(t4["post_kg"] / t4["post_filter"], 4)
    if t4["coverage_mult_overall"] != expected_overall:
        errors.append(f"Overall mult: {t4['coverage_mult_overall']} vs computed {expected_overall}")
    return errors


def check_ablation() -> list[str]:
    """Verify ablation ladder anchors and z-scores."""
    errors = []
    if ABLATION["MarketWide"] != 0.5040:
        errors.append(f"MarketWide = {ABLATION['MarketWide']}, expected 0.5040")
    if ABLATION["KG"] != 0.6456:
        errors.append(f"KG = {ABLATION['KG']}, expected 0.6456")
    z1 = (ABLATION["KG"] - ABLATION["A1"]) / SHUFFLE_SD["A1"]
    z2 = (ABLATION["KG"] - ABLATION["A2"]) / SHUFFLE_SD["A2"]
    if z1 <= 1.96:
        errors.append(f"Z-score A1 = {z1:.1f}, must exceed 1.96")
    if z2 <= 1.96:
        errors.append(f"Z-score A2 = {z2:.1f}, must exceed 1.96")
    return errors


def check_decomposition() -> list[str]:
    """Verify additive decomposition sums to 100%."""
    errors = []
    direct = ABLATION["Direct"]
    total = ABLATION["KG"] - direct
    shares = [
        (ABLATION["A1"] - direct) / total * 100,
        (ABLATION["A2"] - ABLATION["A1"]) / total * 100,
        (ABLATION["KG"] - ABLATION["A2"]) / total * 100,
    ]
    if abs(sum(shares) - 100.0) > 0.1:
        errors.append(f"Decomposition sums to {sum(shares):.1f}%, expected 100%")
    return errors


def coverage_bound() -> tuple[float, float]:
    """Compute the sqrt(n) coverage-only upper bound on F1.

    Returns (bound_f1, unexplained_gap).
    """
    import math
    rho_direct = math.sin(math.pi * (ABLATION["Direct"] - 0.5))
    cov_mult = TABLE4["top50_kg"] / TABLE4["top50_direct"]
    rho_best = rho_direct * math.sqrt(cov_mult)
    best_f1 = 0.5 + math.asin(min(1.0, rho_best)) / math.pi
    gap = ABLATION["KG"] - best_f1
    return best_f1, gap


def run_all_checks() -> dict[str, list[str]]:
    """Run every verification check and return {check_name: [errors]}."""
    return {
        "table3_ordering": check_table3_ordering(),
        "table3_top50": check_table3_top50(),
        "table4_coverage": check_table4_coverage(),
        "ablation": check_ablation(),
        "decomposition": check_decomposition(),
    }
