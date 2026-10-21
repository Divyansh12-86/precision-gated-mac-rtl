"""
sim/gen_vectors.py — Deterministic Vector Generation Factory

Generates test vector suites per Section 7 Phase 1:
- smoke: rec 100, first 1000 samples, fixed policy
- corner: synthetic corner cases (impulses, alternating, ramps, random, stuck gates)
- std_<policy>_<rec>: 4 records x 60,000 samples x 2 policies
Outputs in each vector directory:
- tv_inputs.hex (4 hex digits)
- tv_gate_flags.hex (1 hex digit)
- tv_outputs_full.hex (8 hex digits, 32-bit accumulator)
- tv_outputs_gated.hex (8 hex digits, 32-bit accumulator)
- tv_outputs_allapprox.hex (8 hex digits, 32-bit accumulator)
- tv_peaks.hex (1 hex digit)
- tv_mwi.hex (6 hex digits)
- coeffs.mem (51 lines, 4 hex digits)
- manifest.json (metadata & sha256 hashes)
"""

import os
import sys
import json
import hashlib
import argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from golden_v2 import (
    load_record_data, design_fir_filter, run_fir_filter_vectorized,
    truncate_operand_8b
)
from qrs_detector_v2 import HardwareQRSDetectorV2

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
TV_BASE_DIR = os.path.join(DATA_DIR, "test_vectors")

def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def export_vector_dir(out_dir, x16, taps, gate_flags, pks, mwi, y_full, y_gated, y_allapprox, meta):
    os.makedirs(out_dir, exist_ok=True)
    n = len(x16)

    # 1. tv_inputs.hex (4 hex digits)
    p_in = os.path.join(out_dir, "tv_inputs.hex")
    with open(p_in, "w") as f:
        for val in x16:
            f.write(f"{int(val) & 0xFFFF:04X}\n")

    # 2. tv_gate_flags.hex (1 digit)
    p_gf = os.path.join(out_dir, "tv_gate_flags.hex")
    with open(p_gf, "w") as f:
        for val in gate_flags:
            f.write(f"{int(val) & 0x1:01X}\n")

    # 3. tv_outputs_full.hex (8 hex digits)
    p_yf = os.path.join(out_dir, "tv_outputs_full.hex")
    with open(p_yf, "w") as f:
        for val in y_full:
            f.write(f"{int(val) & 0xFFFFFFFF:08X}\n")

    # 4. tv_outputs_gated.hex (8 hex digits)
    p_yg = os.path.join(out_dir, "tv_outputs_gated.hex")
    with open(p_yg, "w") as f:
        for val in y_gated:
            f.write(f"{int(val) & 0xFFFFFFFF:08X}\n")

    # 5. tv_outputs_allapprox.hex (8 hex digits)
    p_ya = os.path.join(out_dir, "tv_outputs_allapprox.hex")
    with open(p_ya, "w") as f:
        for val in y_allapprox:
            f.write(f"{int(val) & 0xFFFFFFFF:08X}\n")

    # 6. tv_peaks.hex (1 digit)
    p_pk = os.path.join(out_dir, "tv_peaks.hex")
    with open(p_pk, "w") as f:
        for val in pks:
            f.write(f"{int(val) & 0x1:01X}\n")

    # 7. tv_mwi.hex (6 hex digits)
    p_mwi = os.path.join(out_dir, "tv_mwi.hex")
    with open(p_mwi, "w") as f:
        for val in mwi:
            f.write(f"{int(val) & 0x3FFFF:06X}\n")

    # 8. coeffs.mem (51 lines, 4 hex digits)
    p_cm = os.path.join(out_dir, "coeffs.mem")
    with open(p_cm, "w") as f:
        for val in taps:
            f.write(f"{int(val) & 0xFFFF:04X}\n")

    # Also maintain coeffs.mem in BASE_DIR for root-level toolchain commands (e.g. Yosys)
    root_cm = os.path.join(BASE_DIR, "coeffs.mem")
    with open(root_cm, "w") as f:
        for val in taps:
            f.write(f"{int(val) & 0xFFFF:04X}\n")

    # 9. manifest.json
    manifest = {
        "metadata": meta,
        "n_samples": n,
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
    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Generated {n} vectors in: {out_dir}")

def generate_record_set(record_id, policy, n_samples, set_name=None):
    if set_name is None:
        set_name = f"std_{policy}_{record_id}" if n_samples == 60000 else f"rec_{policy}_{record_id}_{n_samples}"

    out_dir = os.path.join(TV_BASE_DIR, set_name)
    x16, ann_sample, ann_sym, sq_shift, rec = load_record_data(record_id, policy=policy, max_samples=n_samples)
    taps = design_fir_filter()

    det = HardwareQRSDetectorV2(sq_shift=sq_shift)
    gf, pks, mwi = det.detect_stream(x16)
    y_full, y_gated, y_allapprox = run_fir_filter_vectorized(x16, taps, gf)

    meta = {
        "set_name": set_name,
        "record_id": record_id,
        "policy": policy,
        "sq_shift": sq_shift,
        "n_samples": len(x16)
    }
    export_vector_dir(out_dir, x16, taps, gf, pks, mwi, y_full, y_gated, y_allapprox, meta)

def generate_smoke():
    out_dir = os.path.join(TV_BASE_DIR, "smoke")
    x16, _, _, sq_shift, _ = load_record_data("100", policy="fixed", max_samples=1000)
    taps = design_fir_filter()
    det = HardwareQRSDetectorV2(sq_shift=sq_shift)
    gf, pks, mwi = det.detect_stream(x16)
    y_full, y_gated, y_allapprox = run_fir_filter_vectorized(x16, taps, gf)
    meta = {"set_name": "smoke", "record_id": "100", "policy": "fixed", "sq_shift": sq_shift}
    export_vector_dir(out_dir, x16, taps, gf, pks, mwi, y_full, y_gated, y_allapprox, meta)

    # Also keep top-level test_vectors populated for backward compatibility
    export_vector_dir(TV_BASE_DIR, x16, taps, gf, pks, mwi, y_full, y_gated, y_allapprox, meta)

def generate_corner():
    out_dir = os.path.join(TV_BASE_DIR, "corner")
    taps = design_fir_filter()

    # Synthetic corner test sequence
    pieces = []
    gate_pieces = []

    # 1. All zeros (100 samples)
    z100 = np.zeros(100, dtype=np.int32)
    pieces.append(z100)
    gate_pieces.append(np.zeros(100, dtype=np.int32))

    # 2. Single positive impulse 0x7FFF (32767) followed by 80 zeros
    imp_pos = np.zeros(81, dtype=np.int32); imp_pos[0] = 32767
    pieces.append(imp_pos)
    gate_pieces.append(np.ones(81, dtype=np.int32)) # Gate stuck 1

    # 3. Single negative impulse 0x8000 (-32768) followed by 80 zeros
    imp_neg = np.zeros(81, dtype=np.int32); imp_neg[0] = -32768
    pieces.append(imp_neg)
    gate_pieces.append(np.zeros(81, dtype=np.int32)) # Gate stuck 0

    # 4. Alternating +32767 / -32768 (100 samples)
    alt = np.array([32767 if i % 2 == 0 else -32768 for i in range(100)], dtype=np.int32)
    pieces.append(alt)
    gate_pieces.append(np.array([i % 2 for i in range(100)], dtype=np.int32))

    # 5. Ramp over full range (-32768 to 32767 step 256)
    ramp = np.arange(-32768, 32768, 256, dtype=np.int32)
    pieces.append(ramp)
    gate_pieces.append(np.array([(i // 8) % 2 for i in range(len(ramp))], dtype=np.int32))

    # 6. Seeded pseudo-random 16-bit signed (1000 samples)
    rng = np.random.RandomState(42)
    rand16 = rng.randint(-32768, 32768, size=1000, dtype=np.int32)
    pieces.append(rand16)
    # Random gate toggling each sample
    rand_gate = rng.randint(0, 2, size=1000, dtype=np.int32)
    gate_pieces.append(rand_gate)

    x16 = np.concatenate(pieces)
    gate_flags = np.concatenate(gate_pieces)

    # Run detector on corner just to get valid pks and mwi
    det = HardwareQRSDetectorV2(sq_shift=11)
    _, pks, mwi = det.detect_stream(x16)

    y_full, y_gated, y_allapprox = run_fir_filter_vectorized(x16, taps, gate_flags)

    meta = {
        "set_name": "corner",
        "record_id": "synthetic",
        "description": "Impulses, alternating extrema, ramps, and random toggling"
    }
    export_vector_dir(out_dir, x16, taps, gate_flags, pks, mwi, y_full, y_gated, y_allapprox, meta)

def generate_noise_stress():
    out_dir = os.path.join(TV_BASE_DIR, "noise_stress")
    N = 5000
    x16_clean, _, _, sq_shift, _ = load_record_data("100", policy="fixed", max_samples=N)
    t = np.arange(N) / 360.0

    # 1. Baseline wander (0.3 Hz, amplitude 2500)
    bw = 2500.0 * np.sin(2.0 * np.pi * 0.3 * t)

    # 2. Powerline interference (50 Hz, amplitude 1500)
    pl = 1500.0 * np.sin(2.0 * np.pi * 50.0 * t)

    # 3. EMG high frequency Gaussian noise (std 600)
    np.random.seed(42)
    emg = np.random.normal(0, 600, N)

    x_noisy = x16_clean.astype(np.float64) + bw + pl + emg
    x16_noisy = np.clip(np.round(x_noisy), -32768, 32767).astype(np.int32)

    taps = design_fir_filter()
    det = HardwareQRSDetectorV2(sq_shift=sq_shift)
    gf, pks, mwi = det.detect_stream(x16_noisy)
    yf, yg, ya = run_fir_filter_vectorized(x16_noisy, taps, gf)

    meta = {
        "set_name": "noise_stress",
        "record_id": "100_noisy",
        "description": "MIT-BIH 100 with baseline wander (0.3Hz), powerline (50Hz), and EMG noise"
    }
    export_vector_dir(out_dir, x16_noisy, taps, gf, pks, mwi, yf, yg, ya, meta)

def generate_all():
    print("=== Generating smoke set ===")
    generate_smoke()

    print("\n=== Generating corner set ===")
    generate_corner()

    print("\n=== Generating noise stress set (T10) ===")
    generate_noise_stress()

    print("\n=== Generating standard regression sets (60,000 samples) ===")
    for rec in ["100", "101", "103", "105"]:
        for pol in ["fixed", "minmax"]:
            generate_record_set(rec, policy=pol, n_samples=60000, set_name=f"std_{pol}_{rec}")

    print("\nAll test vector sets generated successfully!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate RTL verification test vectors")
    parser.add_argument("--all", action="store_true", help="Generate all standard vector sets")
    parser.add_argument("--smoke", action="store_true", help="Generate smoke test set")
    parser.add_argument("--corner", action="store_true", help="Generate corner test set")
    parser.add_argument("--record", type=str, help="Record ID (e.g. 100)")
    parser.add_argument("--policy", type=str, default="fixed", choices=["fixed", "minmax", "fixed_g7"])
    parser.add_argument("--n", type=int, default=60000, help="Number of samples")
    parser.add_argument("--out", type=str, help="Output directory")

    args = parser.parse_args()

    if args.all:
        generate_all()
    elif args.smoke:
        generate_smoke()
    elif args.corner:
        generate_corner()
    elif args.record:
        generate_record_set(args.record, policy=args.policy, n_samples=args.n, set_name=args.out)
    else:
        generate_all()
