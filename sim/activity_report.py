"""
sim/activity_report.py — Run RTL Activity Simulation and Generate reports/activity.json
"""

import os
import sys
import json
import re
import subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
BUILD_DIR = os.path.join(BASE_DIR, "build_activity")
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(BUILD_DIR, exist_ok=True)

def run_activity():
    # 1. Compile tb_activity
    cmd_compile = [
        "verilator", "--binary", "--timing",
        "-Wno-WIDTHTRUNC", "-Wno-WIDTHEXPAND", "-Wno-INITIALDLY",
        "-Irtl",
        "tb/tb_activity.v",
        "rtl/baseline_fir_exact.v",
        "rtl/pg_top.v",
        "rtl/qrs_detector.v",
        "rtl/pg_fir.v",
        "rtl/sample_delay_line.v",
        "rtl/fir_coeff_rom.v",
        "rtl/mult_split.v",
        "rtl/pg_mac.v",
        "--Mdir", BUILD_DIR,
        "-o", "sim_activity"
    ]
    print("Compiling tb_activity with Verilator...")
    res = subprocess.run(cmd_compile, cwd=BASE_DIR, capture_output=True, text=True)
    if res.returncode != 0:
        print("Compilation failed:\n", res.stderr)
        sys.exit(1)

    # 2. Run on smoke set (1000 samples)
    bin_path = os.path.join(BUILD_DIR, "sim_activity")
    cmd_run = [bin_path, "+VEC_DIR=data/test_vectors/smoke"]
    print("Running activity simulation on 1,000 samples...")
    res_run = subprocess.run(cmd_run, cwd=BASE_DIR, capture_output=True, text=True)
    out = res_run.stdout
    print(out)

    # 3. Parse outputs
    pat = re.compile(r"(\w+):\s+oph=(\d+)\s+opl=(\d+)\s+mult=(\d+)\s+acc=(\d+)\s+total=(\d+)")
    data = {}
    for line in out.splitlines():
        m = pat.search(line)
        if m:
            name, oph, opl, mult, acc, tot = m.groups()
            data[name.lower()] = {
                "op_high": int(oph),
                "op_low": int(opl),
                "mult": int(mult),
                "acc": int(acc),
                "total": int(tot)
            }

    if "baseline" in data and "gated_auto" in data:
        base = data["baseline"]
        auto = data["gated_auto"]
        data["savings_pct"] = {
            "op_low_reduction_pct": round((1.0 - auto["op_low"] / base["op_low"]) * 100.0, 2) if base["op_low"] else 0.0,
            "mult_reduction_pct": round((1.0 - auto["mult"] / base["mult"]) * 100.0, 2) if base["mult"] else 0.0,
            "acc_reduction_pct": round((1.0 - auto["acc"] / base["acc"]) * 100.0, 2) if base["acc"] else 0.0,
            "total_datapath_reduction_pct": round((1.0 - auto["total"] / base["total"]) * 100.0, 2) if base["total"] else 0.0
        }

    # 4. Save reports/activity.json
    act_file = os.path.join(REPORTS_DIR, "activity.json")
    with open(act_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved activity metrics to {act_file}")

    # Also update reports/results.json if present
    res_file = os.path.join(REPORTS_DIR, "results.json")
    if os.path.exists(res_file):
        with open(res_file, "r") as f:
            rj = json.load(f)
        rj["activity"] = data
        with open(res_file, "w") as f:
            json.dump(rj, f, indent=2)
        print(f"Updated {res_file} with activity data.")

if __name__ == "__main__":
    run_activity()
