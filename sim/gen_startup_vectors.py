"""
sim/gen_startup_vectors.py — Generate start-up and offset vector sets to exercise reset thresholds.
Creates slices starting at offsets [0, 37, 211, 512, 1000] for records 100, 103, 105 (500 samples each).
"""
import os
import numpy as np
from golden_v2 import load_record_data, design_fir_filter, run_fir_filter_vectorized
from qrs_detector_v2 import HardwareQRSDetectorV2
from gen_vectors import export_vector_dir

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TV_DIR = os.path.join(BASE_DIR, "data", "test_vectors")

OFFSETS = [0, 37, 200, 211, 512, 1000]
RECORDS = ["100", "103", "105"]
N_SAMPLES = 500

def generate_startup_sets():
    taps = design_fir_filter()
    count = 0

    for rec in RECORDS:
        x_full, _, _, sq_shift, _ = load_record_data(rec, policy="fixed", max_samples=5000)
        for offset in OFFSETS:
            x_slice = x_full[offset:offset + N_SAMPLES]
            if len(x_slice) < N_SAMPLES:
                continue

            set_name = f"startup_{rec}_off{offset}"
            out_dir = os.path.join(TV_DIR, set_name)

            det = HardwareQRSDetectorV2(sq_shift=sq_shift)
            gf, pks, mwi = det.detect_stream(x_slice)
            yf, yg, ya = run_fir_filter_vectorized(x_slice, taps, gf)

            meta = {
                "set_name": set_name,
                "record_id": rec,
                "offset": offset,
                "n_samples": N_SAMPLES,
                "purpose": "Start-up transient and reset threshold verification"
            }
            export_vector_dir(out_dir, x_slice, taps, gf, pks, mwi, yf, yg, ya, meta)
            count += 1

    print(f"Generated {count} startup/offset test vector sets in {TV_DIR}/startup_*")

if __name__ == "__main__":
    generate_startup_sets()
