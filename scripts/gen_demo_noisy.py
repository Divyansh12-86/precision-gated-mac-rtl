#!/usr/bin/env python3
"""
scripts/gen_demo_noisy.py — Generates demo_noisy_100 vector set and ecg_rom_demo_noisy.mem

Conforms to Section 4B Task 4 of ROUND6_GUIDE_AGENT.md:
  - MIT-BIH Record 100, 60,000 samples, fixed scaling policy ((adu - 1024) << 5)
  - Synthetic muscle/EMG composite noise added in integer ADU domain before << 5 scaling at 12 dB SNR
  - Same SNR definition and seed formula (seed=54) as sim/noise_sweep.py
  - Strictly preserves (x & 31) == 0 for all 60,000 samples
  - Generates data/test_vectors/demo_noisy_100/ (tv_*.hex, coeffs.mem, manifest.json)
  - Generates ecg_rom_demo_noisy.mem (60,000 lines)
  - Validates detector Se >= 99% and +P >= 90%
"""

import os
import sys
import json
import hashlib
import numpy as np
import wfdb

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "sim"))

from golden_v2 import run_fir_filter_vectorized
from qrs_detector_v2 import HardwareQRSDetectorV2, evaluate_detector_beats_only, BEAT_SYMBOLS
from noise_sweep import generate_noisy_adu_stream

TV_DIR = os.path.join(BASE_DIR, "data", "test_vectors", "demo_noisy_100")
ROM_PATH = os.path.join(BASE_DIR, "ecg_rom_demo_noisy.mem")
COEFFS_PATH = os.path.join(BASE_DIR, "coeffs.mem")
MITBIH_DIR = os.path.join(BASE_DIR, "data", "mitbih")

def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def main():
    print("==================================================================")
    print("GENERATING DEMO DATASET: demo_noisy_100 (60,000 samples)")
    print("==================================================================")

    os.makedirs(TV_DIR, exist_ok=True)

    # 1. Load MIT-BIH record 100
    rec_path = os.path.join(MITBIH_DIR, "100")
    rec = wfdb.rdrecord(rec_path, physical=False)
    n_samples = 60000
    adu_raw = rec.d_signal[:n_samples, 0].astype(np.int64)

    # 2. Synthesize composite noise in integer ADU domain at 12 dB SNR (seed = 42 + 12 = 54)
    target_snr_db = 12
    seed = 42 + target_snr_db
    x16_noisy = generate_noisy_adu_stream(adu_raw, target_snr_db, seed=seed)

    # Check ADU invariant: (x & 31) == 0
    lsb_zeros = int(np.sum((x16_noisy & 31) == 0))
    if lsb_zeros != n_samples:
        print(f"ERROR: ADU scaling invariant (x & 31) == 0 violated! ({lsb_zeros}/{n_samples})")
        sys.exit(1)
    print(f"[PASS] ADU invariant (x & 31) == 0 verified for {n_samples}/{n_samples} samples.")

    # 3. Read frozen coeffs.mem
    with open(COEFFS_PATH, "r") as f:
        taps_raw = [int(line.strip(), 16) for line in f if line.strip()]
    taps = np.array([v if v < 32768 else v - 65536 for v in taps_raw], dtype=np.int32)
    print(f"[PASS] Loaded {len(taps)} FIR filter taps from coeffs.mem.")

    # 4. Run Golden Model v2 QRS detector
    det = HardwareQRSDetectorV2(sq_shift=11)
    gate_flags, pks, mwi = det.detect_stream(x16_noisy)

    # 5. Run Golden Model v2 FIR filter
    y_full, y_gated, y_allapprox = run_fir_filter_vectorized(x16_noisy, taps, gate_flags)

    # 6. Evaluate detector against ground truth annotations
    ann = wfdb.rdann(rec_path, 'atr')
    ann_s = ann.sample[ann.sample < n_samples]
    ann_sym = [ann.symbol[i] for i, s in enumerate(ann.sample) if s < n_samples]
    peaks = [i - 1 for i, p in enumerate(pks) if p == 1]
    det_eval = evaluate_detector_beats_only(peaks, ann_s, ann_sym, tolerance=50)

    se = det_eval["sensitivity"]
    pp = det_eval["positive_predictivity"]
    full_duty = float(np.mean(gate_flags) * 100.0)

    print(f"\nDetector Evaluation on demo_noisy_100:")
    print(f"  Sensitivity (Se):            {se:.2f}% (required >= 99%)")
    print(f"  Positive Predictivity (+P):  {pp:.2f}% (required >= 90%)")
    print(f"  Full Precision Gate Duty:    {full_duty:.2f}%")
    print(f"  Approximate Precision Duty:  {100.0 - full_duty:.2f}%")

    if se < 99.0:
        print(f"ERROR: Sensitivity {se:.2f}% < 99.0% threshold!")
        sys.exit(1)
    if pp < 90.0:
        print(f"ERROR: Positive Predictivity {pp:.2f}% < 90.0% threshold!")
        sys.exit(1)

    # 7. Write test vector files into TV_DIR
    p_in = os.path.join(TV_DIR, "tv_inputs.hex")
    with open(p_in, "w") as f:
        for val in x16_noisy:
            f.write(f"{int(val) & 0xFFFF:04X}\n")

    p_gf = os.path.join(TV_DIR, "tv_gate_flags.hex")
    with open(p_gf, "w") as f:
        for val in gate_flags:
            f.write(f"{int(val) & 0x1:01X}\n")

    p_yf = os.path.join(TV_DIR, "tv_outputs_full.hex")
    with open(p_yf, "w") as f:
        for val in y_full:
            f.write(f"{int(val) & 0xFFFFFFFF:08X}\n")

    p_yg = os.path.join(TV_DIR, "tv_outputs_gated.hex")
    with open(p_yg, "w") as f:
        for val in y_gated:
            f.write(f"{int(val) & 0xFFFFFFFF:08X}\n")

    p_ya = os.path.join(TV_DIR, "tv_outputs_allapprox.hex")
    with open(p_ya, "w") as f:
        for val in y_allapprox:
            f.write(f"{int(val) & 0xFFFFFFFF:08X}\n")

    p_pk = os.path.join(TV_DIR, "tv_peaks.hex")
    with open(p_pk, "w") as f:
        for val in pks:
            f.write(f"{int(val) & 0x1:01X}\n")

    p_mwi = os.path.join(TV_DIR, "tv_mwi.hex")
    with open(p_mwi, "w") as f:
        for val in mwi:
            f.write(f"{int(val) & 0x3FFFF:06X}\n")

    p_cm = os.path.join(TV_DIR, "coeffs.mem")
    with open(p_cm, "w") as f:
        for val in taps_raw:
            f.write(f"{val:04X}\n")

    meta = {
        "set_name": "demo_noisy_100",
        "record_id": "100",
        "policy": "fixed",
        "n_samples": n_samples,
        "snr_db": target_snr_db,
        "noise_type": "composite_emg_bw_pl",
        "seed": seed,
        "sensitivity_pct": round(se, 2),
        "positive_predictivity_pct": round(pp, 2),
        "gate_duty_full_pct": round(full_duty, 2)
    }

    manifest = {
        "metadata": meta,
        "n_samples": n_samples,
        "files": {
            "tv_inputs.hex": sha256_file(p_in),
            "tv_gate_flags.hex": sha256_file(p_gf),
            "tv_outputs_full.hex": sha256_file(p_yf),
            "tv_outputs_gated.hex": sha256_file(p_yg),
            "tv_outputs_allapprox.hex": sha256_file(p_ya),
            "tv_peaks.hex": sha256_file(p_pk),
            "tv_mwi.hex": sha256_file(p_mwi),
            "coeffs.mem": sha256_file(p_cm)
        }
    }
    with open(os.path.join(TV_DIR, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"[PASS] Successfully exported test vectors to {TV_DIR}.")

    # 8. Write ecg_rom_demo_noisy.mem
    with open(ROM_PATH, "w") as f:
        for val in x16_noisy:
            f.write(f"{int(val) & 0xFFFF:04X}\n")

    print(f"[PASS] Successfully generated {ROM_PATH} ({n_samples} lines).")
    print("DEMO DATASET GENERATION: COMPLETE")

if __name__ == "__main__":
    main()
