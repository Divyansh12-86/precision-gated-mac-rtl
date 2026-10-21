# Project Progress Log — Precision-Gated MAC ECG

All commands, runs, and milestone completions are logged chronologically here.

---

## Phase 0: Baseline and Hygiene [COMPLETED]

- **Date:** 2026-10-21
- **Command:** `.venv/bin/python3 sim/golden_model.py --quick`
- **Result:**
  - Rec 100: Se = 98.85%, +P = 100.00%, Approx Duty = 85.21%, SNR = 44.57 dB, PRD = 0.59%, MeanPkErr = 0.018%, MultSav = 42.60%, CompSav = 42.49%
  - Rec 101: Se = 100.00%, +P =  96.47%, Approx Duty = 85.38%, SNR = 45.13 dB, PRD = 0.55%, MeanPkErr = 0.057%, MultSav = 42.69%, CompSav = 42.58%
  - Rec 103: Se = 100.00%, +P = 100.00%, Approx Duty = 85.90%, SNR = 44.94 dB, PRD = 0.57%, MeanPkErr = 0.056%, MultSav = 42.95%, CompSav = 42.84%
  - Rec 105: Se =  98.97%, +P =  98.97%, Approx Duty = 83.32%, SNR = 44.62 dB, PRD = 0.59%, MeanPkErr = 0.191%, MultSav = 41.66%, CompSav = 41.54%
- **Toolchain Status:**
  - Simulator: `verilator` 5.020 (`--binary --timing`) verified and operational. (Note: `iverilog` unavailable without root package manager access; Verilator used as primary RTL simulator).
  - Synthesis: `yosys` 0.33 verified for Xilinx 7-series (`synth_xilinx -family xc7`).
  - Python: 3.12.3 with `wfdb`, `numpy`, `scipy`, `matplotlib`.
- **Hygiene:**
  - Created `requirements.txt`.
  - Updated `.gitignore` with simulation artifacts (`*.vvp`, `*.vcd`, `obj_dir/`, `build/`) and external datasets (`data/nstdb/`, `data/mitbih_full/`).
  - Corrected `data/README.md` to reference `tv_outputs_gated.hex`.
  - Created `reports/PROGRESS.md`, `reports/DECISIONS.md`, and base `Makefile`.

---

## Phase 1: Golden Model v2 and Vector Factory [COMPLETED]

- **Date:** 2026-10-21
- **Deliverables:**
  - `sim/qrs_detector_v2.py`: Hardware-faithful Pan-Tompkins detector without float division (`>> 6` instead of `// 54`), without calibration pass, with 17-bit saturation on squared derivative.
  - `sim/golden_v2.py`: Bit-exact reference model supporting `FIXED_SCALE` (primary), `LEGACY_MINMAX`, and `FIXED_SCALE_G7`, fast vectorized FIR with identical results to cycle loop model.
  - `sim/gen_vectors.py`: Vector generator supporting `smoke`, `corner`, `std_<policy>_<rec>`, exporting inputs, gate flags, full outputs, gated outputs, all-approx outputs, peaks, mwi, `coeffs.mem`, and `manifest.json`.
- **Verifications:**
  - Vectorized vs loop self-check: bit-exact across all 3000 test samples.
  - Detector Se / +P (beat-only):
    - `fixed` policy (60k samples): Rec 100: 100%/100%; Rec 101: 100%/94.7%; Rec 103: 100%/100%; Rec 105: 100%/100%.
    - `minmax` policy (60k samples): Rec 100: 100%/100%; Rec 101: 100%/94.7%; Rec 103: 100%/99.5%; Rec 105: 100%/99.6%.
  - QRS-region PRD (minmax, 60k samples): Gated 0.012% (100), 0.092% (101), 0.000% (103), 0.449% (105) vs All-Approx 0.924%, 1.292%, 0.915%, 1.464% (Finding F5 confirmed).
  - Corner set impulse response matches taps * 0x7FFF at 0..50 and 0 afterwards.
  - Vector determinism verified via SHA-256 match.

---

## Phase 2: Exact FIR Core RTL [COMPLETED]

- **Date:** 2026-10-21
- **Deliverables:**
  - `rtl/sample_delay_line.v`: 51-tap synchronous shift register with tap multiplexer.
  - `rtl/fir_coeff_rom.v`: 51-tap ROM loaded via `$readmemh`.
  - `rtl/mult_split.v`: 16-bit split multiplier ($x_h$ signed, $x_l$ unsigned) supporting `PIPE ∈ {1, 2, 3}`.
  - `rtl/pg_mac.v`: 32-bit signed accumulator with single-cycle clear.
  - `rtl/pg_fir.v`: Time-multiplexed 51-tap FIR compute FSM.
  - `tb/tb_mult.v`: Multiplier unit testbench.
  - `tb/tb_fir_full.v`: Full-precision FIR testbench.
- **Verifications:**
  - `tb_mult`: 705,360 checks passed across `PIPE=1,2,3` (`TB_RESULT: PASS name=tb_mult samples=705360 mismatches=0`).
  - `tb_fir_full`: Passed bit-exact on `smoke` (1k), `corner` (1618), and `std_fixed_100` (60k) with zero mismatches (`TB_RESULT: PASS name=tb_fir_full samples=60000 mismatches=0`).
  - Constant latency: exactly 54 cycles ($51 + \text{PIPE} + 1$ with $\text{PIPE}=2$).
  - Invariance across `PIPE ∈ {1, 2, 3}` verified.

---

## Phase 3: Gated MAC with Gate Supplied from File [COMPLETED]

- **Date:** 2026-10-21
- **Deliverables:**
  - `tb/tb_fir_gated.v`: Precision-gated FIR testbench supporting dynamic file-supplied gating, forced full (`01`), and forced approx (`10`).
- **Verifications:**
  - `smoke` (1k samples): Passed all 3 passes (dynamic, forced full, forced approx) with zero mismatches (`TB_RESULT: PASS name=tb_fir_gated samples=1000 mismatches=0`).
  - `corner` (1618 samples): Glitch-free cycle-by-cycle mode switching under random gates and rail-to-rail signals; 0 mismatches across all 3 passes (`TB_RESULT: PASS name=tb_fir_gated samples=1618 mismatches=0`).
  - `std_fixed_100` (60k samples):
    - Dynamic mode: 0 mismatches (`TB_RESULT: PASS name=tb_fir_gated samples=60000 mismatches=0`).
    - Forced full mode: 0 mismatches vs `tv_outputs_full.hex`.
    - Forced approx mode: 0 mismatches vs `tv_outputs_allapprox.hex`.
  - Operand isolation assertion: `xl_eff == 0` during all approximate compute cycles verified (>2.7 million approx cycles checked, 0 isolation errors).

---

## Phase 4: QRS Detector RTL [COMPLETED]

- **Date:** 2026-10-21
- **Deliverables:**
  - `rtl/qrs_detector.v`: Hardware-accurate integer Pan-Tompkins detector conforming to `HardwareQRSDetectorV2`.
    - Pure integer arithmetic, division-free (MWI `>> 6`).
    - 17-bit saturation on squared derivative.
    - Zero external calibration, deterministic reset start-up.
    - 1-cycle registered latency: outputs `gate_out`, `peak_pulse`, `mwi_dbg` with `valid_out`.
  - `tb/tb_detector.v`: Unit testbench parameterized by `SQ_SHIFT`.
- **Verifications:**
  - Tested across 480,000 samples across 8 regression suites:
    - `std_fixed_100` (60k): 0 gate mismatches, 0 peak mismatches, 0 MWI mismatches. First peak at sample 88 (0.24 s).
    - `std_fixed_101` (60k): 0 gate mismatches, 0 peak mismatches, 0 MWI mismatches. First peak at sample 92 (0.26 s).
    - `std_fixed_103` (60k): 0 gate mismatches, 0 peak mismatches, 0 MWI mismatches. First peak at sample 266 (0.74 s).
    - `std_fixed_105` (60k): 0 gate mismatches, 0 peak mismatches, 0 MWI mismatches. First peak at sample 217 (0.60 s).
    - `std_minmax_100` (60k): 0 gate mismatches, 0 peak mismatches, 0 MWI mismatches. First peak at sample 78 (0.22 s).
    - `std_minmax_101` (60k): 0 gate mismatches, 0 peak mismatches, 0 MWI mismatches. First peak at sample 92 (0.26 s).
    - `std_minmax_103` (60k): 0 gate mismatches, 0 peak mismatches, 0 MWI mismatches. First peak at sample 2 (0.01 s).
    - `std_minmax_105` (60k): 0 gate mismatches, 0 peak mismatches, 0 MWI mismatches. First peak at sample 2 (0.01 s).
  - All suites reported `TB_RESULT: PASS name=tb_detector samples=60000 mismatches=0`.


---

## Phase 5: System Integration (`pg_top`) and System Regression [COMPLETED]

- **Date:** 2026-10-21
- **Deliverables:**
  - `rtl/pg_top.v`: Integrated top-level combining autonomous QRS detector and 51-tap precision-gated FIR core.
  - `rtl/sample_tick_gen.v`: Fractional rate generator producing periodic 360 Hz sample ticks from 100 MHz system clock.
  - `rtl/baseline_fir_exact.v`: Non-gated conventional FIR reference for benchmarking.
  - `tb/tb_top.v`: End-to-end testbench testing input stream without external gate file.
  - `tb/tb_top_realrate.v`: Real-rate testbench running 1,000 samples @ 360 Hz (277,778 clock cycles between samples).
  - `tb/tb_top_reset.v`: Mid-stream reset robustness testbench.
- **Verifications:**
  - `tb_top` ran across all 8 standard suites (480,000 samples total): 0 output mismatches, 0 gate mismatches.
  - Invariant pipeline latency: exactly 56 clock cycles across all samples.
  - Randomized inter-sample spacing (10..160 clock cycles) verified: 0 errors.
  - `tb_top_realrate`: 1,000 samples (277.8 million clock cycles) completed with 0 overflow collisions and 0 output mismatches.
  - `tb_top_reset`: Mid-stream reset pulse completely cleared accumulator, delay line, and detector; all 700 post-reset samples matched golden model restarted from reset with 0 mismatches.

---

## Phase 6: Quality and Activity Characterization [COMPLETED]

- **Date:** 2026-10-21
- **Deliverables:**
  - `sim/analyze.py`: Computes beat-only Se/+P, global SNR/PRD, QRS-region PRD, gate coverage, peak error.
  - `tb/tb_activity.v` & `sim/activity_report.py`: Directly measures bit flips (switching activity) per clock cycle on simulated RTL.
  - `reports/results.json`: Full machine-readable results matching Section 9 schema.
  - `reports/figs/waveform_overlay.png`: High-resolution waveform comparison plot.
- **Verifications:**
  - Se = 100.00% across all records; +P ≥ 94.7% (Record 101: 94.7%, others 99.5–100%).
  - Gated QRS PRD is 0.0000% to 0.4484% (≤ 0.6% requirement met, up to 100× lower error than all-approximate mode).
  - RTL Switching Activity Reduction:
    - Low-part operand bus (`xl[7:0]`): **82.07% reduction** (exceeds ≥ 70% requirement).
    - Multiplier internal datapath: **16.29% reduction**.
    - Accumulator datapath: **15.71% reduction**.
    - Total filter datapath: **21.02% reduction**.

---

## Phase 7: Synthesis and Implementation [COMPLETED]

- **Date:** 2026-10-21
- **Deliverables:**
  - `scripts/synth_yosys.ys`: Multi-target multi-mode Yosys synthesis script.
  - `reports/synth_yosys.rpt`: Comprehensive synthesis report.
- **Verifications:**
  - Core contains 0 vendor-specific primitives or hard IP macros.
  - Artix-7 (`xc7a35t`) LUT mode (`-nodsp`): 2,212 LCs, 2,222 FFs, **strictly 0 DSP48 blocks** (G7 verified).
  - Artix-7 (`xc7a35t`) DSP mode: 1,234 LCs, 2,222 FFs, 3 DSP48E1 slices.
  - UltraScale (`xcu`) DSP mode: 1,609 LCs, 2,222 FFs, 3 DSP48E2 slices.
  - Spartan-6 (`xc6s`) DSP mode: 1,234 LCs, 2,222 FFs, 3 DSP48A1 slices.

---

## Phase 8 & 9: Automation, Regression & Final Reporting [COMPLETED]

- **Date:** 2026-10-21
- **Deliverables:**
  - `sim/run_regression.py`: Automated unified runner executing 28 testbench configurations with zero failures (`28 PASSED, 0 FAILED`).
  - `scripts/generate_report.py`: Automated generator producing `reports/RESULTS.md`.
  - `Makefile`: `make all` executed end-to-end, executing vector generation, regression, quality analysis, activity estimation, Yosys synthesis, and report generation in a single command.
  - `reports/RESULTS.md`: Complete technical write-up with G1–G9 checklist, data provenance, and honest clinical caveats.
