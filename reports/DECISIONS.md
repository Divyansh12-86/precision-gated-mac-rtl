# Design Decisions & Deviations Log — Precision-Gated MAC ECG

All architectural decisions, parameter choices, and deviations from early specifications are logged here.

---

## 1. Input Policy Definition
- **LEGACY_MINMAX:** Input scaled by per-slice min/max to [-1, 1], then converted to Q1.15. Maintained for continuity with previous results.
- **FIXED_SCALE (Primary Hardware Policy):** Uses raw 11-bit ADC values from MIT-BIH (`200 ADU/mV`, zero at 1024): `x16 = (adu - 1024) << 5`. This is causal, non-saturating, and represents real hardware ADC input.
- **FIXED_SCALE_G7:** `(adu - 1024) << 7` with saturation to test sensitivity to higher analog front-end gain.

## 2. QRS Detector v2 Synthesizable Refinements
- **Division Elimination:** Moving Window Integrator output calculation replaced from `mwi_acc // 54` to `mwi_acc >> 6` (pure 6-bit right shift, synthesizable in RTL with zero logic overhead).
- **Static Reset Values:** Eliminated `calibrate()` percentile calculation; initial state uses parameters `INIT_SPKI=1500`, `INIT_NPKI=50`, `INIT_THR=412`.
- **Parameterised `SQ_SHIFT`:** 15 for `LEGACY_MINMAX`, 11 for `FIXED_SCALE` (gain factor 5), 13 for `FIXED_SCALE_G7`.
- **17-bit Saturation on Squared Derivative:** $(d \cdot d) \gg \text{SQ\_SHIFT}$ is saturated to unsigned 17-bit (`17'h1FFFF = 131071`). In real ECG signals with `SQ_SHIFT=11`, $s$ is normally $< 50000$. Under extreme synthetic corner inputs (full scale rail-to-rail step), this saturation guarantees $s$ fits in 17 bits and prevents 24-bit overflow of `mwi_acc`.

## 3. Simulator & Tooling Selection
- `verilator` 5.020 with SystemVerilog testbench support (`--binary --timing`) is selected as the primary simulation environment because `iverilog` is not pre-installed in the user environment.
- `yosys` 0.33 with `synth_xilinx -family xc7` selected as the primary synthesis engine.

## 4. Arithmetic Datapath & Multiplier Split
- Single time-multiplexed MAC computing 51 taps per 360 Hz sample period.
- `mult_split`: Operand input $x$ split into high byte $x_h[7:0]$ (signed) and low byte $x_l[7:0]$ (unsigned):
  $$x \cdot h = ((x_h \cdot h) \ll 8) + (x_l \cdot h)$$
  In approximate mode, $x_l$ is clamped to 0 and the low multiplier register is clock-gated / inactive.
  Output bit-exact match with Python: $((x \gg 8) \ll 8) \cdot h$.
- 32-bit signed accumulator guaranteed no-overflow ($|acc| \le 32768 \times 40569 \approx 2^{30.31} < 2^{31}$).

## 5. Autonomous Integration & Pipeline Timing
- **Integration Flow:** Upon `sample_valid`, `qrs_detector` computes synchronously in 1 cycle, asserting `valid_out` and `gate_out`. At cycle 1, `pg_fir` is triggered with latched sample and detector gate, completing all 51 taps in 54 cycles.
- **Constant Latency:** Total pipeline latency is invariant at exactly 56 clock cycles from `sample_valid` to `y_valid`.
- **Top-Level `busy` Handshake:** `busy = fir_busy || det_pending || fir_sample_valid` guarantees glitch-free handoff without inter-sample races.

## 6. Multi-Target FPGA Synthesis
- Pure Verilog-2001 / SystemVerilog core contains 0 vendor-specific blackboxes or hard IP macros.
- In LUT mode (`synth_xilinx -nodsp -noiopad`), Yosys synthesizes all multipliers into LUT logic (0 DSP48 blocks inferred), strictly satisfying Criterion G7.
- Portability verified across Artix-7 (`xc7`), UltraScale (`xcu`), and Spartan-6 (`xc6s`).
