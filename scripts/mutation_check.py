"""
scripts/mutation_check.py — Mutation Testing Harness for Precision-Gated MAC ECG

Evaluates the sensitivity and rigor of the test suite by injecting 21 mandatory
mutants into the RTL (including the circular delay line, RAM-based detector,
serial squarer, and pointer arithmetic) and verifying that every mutant is CAUGHT
(produces a simulation mismatch or latency contract violation) and none SURVIVE undetected.

Outputs:
  reports/mutation.json
"""

import os
import sys
import json
import shutil
import subprocess
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RTL_DIR = os.path.join(BASE_DIR, "rtl")
TB_DIR = os.path.join(BASE_DIR, "tb")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
WORK_DIR = os.path.join(BASE_DIR, "build_mutation")

os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(WORK_DIR, exist_ok=True)

MUTANTS = [
    {
        "id": "MUT01_tap_coeff",
        "file": "fir_coeff_rom.v",
        "target": "rom[tap_idx]",
        "replacement": "(rom[tap_idx] + 16'sd1)",
        "desc": "Tap coefficient incremented by +1",
        "test_suite": "smoke"
    },
    {
        "id": "MUT02_mwi_shift",
        "file": "qrs_detector.v",
        "target": "next_mwi_acc[23:6]",
        "replacement": "next_mwi_acc[23:5]",
        "desc": "MWI output right-shift changed from >>6 to >>5",
        "test_suite": "smoke"
    },
    {
        "id": "MUT03_gate_len",
        "file": "qrs_detector.v",
        "target": "parameter GATE_LEN     = 43,",
        "replacement": "parameter GATE_LEN     = 42,",
        "desc": "GATE_LEN reduced from 43 to 42",
        "test_suite": "smoke"
    },
    {
        "id": "MUT04_refract_len",
        "file": "qrs_detector.v",
        "target": "parameter REFRACT_LEN  = 72,",
        "replacement": "parameter REFRACT_LEN  = 70,",
        "desc": "REFRACT_LEN reduced from 72 to 70",
        "test_suite": "std_fixed_101"
    },
    {
        "id": "MUT05_init_thresh",
        "file": "qrs_detector.v",
        "target": "parameter INIT_THRESH  = 412,",
        "replacement": "parameter INIT_THRESH  = 600,",
        "desc": "INIT_THRESH modified from 412 to 600",
        "test_suite": "startup_105_off200"
    },
    {
        "id": "MUT06_init_spki",
        "file": "qrs_detector.v",
        "target": "parameter INIT_SPKI    = 1500,",
        "replacement": "parameter INIT_SPKI    = 1800,",
        "desc": "INIT_SPKI modified from 1500 to 1800",
        "test_suite": "startup_105_off211"
    },
    {
        "id": "MUT07_init_npki",
        "file": "qrs_detector.v",
        "target": "parameter INIT_NPKI    = 50,",
        "replacement": "parameter INIT_NPKI    = 100,",
        "desc": "INIT_NPKI modified from 50 to 100",
        "test_suite": "std_fixed_105"
    },
    {
        "id": "MUT08_decay_after",
        "file": "qrs_detector.v",
        "target": "parameter DECAY_AFTER  = 288,",
        "replacement": "parameter DECAY_AFTER  = 250,",
        "desc": "DECAY_AFTER reduced from 288 to 250",
        "test_suite": "std_fixed_101"
    },
    {
        "id": "MUT09_truncation_width",
        "file": "mult_split.v",
        "target": "(approx_r1 ? 32'sd0 : {{7{p_low_r1[24]}}, p_low_r1})",
        "replacement": "(approx_r1 ? 32'sd1 : {{7{p_low_r1[24]}}, p_low_r1})",
        "desc": "Approximate mode mask corrupted with non-zero offset",
        "test_suite": "smoke"
    },
    {
        "id": "MUT10_squarer_sat",
        "file": "qrs_detector.v",
        "target": "wire [16:0] s = (s_shifted > 34'd131071) ? 17'd131071 : s_shifted[16:0];",
        "replacement": "wire [16:0] s = s_shifted[16:0];",
        "desc": "Squarer 17-bit saturation removed",
        "test_suite": "sat_test"
    },
    {
        "id": "MUT11_acc_width",
        "file": "pg_mac.v",
        "target": "acc_out <= acc_out + prod_in;",
        "replacement": "acc_out <= (acc_out + prod_in) & 32'h7fffffff;",
        "desc": "Accumulator corrupted to 31-bit signed dynamic range",
        "test_suite": "smoke"
    },
    {
        "id": "MUT12_gate_latch",
        "file": "pg_fir.v",
        "target": "mode_approx_q <= ~eff_gate; // Latch mode for all 51 taps",
        "replacement": "mode_approx_q <= 1'b0; // Mutant: gate lost",
        "desc": "Gate latching corrupted to stuck full",
        "test_suite": "smoke"
    },
    {
        "id": "MUT13_delay_line_off",
        "file": "sample_delay_line.v",
        "target": "wire [5:0] rd_addr = wr_ptr - 6'd1 - {1'b0, tap_idx};",
        "replacement": "wire [5:0] rd_addr = wr_ptr - 6'd2 - {1'b0, tap_idx};",
        "desc": "Delay line tap indexing off by one (-2 bias)",
        "test_suite": "smoke"
    },
    {
        "id": "MUT14_prod_low_sign",
        "file": "mult_split.v",
        "target": "{{7{p_low_r1[24]}}, p_low_r1}",
        "replacement": "{7'd0, p_low_r1}",
        "desc": "Sign extension replaced by zero extension on low product",
        "test_suite": "smoke"
    },
    {
        "id": "MUT15_delay_valid_cnt",
        "file": "sample_delay_line.v",
        "target": "if (valid_cnt < N_TAPS[5:0]) begin",
        "replacement": "if (valid_cnt < 6'd47) begin",
        "desc": "valid_cnt saturates at 47 instead of 51 taps (truncating effective taps)",
        "test_suite": "smoke"
    },
    {
        "id": "MUT16_delay_rd_addr_nobias",
        "file": "sample_delay_line.v",
        "target": "wire [5:0] rd_addr = wr_ptr - 6'd1 - {1'b0, tap_idx};",
        "replacement": "wire [5:0] rd_addr = wr_ptr - {1'b0, tap_idx};",
        "desc": "Delay line tap indexing offset by +1 (no -1 bias)",
        "test_suite": "smoke"
    },
    {
        "id": "MUT17_delay_wrptr_step",
        "file": "sample_delay_line.v",
        "target": "wr_ptr      <= wr_ptr + 6'd1;",
        "replacement": "wr_ptr      <= wr_ptr + 6'd2;",
        "desc": "Sample delay line write pointer steps by 2 instead of 1",
        "test_suite": "smoke"
    },
    {
        "id": "MUT18_mwi_ptr_wrap",
        "file": "qrs_detector.v",
        "target": "                // Serial square calculation complete: update MWI and detector state\n                sq_busy <= 1'b0;\n\n                mwi_ram[ptr] <= s;\n                ptr <= (ptr == MWI_LEN[5:0] - 6'd1) ? 6'd0 : (ptr + 6'd1);",
        "replacement": "                // Serial square calculation complete: update MWI and detector state\n                sq_busy <= 1'b0;\n\n                mwi_ram[ptr] <= s;\n                ptr <= (ptr == 6'd63) ? 6'd0 : (ptr + 6'd1);",
        "desc": "MWI circular buffer pointer wraps at 63 instead of 53",
        "test_suite": "std_fixed_101"
    },
    {
        "id": "MUT19_serial_sq_early",
        "file": "qrs_detector.v",
        "target": "if (sq_step == 5'd16) begin",
        "replacement": "if (sq_step == 5'd15) begin",
        "desc": "Serial squarer finishes 1 cycle early (16 cycles instead of 17)",
        "test_suite": "smoke"
    },
    {
        "id": "MUT20_det_valid_early",
        "file": "qrs_detector.v",
        "target": "                mwi_dbg         <= next_mwi_out;\n                valid_out       <= 1'b1;\n            end else begin\n                sq_accum <= next_sq_accum;\n                sq_step  <= sq_step + 5'd1;\n                valid_out <= 1'b0;",
        "replacement": "                mwi_dbg         <= next_mwi_out;\n                valid_out       <= 1'b0;\n            end else begin\n                sq_accum <= next_sq_accum;\n                sq_step  <= sq_step + 5'd1;\n                valid_out <= (sq_step == 5'd15);",
        "desc": "Detector valid_out asserted 1 cycle before serial squarer completes",
        "test_suite": "smoke"
    },
    {
        "id": "MUT21_detector_reset_thresh",
        "file": "qrs_detector.v",
        "target": "threshold       <= INIT_THRESH[23:0];",
        "replacement": "threshold       <= 24'd0;",
        "desc": "Reset clears detector adaptive threshold to 0 instead of INIT_THRESH",
        "test_suite": "smoke"
    }
]

def check_unmutated_baseline():
    print("[MUTATION] Verifying unmutated baseline design across test suites...", flush=True)
    base_build_dir = os.path.join(WORK_DIR, "baseline_build")
    os.makedirs(base_build_dir, exist_ok=True)

    cmd_compile = [
        "verilator", "--binary", "--timing",
        "-Wno-WIDTHTRUNC", "-Wno-WIDTHEXPAND", "-Wno-INITIALDLY",
        f"-I{RTL_DIR}",
        "tb/tb_top.v",
        f"{RTL_DIR}/pg_top.v",
        f"{RTL_DIR}/qrs_detector.v",
        f"{RTL_DIR}/pg_fir.v",
        f"{RTL_DIR}/sample_delay_line.v",
        f"{RTL_DIR}/fir_coeff_rom.v",
        f"{RTL_DIR}/mult_split.v",
        f"{RTL_DIR}/pg_mac.v",
        "--Mdir", base_build_dir,
        "-o", "sim_top_base"
    ]
    res_c = subprocess.run(cmd_compile, cwd=BASE_DIR, capture_output=True, text=True)
    if res_c.returncode != 0:
        print("ERROR: Unmutated baseline failed to compile!\n", res_c.stderr)
        return False

    bin_path = os.path.join(base_build_dir, "sim_top_base")
    unique_suites = sorted(list(set(m["test_suite"] for m in MUTANTS)))
    for suite in unique_suites:
        cmd_run = [bin_path, f"+VEC_DIR=data/test_vectors/{suite}"]
        res_r = subprocess.run(cmd_run, cwd=BASE_DIR, capture_output=True, text=True)
        if res_r.returncode != 0 or "TB_RESULT: PASS" not in res_r.stdout:
            print(f"ERROR: Unmutated baseline failed on suite: {suite}!\n", res_r.stdout, res_r.stderr)
            return False

    return True

def run_mutation_test(mutant):
    mid = mutant["id"]
    rel_file = mutant["file"]
    target = mutant["target"]
    replacement = mutant["replacement"]
    suite = mutant["test_suite"]

    print(f"\n--- Testing Mutant: {mid} ({mutant['desc']}) ---")
    mut_rtl_dir = os.path.join(WORK_DIR, mid, "rtl")
    os.makedirs(mut_rtl_dir, exist_ok=True)

    # 1. Copy fresh RTL
    for f in os.listdir(RTL_DIR):
        src = os.path.join(RTL_DIR, f)
        if os.path.isfile(src):
            shutil.copy2(src, mut_rtl_dir)

    # 2. Mutate file
    mut_file_path = os.path.join(mut_rtl_dir, rel_file)
    with open(mut_file_path, "r") as f:
        content = f.read()

    if target not in content:
        print(f"ERROR: Target string not found in {rel_file}!")
        return {"id": mid, "status": "BUILD_ERROR", "desc": mutant["desc"]}

    mut_content = content.replace(target, replacement, 1)
    with open(mut_file_path, "w") as f:
        f.write(mut_content)

    # 3. Compile tb_top with Verilator
    build_dir = os.path.join(WORK_DIR, mid, "build")
    cmd_compile = [
        "verilator", "--binary", "--timing",
        "-Wno-WIDTHTRUNC", "-Wno-WIDTHEXPAND", "-Wno-INITIALDLY",
        f"-I{mut_rtl_dir}",
        "tb/tb_top.v",
        f"{mut_rtl_dir}/pg_top.v",
        f"{mut_rtl_dir}/qrs_detector.v",
        f"{mut_rtl_dir}/pg_fir.v",
        f"{mut_rtl_dir}/sample_delay_line.v",
        f"{mut_rtl_dir}/fir_coeff_rom.v",
        f"{mut_rtl_dir}/mult_split.v",
        f"{mut_rtl_dir}/pg_mac.v",
        "--Mdir", build_dir,
        "-o", "sim_top_mut"
    ]

    t0 = time.time()
    res_c = subprocess.run(cmd_compile, cwd=BASE_DIR, capture_output=True, text=True)
    if res_c.returncode != 0:
        # Build error is a harness error, not a caught mutant
        print(f"  Result: BUILD_ERROR in {time.time() - t0:.2f}s:\n{res_c.stderr[:300]}")
        return {"id": mid, "status": "BUILD_ERROR", "desc": mutant["desc"]}

    # 4. Run testbench on the targeted test suite
    bin_path = os.path.join(build_dir, "sim_top_mut")
    cmd_run = [bin_path, f"+VEC_DIR=data/test_vectors/{suite}"]
    res_r = subprocess.run(cmd_run, cwd=BASE_DIR, capture_output=True, text=True)
    elapsed = time.time() - t0
    out = res_r.stdout + res_r.stderr

    if res_r.returncode != 0 or "TB_RESULT: PASS" not in out:
        print(f"  Result: CAUGHT (simulation failed on {suite} in {elapsed:.2f}s)")
        return {"id": mid, "status": "CAUGHT", "desc": mutant["desc"], "suite": suite}
    else:
        print(f"  Result: SURVIVED (test passed on {suite} in {elapsed:.2f}s) --> INADEQUATE TEST!")
        return {"id": mid, "status": "SURVIVED", "desc": mutant["desc"], "suite": suite}

def main():
    print("==================================================================")
    print(f"STARTING MUTATION TESTING HARNESS ({len(MUTANTS)} MANDATORY MUTANTS)")
    print("==================================================================")

    # 1. Unmutated baseline pre-check
    if not check_unmutated_baseline():
        print("FATAL: Unmutated baseline check FAILED. Aborting mutation testing.")
        sys.exit(1)
    print("unmutated baseline: PASS\n", flush=True)

    results = []
    caught = 0
    survived = 0
    build_errors = 0

    for m in MUTANTS:
        res = run_mutation_test(m)
        results.append(res)
        if res["status"] == "CAUGHT":
            caught += 1
        elif res["status"] == "BUILD_ERROR":
            build_errors += 1
        else:
            survived += 1

    summary = {
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_mutants": len(MUTANTS),
        "caught": caught,
        "survived": survived,
        "build_errors": build_errors,
        "results": results
    }

    out_file = os.path.join(REPORTS_DIR, "mutation.json")
    with open(out_file, "w") as f:
        json.dump(summary, f, indent=2)

    print("\n==================================================================")
    print(f"MUTATION SUMMARY: mutants: {len(MUTANTS)} caught: {caught} survived: {survived} build_errors: {build_errors}")
    print(f"Written results to {out_file}")
    print("==================================================================")

    if survived > 0 or build_errors > 0 or caught != len(MUTANTS):
        sys.exit(1)

if __name__ == "__main__":
    main()
