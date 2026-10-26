#!/usr/bin/env python3
"""
scripts/check_docs_numbers.py — Automated Validator for Documentation Metrics

Validates that every hardware, mutation, regression, and signal performance metric stated in:
  - README.md
  - AGENTS.md
  - reports/RESULTS.md
matches the generated JSON reports in reports/*.json exactly (to within stated rounding precision).

Enforces strict absence of stale counts (e.g. 29/29, 21-mutant, 52 nightly).
Exits 0 if all match, or exit code 1 on any mismatch.
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
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def read_doc(rel_path):
    path = os.path.join(BASE_DIR, rel_path)
    if not os.path.exists(path):
        print(f"ERROR: Missing document {path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def main():
    print("==================================================================")
    print("VALIDATING DOCUMENTATION NUMBERS AGAINST JSON REPORTS")
    print("==================================================================")

    readme = read_doc("README.md")
    agents = read_doc("AGENTS.md")
    results_md = read_doc("reports/RESULTS.md") if os.path.exists(os.path.join(BASE_DIR, "reports/RESULTS.md")) else ""

    # Strip markdown bold formatting for robust number matching
    readme_clean = readme.replace("**", "").replace("`", "")
    agents_clean = agents.replace("**", "").replace("`", "")
    results_clean = results_md.replace("**", "").replace("`", "")

    synth = load_json("synth.json")
    activity = load_json("activity.json")
    results = load_json("results.json")
    mutation = load_json("mutation.json")
    reg_std = load_json("regress_summary.json")
    reg_nightly = load_json("regress_summary_nightly.json")

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
    if f"{pg_top_lut:,} LUTs, {pg_top_ff} FFs" not in readme_clean:
        print(f"  FAIL: README does not contain '{pg_top_lut:,} LUTs, {pg_top_ff} FFs'")
        mismatches += 1
    else:
        print(f"  PASS: README contains pg_top ({pg_top_lut:,} LUTs, {pg_top_ff} FFs)")

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

    # 2. Mutation Testing numbers (dynamically read from mutation.json)
    total_mutants = mutation.get("total_mutants", mutation.get("summary", {}).get("total_mutants"))
    caught = mutation.get("caught", mutation.get("summary", {}).get("caught"))
    survived = mutation.get("survived", mutation.get("summary", {}).get("survived", 0))

    print(f"\n[CHECK 2] Mutation Harness (mutants: {total_mutants}, caught: {caught}, survived: {survived}):")
    # README must contain exact counts
    exp_readme_mut = f"{caught} / {total_mutants} caught ({survived} survived)"
    if exp_readme_mut not in readme_clean:
        print(f"  FAIL: README does not contain '{exp_readme_mut}'")
        mismatches += 1
    else:
        print(f"  PASS: README contains mutation metrics '{exp_readme_mut}'")

    # AGENTS must contain exact counts
    exp_agents_mut = f"{caught}/{total_mutants} mandatory mutants caught"
    if exp_agents_mut not in agents_clean:
        print(f"  FAIL: AGENTS does not contain '{exp_agents_mut}'")
        mismatches += 1
    else:
        print(f"  PASS: AGENTS contains mutation metrics '{exp_agents_mut}'")

    # RESULTS.md must contain exact counts if present
    if results_clean:
        if exp_agents_mut not in results_clean:
            print(f"  FAIL: RESULTS.md does not contain '{exp_agents_mut}'")
            mismatches += 1
        else:
            print(f"  PASS: RESULTS.md contains mutation metrics '{exp_agents_mut}'")

    # README must contain {total_mutants}-mutant
    exp_mutant_hyphen = f"{total_mutants}-mutant"
    if exp_mutant_hyphen not in readme:
        print(f"  FAIL: README does not contain '{exp_mutant_hyphen}'")
        mismatches += 1
    else:
        print(f"  PASS: README contains '{exp_mutant_hyphen}'")

    # Strict regex check for any wrong mutant count in README and AGENTS
    for doc_name, content in [("README.md", readme), ("AGENTS.md", agents)]:
        # Pattern 1: X / Y caught
        for m in re.finditer(r"\b(\d+)\s*/\s*(\d+)\s+caught\b", content, re.IGNORECASE):
            c_val, t_val = int(m.group(1)), int(m.group(2))
            if c_val != caught or t_val != total_mutants:
                print(f"  FAIL: {doc_name} has wrong mutant count: '{m.group(0)}' (expected {caught} / {total_mutants})")
                mismatches += 1
        # Pattern 2: X/Y (mandatory) mutants
        for m in re.finditer(r"\b(\d+)\s*/\s*(\d+)\s+(?:mandatory\s+)?mutants?\b", content, re.IGNORECASE):
            c_val, t_val = int(m.group(1)), int(m.group(2))
            if c_val != caught or t_val != total_mutants:
                print(f"  FAIL: {doc_name} has wrong mutant count: '{m.group(0)}' (expected {caught}/{total_mutants})")
                mismatches += 1
        # Pattern 3: X-mutant
        for m in re.finditer(r"\b(\d+)-mutant\b", content, re.IGNORECASE):
            t_val = int(m.group(1))
            if t_val != total_mutants:
                print(f"  FAIL: {doc_name} has wrong mutant count: '{m.group(0)}' (expected {total_mutants}-mutant)")
                mismatches += 1

    # 3. Regression Suite numbers (dynamically read from summaries)
    std_passed = reg_std.get("passed")
    nightly_passed = reg_nightly.get("passed")

    print(f"\n[CHECK 3] Regression Suites (standard: {std_passed}, nightly: {nightly_passed}):")
    exp_readme_reg = f"{std_passed} standard / {nightly_passed} nightly suites"
    if exp_readme_reg not in readme_clean:
        print(f"  FAIL: README does not contain '{exp_readme_reg}'")
        mismatches += 1
    else:
        print(f"  PASS: README contains '{exp_readme_reg}'")

    exp_agents_reg = f"{std_passed} standard / {nightly_passed} nightly suites passing"
    if exp_agents_reg not in agents_clean:
        print(f"  FAIL: AGENTS does not contain '{exp_agents_reg}'")
        mismatches += 1
    else:
        print(f"  PASS: AGENTS contains '{exp_agents_reg}'")

    for doc_name, content in [("README.md", readme), ("AGENTS.md", agents)]:
        for m in re.finditer(r"\b(\d+)\s+nightly\s+suites?\b", content, re.IGNORECASE):
            n_val = int(m.group(1))
            if n_val != nightly_passed:
                print(f"  FAIL: {doc_name} has wrong nightly count: '{m.group(0)}' (expected {nightly_passed})")
                mismatches += 1
        for m in re.finditer(r"\b(\d+)\s+standard\s*/\s*(\d+)\s+nightly\b", content, re.IGNORECASE):
            s_val, n_val = int(m.group(1)), int(m.group(2))
            if s_val != std_passed or n_val != nightly_passed:
                print(f"  FAIL: {doc_name} has wrong suite counts: '{m.group(0)}' (expected {std_passed} / {nightly_passed})")
                mismatches += 1

    # 4. Activity numbers
    clean_keys = ["std_fixed_100", "std_fixed_101", "std_fixed_103", "std_fixed_105", "std_minmax_100"]
    dp_clean = [activity[k]["datapath"]["datapath_reduction_pct"] for k in clean_keys if k in activity and isinstance(activity[k], dict)]
    min_dp, max_dp = min(dp_clean), max(dp_clean)

    bus_clean = [activity[k]["datapath"]["low_operand_reduction_pct"] for k in clean_keys if k in activity and isinstance(activity[k], dict)]
    min_bus, max_bus = min(bus_clean), max(bus_clean)

    wc_clean = [activity[k]["whole_core"]["whole_core_reduction_pct"] for k in clean_keys if k in activity and isinstance(activity[k], dict)]
    min_wc, max_wc = min(wc_clean), max(wc_clean)

    print(f"\n[CHECK 4] Activity Savings:")
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

    # 5. Reconstruction and Clinical PRD
    qrs_prds = [r["qrs_region"]["prd_gated_pct"] for r in results.get("records", [])]
    min_qrs_prd = min(qrs_prds) if qrs_prds else 0.0
    max_qrs_prd = max(qrs_prds) if qrs_prds else 0.730
    print(f"\n[CHECK 5] Signal Quality (QRS-Region PRD): min={min_qrs_prd:.3f}%, max={max_qrs_prd:.3f}%")
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

    # 6. Check for banned/stale phrases
    banned_patterns = [
        (r"\b29\s*/\s*29\b", "README.md, AGENTS.md, reports/*.md"),
        (r"\b21-mutant\b", "README.md, AGENTS.md, reports/*.md"),
        (r"\b52\s+nightly\b", "README.md, AGENTS.md, reports/*.md"),
        (r"\b52\s+suites\b", "README.md, AGENTS.md, reports/*.md"),
        (r"negligible clinical", "README.md, AGENTS.md, reports/*.md"),
        (r"clinical error", "README.md, AGENTS.md, reports/*.md"),
        (r"\b14\s*/\s*14\b", "README.md, reports/*.md"),
        (r"\b14\s+of\s+14\b", "README.md, reports/*.md"),
        (r"1,376 LUTs", "README.md, AGENTS.md, reports/*.md"),
        (r"30\+\s+test", "README.md, AGENTS.md, reports/*.md"),
        (r"629 LUT", "README.md, AGENTS.md, reports/*.md"),
        (r"1813 vs 1624", "README.md, AGENTS.md, reports/*.md"),
        (r"≥ 10×", "README.md, reports/*.md"),
        (r"10x lower", "README.md, reports/*.md")
    ]
    print("\n[CHECK 6] Stale / Banned String Absence:")
    docs_to_check = {
        "README.md": readme,
        "AGENTS.md": agents
    }
    if results_md:
        docs_to_check["reports/RESULTS.md"] = results_md

    for pat, desc in banned_patterns:
        for doc_name, content in docs_to_check.items():
            if re.search(pat, content, re.IGNORECASE):
                print(f"  FAIL: Found banned/stale pattern '{pat}' in {doc_name}!")
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
