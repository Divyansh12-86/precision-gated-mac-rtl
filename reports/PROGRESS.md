# Project Progress Log — Precision-Gated MAC ECG

All commands, runs, architectural refactors, and milestone completions are logged chronologically here.

---

## Phase 0: Baseline and Hygiene [COMPLETED]

- **Date:** 2026-10-21
- **Toolchain Status:**
  - Simulator: `verilator` 5.020 (`--binary --timing`) verified as primary RTL simulation engine.
  - Synthesis: `yosys` 0.33 verified for Xilinx 7-series (`synth_xilinx -family xc7`).
  - Python: 3.12.3 with `wfdb`, `numpy`, `scipy`, `matplotlib`.
- **Hygiene:**
  - Standardized `.gitignore`, initialized `Makefile` and tracking documentation.

---

## Phase 1: Golden Model v2 and Vector Factory [COMPLETED]

- **Date:** 2026-10-21
- **Deliverables:**
  - `sim/qrs_detector_v2.py`: Hardware-equivalent Pan-Tompkins integer QRS detector (`>> 6` MWI, 17-bit saturation on squared derivative, deterministic reset).
  - `sim/golden_v2.py`: Bit-exact reference model supporting `FIXED_SCALE` (primary hardware policy) and `LEGACY_MINMAX`.
  - `sim/gen_vectors.py`: Deterministic vector generator exporting inputs, gates, full/gated/all-approx outputs, peaks, MWI, and SHA-256 manifests.

---

## Phase 2: Exact and Gated FIR RTL Implementation [COMPLETED]

- **Date:** 2026-10-21
- **Deliverables:**
  - `rtl/sample_delay_line.v`: Synchronous circular delay line with tap multiplexer.
  - `rtl/fir_coeff_rom.v`: 51-tap symmetric coefficient ROM.
  - `rtl/mult_split.v`: High/low split multiplier with operand isolation and clock-enable gating.
  - `rtl/pg_mac.v`: 32-bit saturating accumulator.
  - `rtl/pg_fir.v`: 51-tap time-multiplexed compute engine.

---

## Phase 3: Autonomous Pan-Tompkins QRS Detector & Top-Level Integration [COMPLETED]

- **Date:** 2026-10-21
- **Deliverables:**
  - `rtl/qrs_detector.v`: Autonomous real-time QRS detector with circular MWI buffer and adaptive dual thresholds.
  - `rtl/pg_top.v`: Integrated top-level filter core.
  - `rtl/baseline_fir_exact.v`: Non-gated conventional FIR filter baseline for like-for-like comparison.
  - `rtl/sample_tick_gen.v`: 360 Hz sample pacing generator from 100 MHz clock.

---

## Phase 4: Architectural Optimization & Area Reduction [COMPLETED]

- **Date:** 2026-10-21
- **Refactors:**
  - `sample_delay_line.v`: Replaced 51-stage register array (816 FFs) with 64x16 Distributed RAM (`RAM64M`) circular buffer (12 FFs).
  - `qrs_detector.v`: Replaced 54-stage MWI register array (1,279 FFs) with 64x17 Distributed RAM; replaced 17x17 combinational squarer with 17-cycle serial shift-add squarer (`SERIAL_SQ = 1`); unified threshold adaptation subtractor.
  - Pipeline Latency: Constant 73 clock cycles ($17 + 54 + 2$).
- **Synthesis Results (Yosys `xc7 -nodsp`):**
  - `pg_top`: **1,376 LUTs, 417 FFs** (smashed target of $\le 1500$ LUTs, $\le 800$ FFs; down from 2,691 LUTs, 2,246 FFs).
  - `qrs_detector`: **624 LUTs, 254 FFs** (down from 1,643 LUTs, 1,279 FFs).
  - `baseline_fir_exact`: **843 LUTs, 123 FFs**.

---

## Phase 5: Hardware Demonstration & Bit-Level UART Replay [COMPLETED]

- **Date:** 2026-10-21
- **Deliverables:**
  - `fpga/board_core.v`: Unified demonstration core (ROM replay -> 360 Hz pacer -> `pg_top` -> framed UART).
  - `fpga/uart_tx.v`: 115,200 baud 8N1 serial transmitter with XOR checksum framing.
  - `fpga/top_basys3.v`: Wrapper for Digilent Basys 3 (1,112 LUTs, 582 FFs, 2 DSP48E1; 5.35% utilisation).
  - `fpga/top_nexys_a7.v`: Wrapper for Digilent Nexys A7 (1,107 LUTs, 582 FFs, 2 DSP48E1; 5.32% utilisation).
  - `tb/tb_board_core.v`: Bit-level UART testbench. Decoded 5,000 frames with 0 preamble errors, 0 checksum errors, and 0 sample mismatches.

---

## Phase 6: Switching Activity, Mutation Testing, & Noise Characterization [COMPLETED]

- **Date:** 2026-10-21
- **Deliverables:**
  - `sim/activity_report.py`: Evaluated whole-core and datapath toggles across 6 sets:
    - Standard records: 20.97% – 22.00% datapath savings (32.90% minmax); 13.37% – 14.29% whole-core savings (21.67% minmax); 83.19% – 85.83% low-operand bus savings.
    - Noise stress: 17.57% datapath, 8.56% whole-core, 42.34% low-operand savings.
  - `scripts/mutation_check.py`: 14 of 14 mandatory mutants caught (0 survived).
  - `sim/noise_sweep.py`: Characterized SNRs 24, 18, 12, 6, 0 dB across records 100, 103, 105. All 15 sweeps verified bit-exact on RTL (0 mismatches).
  - `sim/run_regression.py`: Executed comprehensive regression suite (**34 PASSED, 0 FAILED**).
