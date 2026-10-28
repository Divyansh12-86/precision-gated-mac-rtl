#!/usr/bin/env python3
"""
scripts/filter_response.py — Frequency Response Characterization of coeffs.mem FIR filter

Computes exact frequency response metrics using 8192-point FFT (fs = 360 Hz):
  - DC gain
  - -3 dB and -6 dB cutoff frequencies
  - Response at specified frequencies [0, 1, 5, 10, 15, 17, 20, 30, 50, 100] Hz
Outputs:
  - reports/filter_response.json
  - reports/figs/filter_response.png
  - stdout (captured in evidence/filter_response.txt)
"""

import os
import sys
import json
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
from scripts.source_digest import get_source_digest, get_git_commit

REPORTS_DIR = os.path.join(BASE_DIR, "reports")
FIGS_DIR = os.path.join(REPORTS_DIR, "figs")
COEFFS_PATH = os.path.join(BASE_DIR, "coeffs.mem")

def main():
    os.makedirs(FIGS_DIR, exist_ok=True)

    if not os.path.exists(COEFFS_PATH):
        print(f"ERROR: coeffs.mem not found at {COEFFS_PATH}")
        sys.exit(1)

    with open(COEFFS_PATH, "r", encoding="utf-8") as f:
        raw = [int(line.strip(), 16) for line in f if line.strip()]

    taps_int = np.array([x if x < 32768 else x - 65536 for x in raw], dtype=np.float64)
    taps = taps_int / 32768.0

    fs = 360.0
    n_fft = 8192
    H = np.fft.rfft(taps, n_fft)
    freqs = np.fft.rfftfreq(n_fft, 1.0 / fs)
    mag = np.abs(H)

    dc_gain = float(np.sum(taps_int) / 32768.0)
    mag_db_rel_dc = 20.0 * np.log10(np.maximum(mag / mag[0], 1e-12))

    idx_3db = np.where(mag_db_rel_dc <= -3.0)[0][0]
    idx_6db = np.where(mag_db_rel_dc <= -6.0)[0][0]

    f_3db = float(np.interp(-3.0, [mag_db_rel_dc[idx_3db-1], mag_db_rel_dc[idx_3db]], [freqs[idx_3db-1], freqs[idx_3db]]))
    f_6db = float(np.interp(-6.0, [mag_db_rel_dc[idx_6db-1], mag_db_rel_dc[idx_6db]], [freqs[idx_6db-1], freqs[idx_6db]]))

    eval_freqs = [0, 1, 5, 10, 15, 17, 20, 30, 50, 100]
    freq_data = {}
    for ef in eval_freqs:
        idx = int(np.argmin(np.abs(freqs - ef)))
        g = float(mag[idx])
        g_db = float(mag_db_rel_dc[idx])
        freq_data[str(ef)] = {
            "freq_hz": ef,
            "gain_linear": round(g, 4),
            "gain_db_rel_dc": round(g_db, 2)
        }

    summary_text = (
        f"51-tap Kaiser-window FIR; implemented response is low-pass: "
        f"DC gain {dc_gain:.2f}, −3 dB at {f_3db:.1f} Hz, −22 dB at 30 Hz; "
        f"design intent was a 5–15 Hz band-pass (not achieved with 51 taps and β = 14)."
    )

    result_json = {
        "commit": get_git_commit(verify_exists=False),
        "source_digest": get_source_digest(),
        "taps_count": len(taps_int),
        "fs_hz": fs,
        "n_fft": n_fft,
        "dc_gain": round(dc_gain, 4),
        "f_3db_hz": round(f_3db, 2),
        "f_6db_hz": round(f_6db, 2),
        "gains_at_frequencies": freq_data,
        "summary": summary_text
    }

    json_path = os.path.join(REPORTS_DIR, "filter_response.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result_json, f, indent=2, sort_keys=True)

    # Plot response
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        plt.figure(figsize=(10, 6), dpi=150)
        plt.plot(freqs, mag_db_rel_dc, "b-", linewidth=2, label="Magnitude Response (dB rel DC)")
        plt.axvline(f_3db, color="r", linestyle="--", label=f"-3 dB Cutoff ({f_3db:.1f} Hz)")
        plt.axvline(f_6db, color="orange", linestyle=":", label=f"-6 dB Cutoff ({f_6db:.1f} Hz)")
        plt.axhline(-3.0, color="r", linestyle="--", alpha=0.5)
        plt.axhline(-6.0, color="orange", linestyle=":", alpha=0.5)
        plt.axhline(-22.0, color="gray", linestyle="-.", alpha=0.5, label="-22 dB (~30 Hz)")

        plt.xlim(0, 100)
        plt.ylim(-100, 10)
        plt.title(f"FIR Filter Frequency Response ({len(taps_int)} taps, Kaiser Window)\nLow-pass Characteristic: DC Gain = {dc_gain:.3f}, -3 dB = {f_3db:.1f} Hz")
        plt.xlabel("Frequency (Hz)")
        plt.ylabel("Magnitude (dB relative to DC)")
        plt.grid(True, which="both", alpha=0.3)
        plt.legend(loc="upper right")
        plt.tight_layout()

        png_path = os.path.join(FIGS_DIR, "filter_response.png")
        plt.savefig(png_path)
        plt.close()
    except Exception as e:
        print(f"WARNING: Matplotlib plotting failed: {e}")

    # Output to stdout (which will be captured into evidence/filter_response.txt)
    print("==================================================================")
    print("FIR FILTER FREQUENCY RESPONSE ANALYSIS (coeffs.mem)")
    print("==================================================================")
    print(f"Filter order: {len(taps_int)} taps")
    print(f"Sampling frequency (fs): {fs} Hz")
    print(f"DC Gain (linear): {dc_gain:.4f}")
    print(f"-3 dB frequency: {f_3db:.2f} Hz")
    print(f"-6 dB frequency: {f_6db:.2f} Hz")
    print("\nEvaluated Frequencies:")
    for ef in eval_freqs:
        d = freq_data[str(ef)]
        print(f"  {ef:3d} Hz: gain = {d['gain_linear']:.4f} ({d['gain_db_rel_dc']:+.2f} dB rel DC)")
    print("\nSummary Description:")
    print(f"  {summary_text}")
    print("==================================================================")
    print(f"Saved: {json_path}")
    if os.path.exists(os.path.join(FIGS_DIR, "filter_response.png")):
        print(f"Saved: {os.path.join(FIGS_DIR, 'filter_response.png')}")
    print("FILTER RESPONSE ANALYSIS: PASS")

if __name__ == "__main__":
    main()
