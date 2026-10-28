# Design Decisions & Deviations Log — Precision-Gated MAC ECG

All architectural decisions, parameter choices, and optimizations are logged here.

---

## 1. Input Policy Definition
- **LEGACY_MINMAX:** Input scaled by per-slice min/max to [-1, 1], then converted to Q1.15. Maintained for continuity with previous results.
- **FIXED_SCALE (Primary Hardware Policy):** Uses raw 11-bit ADC values from MIT-BIH (`200 ADU/mV`, zero at 1024): `x16 = (adu - 1024) << 5`. This is causal, non-saturating, and represents real hardware ADC input.
- **FIXED_SCALE_G7:** `(adu - 1024) << 7` with saturation to test sensitivity to higher analog front-end gain.

---

## 2. QRS Detector v2 Refinements
- **Division Elimination:** Moving Window Integrator output calculation replaced from `mwi_acc // 54` to `mwi_acc >> 6` (pure 6-bit right shift, synthesizable with zero logic overhead).
- **Static Reset Values:** Eliminated `calibrate()` percentile calculation; initial state uses parameters `INIT_SPKI=1500`, `INIT_NPKI=50`, `INIT_THR=412`.
- **Parameterised `SQ_SHIFT`:** 15 for `LEGACY_MINMAX`, 11 for `FIXED_SCALE` (gain factor 5), 13 for `FIXED_SCALE_G7`.
- **17-bit Saturation on Squared Derivative:** $(d \cdot d) \gg \text{SQ\_SHIFT}$ is saturated to unsigned 17-bit (`17'h1FFFF = 131071`), guaranteeing $s$ fits in 17 bits and preventing 24-bit overflow of `mwi_acc`.
- **17-Cycle Serial Squarer (`SERIAL_SQ = 1`):** Shift-add squarer computes $d^2 \gg \text{SQ\_SHIFT}$ over 17 clock cycles, eliminating the wide combinational multiplier and saving over 1,000 LUTs in LUT mode.

---

## 3. Distributed RAM Circular Buffers (Phase C Area Optimization)
- **Sample Delay Line:** Refactored from a 51-register shift array (816 FFs) to a 64x16 Distributed RAM circular buffer (`RAM64M`), dropping flip-flop count to only 12 FFs.
- **MWI Integration Buffer:** Refactored from a 54-register shift array (1,279 FFs) to a 64x17 Distributed RAM circular buffer (`RAM64M`), dropping flip-flop count to only 254 FFs.

---

## 4. Arithmetic Datapath & Multiplier Split
- Single time-multiplexed MAC computing 51 taps per 360 Hz sample period.
- `mult_split`: Operand input $x$ split into high byte $x_h[7:0]$ (signed) and low byte $x_l[7:0]$ (unsigned):
  $$x \cdot h = ((x_h \cdot h) \ll 8) + (x_l \cdot h)$$
  In approximate mode, $x_l$ is clamped to 0 and the low multiplier register is clock-enable gated (`p_low_r1` holds previous product).
  Output bit-exact match with Python: $((x \gg 8) \ll 8) \cdot h$.
- 32-bit signed accumulator guaranteed no-overflow ($|acc| \le 32768 \times 40569 \approx 2^{30.31} < 2^{31}$).

---

## 5. Autonomous Integration & Invariant Pipeline Timing
- **Sample Latency:** System latency is invariant at exactly **73 clock cycles** ($17\text{ (detector serial square)} + 54\text{ (FIR taps + drain)} + 2\text{ (synchronization)}$) from `sample_valid` to `y_valid`.
- **ROM Pipeline Alignment:** ROM read in `board_core.v` is synchronous (`always @(posedge clk) rom_sample <= rom[rom_addr];`), updating every clock cycle so `rom_sample` holds `rom[rom_addr]` well before `sample_tick` asserts.

---

## 7. Git Tag Semantics & Provenance (Round 2)
- **Tag `finalize-r1-complete`:** Originally named `pre-finalize` during Round-1 development. Because the working tree history was amended and re-sequenced during Round-1 closure to maintain an exact parent-code to report-commit relationship, the original tag was renamed to `finalize-r1-complete` (`9ada39e`) to honestly reflect that it represents the post-refactor baseline rather than a pre-refactor state.
- **Tag `round2-start`:** Created as an annotated tag at commit `90af974` marking the exact starting point of the Round-2 engineering campaign ("Make It Provable, Honest and Hardware-Safe"). All Round-2 commits descend from this baseline.

---

## 8. Live ECG Viewer Integration (Round 6)
- **Component:** `scripts/ecg_live_viewer.py` integrated as supplied by reviewer.
- **SHA256 Checksum:** `38689b90bf02017317d9313c8b8d854bceac112150b2886ebf59f50c2868ea94`
- **Capabilities:**
  - 3-panel display: Unfiltered ROM input, precision-gated filtered output, difference/error trace.
  - Header displays live active percentage ("SYSTEM ACTIVE: xx.x%") with dual status indicators (RED = QRS Full, GREEN = Approx).
  - Side panel shows bit-exact hardware status, stream statistics, and low-operand toggle reduction model.
  - Verified bit-exact match against real RTL byte stream `reports/board_uart_dump.bin`: 4,949 frames decoded with 0 mismatches.
  - Headless snapshot generation (`--snapshot`) producing publication-grade PNG figures (> 40 kB, 1496x902 px).
- **Selftest:** Verified via `scripts/ecg_live_viewer.py --selftest` (12/12 passing).

---

## 9. Demo Dataset Synthesis (`demo_noisy_100`)
- **Dataset:** `data/test_vectors/demo_noisy_100` and `ecg_rom_demo_noisy.mem` (60,000 samples).
- **Policy:** MIT-BIH Record 100 under `FIXED_SCALE` policy (`x16 = (adu - 1024) << 5`).
- **Noise Model & SNR Definition:**
  - Target SNR: 12 dB relative to clean ECG signal power centered around 1024 ADU.
  - Noise is synthesized in the integer ADU domain *before* `<< 5` scaling to preserve the hardware ADC structure:
    $$p_{sig} = \text{mean}((adu - 1024)^2)$$
    $$p_{target} = p_{sig} / 10^{12/10}$$
    $$noise_{raw} = 0.4 \cdot \sin(2\pi \cdot 0.3 \cdot t) + 0.3 \cdot \sin(2\pi \cdot 50 \cdot t) + 0.3 \cdot \mathcal{N}(0, 1)$$
    $$scale = \sqrt{p_{target} / (\text{mean}(noise_{raw}^2) + \epsilon)}$$
    $$adu_{noisy} = \text{clip}(\text{round}(adu + noise_{raw} \cdot scale), 0, 2047)$$
    $$x16_{noisy} = \text{clip}((adu_{noisy} - 1024) \ll 5, -32768, 32767)$$
  - Seed: $42 + 12 = 54$ (identical formula and seed convention as `sim/noise_sweep.py`).
  - Guarantees $(x16_{noisy} \& 31) == 0$ for 100% of samples (60,000/60,000).
- **Quality Performance:**
  - Sensitivity (Se): 100.00% (target $\ge 99\%$)
  - Positive Predictivity (+P): 98.58% (target $\ge 90\%$)
  - Full-Precision Gate Duty: 15.12%
  - Datapath switching reduction: 19.95%
  - Whole-core switching reduction: 11.67%

---

## 10. FIR Filter Response & OPEN DECISION FOR THE USER
- **Filter Analysis (`scripts/filter_response.py`):**
  - Order: 51 taps (Kaiser window $\beta = 14$, $f_s = 360$ Hz).
  - Implemented response: Low-pass smoothing filter with DC gain 1.029, -3 dB at 16.57 Hz, -6 dB at 20.04 Hz, -22.56 dB at 30 Hz, < -80 dB above 40 Hz.
  - Retains baseline wander (0.3 Hz) and DC offset; removes muscle tremor / EMG (> 20 Hz) and 50/60 Hz powerline hum.
  - Design intent was a 5–15 Hz band-pass filter; this was not achieved with 51 taps and $\beta = 14$ because the transition band is wider than the 5 Hz low cutoff.
- **OPEN DECISION FOR THE USER:**
  - **Option A (Document as Low-Pass — DEFAULT / RECOMMENDED):** Keep `coeffs.mem` and RTL completely unchanged. Honestly document the filter as a low-pass smoothing / noise-suppression filter for ECG pre-processing. Zero risk to existing bit-exact verification, FPGA bitstreams, or patent claims.
  - **Option B (Redesign as True Band-Pass):** Redesign filter coefficients to achieve true band-pass rejection (e.g. 0.5–40 Hz or 5–15 Hz). Achieving a sharp 5 Hz low-cutoff transition at $f_s = 360$ Hz requires $\ge 255$ taps.
    - *Hardware Cost Estimate for Option B:*
      - Delay line RAM grows from 64x16 to 256x16 or 512x16 (+12 to +36 FFs or BRAM).
      - Pipeline latency increases from 73 cycles to $\ge 277$ cycles per sample tick.
      - Yosys logic increase: approximately $+150$ to $+300$ LUTs for wider counter/ROM addressing logic.
      - Full regression vectors, golden models, and ROMs must be regenerated.
