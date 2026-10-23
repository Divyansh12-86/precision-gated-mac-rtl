"""
scripts/synth_runner.py — Yosys Synthesis Runner & Metric Parser

Executes scripts/synth_yosys.ys and generates reports/synth.json.
Conforms strictly to Phase E:
  - Like-for-like comparison (same-mode rows only: LUT mode vs LUT mode, DSP mode vs DSP mode)
  - Family generic note: "xc7 family generic (no part-specific data)"
  - Overhead row: pg_top - baseline in same mode
  - Artix-7 35T utilisation percentages (Basys 3 reference: 20,800 LUT, 41,600 FF, 90 DSP)
  - Explicit timing and power note: "NOT RUN (no Vivado installed on host)"
"""

import os
import sys
import json
import re
import subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

BASYS3_BUDGET = {
    "luts": 20800,
    "ffs": 41600,
    "dsps": 90
}

def parse_cell_body(body):
    cells = {}
    for line in body.splitlines():
        cm = re.match(r"^\s*([A-Za-z0-9_]+)\s+(\d+)\s*$", line)
        if cm:
            cname, cnt = cm.groups()
            cells[cname] = int(cnt)

    lut_cnt = sum(cnt for cname, cnt in cells.items() if re.match(r"^LUT[1-6]$", cname))
    ff_cnt = sum(cnt for cname, cnt in cells.items() if cname.startswith("FD"))
    dsp_cnt = cells.get("DSP48E1", 0) + cells.get("DSP48", 0) + cells.get("DSP48A1", 0)
    carry_cnt = cells.get("CARRY4", 0)
    muxf_cnt = cells.get("MUXF7", 0) + cells.get("MUXF8", 0)
    bram_cnt = cells.get("RAMB18E1", 0) + cells.get("RAMB36E1", 0) * 2
    lutram_cnt = sum(cnt for cname, cnt in cells.items() if cname.startswith("RAM") and not cname.startswith("RAMB"))

    return {
        "luts": lut_cnt,
        "ffs": ff_cnt,
        "dsps": dsp_cnt,
        "carry4": carry_cnt,
        "muxf": muxf_cnt,
        "lutram": lutram_cnt,
        "bram_18k": bram_cnt,
        "cells": cells
    }

def main():
    ys_path = os.path.join(BASE_DIR, "scripts", "synth_yosys.ys")
    rpt_path = os.path.join(REPORTS_DIR, "synth_yosys.rpt")

    print("[SYNTH] Running Yosys synthesis script...", flush=True)
    cmd = ["yosys", "-s", ys_path]
    res = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True)
    with open(rpt_path, "w") as f:
        f.write(res.stdout)
        if res.stderr:
            f.write("\nSTDERR:\n" + res.stderr)

    if res.returncode != 0:
        print(f"Yosys synthesis failed:\n{res.stderr}")
        sys.exit(1)

    print(f"[SYNTH] Parsing synthesis report from {rpt_path}...")
    section_defs = [
        ("baseline_fir_lut", "baseline_fir_exact", "LUT"),
        ("pg_top_lut", "pg_top", "LUT"),
        ("qrs_detector_lut", "qrs_detector", "LUT"),
        ("baseline_fir_dsp", "baseline_fir_exact", "DSP"),
        ("pg_top_dsp", "pg_top", "DSP"),
        ("top_basys3", "top_basys3", "DSP"),
        ("top_nexys_a7", "top_nexys_a7", "DSP"),
        ("top_basys3_lut", "top_basys3", "LUT"),
        ("top_nexys_a7_lut", "top_nexys_a7", "LUT")
    ]

    # Split report by SYNTH_SECTION:
    sec_splits = re.split(r"SYNTH_SECTION:\s*(\w+)", res.stdout)
    sec_dict = {}
    for i in range(1, len(sec_splits), 2):
        s_name = sec_splits[i].strip()
        s_text = sec_splits[i+1]
        sec_dict[s_name] = s_text

    parsed = {}
    for key, mod_name, mode in section_defs:
        s_text = sec_dict.get(key, "")
        # Look for "=== design hierarchy ===" first
        h_splits = s_text.split("=== design hierarchy ===")
        if len(h_splits) > 1:
            # Take the last hierarchy block
            body = h_splits[-1]
        else:
            # Look for "=== <mod_name> ==="
            m_splits = re.split(rf"===\s*{mod_name}\s*===", s_text)
            body = m_splits[-1] if len(m_splits) > 1 else s_text

        metrics = parse_cell_body(body)
        pct_lut = round((metrics["luts"] / BASYS3_BUDGET["luts"]) * 100.0, 2)
        pct_ff = round((metrics["ffs"] / BASYS3_BUDGET["ffs"]) * 100.0, 2)
        pct_dsp = round((metrics["dsps"] / BASYS3_BUDGET["dsps"]) * 100.0, 2)

        parsed[key] = {
            "module": mod_name,
            "mode": mode,
            "luts": metrics["luts"],
            "ffs": metrics["ffs"],
            "dsps": metrics["dsps"],
            "carry4": metrics["carry4"],
            "muxf": metrics["muxf"],
            "lutram": metrics["lutram"],
            "bram_18k": metrics["bram_18k"],
            "basys3_util_pct": {
                "lut_pct": pct_lut,
                "ff_pct": pct_ff,
                "dsp_pct": pct_dsp
            }
        }

    # Same-mode overhead rows
    overhead_lut = {
        "comparison": "pg_top - baseline (LUT mode)",
        "delta_luts": parsed["pg_top_lut"]["luts"] - parsed["baseline_fir_lut"]["luts"],
        "delta_ffs": parsed["pg_top_lut"]["ffs"] - parsed["baseline_fir_lut"]["ffs"],
        "delta_dsps": 0
    }
    overhead_dsp = {
        "comparison": "pg_top - baseline (DSP mode)",
        "delta_luts": parsed["pg_top_dsp"]["luts"] - parsed["baseline_fir_dsp"]["luts"],
        "delta_ffs": parsed["pg_top_dsp"]["ffs"] - parsed["baseline_fir_dsp"]["ffs"],
        "delta_dsps": parsed["pg_top_dsp"]["dsps"] - parsed["baseline_fir_dsp"]["dsps"]
    }

    synth_json_data = {
        "target_technology": "Xilinx 7-Series xc7 family generic (no part-specific data)",
        "tool": "Yosys 0.33",
        "timing_and_power_status": "NOT RUN (no Vivado installed on host; Vivado OOC script provided in scripts/synth_vivado_ooc.tcl)",
        "phase_c_target_check": {
            "pg_top_lut_actual": f"{parsed['pg_top_lut']['luts']} LUTs, {parsed['pg_top_lut']['ffs']} FFs",
            "pg_top_lut_target": "<= 1500 LUTs, <= 800 FFs",
            "target_met": (parsed["pg_top_lut"]["luts"] <= 1500) and (parsed["pg_top_lut"]["ffs"] <= 800)
        },
        "modules": parsed,
        "gating_overhead_same_mode": {
            "lut_mode": overhead_lut,
            "dsp_mode": overhead_dsp
        }
    }

    out_json = os.path.join(REPORTS_DIR, "synth.json")
    with open(out_json, "w") as f:
        json.dump(synth_json_data, f, indent=2)
    print(f"\n[DONE] Synthesis metrics saved to {out_json}")

    print("\n==================================================================")
    print("SYNTHESIS SUMMARY TABLE (Like-For-Like Same-Mode Comparison):")
    print("==================================================================")
    print(f"{'Module':<20} {'Mode':<6} {'LUTs':<8} {'FFs':<8} {'DSPs':<6} {'Basys3 LUT%':<12}")
    print("------------------------------------------------------------------")
    for k, v in parsed.items():
        print(f"{v['module']:<20} {v['mode']:<6} {v['luts']:<8} {v['ffs']:<8} {v['dsps']:<6} {v['basys3_util_pct']['lut_pct']:<12}%")
    print("------------------------------------------------------------------")
    print(f"Overhead LUT mode: +{overhead_lut['delta_luts']} LUTs, +{overhead_lut['delta_ffs']} FFs")
    print(f"Overhead DSP mode: +{overhead_dsp['delta_luts']} LUTs, +{overhead_dsp['delta_ffs']} FFs, {overhead_dsp['delta_dsps']} DSPs")
    print("==================================================================")

if __name__ == "__main__":
    main()
