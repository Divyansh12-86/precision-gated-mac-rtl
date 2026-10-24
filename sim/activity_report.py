"""
sim/activity_report.py — RTL Switching Activity Characterization (Datapath + Whole Core)

Executes tb_activity across 6 standard and noise sets:
  - std_fixed_100
  - std_fixed_101
  - std_fixed_103
  - std_fixed_105
  - std_minmax_100
  - noise_stress

Captures:
  1. Datapath: Operand High, Operand Low, Multiplier, Accumulator
  2. Whole-Core: Datapath + DelayLine RAM + Control FSM + QRS Detector
Outputs:
  reports/activity.json (per-set unweighted metrics, datapath and whole-core)
"""

import os
import sys
import json
import re
import subprocess
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
BUILD_DIR = os.path.join(BASE_DIR, "build_activity")
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(BUILD_DIR, exist_ok=True)

SETS = [
    "std_fixed_100",
    "std_fixed_101",
    "std_fixed_103",
    "std_fixed_105",
    "std_minmax_100",
    "noise_stress"
]

def compile_tb():
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
    print("[ACTIVITY] Compiling tb_activity with Verilator...", flush=True)
    res = subprocess.run(cmd_compile, cwd=BASE_DIR, capture_output=True, text=True)
    if res.returncode != 0:
        print("Compilation failed:\n", res.stderr)
        sys.exit(1)
    return os.path.join(BUILD_DIR, "sim_activity")

def run_set(bin_path, set_name):
    vec_dir = os.path.join("data/test_vectors", set_name)
    print(f"\n[ACTIVITY] Running activity simulation for {set_name}...", flush=True)
    t0 = time.time()
    res = subprocess.run([bin_path, f"+VEC_DIR={vec_dir}"], cwd=BASE_DIR, capture_output=True, text=True)
    elapsed = time.time() - t0
    out = res.stdout
    if res.returncode != 0:
        print(f"Error running {set_name}:\n{res.stderr}")
        sys.exit(1)

    # Regex patterns
    pat_dp = re.compile(r"(\w+):\s+oph=(\d+)\s+opl=(\d+)\s+mult=(\d+)\s+acc=(\d+)\s+total=(\d+)")
    pat_core = re.compile(r"CORE_(\w+):\s+dp=(\d+)\s+dline=(\d+)\s+ctrl=(\d+)\s+det=(\d+)\s+core_total=(\d+)")

    dp_data = {}
    for line in out.splitlines():
        m = pat_dp.search(line)
        if m:
            name, oph, opl, mult, acc, tot = m.groups()
            dp_data[name.lower()] = {
                "op_high": int(oph),
                "op_low": int(opl),
                "mult": int(mult),
                "acc": int(acc),
                "total": int(tot)
            }

    core_data = {}
    for line in out.splitlines():
        m = pat_core.search(line)
        if m:
            name, dp, dline, ctrl, det, tot = m.groups()
            core_data[name.lower()] = {
                "datapath": int(dp),
                "delay_line": int(dline),
                "control": int(ctrl),
                "detector": int(det),
                "core_total": int(tot)
            }

    base_dp = dp_data.get("baseline", {})
    auto_dp = dp_data.get("gated_auto", {})
    base_core = core_data.get("baseline", {})
    auto_core = core_data.get("gated_auto", {})

    dp_tot_base = base_dp.get("total", 0)
    dp_tot_auto = auto_dp.get("total", 0)
    opl_base = base_dp.get("op_low", 0)
    opl_auto = auto_dp.get("op_low", 0)

    core_tot_base = base_core.get("core_total", 0)
    core_tot_auto = auto_core.get("core_total", 0)

    dp_reduc = round((1.0 - dp_tot_auto / dp_tot_base) * 100.0, 2) if dp_tot_base else 0.0
    opl_reduc = round((1.0 - opl_auto / opl_base) * 100.0, 2) if opl_base else 0.0
    core_reduc = round((1.0 - core_tot_auto / core_tot_base) * 100.0, 2) if core_tot_base else 0.0

    print(f"  --> Datapath: Baseline={dp_tot_base:,} | Gated={dp_tot_auto:,} | Reduction={dp_reduc:.2f}% | OPL Reduc={opl_reduc:.2f}%")
    print(f"  --> Whole Core: Baseline={core_tot_base:,} | Gated={core_tot_auto:,} | Reduction={core_reduc:.2f}% ({elapsed:.2f}s)")

    return {
        "set_name": set_name,
        "datapath": {
            "baseline": base_dp,
            "gated_auto": auto_dp,
            "gated_full": dp_data.get("gated_full", {}),
            "gated_approx": dp_data.get("gated_approx", {}),
            "low_operand_reduction_pct": opl_reduc,
            "datapath_reduction_pct": dp_reduc
        },
        "whole_core": {
            "baseline": base_core,
            "gated_auto": auto_core,
            "whole_core_reduction_pct": core_reduc
        }
    }

def main():
    bin_path = compile_tb()
    results = {}
    for s in SETS:
        results[s] = run_set(bin_path, s)

    act_file = os.path.join(REPORTS_DIR, "activity.json")
    with open(act_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[DONE] Saved activity report for all {len(SETS)} sets to {act_file}")

    # Also update reports/results.json if present
    res_file = os.path.join(REPORTS_DIR, "results.json")
    if os.path.exists(res_file):
        with open(res_file, "r") as f:
            rj = json.load(f)
        rj["activity_multiset"] = results
        # keep standard 100 as top-level activity
        if "std_fixed_100" in results:
            rj["activity"] = results["std_fixed_100"]["datapath"]
        with open(res_file, "w") as f:
            json.dump(rj, f, indent=2)
        print(f"Updated {res_file} with activity data.")

if __name__ == "__main__":
    main()
