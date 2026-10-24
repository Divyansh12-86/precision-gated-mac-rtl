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
