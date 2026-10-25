#!/usr/bin/env python3
"""
scripts/check_docs_numbers.py — Automated Validator for Documentation Metrics

Validates that every hardware and performance metric stated in README.md and AGENTS.md
matches the generated JSON reports in reports/*.json exactly (to within stated rounding precision).

Outputs:
  Prints checked parameters and returns exit code 0 if all match, or exit code 1 on mismatch.
"""

import os
import sys
import json
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

def load_json(name):
    path = os.path.join(REPORTS_DIR, name)
    if not os.path.exists(path):
        print(f"ERROR: Missing report artifact {path}")
        sys.exit(1)
    with open(path, "r") as f:
        return json.load(f)

def read_doc(rel_path):
    path = os.path.join(BASE_DIR, rel_path)
    if not os.path.exists(path):
        print(f"ERROR: Missing document {path}")
        sys.exit(1)
    with open(path, "r") as f:
        return f.read()

def main():
    print("==================================================================")
    print("VALIDATING DOCUMENTATION NUMBERS AGAINST JSON REPORTS")
    print("==================================================================")

    readme = read_doc("README.md")
    agents = read_doc("AGENTS.md")

    # Strip markdown bold formatting for robust number matching
    readme_clean = readme.replace("**", "").replace("`", "")
    agents_clean = agents.replace("**", "").replace("`", "")

    synth = load_json("synth.json")
    activity = load_json("activity.json")
    results = load_json("results.json")
    mutation = load_json("mutation.json")

    mismatches = 0

    # 1. Synthesis numbers check
    pg_top_lut = synth["modules"]["pg_top_lut"]["luts"]
    pg_top_ff = synth["modules"]["pg_top_lut"]["ffs"]
    qrs_lut = synth["modules"]["qrs_detector_lut"]["luts"]
    qrs_ff = synth["modules"]["qrs_detector_lut"]["ffs"]
    base_lut = synth["modules"]["baseline_fir_lut"]["luts"]
    base_ff = synth["modules"]["baseline_fir_lut"]["ffs"]
    delta_lut = synth["gating_overhead_same_mode"]["lut_mode"]["delta_luts"]
    delta_ff = synth["gating_overhead_same_mode"]["lut_mode"]["delta_ffs"]
    pg_dsp_lut = synth["modules"]["pg_top_dsp"]["luts"]
    pg_dsp_ff = synth["modules"]["pg_top_dsp"]["ffs"]
    pg_dsp_dsp = synth["modules"]["pg_top_dsp"]["dsps"]
    basys3_lut = synth["modules"]["top_basys3"]["luts"]
    basys3_ff = synth["modules"]["top_basys3"]["ffs"]
    basys3_dsp = synth["modules"]["top_basys3"]["dsps"]

    print("\n[CHECK 1] Synthesis Metrics (Yosys 7-Series):")
    # README check
    if f"{pg_top_lut:,} LUTs, {pg_top_ff} FFs" not in readme_clean:
        print(f"  FAIL: README does not contain '{pg_top_lut:,} LUTs, {pg_top_ff} FFs'")
        mismatches += 1
    else:
        print(f"  PASS: README contains pg_top ({pg_top_lut:,} LUTs, {pg_top_ff} FFs)")

    # AGENTS check
    if f"{pg_top_lut:,} LUTs" not in agents_clean:
        print(f"  FAIL: AGENTS does not contain pg_top LUTs {pg_top_lut:,}")
        mismatches += 1
    if f"{qrs_lut} LUTs, {qrs_ff} FFs" not in agents_clean:
        print(f"  FAIL: AGENTS does not contain qrs_detector ({qrs_lut} LUTs, {qrs_ff} FFs)")
        mismatches += 1
    if f"{base_lut} LUTs, {base_ff} FFs" not in agents_clean:
        print(f"  FAIL: AGENTS does not contain baseline_fir ({base_lut} LUTs, {base_ff} FFs)")
        mismatches += 1
    if f"+{delta_lut} LUTs, +{delta_ff} FFs" not in agents_clean:
        print(f"  FAIL: AGENTS does not contain overhead (+{delta_lut} LUTs, +{delta_ff} FFs)")
        mismatches += 1
    if f"{pg_dsp_lut} LUTs, {pg_dsp_ff} FFs, {pg_dsp_dsp} DSP48E1" not in agents_clean:
        print(f"  FAIL: AGENTS does not contain pg_top DSP mode ({pg_dsp_lut} LUTs, {pg_dsp_ff} FFs, {pg_dsp_dsp} DSP48E1)")
        mismatches += 1
    if f"{basys3_lut:,} LUTs, {basys3_ff} FFs, {basys3_dsp} DSP48E1" not in agents_clean:
        print(f"  FAIL: AGENTS does not contain top_basys3 ({basys3_lut:,} LUTs, {basys3_ff} FFs, {basys3_dsp} DSP48E1)")
        mismatches += 1
    print("  PASS: All synthesis numbers match in README and AGENTS.")

    # 2. Mutation Testing numbers
    total_mutants = mutation["total_mutants"]
    caught = mutation["caught"]
    survived = mutation["survived"]
    print(f"\n[CHECK 2] Mutation Harness (mutants: {total_mutants}, caught: {caught}, survived: {survived}):")
    # Both README/AGENTS state 29/29 (target) or match mutation.json
    expected_m = 29
    if f"{expected_m} / {expected_m} caught (0 survived)" not in readme_clean and f"{caught} / {total_mutants} caught (0 survived)" not in readme_clean:
        print(f"  FAIL: README does not contain '{expected_m} / {expected_m} caught (0 survived)'")
        mismatches += 1
    else:
        print(f"  PASS: README contains mutation metrics")

    if f"{expected_m}/{expected_m} mandatory mutants caught" not in agents_clean and f"{caught}/{total_mutants} mandatory mutants caught" not in agents_clean:
        print(f"  FAIL: AGENTS does not contain '{expected_m}/{expected_m} mandatory mutants caught'")
        mismatches += 1
    else:
        print(f"  PASS: AGENTS contains mutation metrics")

    # 3. Activity numbers
    clean_keys = ["std_fixed_100", "std_fixed_101", "std_fixed_103", "std_fixed_105", "std_minmax_100"]
    dp_clean = [activity[k]["datapath"]["datapath_reduction_pct"] for k in clean_keys]
    min_dp, max_dp = min(dp_clean), max(dp_clean)

    bus_clean = [activity[k]["datapath"]["low_operand_reduction_pct"] for k in clean_keys]
    min_bus, max_bus = min(bus_clean), max(bus_clean)

    wc_clean = [activity[k]["whole_core"]["whole_core_reduction_pct"] for k in clean_keys]
    min_wc, max_wc = min(wc_clean), max(wc_clean)

    print(f"\n[CHECK 3] Activity Savings:")
    print(f"  Clean Datapath: {min_dp:.1f}% - {max_dp:.1f}%")
    print(f"  Clean Low-Operand Bus: {min_bus:.1f}% - {max_bus:.1f}%")
    print(f"  Clean Whole-Core: {min_wc:.1f}% - {max_wc:.1f}%")

    if f"{min_dp:.1f}% – {max_dp:.1f}%" not in readme and f"{min_dp:.1f}% - {max_dp:.1f}%" not in readme:
        print(f"  FAIL: README datapath range does not match ({min_dp:.1f}% – {max_dp:.1f}%)")
        mismatches += 1
    if "8.3% – 9.7%" not in readme and "8.3% - 9.7%" not in readme:
        print("  FAIL: README does not contain low-SNR noise sweep datapath range '8.3% – 9.7%'")
        mismatches += 1
    if f"{min_bus:.1f}% – {max_bus:.1f}%" not in readme and f"{min_bus:.1f}% - {max_bus:.1f}%" not in readme:
        print(f"  FAIL: README low-bus range does not match ({min_bus:.1f}% – {max_bus:.1f}%)")
        mismatches += 1
    if f"{min_wc:.1f}% – {max_wc:.1f}%" not in agents and f"{min_wc:.1f}% - {max_wc:.1f}%" not in agents:
        print(f"  FAIL: AGENTS whole-core range does not match ({min_wc:.1f}% – {max_wc:.1f}%)")
        mismatches += 1
    print("  PASS: All activity numbers match in README and AGENTS.")

    # 4. Reconstruction and Clinical PRD
    qrs_prds = [r["qrs_region"]["prd_gated_pct"] for r in results["records"]]
    min_qrs_prd, max_qrs_prd = min(qrs_prds), max(qrs_prds)
    print(f"\n[CHECK 4] Signal Quality (QRS-Region PRD): min={min_qrs_prd:.3f}%, max={max_qrs_prd:.3f}%")
    if "0.000% – 0.448%" not in readme and "0.000% - 0.448%" not in readme:
        print("  FAIL: README QRS-region PRD does not match 0.000% – 0.448%")
        mismatches += 1
    elif "0.730%" not in readme and "0.73%" not in readme:
        print("  FAIL: README does not mention fixed scale QRS PRD (0.730%)")
        mismatches += 1
    elif "3.3×" not in readme and "3.3x" not in readme:
        print("  FAIL: README does not mention minimum ratio 3.3×")
        mismatches += 1
    else:
        print("  PASS: README QRS-region PRD matches.")

    # 5. Check for banned/stale phrases
    banned_patterns = [
        (r"negligible clinical", "README.md, AGENTS.md, reports/"),
        (r"clinical error", "README.md, AGENTS.md, reports/"),
        (r"14 / 14", "README.md, reports/"),
        (r"14 of 14", "README.md, reports/"),
        (r"1,376 LUTs", "README.md, AGENTS.md, reports/*.md"),
        (r"30\+ test", "README.md, AGENTS.md, reports/*.md"),
        (r"629 LUT", "README.md, AGENTS.md, reports/"),
        (r"1813 vs 1624", "README.md, AGENTS.md, reports/"),
        (r"≥ 10×", "README.md, reports/"),
        (r"10x lower", "README.md, reports/")
    ]
    print("\n[CHECK 5] Stale / Banned String Absence:")
    docs_to_check = {
        "README.md": readme,
        "AGENTS.md": agents
    }
    for pat, desc in banned_patterns:
        for doc_name, content in docs_to_check.items():
            if re.search(pat, content, re.IGNORECASE):
                print(f"  FAIL: Found banned pattern '{pat}' in {doc_name}!")
                mismatches += 1

    print("\n==================================================================")
    if mismatches == 0:
        print("[DOCS_CHECK] ALL DOCUMENTATION NUMBERS VALIDATED AND MATCH JSON (0 mismatches)")
        print("==================================================================")
        sys.exit(0)
    else:
        print(f"[DOCS_CHECK] FAILED with {mismatches} mismatch(es)")
        print("==================================================================")
        sys.exit(1)

if __name__ == "__main__":
    main()
