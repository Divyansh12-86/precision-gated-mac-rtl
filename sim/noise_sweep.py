"""
sim/noise_sweep.py — Noise Characterization Sweep across SNRs {24, 18, 12, 6, 0} dB

Conforms strictly to Phase G:
  - Records: 100, 103, 105
  - Target SNRs: 24, 18, 12, 6, 0 dB relative to clean QRS-band signal power
  - Noise components: baseline wander (0.3 Hz), powerline hum (50 Hz), EMG Gaussian noise
  - Computes for each:
      * Se and +P (beat-only)
      * Gate duty cycle (% full precision vs approx)
      * QRS-region PRD (gated vs all-approx)
      * Datapath toggle activity reduction %
      * RTL bit-exactness verification via tb_top (0 mismatches)
  - Outputs:
      * reports/noise_sweep.json
      * reports/figs/noise_sweep_plot.png
"""

import os
import sys
import json
import re
import subprocess
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import wfdb

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TV_DIR = os.path.join(BASE_DIR, "data", "test_vectors")
MITBIH_DIR = os.path.join(BASE_DIR, "data", "mitbih")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
FIGS_DIR = os.path.join(REPORTS_DIR, "figs")
os.makedirs(FIGS_DIR, exist_ok=True)
os.makedirs(TV_DIR, exist_ok=True)

from golden_v2 import load_record_data, design_fir_filter, run_fir_filter_vectorized
from qrs_detector_v2 import HardwareQRSDetectorV2, evaluate_detector_beats_only, BEAT_SYMBOLS
from gen_vectors import export_vector_dir

RECORDS = ["100", "103", "105"]
SNRS_DB = [24, 18, 12, 6, 0]
N_SAMPLES = 5000
FS = 360.0

def compute_prd(ref, test, eps=1e-12):
    ref = np.asarray(ref, dtype=np.float64)
    test = np.asarray(test, dtype=np.float64)
    num = np.sum((ref - test) ** 2)
    den = np.sum(ref ** 2)
    if den < eps:
        return 0.0
    return float(100.0 * np.sqrt(num / den))

def generate_noisy_signal(x_clean, target_snr_db, seed=42):
    np.random.seed(seed)
    N = len(x_clean)
    t = np.arange(N) / FS

    # Clean signal power
    p_sig = np.mean(x_clean.astype(np.float64) ** 2)
    p_noise_target = p_sig / (10.0 ** (target_snr_db / 10.0))

    # Composite noise components (unnormalized)
    bw = np.sin(2.0 * np.pi * 0.3 * t)          # Baseline wander (0.3 Hz)
    pl = np.sin(2.0 * np.pi * 50.0 * t)         # Powerline hum (50 Hz)
    emg = np.random.normal(0.0, 1.0, N)         # High-frequency EMG

    # Equal weight combination
    raw_noise = 0.4 * bw + 0.3 * pl + 0.3 * emg
    raw_p = np.mean(raw_noise ** 2)

    # Scale to match target noise power
    scale = np.sqrt(p_noise_target / (raw_p + 1e-12))
    noise = raw_noise * scale

    x_noisy = x_clean.astype(np.float64) + noise
    x16_noisy = np.clip(np.round(x_noisy), -32768, 32767).astype(np.int32)
    return x16_noisy

def run_noise_sweep():
    taps = design_fir_filter()
    results = {}

    # Compile tb_top once for verification
    build_dir = os.path.join(BASE_DIR, "build_noise_sweep")
    os.makedirs(build_dir, exist_ok=True)
    bin_top = os.path.join(build_dir, "sim_top_noise")
    cmd_compile = [
        "verilator", "--binary", "--timing",
        "-Wno-WIDTHTRUNC", "-Wno-WIDTHEXPAND", "-Wno-INITIALDLY",
        "-Irtl",
        "tb/tb_top.v",
        "rtl/pg_top.v", "rtl/qrs_detector.v", "rtl/pg_fir.v",
        "rtl/sample_delay_line.v", "rtl/fir_coeff_rom.v", "rtl/mult_split.v", "rtl/pg_mac.v",
        "--Mdir", build_dir, "-o", "sim_top_noise"
    ]
    print("[NOISE_SWEEP] Compiling tb_top for verification...", flush=True)
    res_c = subprocess.run(cmd_compile, cwd=BASE_DIR, capture_output=True, text=True)
    if res_c.returncode != 0:
        print(f"Compilation error:\n{res_c.stderr}")
        sys.exit(1)

    # Compile tb_activity once for exact switching activity measurements
    bin_act = os.path.join(build_dir, "sim_act_noise")
    cmd_compile_act = [
        "verilator", "--binary", "--timing",
        "-Wno-WIDTHTRUNC", "-Wno-WIDTHEXPAND", "-Wno-INITIALDLY",
        "-Irtl",
        "tb/tb_activity.v",
        "rtl/baseline_fir_exact.v", "rtl/pg_top.v", "rtl/qrs_detector.v",
        "rtl/pg_fir.v", "rtl/sample_delay_line.v", "rtl/fir_coeff_rom.v",
        "rtl/mult_split.v", "rtl/pg_mac.v",
        "--Mdir", build_dir, "-o", "sim_act_noise"
    ]
    print("[NOISE_SWEEP] Compiling tb_activity for switching characterization...", flush=True)
    res_ca = subprocess.run(cmd_compile_act, cwd=BASE_DIR, capture_output=True, text=True)
    if res_ca.returncode != 0:
        print(f"tb_activity compilation error:\n{res_ca.stderr}")
        sys.exit(1)

    for rec_id in RECORDS:
        results[rec_id] = {}
        # Load clean reference data
        x16_clean, _, _, sq_shift, _ = load_record_data(rec_id, policy="fixed", max_samples=N_SAMPLES)
        ann = wfdb.rdann(os.path.join(MITBIH_DIR, rec_id), 'atr')
        ann_s = ann.sample[ann.sample < N_SAMPLES]
        ann_sym = [ann.symbol[i] for i, s in enumerate(ann.sample) if s < N_SAMPLES]
        true_beats = [s for s, sym in zip(ann_s, ann_sym) if sym in BEAT_SYMBOLS]

        for snr in SNRS_DB:
            set_name = f"noise_{rec_id}_{snr}db"
            out_vec_dir = os.path.join(TV_DIR, set_name)
            os.makedirs(out_vec_dir, exist_ok=True)

            # Generate noisy stream
            x16_noisy = generate_noisy_signal(x16_clean, snr, seed=42 + snr)

            # Golden Model v2 processing
            det = HardwareQRSDetectorV2(sq_shift=sq_shift)
            gf, pks, mwi = det.detect_stream(x16_noisy)
            yf, yg, ya = run_fir_filter_vectorized(x16_noisy, taps, gf)

            # Export test vectors for RTL verification
            meta = {
                "set_name": set_name,
                "record_id": rec_id,
                "snr_db": snr,
                "n_samples": N_SAMPLES
            }
            export_vector_dir(out_vec_dir, x16_noisy, taps, gf, pks, mwi, yf, yg, ya, meta)

            # 1. Detector Sensitivity & Positive Predictivity
            peak_indices = [i - 1 for i, p in enumerate(pks) if p == 1]
            det_eval = evaluate_detector_beats_only(peak_indices, ann_s, ann_sym, tolerance=50)

            # 2. Gate duty (% of time in full precision mode)
            gate_duty_pct = float(np.mean(gf) * 100.0)
            approx_duty_pct = 100.0 - gate_duty_pct

            # 3. QRS-region PRD (gated vs all-approx)
            qrs_mask = np.zeros(N_SAMPLES, dtype=bool)
            for r in true_beats:
                q_start = r + 15
                q_end = min(N_SAMPLES, r + 37)
                if q_start < N_SAMPLES and q_end > q_start:
                    qrs_mask[q_start:q_end] = True

            yf_norm = yf.astype(np.float64) / 32768.0
            yg_norm = yg.astype(np.float64) / 32768.0
            ya_norm = ya.astype(np.float64) / 32768.0

            if np.any(qrs_mask):
                qrs_prd_gated = compute_prd(yf_norm[qrs_mask], yg_norm[qrs_mask])
                qrs_prd_allapprox = compute_prd(yf_norm[qrs_mask], ya_norm[qrs_mask])
            else:
                qrs_prd_gated = 0.0
                qrs_prd_allapprox = 0.0

            # 4. RTL Verification (mismatches = 0)
            cmd_tb = [bin_top, f"+VEC_DIR={out_vec_dir}"]
            res_tb = subprocess.run(cmd_tb, cwd=BASE_DIR, capture_output=True, text=True)
            rtl_pass = (res_tb.returncode == 0) and ("TB_RESULT: PASS" in res_tb.stdout)
            if not rtl_pass:
                print(f"FATAL: RTL verification failed on {set_name}!")
                print(res_tb.stdout[-500:])
                sys.exit(1)

            # 5. Measure exact RTL switching activity reduction
            res_act = subprocess.run([bin_act, f"+VEC_DIR={out_vec_dir}"], cwd=BASE_DIR, capture_output=True, text=True)
            pat_dp = re.compile(r"(\w+):\s+oph=(\d+)\s+opl=(\d+)\s+mult=(\d+)\s+acc=(\d+)\s+total=(\d+)")
            pat_core = re.compile(r"CORE_(\w+):\s+dp=(\d+)\s+dline=(\d+)\s+ctrl=(\d+)\s+det=(\d+)\s+core_total=(\d+)")

            dp_data = {}
            for line in res_act.stdout.splitlines():
                m = pat_dp.search(line)
                if m:
                    name, oph, opl, mult, acc, tot = m.groups()
                    dp_data[name.lower()] = int(tot)

            core_data = {}
            for line in res_act.stdout.splitlines():
                m = pat_core.search(line)
                if m:
                    name, dp, dline, ctrl, det, tot = m.groups()
                    core_data[name.lower()] = int(tot)

            base_dp_tot = dp_data.get("baseline", 0)
            auto_dp_tot = dp_data.get("gated_auto", 0)
            base_core_tot = core_data.get("baseline", 0)
            auto_core_tot = core_data.get("gated_auto", 0)

            dp_saving_pct = round((1.0 - auto_dp_tot / base_dp_tot) * 100.0, 2) if base_dp_tot else 0.0
            core_saving_pct = round((1.0 - auto_core_tot / base_core_tot) * 100.0, 2) if base_core_tot else 0.0

            # Estimate datapath toggle saving from approx duty
            # Datapath toggle saving is approx ~ 0.25 * approx_duty_pct
            # (since approx mode eliminates partial products and accumulator LSB toggles)
            est_dp_saving_pct = round(approx_duty_pct * 0.252, 2)

            point_result = {
                "snr_db": snr,
                "sensitivity_pct": round(det_eval["sensitivity"], 2),
                "positive_predictivity_pct": round(det_eval["positive_predictivity"], 2),
                "gate_duty_full_pct": round(gate_duty_pct, 2),
                "approx_duty_pct": round(approx_duty_pct, 2),
                "qrs_prd_gated_pct": round(qrs_prd_gated, 3),
                "qrs_prd_allapprox_pct": round(qrs_prd_allapprox, 3),
                "datapath_reduction_pct": dp_saving_pct,
                "whole_core_reduction_pct": core_saving_pct,
                "est_datapath_saving_pct": est_dp_saving_pct,
                "rtl_verified": rtl_pass
            }
            results[rec_id][str(snr)] = point_result
            print(f"  [{rec_id} @ {snr:2d} dB] Se={det_eval['sensitivity']:.1f}% | +P={det_eval['positive_predictivity']:.1f}% | FullDuty={gate_duty_pct:.1f}% | DP-Saving={dp_saving_pct:.2f}% | Core-Saving={core_saving_pct:.2f}% | RTL=PASS", flush=True)

    # Save reports/noise_sweep.json
    out_json = os.path.join(REPORTS_DIR, "noise_sweep.json")
    with open(out_json, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[DONE] Noise sweep metrics saved to {out_json}")

    # Generate Plot
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    colors = {"100": "#1f77b4", "103": "#2ca02c", "105": "#d62728"}

    for rec in RECORDS:
        snrs = [r["snr_db"] for r in results[rec].values()]
        full_duties = [r["gate_duty_full_pct"] for r in results[rec].values()]
        dp_savings = [r["datapath_reduction_pct"] for r in results[rec].values()]
        core_savings = [r["whole_core_reduction_pct"] for r in results[rec].values()]

        axes[0].plot(snrs, full_duties, marker='o', linewidth=2, color=colors[rec], label=f"Record {rec}")
        axes[1].plot(snrs, dp_savings, marker='s', linewidth=2, color=colors[rec], label=f"Record {rec} (Datapath)")
        axes[1].plot(snrs, core_savings, marker='^', linestyle='--', linewidth=1.5, color=colors[rec], alpha=0.7, label=f"Record {rec} (Whole Core)")

    axes[0].set_title("Full-Precision Gate Duty vs Input SNR", fontsize=12, fontweight="bold")
    axes[0].set_xlabel("Input SNR (dB)", fontsize=11)
    axes[0].set_ylabel("Full Precision Duty (%)", fontsize=11)
    axes[0].grid(True, linestyle="--", alpha=0.6)
    axes[0].legend()
    axes[0].invert_xaxis() # High SNR to Low SNR

    axes[1].set_title("Measured RTL Switching Savings vs Input SNR", fontsize=12, fontweight="bold")
    axes[1].set_xlabel("Input SNR (dB)", fontsize=11)
    axes[1].set_ylabel("RTL Toggle Activity Saving (%)", fontsize=11)
    axes[1].grid(True, linestyle="--", alpha=0.6)
    axes[1].legend()
    axes[1].invert_xaxis()

    plt.tight_layout()
    plot_path = os.path.join(FIGS_DIR, "noise_sweep_plot.png")
    plt.savefig(plot_path, dpi=200)
    plt.close()
    print(f"[DONE] Noise sweep plot saved to {plot_path}")

if __name__ == "__main__":
    run_noise_sweep()
