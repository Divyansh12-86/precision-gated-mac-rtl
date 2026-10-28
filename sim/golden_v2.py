"""
sim/golden_v2.py — Bit-Exact Golden Reference Model v2

Implements canonical numerical contract (Section 4):
- Policies: FIXED_SCALE (primary), LEGACY_MINMAX, FIXED_SCALE_G7.
- Filter: 51-tap Kaiser-window FIR; implemented response is low-pass: DC gain 1.03, −3 dB at 16.6 Hz, −22 dB at 30 Hz; design intent was a 5–15 Hz band-pass (not achieved with 51 taps and β = 14). Q1.15 taps.
- Vectorized bit-exact convolution for 32-bit accumulators.
- Beat-only QRS quality evaluation per Section 9.
"""

import os
import numpy as np
import scipy.signal as signal
import wfdb
from qrs_detector_v2 import HardwareQRSDetectorV2, BEAT_SYMBOLS

FS = 360
FIR_ORDER = 50
N_TAPS = FIR_ORDER + 1
HP_CUTOFF = 5
LP_CUTOFF = 15
KAISER_BETA = 14
Q_FRAC = 15

def to_fixed(x, frac_bits=Q_FRAC):
    """Convert float in [-1.0, 1.0] to signed 16-bit Q1.15."""
    return np.clip(np.round(x * (2**frac_bits)), -32768, 32767).astype(np.int32)

def design_fir_filter():
    """Design Kaiser FIR filter (design intent was 5-15 Hz band-pass, not achieved with 51 taps; implemented response is low-pass) and quantize taps to signed 16-bit Q1.15."""
    nyq = 0.5 * FS
    low = HP_CUTOFF / nyq
    high = LP_CUTOFF / nyq
    taps = signal.firwin(N_TAPS, [low, high], pass_zero=False, window=('kaiser', KAISER_BETA))
    quantized_taps = to_fixed(taps)
    # Check tap symmetry and bound
    assert np.array_equal(quantized_taps, quantized_taps[::-1]), "FIR taps must be symmetric"
    sum_abs = np.sum(np.abs(quantized_taps.astype(np.int64)))
    max_acc = 32768 * sum_abs
    assert max_acc < (1 << 31), f"Accumulator overflow possible: max {max_acc}"
    return quantized_taps

def truncate_operand_8b(x):
    """
    Hardware truncation semantic: arithmetic floor of low 8 bits.
    In two's complement: (x >> 8) << 8.
    """
    x_int = x.astype(np.int64)
    return (x_int >> 8) << 8

def load_record_data(record_id, policy="fixed", max_samples=None, data_dir="data/mitbih"):
    """
    Load MIT-BIH record under chosen input policy (Section 4.1).
    Returns (x16, ann_sample, ann_symbol, sq_shift, record_meta).
    """
    path = os.path.join(data_dir, record_id)
    rec = wfdb.rdrecord(path, physical=False)
    ann = wfdb.rdann(path, 'atr')

    # Channel 0 (MLII lead)
    adu = rec.d_signal[:, 0].astype(np.int64)
    adc_zero = rec.adc_zero[0] if rec.adc_zero is not None else 1024

    if max_samples is not None:
        adu = adu[:max_samples]
        valid_mask = ann.sample < max_samples
        ann_sample = ann.sample[valid_mask]
        ann_symbol = [ann.symbol[i] for i, v in enumerate(valid_mask) if v]
    else:
        ann_sample = ann.sample
        ann_symbol = ann.symbol

    if policy == "fixed":
        # PRIMARY: 11-bit ADC, zero=1024, gain GS=5 -> range exactly [-32768, 32767]
        x16 = ((adu - adc_zero) << 5).astype(np.int32)
        sq_shift = 11
    elif policy == "minmax":
        # LEGACY: Min-max normalization over slice to [-1, 1], then Q1.15
        p_rec = wfdb.rdrecord(path, physical=True)
        raw = p_rec.p_signal[:len(adu), 0]
        s_min, s_max = np.min(raw), np.max(raw)
        norm = (raw - s_min) / (s_max - s_min) * 2.0 - 1.0
        x16 = to_fixed(norm)
        sq_shift = 15
    elif policy == "fixed_g7":
        # SENSITIVITY: Gain GS=7 with clipping to int16
        x_raw = (adu - adc_zero) << 7
        x16 = np.clip(x_raw, -32768, 32767).astype(np.int32)
        sq_shift = 13
    else:
        raise ValueError(f"Unknown policy: {policy}")

    assert np.min(x16) >= -32768 and np.max(x16) <= 32767, "Input x16 exceeds signed 16-bit!"
    return x16, ann_sample, ann_symbol, sq_shift, rec

def run_fir_filter_vectorized(x16, taps, gate_flags):
    """
    Vectorized bit-exact FIR filter.
    Returns:
      y_full: 32-bit signed accumulator array (exact mode)
      y_gated: 32-bit signed accumulator array (precision-gated mode)
      y_allapprox: 32-bit signed accumulator array (approx mode 100% of time)
    """
    n = len(x16)
    x64 = x16.astype(np.int64)
    taps64 = taps.astype(np.int64)

    # Full precision accumulator
    y_full = np.convolve(x64, taps64, mode='full')[:n]

    # Truncated operand accumulator
    x_trunc = truncate_operand_8b(x16)
    y_allapprox = np.convolve(x_trunc, taps64, mode='full')[:n]

    # Precision-gated: sample i uses full if gate_flags[i]==1 else approx
    gate_bool = gate_flags.astype(bool)
    y_gated = np.where(gate_bool, y_full, y_allapprox)

    # Accumulator bounds assertion
    assert np.max(np.abs(y_full)) < (1 << 31), "y_full exceeded 32-bit signed range!"
    assert np.max(np.abs(y_gated)) < (1 << 31), "y_gated exceeded 32-bit signed range!"

    return y_full, y_gated, y_allapprox

def run_fir_filter_loop(x16, taps, gate_flags):
    """
    Cycle-by-cycle shift-register loop implementation.
    Used to self-check vectorized model.
    """
    n = len(x16)
    y_full = np.zeros(n, dtype=np.int64)
    y_gated = np.zeros(n, dtype=np.int64)
    y_allapprox = np.zeros(n, dtype=np.int64)

    buf = np.zeros(len(taps), dtype=np.int64)
    taps64 = taps.astype(np.int64)

    for i in range(n):
        buf[1:] = buf[:-1]
        buf[0] = x16[i]

        acc_f = np.sum(buf * taps64)
        y_full[i] = acc_f

        buf_trunc = (buf >> 8) << 8
        acc_a = np.sum(buf_trunc * taps64)
        y_allapprox[i] = acc_a

        if gate_flags[i]:
            y_gated[i] = acc_f
        else:
            y_gated[i] = acc_a

    return y_full, y_gated, y_allapprox

def evaluate_quality(y_full, y_gated, y_allapprox, gate_flags, ann_sample, ann_symbol):
    """
    Compute rigorous metrics per Section 9:
    - Global PRD & SNR (comparing >>15 output)
    - QRS-region PRD (gated vs all-approx)
    - Non-QRS region PRD
    - Gate coverage
    - R-peak amplitude error
    """
    n = len(y_full)
    # Output signals as Q1.15 float
    yf_f = (y_full >> 15).astype(np.float64)
    yg_f = (y_gated >> 15).astype(np.float64)
    ya_f = (y_allapprox >> 15).astype(np.float64)

    # Global approximation error metrics
    e_gated = yf_f - yg_f
    e_approx = yf_f - ya_f

    sig_pow = np.sum(yf_f**2)
    err_pow_g = np.sum(e_gated**2)
    err_pow_a = np.sum(e_approx**2)

    prd_global_g = (np.sqrt(err_pow_g / sig_pow) * 100.0) if sig_pow > 0 else 0.0
    prd_global_a = (np.sqrt(err_pow_a / sig_pow) * 100.0) if sig_pow > 0 else 0.0

    snr_global_g = (10.0 * np.log10(sig_pow / err_pow_g)) if err_pow_g > 0 else float('inf')
    snr_global_a = (10.0 * np.log10(sig_pow / err_pow_a)) if err_pow_a > 0 else float('inf')

    # Duty cycle
    duty_full_pct = float(np.mean(gate_flags) * 100.0)
    duty_approx_pct = 100.0 - duty_full_pct

    # QRS-region mask (filtered QRS is centered at R + 25; window R+15 .. R+36)
    qrs_mask = np.zeros(n, dtype=bool)
    true_beats = [s for s, sym in zip(ann_sample, ann_symbol) if sym in BEAT_SYMBOLS and s + 36 < n]

    fully_covered_beats = 0
    rpeak_errors = []

    for r in true_beats:
        r_start = r + 15
        r_end = min(n, r + 37)
        qrs_mask[r_start:r_end] = True

        # Check gate coverage (R+15 .. R+35)
        cov_end = min(n, r + 36)
        if np.all(gate_flags[r_start:cov_end] == 1):
            fully_covered_beats += 1

        # Peak error at maximum |yf| within window
        win_f = np.abs(yf_f[r_start:r_end])
        if len(win_f) > 0:
            max_idx = r_start + int(np.argmax(win_f))
            peak_val = abs(yf_f[max_idx])
            if peak_val > 0.01:
                err_val = abs(yf_f[max_idx] - yg_f[max_idx])
                rpeak_errors.append((err_val / peak_val) * 100.0)

    # QRS-region PRD
    qrs_sig_pow = np.sum(yf_f[qrs_mask]**2) if np.any(qrs_mask) else 0.0
    qrs_err_pow_g = np.sum(e_gated[qrs_mask]**2) if np.any(qrs_mask) else 0.0
    qrs_err_pow_a = np.sum(e_approx[qrs_mask]**2) if np.any(qrs_mask) else 0.0

    prd_qrs_gated = (np.sqrt(qrs_err_pow_g / qrs_sig_pow) * 100.0) if qrs_sig_pow > 0 else 0.0
    prd_qrs_approx = (np.sqrt(qrs_err_pow_a / qrs_sig_pow) * 100.0) if qrs_sig_pow > 0 else 0.0

    # Non-QRS region PRD
    non_qrs_mask = ~qrs_mask
    nq_sig_pow = np.sum(yf_f[non_qrs_mask]**2) if np.any(non_qrs_mask) else 0.0
    nq_err_pow_g = np.sum(e_gated[non_qrs_mask]**2) if np.any(non_qrs_mask) else 0.0
    prd_non_qrs_gated = (np.sqrt(nq_err_pow_g / nq_sig_pow) * 100.0) if nq_sig_pow > 0 else 0.0

    gate_coverage_pct = (fully_covered_beats / len(true_beats) * 100.0) if len(true_beats) > 0 else 0.0
    rpeak_err_max = float(np.max(rpeak_errors)) if rpeak_errors else 0.0
    rpeak_err_mean = float(np.mean(rpeak_errors)) if rpeak_errors else 0.0

    return {
        "duty_full_pct": duty_full_pct,
        "duty_approx_pct": duty_approx_pct,
        "global": {
            "prd_gated_pct": prd_global_g,
            "prd_allapprox_pct": prd_global_a,
            "snr_gated_db": snr_global_g,
            "snr_allapprox_db": snr_global_a
        },
        "qrs_region": {
            "prd_gated_pct": prd_qrs_gated,
            "prd_allapprox_pct": prd_qrs_approx,
            "gate_coverage_pct": gate_coverage_pct,
            "rpeak_err_pct_max": rpeak_err_max,
            "rpeak_err_pct_mean": rpeak_err_mean
        },
        "non_qrs_region": {
            "prd_gated_pct": prd_non_qrs_gated
        }
    }
