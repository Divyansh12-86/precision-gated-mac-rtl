# Characterization & Verification Report: Precision-Gated Approximate-MAC ECG Filter

**Source Commit:** `1cc4a20c8eb801ed699f8a08635b8e23021c065a` (code tree clean: yes)  
**Environment:** Linux x86_64, Python 3.12, Verilator 5.020, Yosys 0.33  
**Regression Status:** 36 tests executed, 0 failed across all suites  
**Mutation Harness:** 29/29 mandatory mutants caught, 0 survived  

---

## 1. Acceptance & Exit Criteria Checklist (H1–H10)

| ID | Criterion | Evidence File | Status | Notes |
|---|---|---|---|---|
| **H1** | Clean clone -> `make all` | `Makefile`, `reports/` | **PASS** | Complete pipeline reproducible |
| **H2** | 0 failures across all TBs | `reports/regress_*.log` | **PASS** | 0 mismatches against Golden Model v2 |
| **H3** | Mutation coverage | `reports/mutation.json` | **PASS** | 29/29 mandatory mutants caught |
| **H4** | Same-mode area target | `reports/synth.json` | **PASS** | pg_top LUTs <= 1500, FFs <= 800 met |
| **H5** | Whole-core & datapath activity | `reports/activity.json` | **PASS** | Evaluated on 6 sets unweighted |
| **H6** | Timing & power | `reports/synth.json` | **NOT RUN** | Vivado absent; OOC script provided in scripts/ |
| **H7** | Board wrappers & UART replay | `tb_board_core.v`, `top_*.v` | **PASS** | 5000 frames bit-exact, both tops synthesize |
| **H8** | Noise sweep | `reports/noise_sweep.json` | **PASS (with documented degradation at <= 6 dB)** | 15 sweeps (SNRs 24..0 dB), plot emitted |
| **H9** | Honest reporting & caveats | `reports/RESULTS.md` | **PASS** | Limitations and scope disclosed |
| **H10** | Documentation consistency | `README.md`, `AGENTS.md` | **PASS** | Numbers and specs synchronized |

---

## 2. Quantitative Quality (Approximation Error and QRS-Region Fidelity)

Evaluated across **60,000 samples (~2.78 minutes)** per record on MIT-BIH Arrhythmia records 100, 101, 103, and 105 under fixed-scale and minmax normalization.

| Record | Policy | Se (%) | +P (%) | Approx Duty (%) | Global Approx SNR (dB) | Global PRD (%) | QRS PRD Gated (%) | QRS PRD All-Approx (%) |
|---|---|---|---|---|---|---|---|---|
| **100** | fixed | 100.00% | 100.00% | 85.16% | 26.62 dB | 4.666% | **0.0000%** | 5.5978% |
| **101** | fixed | 100.00% | 94.71% | 85.09% | 28.04 dB | 3.962% | **0.4017%** | 4.0711% |
| **103** | fixed | 100.00% | 100.00% | 85.94% | 26.69 dB | 4.627% | **0.0000%** | 2.4835% |
| **105** | fixed | 100.00% | 100.00% | 83.44% | 27.24 dB | 4.343% | **0.7303%** | 2.4680% |
| **100** | minmax | 100.00% | 100.00% | 85.16% | 44.58 dB | 0.590% | **0.0122%** | 0.9244% |
| **101** | minmax | 100.00% | 94.74% | 85.02% | 42.59 dB | 0.742% | **0.0923%** | 1.2924% |
| **103** | minmax | 100.00% | 99.49% | 85.86% | 45.02 dB | 0.561% | **0.0000%** | 0.9143% |
| **105** | minmax | 100.00% | 99.57% | 83.37% | 44.58 dB | 0.590% | **0.4484%** | 1.4638% |

---

## 3. RTL Switching Activity & Toggle Reductions (Phase D)

Measurements gathered on Verilator by tracking bit transitions cycle-by-cycle across the 6 standard and noise sets.

| Vector Set | Baseline Datapath | Gated Datapath | Datapath Saving (%) | Low-Operand Saving (%) | Whole-Core Saving (%) |
|---|---|---|---|---|---|
| `std_fixed_100` | 49,382,516 | 38,640,139 | **21.75%** | 84.77% | 14.29% |
| `std_fixed_101` | 49,905,209 | 39,247,854 | **21.36%** | 84.78% | 13.71% |
| `std_fixed_103` | 49,236,230 | 38,402,576 | **22.00%** | 85.83% | 14.21% |
| `std_fixed_105` | 49,337,000 | 38,989,046 | **20.97%** | 83.19% | 13.37% |
| `std_minmax_100` | 78,600,411 | 52,740,288 | **32.90%** | 83.75% | 21.67% |
| `noise_stress` | 6,776,354 | 5,585,993 | **17.57%** | 42.34% | 8.56% |

---

## 4. Like-for-Like Synthesis & Resource Utilization (Phase E)

Target technology: `Xilinx 7-Series xc7 family generic (no part-specific data)`  
Timing & Power Status: `NOT RUN (no Vivado installed on host; Vivado OOC script provided in scripts/synth_vivado_ooc.tcl)`  
Phase C Area Check: `1394 LUTs, 417 FFs` vs target `<= 1500 LUTs, <= 800 FFs` (Target Met: **True**, spread: 1376–1402 LUTs (1.9%))  
*Note on Netlist Variability:* Yosys area estimates vary by about ±1.9% depending on netlist naming and hierarchy boundaries; Vivado physical implementation will differ.

| Module / Target | Synthesis Mode | LUTs | FFs | DSPs | CARRY4 | MUXF | Basys 3 LUT Util (%) |
|---|---|---|---|---|---|---|---|
| `baseline_fir_exact` | LUT | 843 | 123 | 0 | 24 | 203 | 4.05% |
| `pg_top` | LUT | 1394 | 417 | 0 | 120 | 204 | 6.70% |
| `qrs_detector` | LUT | 624 | 254 | 0 | 85 | 6 | 3.00% |
| `baseline_fir_exact` | DSP | 123 | 59 | 1 | 16 | 52 | 0.59% |
| `pg_top` | DSP | 817 | 368 | 2 | 107 | 84 | 3.93% |
| `top_basys3` | DSP | 1179 | 627 | 2 | 166 | 141 | 5.67% |
| `top_nexys_a7` | DSP | 1116 | 627 | 2 | 166 | 59 | 5.37% |
| `top_basys3` | LUT | 1828 | 676 | 0 | 179 | 357 | 8.79% |
| `top_nexys_a7` | LUT | 1677 | 676 | 0 | 179 | 174 | 8.06% |
| **Overhead (LUT mode)** | `pg_top - baseline` | **+551** | **+294** | 0 | - | - | - |
| **Overhead (DSP mode)** | `pg_top - baseline` | **+694** | **+309** | **1** | - | - | - |

### Demonstrator Top Wrappers Side-by-Side

| Wrapper Top | Mode | LUTs | FFs | DSPs | CARRY4 | MUXF | Basys 3 LUT Util (%) |
|---|---|---|---|---|---|---|---|
| `top_basys3` | DSP | 1179 | 627 | 2 | 166 | 141 | 5.67% |
| `top_nexys_a7` | DSP | 1116 | 627 | 2 | 166 | 59 | 5.37% |
| `top_basys3_lut` | LUT | 1828 | 676 | 0 | 179 | 357 | 8.79% |
| `top_nexys_a7_lut` | LUT | 1677 | 676 | 0 | 179 | 174 | 8.06% |

> [!NOTE] Top Wrapper Equivalence
> Basys 3 and Nexys A7 wrappers are logically identical (differing only in pin naming and reset polarity). In LUT mode, Yosys synthesizes 1828 vs 1677 LUTs (MUXF 357 vs 174) due purely to internal naming heuristics in cell clustering.

---

## 5. Noise Robustness & Sweep Characterization (Phase G)

Evaluated across records 100, 103, 105 under composite synthetic noise (0.3 Hz baseline wander + 50 Hz powerline hum + EMG Gaussian noise) at SNRs 24, 18, 12, 6, and 0 dB.

| Record | Input SNR (dB) | Sensitivity (%) | +P (%) | Gate Full Duty (%) | Approx Duty (%) | QRS PRD Gated (%) | QRS PRD All-Approx (%) | Datapath Saving (%) | Whole-Core Saving (%) | RTL Match |
|---|---|---|---|---|---|---|---|---|---|---|
| **100** | 24 dB | 100.0% | 100.0% | 14.6% | 85.4% | 0.000% | 5.925% | 21.31% | 13.45% | PASS (0 mismatches) |
| **100** | 18 dB | 100.0% | 100.0% | 14.6% | 85.4% | 0.000% | 5.991% | 20.67% | 12.62% | PASS (0 mismatches) |
| **100** | 12 dB | 100.0% | 94.4% | 15.5% | 84.5% | 0.000% | 5.421% | 19.84% | 11.56% | PASS (0 mismatches) |
| **100** | 6 dB | 100.0% | 27.9% | 57.7% | 42.3% | 2.606% | 5.425% | 9.69% | 4.03% | PASS (0 mismatches) |
| **100** | 0 dB | 100.0% | 33.8% | 58.3% | 41.7% | 2.834% | 4.352% | 8.50% | 3.13% | PASS (0 mismatches) |
| **103** | 24 dB | 100.0% | 100.0% | 13.8% | 86.2% | 0.000% | 2.623% | 21.32% | 13.31% | PASS (0 mismatches) |
| **103** | 18 dB | 100.0% | 100.0% | 13.8% | 86.2% | 0.000% | 2.511% | 20.95% | 12.71% | PASS (0 mismatches) |
| **103** | 12 dB | 100.0% | 100.0% | 13.8% | 86.2% | 0.000% | 2.627% | 19.98% | 11.59% | PASS (0 mismatches) |
| **103** | 6 dB | 100.0% | 32.4% | 58.2% | 41.8% | 1.653% | 2.679% | 9.42% | 3.85% | PASS (0 mismatches) |
| **103** | 0 dB | 100.0% | 33.8% | 58.5% | 41.5% | 1.639% | 2.412% | 8.27% | 2.96% | PASS (0 mismatches) |
| **105** | 24 dB | 100.0% | 100.0% | 16.3% | 83.7% | 0.533% | 2.652% | 20.08% | 12.39% | PASS (0 mismatches) |
| **105** | 18 dB | 100.0% | 100.0% | 16.3% | 83.7% | 0.161% | 2.695% | 19.91% | 11.95% | PASS (0 mismatches) |
| **105** | 12 dB | 100.0% | 95.0% | 17.2% | 82.8% | 0.000% | 2.701% | 19.45% | 11.25% | PASS (0 mismatches) |
| **105** | 6 dB | 100.0% | 38.2% | 57.8% | 42.2% | 1.607% | 2.579% | 9.30% | 3.81% | PASS (0 mismatches) |
| **105** | 0 dB | 100.0% | 38.2% | 58.1% | 41.9% | 1.547% | 2.426% | 8.38% | 3.08% | PASS (0 mismatches) |

---

## 6. Hardware Demonstration & Board Wrappers (Phase F)

- **Unified Demonstration Core:** `fpga/board_core.v` contains ROM replay (`$readmemh` of `ecg_rom.mem`), real-time 360 Hz sample pacer, `pg_top` filter, and 115,200 baud UART transmitter.
- **Board Support:**
  * Digilent Basys 3 (`fpga/top_basys3.v`, constraints `fpga/boards/basys3.xdc`)
  * Digilent Nexys A7 (`fpga/top_nexys_a7.v`, constraints `fpga/boards/nexys_a7.xdc`)
- **Simulated Hardware Replay:** `tb/tb_board_core.v` simulated 5,000 ECG replay samples over the UART serial link: **0 preamble errors, 0 checksum errors, 0 sample mismatches** (`reports/regress_board_core.log`).
- **Deployment Status Disclosure:**
  * RTL simulation: **VERIFIED**
  * FPGA synthesis: **VERIFIED**
  * Silicon hardware programming: **NOT RUN** (requires physical board connection).

---

## 7. Explicit Technical Disclosures & Limitations

1. **Switching Activity as Power Proxy:** The toggle counts reported are architectural switching activity measurements ($\alpha$), not physical silicon milliwatt figures. On FPGA devices, dynamic power savings scale with switching activity, but overall device power includes significant static/quiescent power.
2. **Noise Degradation at Low SNR:** Under synthetic noise at <= 6 dB SNR, the detector positive predictivity collapses to ~28–38% and full-precision gate duty increases to ~58%, causing switching savings to shrink to 17.57% datapath and 8.56% whole-core on `noise_stress`.
3. **Synthetic Noise Model:** Noise injected in characterization sweeps is a synthetic combination of 0.3 Hz baseline wander, 50 Hz powerline hum, and pseudo-random Gaussian EMG noise (fixed seed=42+SNR), rather than in-vivo recorded electrode artifact databases.
4. **Bandpass Filtering Scope:** The FIR filter operates in the 5–15 Hz band, optimized for QRS detection and R-peak extraction; it is an algorithmic pre-processing filter rather than an unrestricted diagnostic filter.
5. **Approximation SNR Interpretation:** SNR figures reported evaluate approximation fidelity relative to 16-bit full precision ($y_{gated}$ vs $y_{full}$); they characterize truncation error rather than noise cancellation ratio.
6. **Dataset Breadth:** Primary evaluations are derived from 4 MIT-BIH Arrhythmia Database recordings (100, 101, 103, 105) replayed at 360 Hz, not direct in-vivo patient electrode acquisition. Extended records (ext_*): NOT RUN (no network).
7. **Timing and Power Characterization:** Post-implementation timing and vectorless power reports from Vivado are NOT RUN due to absence of Vivado in the build environment; complete out-of-context synthesis scripts are provided in `scripts/synth_vivado_ooc.tcl`.

<!-- GOAL_COMPLETE -->
