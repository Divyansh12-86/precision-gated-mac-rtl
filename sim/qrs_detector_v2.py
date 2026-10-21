"""
sim/qrs_detector_v2.py — Synthesizable Hardware Reference QRS Detector (v2)

Conforms strictly to Section 2.2 and Section 4.5 of the Agent Guide.
Hardware characteristics:
- Integer-only, no division (MWI output uses >> 6).
- No calibration pass: starts deterministically from reset values.
- Assertions on all internal register widths.
- Evaluated per-sample with identical timing semantics as RTL.
"""

import numpy as np

# Standard beat symbols per PhysioNet MIT-BIH (Section 9)
BEAT_SYMBOLS = set("NLRBAaJSVrFejnE/fQ?")

class HardwareQRSDetectorV2:
    def __init__(self, sq_shift=11, mwi_len=54, gate_len=43, refract_len=72, decay_after=288,
                 init_spki=1500, init_npki=50, init_threshold=412):
        self.sq_shift = sq_shift
        self.mwi_len = mwi_len
        self.gate_len = gate_len
        self.refract_len = refract_len
        self.decay_after = decay_after
        self.init_spki = init_spki
        self.init_npki = init_npki
        self.init_threshold = init_threshold
        self.reset()

    def reset(self):
        # 16-bit input delay registers
        self.x_d1 = 0
        self.x_d2 = 0

        # MWI circular buffer & accumulator
        self.mwi_buf = np.zeros(self.mwi_len, dtype=np.int64)
        self.ptr = 0
        self.mwi_acc = 0  # max 54 * 2^17 < 2^23 -> fits unsigned 24-bit

        # Counters & timing
        self.refractory_cnt = 0
        self.time_since_peak = 0
        self.gate_cnt = 0

        # Thresholds (unsigned 24-bit)
        self.spki = int(self.init_spki)
        self.npki = int(self.init_npki)
        self.threshold = int(self.init_threshold)

        # MWI peak history registers
        self.prev_mwi = 0
        self.prev_mwi_2 = 0

    def step(self, x_in):
        """
        Process a single signed 16-bit sample.
        Order of operations strictly matches Section 2.2 / 4.5.
        Returns (gate_flag, is_peak, mwi_out).
        """
        x = int(x_in)
        assert -32768 <= x <= 32767, f"Input x out of range: {x}"

        # 1. 1st-order derivative: d = x - x_d2 (signed 17-bit: [-65536, 65535])
        d = x - self.x_d2
        assert -65536 <= d <= 65535, f"Derivative d out of 17-bit range: {d}"
        self.x_d2 = self.x_d1
        self.x_d1 = x

        # 2. Squaring & shift: s = (d * d) >> SQ_SHIFT (saturated to 17-bit unsigned)
        prod = d * d  # max 65536^2 = 2^32
        s_raw = prod >> self.sq_shift
        s = min((1 << 17) - 1, s_raw)
        assert 0 <= s < (1 << 17), f"s out of 17-bit range: {s}"

        # 3. MWI update: mwi_acc += s - mwi_buf[ptr]
        old_s = int(self.mwi_buf[self.ptr])
        self.mwi_buf[self.ptr] = s
        self.ptr = (self.ptr + 1) % self.mwi_len
        self.mwi_acc = self.mwi_acc + s - old_s
        assert 0 <= self.mwi_acc < (1 << 24), f"mwi_acc out of 24-bit range: {self.mwi_acc}"

        # v2 uses >> 6 (synthesizable shift instead of // 54)
        mwi_out = self.mwi_acc >> 6
        assert 0 <= mwi_out < (1 << 18), f"mwi_out out of 18-bit range: {mwi_out}"

        # 4. Refractory & Decay updates
        if self.refractory_cnt > 0:
            self.refractory_cnt -= 1

        self.time_since_peak += 1
        if self.time_since_peak > self.decay_after:
            # threshold = max(npki*2, threshold - (threshold >> 8) - 1)
            decayed = self.threshold - (self.threshold >> 8) - 1
            floor_val = self.npki * 2
            self.threshold = max(floor_val, decayed)

        # 5. Peak confirmation & Threshold Adaptation
        is_peak = 0
        if self.prev_mwi > self.prev_mwi_2 and self.prev_mwi >= mwi_out:
            # local max occurred 1 sample ago
            pk = self.prev_mwi
            if pk > self.threshold and self.refractory_cnt == 0:
                is_peak = 1
                self.refractory_cnt = self.refract_len
                self.time_since_peak = 0
                self.gate_cnt = self.gate_len
                # EMA update
                self.spki = self.spki - (self.spki >> 3) + (pk >> 3)
                self.threshold = self.npki + ((self.spki - self.npki) >> 2)
            elif self.refractory_cnt == 0 and pk < self.threshold:
                self.npki = self.npki - (self.npki >> 4) + (pk >> 4)
                self.threshold = self.npki + ((self.spki - self.npki) >> 2)

        assert 0 <= self.spki < (1 << 24), f"spki overflow: {self.spki}"
        assert 0 <= self.npki < (1 << 24), f"npki overflow: {self.npki}"
        assert 0 <= self.threshold < (1 << 24), f"threshold overflow: {self.threshold}"

        self.prev_mwi_2 = self.prev_mwi
        self.prev_mwi = mwi_out

        # 6. Gate flag evaluation (AFTER peak branch, same sample)
        gate_flag = 1 if (self.gate_cnt > 0) else 0
        if self.gate_cnt > 0:
            self.gate_cnt -= 1

        return gate_flag, is_peak, mwi_out

    def detect_stream(self, x_stream):
        """Process an entire stream of samples."""
        self.reset()
        n = len(x_stream)
        gate_flags = np.zeros(n, dtype=np.int32)
        peaks = np.zeros(n, dtype=np.int32)
        mwi_signals = np.zeros(n, dtype=np.int32)

        for i in range(n):
            gf, pk, mwi = self.step(x_stream[i])
            gate_flags[i] = gf
            peaks[i] = pk
            mwi_signals[i] = mwi

        return gate_flags, peaks, mwi_signals


def evaluate_detector_beats_only(detected_peak_indices, ann_sample, ann_symbol, tolerance=50):
    """
    Evaluate detector matching ONLY true beat symbols (Section 9).
    Matches detected peak index (convention i-1) within +/- tolerance.
    """
    # Filter only beat annotations
    true_beats = [sample for sample, sym in zip(ann_sample, ann_symbol) if sym in BEAT_SYMBOLS]

    matched_beats = set()
    tp = 0
    fp = 0

    for dp in detected_peak_indices:
        match = False
        for tb in true_beats:
            if abs(dp - tb) <= tolerance:
                if tb not in matched_beats:
                    matched_beats.add(tb)
                match = True
                break
        if match:
            tp += 1
        else:
            fp += 1

    fn = len(true_beats) - len(matched_beats)
    se = (tp / (tp + fn) * 100.0) if (tp + fn) > 0 else 0.0
    pp = (tp / (tp + fp) * 100.0) if (tp + fp) > 0 else 0.0

    return {
        "tp": tp, "fp": fp, "fn": fn,
        "total_true_beats": len(true_beats),
        "total_detected": len(detected_peak_indices),
        "sensitivity": se,
        "positive_predictivity": pp
    }
