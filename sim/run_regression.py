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

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
BUILD_DIR = os.path.join(BASE_DIR, "build_regress")
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(BUILD_DIR, exist_ok=True)

class RegressionRunner:
    def __init__(self):
        self.passes = 0
        self.fails = 0
        self.results = []

    def log(self, msg):
        print(msg, flush=True)

    def run_cmd(self, cmd, desc, log_file=None, append=False):
        self.log(f"\n[RUN] {desc}...")
        t0 = time.time()
        res = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True)
        elapsed = time.time() - t0
        output = res.stdout + ("\nSTDERR:\n" + res.stderr if res.stderr else "")

        if log_file:
            mode = "a" if append else "w"
            with open(log_file, mode) as f:
                f.write(f"=== {desc} (elapsed: {elapsed:.2f}s, exit: {res.returncode}) ===\n")
                f.write(output + "\n")

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

    def compile(self, name, tb_file, srcs, extra_flags=None):
        out_bin = f"sim_{name}"
        cmd = [
            "verilator", "--binary", "--timing",
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

    runner.log("\n==================================================================")
    runner.log(f"REGRESSION SUITE COMPLETED: {runner.passes} PASSED, {runner.fails} FAILED")
    runner.log("==================================================================")

    if runner.fails > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
