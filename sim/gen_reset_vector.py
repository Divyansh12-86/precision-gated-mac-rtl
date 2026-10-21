"""
sim/gen_reset_vector.py — Generate test vectors for mid-stream reset verification.
"""
import os
import numpy as np
from golden_v2 import load_record_data, design_fir_filter, run_fir_filter_vectorized
from qrs_detector_v2 import HardwareQRSDetectorV2

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "test_vectors", "reset_test")
os.makedirs(DATA_DIR, exist_ok=True)

x16, _, _, sq_shift, _ = load_record_data("100", policy="fixed", max_samples=1000)
taps = design_fir_filter()

# Pre-reset portion: samples 0..299
det_pre = HardwareQRSDetectorV2(sq_shift=sq_shift)
gf_pre, _, _ = det_pre.detect_stream(x16[:300])
y_pre, _, _ = run_fir_filter_vectorized(x16[:300], taps, gf_pre)

# Post-reset portion: samples 300..999, starting completely from reset state
x16_post = x16[300:]
det_post = HardwareQRSDetectorV2(sq_shift=sq_shift)
gf_post, _, _ = det_post.detect_stream(x16_post)
_, y_post, _ = run_fir_filter_vectorized(x16_post, taps, gf_post)

# Write pre vectors
with open(os.path.join(DATA_DIR, "tv_inputs_pre.hex"), "w") as f:
    for v in x16[:300]:
        f.write(f"{int(v) & 0xFFFF:04X}\n")

# Write post vectors
with open(os.path.join(DATA_DIR, "tv_inputs_post.hex"), "w") as f:
    for v in x16_post:
        f.write(f"{int(v) & 0xFFFF:04X}\n")

with open(os.path.join(DATA_DIR, "tv_outputs_post.hex"), "w") as f:
    for v in y_post:
        f.write(f"{int(v) & 0xFFFFFFFF:08X}\n")

with open(os.path.join(DATA_DIR, "coeffs.mem"), "w") as f:
    for t in taps:
        f.write(f"{int(t) & 0xFFFF:04X}\n")

print(f"Generated reset verification vectors in {DATA_DIR}: 300 pre-reset, {len(x16_post)} post-reset.")
