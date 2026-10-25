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
sys.path.insert(0, BASE_DIR)
from scripts.source_digest import get_source_digest, get_git_commit, is_git_dirty
RTL_DIR = os.path.join(BASE_DIR, "rtl")
FPGA_DIR = os.path.join(BASE_DIR, "fpga")
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
    },
    {
        "id": "MUT22_frame_bytes_swap",
        "file": "board_core.v",
        "target": "                F_BYTE1: begin\n                    if (!tx_busy && !tx_start_reg) begin\n                        tx_data_reg  <= latched_y[31:24];",
        "replacement": "                F_BYTE1: begin\n                    if (!tx_busy && !tx_start_reg) begin\n                        tx_data_reg  <= latched_y[23:16];",
        "desc": "UART frame payload swaps bytes 1 and 2 (transmits y[23:16] before y[31:24])",
        "tb": "board",
        "scenario": "por_replay"
    },
    {
        "id": "MUT23_checksum_poly",
        "file": "board_core.v",
        "target": "latched_chk   <= 8'hA5 ^ y_acc[31:24] ^ y_acc[23:16] ^ y_acc[15:8] ^ y_acc[7:0] ^",
        "replacement": "latched_chk   <= 8'hA5 | y_acc[31:24] | y_acc[23:16] | y_acc[15:8] | y_acc[7:0] |",
        "desc": "UART frame checksum polynomial changed from XOR to bitwise OR",
        "tb": "board",
        "scenario": "por_replay"
    },
    {
        "id": "MUT24_preamble_val",
        "file": "board_core.v",
        "target": "tx_data_reg  <= 8'hA5; // Sync preamble",
        "replacement": "tx_data_reg  <= 8'hA4; // Sync preamble",
        "desc": "UART frame preamble corrupted from 0xA5 to 0xA4",
        "tb": "board",
        "scenario": "por_replay"
    },
    {
        "id": "MUT25_baud_divisor",
        "file": "uart_tx.v",
        "target": "localparam CLKS_PER_BIT = CLK_HZ / BAUD;",
        "replacement": "localparam CLKS_PER_BIT = (CLK_HZ * 99) / (BAUD * 100);",
        "desc": "UART transmitter baud rate divisor reduced by 1% (clock timing drift)",
        "tb": "board",
        "scenario": "por_replay"
    },
    {
        "id": "MUT26_por_removed",
        "file": "board_core.v",
        "target": "wire rst_n_int = por_done & rst_btn_clean;",
        "replacement": "wire rst_n_int = rst_btn_clean;",
        "desc": "Power-On Reset removed (rst_n_int only driven by external button)",
        "tb": "board",
        "scenario": "por_replay"
    },
    {
        "id": "MUT27_pause_sync_bypass",
        "file": "board_core.v",
        "target": "sw_pause_sync2 <= sw_pause_sync1;",
        "replacement": "sw_pause_sync2 <= sw_pause;",
        "desc": "sw_pause 2-flop synchronizer bypassed (1-stage latch instead of 2-stage)",
        "tb": "board",
        "scenario": "async_switch"
    },
    {
        "id": "MUT28_mode_latch_removed",
        "file": "board_core.v",
        "target": "        end else if (sample_tick) begin\n            mode_force_latched <= sw_mode_sync2;\n        end",
        "replacement": "        end else begin\n            mode_force_latched <= sw_mode_sync2;\n        end",
        "desc": "mode_force sample-tick latch removed (mode switches mid-sample on switch changes)",
        "tb": "board",
        "scenario": "async_switch"
    },
    {
        "id": "MUT29_flags_bit_order",
        "file": "board_core.v",
        "target": "latched_flags <= {5'b00000, (mode_force_latched != 2'b00), peak_pulse, gate_out};",
        "replacement": "latched_flags <= {5'b00000, gate_out, peak_pulse, (mode_force_latched != 2'b00)};",
        "desc": "UART frame flags bit order swapped ({force, peak, gate} -> {gate, peak, force})",
        "tb": "board",
        "scenario": "por_replay"
    },
    {
        "id": "MUT30_por_cycles",
        "file": "board_core.v",
        "target": "parameter POR_CYCLES      = (FAST_TICK > 0) ? 1000 : 65535,",
        "replacement": "parameter POR_CYCLES      = (FAST_TICK > 0) ? 1000 : 6553,",
        "desc": "POR_CYCLES reduced from 65535 to 6553",
        "tb": "board",
        "scenario": "realparams"
    },
    {
        "id": "MUT31_debounce_cycles",
        "file": "board_core.v",
        "target": "parameter DEBOUNCE_CYCLES = (FAST_TICK > 0) ? 32 : 100_000",
        "replacement": "parameter DEBOUNCE_CYCLES = (FAST_TICK > 0) ? 32 : 10_000",
        "desc": "DEBOUNCE_CYCLES reduced from 100000 to 10000",
        "tb": "board",
        "scenario": "realparams"
    }
]

def check_unmutated_baseline():
    print("[MUTATION] Verifying unmutated baseline design across test suites...", flush=True)
    base_build_dir = os.path.join(WORK_DIR, "baseline_build")
    os.makedirs(base_build_dir, exist_ok=True)

    # 1. Baseline tb_top
    cmd_compile_top = [
        "verilator", "--binary", "--timing", "-j", "4",
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
        "--Mdir", os.path.join(base_build_dir, "top"),
        "-o", "sim_top_base"
    ]
    res_c = subprocess.run(cmd_compile_top, cwd=BASE_DIR, capture_output=True, text=True)
    if res_c.returncode != 0:
        print("ERROR: Unmutated baseline tb_top failed to compile!\n", res_c.stderr)
        return False

    bin_top = os.path.join(base_build_dir, "top", "sim_top_base")
    unique_suites = sorted(list(set(m["test_suite"] for m in MUTANTS if m.get("tb", "top") == "top")))
    for suite in unique_suites:
        cmd_run = [bin_top, f"+VEC_DIR=data/test_vectors/{suite}"]
        res_r = subprocess.run(cmd_run, cwd=BASE_DIR, capture_output=True, text=True)
        if res_r.returncode != 0 or "TB_RESULT: PASS" not in res_r.stdout:
            print(f"ERROR: Unmutated baseline tb_top failed on suite: {suite}!\n", res_r.stdout, res_r.stderr)
            return False

    # 2. Baseline tb_board_core
    board_build_dir = os.path.join(WORK_DIR, "board_build")
    cmd_compile_board = [
        "verilator", "--binary", "--timing", "-j", "4",
        "-Wno-WIDTHTRUNC", "-Wno-WIDTHEXPAND", "-Wno-INITIALDLY",
        f"-I{RTL_DIR}", f"-I{FPGA_DIR}",
        "tb/tb_board_core.v",
        f"{FPGA_DIR}/board_core.v",
        f"{FPGA_DIR}/uart_tx.v",
        f"{RTL_DIR}/sample_tick_gen.v",
        f"{RTL_DIR}/pg_top.v",
        f"{RTL_DIR}/qrs_detector.v",
        f"{RTL_DIR}/pg_fir.v",
        f"{RTL_DIR}/sample_delay_line.v",
        f"{RTL_DIR}/fir_coeff_rom.v",
        f"{RTL_DIR}/mult_split.v",
        f"{RTL_DIR}/pg_mac.v",
        "--Mdir", board_build_dir,
        "-o", "sim_board_base"
    ]
    res_cb = subprocess.run(cmd_compile_board, cwd=BASE_DIR, capture_output=True, text=True)
    if res_cb.returncode != 0:
        print("ERROR: Unmutated baseline tb_board_core failed to compile!\n", res_cb.stderr)
        return False

    bin_board = os.path.join(board_build_dir, "sim_board_base")
    for scen in ["por_replay", "async_switch", "realparams"]:
        cmd_run = [bin_board, f"+SCENARIO={scen}"]
        res_r = subprocess.run(cmd_run, cwd=BASE_DIR, capture_output=True, text=True)
        if res_r.returncode != 0 or "TB_RESULT: PASS" not in res_r.stdout:
            print(f"ERROR: Unmutated baseline tb_board_core failed on scenario: {scen}!\n", res_r.stdout, res_r.stderr)
            return False

    return True

def run_mutation_test(mutant):
    mid = mutant["id"]
    rel_file = mutant["file"]
    target = mutant["target"]
    replacement = mutant["replacement"]
    tb_type = mutant.get("tb", "top")
    suite = mutant.get("scenario") if tb_type == "board" else mutant.get("test_suite")

    print(f"\n--- Testing Mutant: {mid} ({mutant['desc']}) ---")
    mut_rtl_dir = os.path.join(WORK_DIR, mid, "rtl")
    mut_fpga_dir = os.path.join(WORK_DIR, mid, "fpga")
    os.makedirs(mut_rtl_dir, exist_ok=True)
    os.makedirs(mut_fpga_dir, exist_ok=True)

    # 1. Copy fresh RTL and FPGA files
    for f in os.listdir(RTL_DIR):
        src = os.path.join(RTL_DIR, f)
        if os.path.isfile(src):
            shutil.copy2(src, mut_rtl_dir)

    for f in os.listdir(FPGA_DIR):
        src = os.path.join(FPGA_DIR, f)
        if os.path.isfile(src):
            shutil.copy2(src, mut_fpga_dir)

    # 2. Mutate file
    if os.path.exists(os.path.join(mut_fpga_dir, rel_file)):
        mut_file_path = os.path.join(mut_fpga_dir, rel_file)
    else:
        mut_file_path = os.path.join(mut_rtl_dir, rel_file)

    with open(mut_file_path, "r") as f:
        content = f.read()

    if target not in content:
        print(f"ERROR: Target string not found in {rel_file}!")
        return {"id": mid, "status": "BUILD_ERROR", "desc": mutant["desc"]}

    mut_content = content.replace(target, replacement, 1)
    with open(mut_file_path, "w") as f:
        f.write(mut_content)

    t0 = time.time()

    if tb_type == "board":
        build_dir = os.path.join(WORK_DIR, "board_build")
        cmd_compile = [
            "verilator", "--binary", "--timing", "-j", "4",
            "-Wno-WIDTHTRUNC", "-Wno-WIDTHEXPAND", "-Wno-INITIALDLY",
            f"-I{mut_rtl_dir}", f"-I{mut_fpga_dir}",
            "tb/tb_board_core.v",
            f"{mut_fpga_dir}/board_core.v",
            f"{mut_fpga_dir}/uart_tx.v",
            f"{mut_rtl_dir}/sample_tick_gen.v",
            f"{mut_rtl_dir}/pg_top.v",
            f"{mut_rtl_dir}/qrs_detector.v",
            f"{mut_rtl_dir}/pg_fir.v",
            f"{mut_rtl_dir}/sample_delay_line.v",
            f"{mut_rtl_dir}/fir_coeff_rom.v",
            f"{mut_rtl_dir}/mult_split.v",
            f"{mut_rtl_dir}/pg_mac.v",
            "--Mdir", build_dir,
            "-o", "sim_board_mut"
        ]
        cmd_run = [os.path.join(build_dir, "sim_board_mut"), f"+SCENARIO={suite}"]
    else:
        build_dir = os.path.join(WORK_DIR, mid, "build")
        cmd_compile = [
            "verilator", "--binary", "--timing", "-j", "4",
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
        cmd_run = [os.path.join(build_dir, "sim_top_mut"), f"+VEC_DIR=data/test_vectors/{suite}"]

    res_c = subprocess.run(cmd_compile, cwd=BASE_DIR, capture_output=True, text=True)
    if res_c.returncode != 0:
        print(f"  Result: BUILD_ERROR in {time.time() - t0:.2f}s:\n{res_c.stderr[:300]}")
        return {"id": mid, "status": "BUILD_ERROR", "desc": mutant["desc"]}

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
    only_ids = None
    for arg in sys.argv[1:]:
        if arg.startswith("--only="):
            only_ids = [x.strip() for x in arg.split("=")[1].split(",")]
        elif arg == "--only" and len(sys.argv) > sys.argv.index(arg) + 1:
            only_ids = [x.strip() for x in sys.argv[sys.argv.index(arg) + 1].split(",")]

    print("==================================================================")
    print(f"STARTING MUTATION TESTING HARNESS ({len(MUTANTS)} MANDATORY MUTANTS)")
    if only_ids:
        print(f"Filter mode: testing only {only_ids}")
    print("==================================================================")

    # 1. Unmutated baseline pre-check
    if not check_unmutated_baseline():
        print("FATAL: Unmutated baseline check FAILED. Aborting mutation testing.")
        sys.exit(1)
    print("unmutated baseline: PASS\n", flush=True)

    out_file = os.path.join(REPORTS_DIR, "mutation.json")
    results_map = {}
    if os.path.exists(out_file):
        try:
            with open(out_file, "r") as f:
                prev = json.load(f)
                for r in prev.get("results", []):
                    results_map[r["id"]] = r
        except Exception:
            pass

    for m in MUTANTS:
        if only_ids and m["id"] not in only_ids:
            continue
        res = run_mutation_test(m)
        results_map[res["id"]] = res

    all_results = sorted(list(results_map.values()), key=lambda r: r["id"])
    caught = sum(1 for r in all_results if r["status"] == "CAUGHT")
    survived = sum(1 for r in all_results if r["status"] == "SURVIVED")
    build_errors = sum(1 for r in all_results if r["status"] == "BUILD_ERROR")

    summary = {
        "build_errors": build_errors,
        "caught": caught,
        "commit": get_git_commit(verify_exists=True),
        "dirty": is_git_dirty(),
        "results": all_results,
        "source_digest": get_source_digest(),
        "survived": survived,
        "total_mutants": len(all_results)
    }

    with open(out_file, "w") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    print("\n==================================================================")
    print(f"MUTATION SUMMARY: mutants: {len(all_results)} caught: {caught} survived: {survived} build_errors: {build_errors}")
    print(f"Written results to {out_file}")
    print("==================================================================")

    if survived > 0 or build_errors > 0 or caught != len(MUTANTS):
        sys.exit(1)

if __name__ == "__main__":
    main()
