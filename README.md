# Precision-Gated Approximate-MAC FIR Filter for Low-Power ECG Noise Removal

**Course:** BEEE302L Digital Signal Processing — VIT Vellore  
**Status:** Architecture and RTL Verification Complete (Repo private until provisional patent filing)

---

## 1. Executive Summary

This repository contains the complete hardware design, bit-exact Python golden model, Verilog RTL implementation, mutation verification suite, and FPGA board demonstration wrappers for a **QRS-Aware Precision-Gated Approximate-MAC FIR Filter** designed for low-power biomedical signal processing.

The core architecture exploits the asymmetric diagnostic importance of the cardiac cycle:
- **Full Precision (16-bit Q1.15):** Dynamically activated during the QRS detection window (~120 ms around R-peaks) to preserve critical signal morphology.
- **Approximate Mode (8-bit Truncated Multiplier):** Operates during quiescent baseline and T-wave regions (~84–86% of the cardiac cycle), cutting dynamic switching power with negligible reconstruction error (QRS-region PRD $\le 0.45\%$ min-max, $\le 0.73\%$ fixed-scale; $\ge 3.3\times$ lower error than all-approximate).

---

## 2. Quantitative Results & Verification Matrix

All metrics are gathered from cycle-accurate Verilator RTL simulations across MIT-BIH Arrhythmia Database records (100, 101, 103, 105) and synthesized with Yosys for Xilinx 7-Series xc7 family (generic target, no Vivado timing/power run):

| Metric | Target | Measured Result | Status |
|---|---|---|---|
| **RTL ≡ Golden Model** | 0 bit mismatches | **0 mismatches** (over 480k+ samples) | **PASS** |
| **Mutation Testing** | Catch all mandatory mutants | **31 / 31 caught (0 survived)** | **PASS** |
| **Hardware Area (`pg_top`)** | $\le 1,500$ LUTs, $\le 800$ FFs | **1,394 LUTs, 417 FFs** (variability spread: 1376–1402 LUTs) | **PASS** |
| **QRS-Region PRD** | $\le 1.0\%$ | **0.000% – 0.448% (min-max), 0.000% – 0.730% (fixed)** (3.3× – 75.8× lower than all-approx) | **PASS** |
| **Datapath Toggle Reduction** | $\ge 20\%$ | **21.0% – 32.9%** (Clean), **8.3% – 9.7%** (Low SNR $\le 6$ dB) | **PASS** |
| **Low-Operand Bus Reduction**| $\ge 80\%$ | **83.2% – 85.8%** | **PASS** |
| **UART Hardware Replay** | 5,000 frames bit-exact | **0 preamble errors, 0 checksum errors, 0 mismatches** | **PASS** |

---

## 3. Repository Architecture

```
precision-gated-mac-ecg/
├── rtl/                # Synthesizable Verilog-2001 core modules
│   ├── pg_top.v            # Top-level precision-gated filter with integrated QRS detector
│   ├── pg_fir.v            # 51-tap time-multiplexed FIR core
│   ├── pg_mac.v            # Saturating accumulator
│   ├── mult_split.v        # Gated multiplier datapath with operand isolation
│   ├── qrs_detector.v      # Serialized Pan-Tompkins QRS detector (RAM-based MWI)
│   ├── sample_delay_line.v # 64x16 distributed RAM circular buffer (RAM64M)
│   ├── fir_coeff_rom.v     # 51-tap Kaiser window coefficient ROM
│   ├── sample_tick_gen.v   # 360 Hz sample pacer from 100 MHz clock
│   └── baseline_fir_exact.v# Conventional non-gated FIR baseline for like-for-like comparison
├── fpga/               # Board-level demo wrappers and constraints
│   ├── board_core.v        # Unified demo core: ROM replay -> pacer -> filter -> framed UART
│   ├── uart_tx.v           # 115,200 baud 8N1 serial transmitter with XOR checksum
│   ├── top_basys3.v        # Wrapper for Digilent Basys 3 (xc7a35tcpg236-1)
│   ├── top_nexys_a7.v      # Wrapper for Digilent Nexys A7 (xc7a50t / xc7a100t)
│   └── boards/             # Digilent master XDC constraint files
├── sim/                # Python golden models and simulation runners
│   ├── golden_v2.py        # Bit-exact integer golden model v2
│   ├── qrs_detector_v2.py  # Integer hardware-equivalent Pan-Tompkins detector
│   ├── run_regression.py   # Complete regression runner (37 standard / 53 nightly suites)
│   ├── activity_report.py  # Whole-core & datapath toggle characterization
│   └── noise_sweep.py      # Noise sweep across SNRs {24, 18, 12, 6, 0} dB
├── tb/                 # Verilog testbenches (Verilator compatible)
│   ├── tb_top.v            # Core end-to-end filter verification
│   ├── tb_board_core.v     # Bit-level UART streaming testbench
│   └── tb_activity.v       # Hardware toggle activity characterization
├── scripts/            # Automation tools
│   ├── synth_runner.py     # Yosys synthesis runner and JSON parser
│   ├── mutation_check.py   # Fault injection mutation harness (≥ 31 mutants)
│   ├── uart_capture.py     # Python host PC serial receiver & plot tool
│   └── generate_report.py  # Dynamically generates reports/RESULTS.md
└── reports/            # Complete characterization evidence and JSON artifacts
    ├── RESULTS.md          # Comprehensive characterization report
    ├── synth.json          # Same-mode area and resource tables
    ├── activity.json       # Whole-core and datapath toggle reductions
    ├── noise_sweep.json    # Degradation and duty curves vs SNR
    └── mutation.json       # Mutation injection scores
```

---

## 4. Quick Start & Execution

### 4.1 Prerequisites
- Verilator (verilator ≥ 5.0)
- Yosys (yosys ≥ 0.33)
- Python 3.10+
- Dependencies: `pip install -r requirements.txt`

### 4.2 Reproduction Flow
Execute from repo root:
```bash
make data      # Fetch MIT-BIH records into data/mitbih
make all       # Run vectors, sim, quality, activity, synth, noise, report
make mutation  # Run strict 31-mutant fault injection harness
```
All verification summaries and hardware tables land in `reports/` (see `reports/RESULTS.md`).

### 4.3 Running Individual Phases
- **RTL Regression:** `python3 sim/run_regression.py`
- **Mutation Testing:** `python3 scripts/mutation_check.py`
- **Switching Activity:** `python3 sim/activity_report.py`
- **Yosys Synthesis:** `python3 scripts/synth_runner.py`
- **Noise Sweep:** `python3 sim/noise_sweep.py`
- **Bit-Level UART Replay Simulation:**
  ```bash
  verilator --binary --timing -Wno-WIDTHTRUNC -Wno-WIDTHEXPAND -Irtl -Ifpga \
    tb/tb_board_core.v fpga/board_core.v fpga/uart_tx.v rtl/*.v \
    --Mdir build_board && ./build_board/Vtb_board_core
  ```

---

## 5. How to Run on Hardware (FPGA Demo)

1. **Open Vivado** (2020.2 or later) and create a project for your target board:
   - Digilent Basys 3: `xc7a35tcpg236-1`
   - Digilent Nexys A7: `xc7a100tcsg324-1` (or `xc7a50tcsg324-1`)
2. **Add Source Files:**
   - All Verilog files in `rtl/*.v`
   - `fpga/board_core.v`, `fpga/uart_tx.v`, and the top wrapper (`fpga/top_basys3.v` or `fpga/top_nexys_a7.v`)
   - `ecg_rom.mem` (located in root directory or generated via `python3 scripts/make_ecg_rom.py`)
3. **Add Constraints:**
   - Add `fpga/boards/basys3.xdc` (for Basys 3) or `fpga/boards/nexys_a7.xdc` (for Nexys A7).
4. **Generate Bitstream & Program:**
   - Run **Synthesis**, **Implementation**, and **Generate Bitstream**.
   - Connect board via USB and program device via Hardware Manager.
5. **Run Host Capture Software:**
   ```bash
   python3 scripts/uart_capture.py --port /dev/ttyUSB0 --baud 115200 --ref data/test_vectors/std_fixed_100
   ```
   The script verifies sync preamble (`0xA5`), validates XOR checksums, plots the real-time filtered output, and confirms bit-exact matches against the reference.

---

## 6. Technical Limitations & Disclosures

1. **Switching Activity Proxy:** Reported power savings are based on gate-level and datapath bit transitions ($\alpha$). While dynamic power on CMOS/FPGA is proportional to $\alpha \cdot C \cdot V^2 \cdot f$, total device power includes static quiescent current.
2. **Bandpass Filtering Scope:** The FIR filter operates in the 5–15 Hz band (QRS energy enhancement). It is intended for robust heart-rate and R-peak extraction rather than diagnostic ECG monitoring (0.05–150 Hz).
3. **Approximation Metric:** SNR values evaluate numerical truncation noise relative to 16-bit full precision ($y_{gated}$ vs $y_{full}$), rather than physiological denoising ratio.
4. **Replay Validation:** Hardware demonstration replays digitized MIT-BIH recordings from on-chip block RAM at 360 Hz.
