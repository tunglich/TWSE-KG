"""
Utility script — run the ablation kit selftests.

Wraps the sim/ directory scripts so they can be invoked from the repo root
with a single command, matching the Market-Timing-DQN utility-script pattern.

CLI:
    python scripts/run_ablation_kit.py
    python scripts/run_ablation_kit.py --selftest-only
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SIM_DIR = REPO_ROOT / "sim"


def run_selftest(script: str) -> int:
    """Run a script with --selftest flag and return exit code."""
    print(f"\n--- {script} --selftest ---")
    result = subprocess.run(
        [sys.executable, str(SIM_DIR / script), "--selftest"],
        cwd=str(SIM_DIR),
        capture_output=False,
    )
    return result.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest-only", action="store_true", help="Only run selftests, skip full run")
    args = ap.parse_args()

    scripts = ["shuffle_control.py", "ablation_design.py", "collect_ablation.py"]
    all_ok = True

    for script in scripts:
        if not (SIM_DIR / script).exists():
            print(f"  [skip] {script} not found")
            continue
        rc = run_selftest(script)
        if rc != 0:
            print(f"  ✗ {script} selftest failed (rc={rc})")
            all_ok = False
        else:
            print(f"  ✓ {script} selftest passed")

    if all_ok:
        print("\nAll ablation kit selftests passed ✓")
        return 0
    else:
        print("\nSome selftests failed ✗")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
