#!/usr/bin/env python3
"""
scripts/run_viewer_snapshots.py — Executes headless viewer snapshots and verifies outputs

Generates the 4 required headless PNG snapshots:
  1. reports/figs/viewer_rtl_dump.png (from reports/board_uart_dump.bin, duration 12)
  2. reports/figs/viewer_sim_auto.png (from simulation, duration 12)
  3. reports/figs/viewer_sim_full.png (from simulation forced full, duration 12)
  4. reports/figs/viewer_sim_approx.png (from simulation forced approx, duration 12)

Verifies each command succeeds with exit code 0 and generated PNGs are > 40 kB.
"""

import os
import sys
import subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON_EXE = sys.executable

def main():
    os.makedirs(os.path.join(BASE_DIR, "reports", "figs"), exist_ok=True)

    commands = [
        [PYTHON_EXE, "scripts/ecg_live_viewer.py", "--file", "reports/board_uart_dump.bin", "--snapshot", "reports/figs/viewer_rtl_dump.png", "--duration", "12"],
        [PYTHON_EXE, "scripts/ecg_live_viewer.py", "--simulate", "--snapshot", "reports/figs/viewer_sim_auto.png", "--duration", "12"],
        [PYTHON_EXE, "scripts/ecg_live_viewer.py", "--simulate", "--sim-mode", "full", "--snapshot", "reports/figs/viewer_sim_full.png", "--duration", "12"],
        [PYTHON_EXE, "scripts/ecg_live_viewer.py", "--simulate", "--sim-mode", "approx", "--snapshot", "reports/figs/viewer_sim_approx.png", "--duration", "12"],
    ]

    for cmd in commands:
        print(f"Command: {' '.join(cmd)}")
        res = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True)
        if res.stdout:
            print(res.stdout, end="")
        if res.stderr:
            print(res.stderr, end="", file=sys.stderr)
        if res.returncode != 0:
            print(f"ERROR: Command failed with exit code {res.returncode}")
            sys.exit(res.returncode)

    figs = ["viewer_rtl_dump.png", "viewer_sim_auto.png", "viewer_sim_full.png", "viewer_sim_approx.png"]
    for fig in figs:
        p = os.path.join(BASE_DIR, "reports", "figs", fig)
        if not os.path.exists(p):
            print(f"ERROR: Missing snapshot PNG: {p}")
            sys.exit(1)
        sz = os.path.getsize(p)
        if sz < 40960:
            print(f"ERROR: Snapshot PNG {fig} is only {sz} bytes (< 40 kB)")
            sys.exit(1)
        print(f"Verified {fig}: {sz} bytes (> 40 kB)")

    print("VIEWER SNAPSHOTS: ALL 4 GENERATED AND VERIFIED")
    sys.exit(0)

if __name__ == "__main__":
    main()
