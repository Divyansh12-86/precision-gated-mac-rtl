"""
sim/gen_noise_stress.py — Generate composite noise stress vector set (T10).
Injects baseline wander (0.3 Hz), powerline hum (50 Hz), and EMG burst noise.
"""
import os
import numpy as np
from golden_v2 import load_record_data, design_fir_filter, run_fir_filter_vectorized
from qrs_detector_v2 import HardwareQRSDetectorV2
from gen_vectors import export_vector_dir

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE_DIR, "data", "test_vectors", "noise_stress")
os.makedirs(OUT_DIR, exist_ok=True)

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
export_vector_dir(OUT_DIR, x16_noisy, taps, gf, pks, mwi, yf, yg, ya, meta)
print(f"Generated {N} noise stress vectors in {OUT_DIR}")
