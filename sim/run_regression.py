"""
sim/run_regression.py — Unified RTL Simulation Regression Runner

Executes comprehensive regression suite across all implemented testbenches:
  1. tb_mult (exhaustive & randomized multiplier check)
  2. tb_fir_full (smoke, corner, std_fixed_100) -> reports/regress_fir_full.log
  3. tb_fir_gated (smoke, corner, std_fixed_100) -> reports/regress_fir_gated.log
  4. tb_detector (8 suites: fixed & minmax for 100, 101, 103, 105) -> reports/regress_detector.log
  5. tb_top (8 suites: fixed & minmax for 100, 101, 103, 105 + smoke + rand gap) -> reports/regress_top.log
  6. tb_top_realrate (1000 samples at 277,778 cycle real-time spacing)
  7. tb_top_reset (mid-stream reset pulse cleanly restores all internal state)
"""

import os
import sys
import subprocess
import time
import json
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
BUILD_DIR = os.path.join(BASE_DIR, "build_regress")
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(BUILD_DIR, exist_ok=True)

def get_tool_versions():
    ver_py = sys.version.split()[0]
    ver_verilator = "unknown"
    try:
        r = subprocess.run(["verilator", "--version"], capture_output=True, text=True)
        if r.returncode == 0:
            ver_verilator = r.stdout.strip().splitlines()[0]
    except Exception:
        pass
    return {
        "python": ver_py,
        "verilator": ver_verilator
    }

def get_git_info():
    commit = "unknown"
    dirty = False
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=BASE_DIR, capture_output=True, text=True)
        if res.returncode == 0:
            commit = res.stdout.strip()
        st = subprocess.run(["git", "status", "--porcelain"], cwd=BASE_DIR, capture_output=True, text=True)
        lines = [l for l in st.stdout.splitlines() if not l[3:].startswith("reports/")]
        dirty = (len(lines) > 0)
    except Exception:
        pass
    return commit, dirty

class RegressionRunner:
    def __init__(self):
        self.passes = 0
        self.fails = 0
        self.results = []
        self.log_buffers = {}

    def log(self, msg):
        print(msg, flush=True)

    def run_cmd(self, cmd, desc, log_file=None, append=False):
        self.log(f"\n[RUN] {desc}...")
        t0 = time.time()
        res = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True)
        elapsed = time.time() - t0
        output = res.stdout + ("\nSTDERR:\n" + res.stderr if res.stderr else "")

        if log_file:
            if log_file not in self.log_buffers or not append:
                self.log_buffers[log_file] = []
            chunk = f"=== {desc} (exit: {res.returncode}) ===\n{output}\n"
            self.log_buffers[log_file].append(chunk)

        passed = (res.returncode == 0) and ("TB_RESULT: PASS" in output)
        if passed:
            self.passes += 1
            self.log(f"  --> PASS ({elapsed:.2f}s)")
            self.results.append((desc, "PASS", elapsed))
        else:
            self.fails += 1
            self.log(f"  --> FAIL ({elapsed:.2f}s)")
            self.log(output[-500:])
            self.results.append((desc, "FAIL", elapsed))
        return passed

    def flush_logs(self, is_nightly=False):
        for log_file, chunks in self.log_buffers.items():
            new_body = "".join(chunks)
            if not is_nightly and os.path.exists(log_file):
                # Preserve existing nightly block if standard regression is run
                try:
                    with open(log_file, "r") as f:
                        old_txt = f.read()
                    idx = old_txt.find("=== tb_top full_")
                    if idx == -1:
                        idx = old_txt.find("=== tb_detector full_")
                    if idx != -1:
                        new_body += old_txt[idx:]
                except Exception:
                    pass
            if os.path.exists(log_file):
                try:
                    with open(log_file, "r") as f:
                        if f.read() == new_body:
                            continue
                except Exception:
                    pass
            with open(log_file, "w") as f:
                f.write(new_body)

    def compile(self, name, tb_file, srcs, extra_flags=None):
        out_bin = f"sim_{name}"
        cmd = [
            "verilator", "--binary", "--timing", "-j", "4",
            "-Wno-WIDTHTRUNC", "-Wno-WIDTHEXPAND", "-Wno-INITIALDLY",
            "-Irtl"
        ]
        if extra_flags:
            cmd.extend(extra_flags)
        cmd.extend([tb_file] + srcs + ["--Mdir", os.path.join(BUILD_DIR, name), "-o", out_bin])

        self.log(f"[BUILD] Compiling {name} with Verilator...")
        res = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True)
        if res.returncode != 0:
            self.log(f"Build failed for {name}:\n{res.stderr}")
            sys.exit(1)
        return os.path.join(BUILD_DIR, name, out_bin)

def main():
    runner = RegressionRunner()
    runner.log("==================================================================")
    runner.log("STARTING COMPLETE RTL SIMULATION REGRESSION SUITE")
    runner.log("==================================================================")

    # 1. Multiplier Unit Test
    bin_mult = runner.compile("mult", "tb/tb_mult.v", ["rtl/mult_split.v"])
    runner.run_cmd([bin_mult], "Unit test: mult_split across PIPE 1, 2, 3")

    # 2. Exact FIR Tests
    fir_srcs = [
        "rtl/pg_fir.v", "rtl/sample_delay_line.v", "rtl/fir_coeff_rom.v",
        "rtl/mult_split.v", "rtl/pg_mac.v"
    ]
    bin_fir_full = runner.compile("fir_full", "tb/tb_fir_full.v", fir_srcs)
    log_fir_full = os.path.join(REPORTS_DIR, "regress_fir_full.log")
    runner.run_cmd([bin_fir_full, "+VEC_DIR=data/test_vectors/smoke"], "tb_fir_full smoke", log_fir_full, append=False)
    runner.run_cmd([bin_fir_full, "+VEC_DIR=data/test_vectors/corner"], "tb_fir_full corner", log_fir_full, append=True)
    runner.run_cmd([bin_fir_full, "+VEC_DIR=data/test_vectors/std_fixed_100"], "tb_fir_full std_fixed_100", log_fir_full, append=True)

    # 3. Gated FIR Tests
    bin_fir_gated = runner.compile("fir_gated", "tb/tb_fir_gated.v", fir_srcs)
    log_fir_gated = os.path.join(REPORTS_DIR, "regress_fir_gated.log")
    runner.run_cmd([bin_fir_gated, "+VEC_DIR=data/test_vectors/smoke"], "tb_fir_gated smoke", log_fir_gated, append=False)
    runner.run_cmd([bin_fir_gated, "+VEC_DIR=data/test_vectors/corner"], "tb_fir_gated corner", log_fir_gated, append=True)
    runner.run_cmd([bin_fir_gated, "+VEC_DIR=data/test_vectors/std_fixed_100"], "tb_fir_gated std_fixed_100", log_fir_gated, append=True)

    # 4. Detector Tests
    det_srcs = ["rtl/qrs_detector.v"]
    bin_det_11 = runner.compile("det_11", "tb/tb_detector.v", det_srcs)
    bin_det_15 = runner.compile("det_15", "tb/tb_detector.v", det_srcs, extra_flags=["-GSQ_SHIFT=15"])
    log_det = os.path.join(REPORTS_DIR, "regress_detector.log")

    runner.run_cmd([bin_det_11, "+VEC_DIR=data/test_vectors/smoke"], "tb_detector smoke", log_det, append=False)
    runner.run_cmd([bin_det_11, "+VEC_DIR=data/test_vectors/noise_stress"], "tb_detector noise_stress (T10)", log_det, append=True)
    for rec in ["100", "101", "103", "105"]:
        runner.run_cmd([bin_det_11, f"+VEC_DIR=data/test_vectors/std_fixed_{rec}"], f"tb_detector std_fixed_{rec}", log_det, append=True)
    for rec in ["100", "101", "103", "105"]:
        runner.run_cmd([bin_det_15, f"+VEC_DIR=data/test_vectors/std_minmax_{rec}"], f"tb_detector std_minmax_{rec}", log_det, append=True)

    # 5. Top-Level Tests
    top_srcs = [
        "rtl/pg_top.v", "rtl/qrs_detector.v", "rtl/pg_fir.v",
        "rtl/sample_delay_line.v", "rtl/fir_coeff_rom.v", "rtl/mult_split.v", "rtl/pg_mac.v"
    ]
    bin_top_11 = runner.compile("top_11", "tb/tb_top.v", top_srcs)
    bin_top_15 = runner.compile("top_15", "tb/tb_top.v", top_srcs, extra_flags=["-GSQ_SHIFT=15"])
    log_top = os.path.join(REPORTS_DIR, "regress_top.log")

    runner.run_cmd([bin_top_11, "+VEC_DIR=data/test_vectors/smoke"], "tb_top smoke", log_top, append=False)
    runner.run_cmd([bin_top_11, "+VEC_DIR=data/test_vectors/smoke", "+RAND_GAP=1"], "tb_top smoke (rand gap)", log_top, append=True)
    runner.run_cmd([bin_top_11, "+VEC_DIR=data/test_vectors/noise_stress"], "tb_top noise_stress (T10)", log_top, append=True)
    for rec in ["100", "101", "103", "105"]:
        runner.run_cmd([bin_top_11, f"+VEC_DIR=data/test_vectors/std_fixed_{rec}"], f"tb_top std_fixed_{rec}", log_top, append=True)
    for rec in ["100", "101", "103", "105"]:
        runner.run_cmd([bin_top_15, f"+VEC_DIR=data/test_vectors/std_minmax_{rec}"], f"tb_top std_minmax_{rec}", log_top, append=True)

    # 6. Real-Rate Test
    bin_top_rr = runner.compile("top_rr", "tb/tb_top_realrate.v", top_srcs + ["rtl/sample_tick_gen.v"])
    runner.run_cmd([bin_top_rr, "+VEC_DIR=data/test_vectors/smoke"], "tb_top_realrate smoke (277.8M cycles)", log_top, append=True)

    # 7. Mid-Stream Reset Test
    bin_top_reset = runner.compile("top_reset", "tb/tb_top_reset.v", top_srcs)
    runner.run_cmd([bin_top_reset], "tb_top_reset mid-stream reset robustness", log_top, append=True)

    # 8. Startup Transient Tests (Phase B Hardening)
    for startup_set in ["startup_100_off0", "startup_103_off0", "startup_105_off200"]:
        runner.run_cmd([bin_top_11, f"+VEC_DIR=data/test_vectors/{startup_set}"], f"tb_top {startup_set}", log_top, append=True)

    # 9. Hardware Replay & UART Bit-Level Verification (Phase F)
    board_srcs = [
        "fpga/board_core.v", "fpga/uart_tx.v", "rtl/sample_tick_gen.v"
    ] + top_srcs
    bin_board = runner.compile("board_core", "tb/tb_board_core.v", board_srcs, extra_flags=["-Ifpga"])
    log_board = os.path.join(REPORTS_DIR, "regress_board_core.log")
    runner.run_cmd([bin_board, "+SCENARIO=por_replay"], "tb_board_core por_replay", log_board, append=False)
    runner.run_cmd([bin_board, "+SCENARIO=async_switch"], "tb_board_core async_switch", log_board, append=True)
    runner.run_cmd([bin_board, "+SCENARIO=debounce_glitch"], "tb_board_core debounce_glitch", log_board, append=True)

    # 10. Nightly Full-Length Regressions (Phase 3)
    is_nightly = "--nightly" in sys.argv
    if is_nightly:
        runner.log("\n--- EXECUTING NIGHTLY SUITE (650,000-sample full records) ---")
        required_nightly_sets = []
        for rec in ["100", "101", "103", "105"]:
            required_nightly_sets.append(f"full_fixed_{rec}")
            required_nightly_sets.append(f"full_minmax_{rec}")

        missing_sets = [
            s for s in required_nightly_sets
            if not os.path.exists(os.path.join(BASE_DIR, "data", "test_vectors", s, "tv_inputs.hex"))
        ]
        if missing_sets:
            runner.log(f"ERROR: Missing required full-length nightly vector set(s): {missing_sets}")
            runner.log("Run 'make full-vectors' (or 'python3 sim/gen_vectors.py --full') to generate them.")
            sys.exit(1)

        for rec in ["100", "101", "103", "105"]:
            vec_fixed = f"data/test_vectors/full_fixed_{rec}"
            vec_minmax = f"data/test_vectors/full_minmax_{rec}"
            runner.run_cmd([bin_det_11, f"+VEC_DIR={vec_fixed}"], f"tb_detector full_fixed_{rec}", log_det, append=True)
            runner.run_cmd([bin_top_11, f"+VEC_DIR={vec_fixed}"], f"tb_top full_fixed_{rec}", log_top, append=True)
            runner.run_cmd([bin_det_15, f"+VEC_DIR={vec_minmax}"], f"tb_detector full_minmax_{rec}", log_det, append=True)
            runner.run_cmd([bin_top_15, f"+VEC_DIR={vec_minmax}"], f"tb_top full_minmax_{rec}", log_top, append=True)

    runner.flush_logs(is_nightly)

    runner.log("\n==================================================================")
    runner.log(f"REGRESSION SUITE COMPLETED: {runner.passes} PASSED, {runner.fails} FAILED")
    runner.log("==================================================================")

    # Always write regression summary without wall-clock date
    commit, dirty = get_git_info()
    tool_vers = get_tool_versions()
    summary_data = {
        "commit": commit,
        "dirty": dirty,
        "failed": runner.fails,
        "mode": "nightly" if is_nightly else "standard",
        "passed": runner.passes,
        "tests": [{"name": desc, "status": status} for desc, status, _ in runner.results],
        "tool_versions": tool_vers
    }

    if is_nightly:
        summary_path = os.path.join(REPORTS_DIR, "regress_summary_nightly.json")
    else:
        summary_path = os.path.join(REPORTS_DIR, "regress_summary.json")

    with open(summary_path, "w") as f:
        json.dump(summary_data, f, indent=2, sort_keys=True)

    if runner.fails > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
