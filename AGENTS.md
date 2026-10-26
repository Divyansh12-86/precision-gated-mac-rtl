# AGENTS.md — Precision-Gated MAC ECG Project (precision-gated-mac-ecg/)

> **Purpose:** Compact, high-signal context for future agent sessions. Only facts an agent would likely miss without help.

---

## Project Identity

| Field | Value |
|-------|-------|
| **Project** | Precision-Gated Approximate-MAC FIR Filter for Low-Power ECG Noise Removal |
| **Course** | BEEE302L Digital Signal Processing, VIT Vellore (3 credits, L-T-P-C: 3-0-0-3) |
| **Student** | Divyansh — 3rd-year EEE, VIT Vellore; VLSI career priority |
| **Status** | Implementation & Verification Complete; repo private until provisional patent filing |
| **Critical Constraint** | Professor grading tied to VIT IPR Cell **IDF approval** (Invention Disclosure Form) |

---

## Current Architecture & State (What Is Done)

| Component | Status | Details & Implementation |
|---|---|---|
| **Python Golden Model v2** | **Complete** | `sim/golden_v2.py`, bit-exact integer math, causal delay matching (group delay 25) |
| **RTL FIR Core** | **Complete** | `rtl/pg_fir.v`, 51-cycle time-multiplexed compute + 2-cycle drain |
| **RAM-Based Delay Line** | **Complete** | `rtl/sample_delay_line.v`, 64x16 distributed RAM (RAM64M), 12 FFs (down from 816) |
| **Approximate Multiplier** | **Complete** | `rtl/mult_split.v`, operand isolation, clock-enable hold (`p_low_r1`) |
| **RAM/Serial QRS Detector** | **Complete** | `rtl/qrs_detector.v`, 64x17 RAM MWI buffer, 17-cycle serial squarer (`SERIAL_SQ=1`), 624 LUTs / 254 FFs |
| **Top-Level Filter Core** | **Complete** | `rtl/pg_top.v`, 1,394 LUTs, 417 FFs (meets $\le 1500$ LUT / $\le 800$ FF target) |
| **Baseline FIR** | **Complete** | `rtl/baseline_fir_exact.v`, identical 51-cycle time multiplexing for like-for-like comparison |
| **UART Hardware Replay** | **Complete** | `fpga/board_core.v`, `fpga/uart_tx.v`, `fpga/top_basys3.v`, `fpga/top_nexys_a7.v` |
| **Bit-Level UART TB** | **Complete** | `tb/tb_board_core.v`, 5000 frames decoded with 0 preamble/chk/sample mismatches |
| **Full Regression Suite** | **Complete** | `sim/run_regression.py`, 37 standard / 53 nightly suites passing (0 mismatches against Golden Model v2) |
| **Mutation Testing** | **Complete** | `scripts/mutation_check.py`, 31/31 mandatory mutants caught (`reports/mutation.json`) |
| **Whole-Core Activity** | **Complete** | `sim/activity_report.py`, 6 standard/noise sets, datapath & whole-core (`reports/activity.json`) |
| **Like-for-Like Synthesis**| **Complete** | `scripts/synth_runner.py`, Yosys 7-series LUT/DSP same-mode tables (`reports/synth.json`) |
| **Noise Characterization** | **Complete** | `sim/noise_sweep.py`, SNRs 24..0 dB on records 100, 103, 105 (`reports/noise_sweep.json`) |
| **Comprehensive Report** | **Complete** | `reports/RESULTS.md` generated dynamically via `scripts/generate_report.py` |

---

## Key Hardware Numbers (Post-Phase C Refactor)

- **LUT Mode Synthesis (Yosys `xc7 -nodsp`):**
  - `pg_top`: **1,394 LUTs** (target $\le 1,500$, spread 1376–1402), **417 FFs** (target $\le 800$)
  - `qrs_detector`: **624 LUTs**, **254 FFs**
  - `baseline_fir_exact`: **843 LUTs**, **123 FFs**
  - Overhead: **+551 LUTs, +294 FFs** (accommodating autonomous real-time Pan-Tompkins QRS detector)
- **DSP Mode Synthesis:**
  - `pg_top`: **817 LUTs**, **368 FFs**, **2 DSP48E1**
  - `top_basys3`: **1,179 LUTs**, **627 FFs**, **2 DSP48E1** (only **5.67%** of Basys 3)
- **Datapath Switching Activity Reduction:**
  - Standard records: **21.0% – 32.9%** toggle savings
  - Low-operand bus: **83.2% – 85.8%** toggle reduction
  - Whole-core (including detector & delay-line RAM): **13.4% – 21.7%** toggle savings
- **Signal Quality & Reconstruction Fidelity (PRD):**
  - QRS-region PRD gated: **0.000% – 0.448%** (min-max, up to 0.730% fixed scale; 3.3× – 75.8× lower than all-approx)
  - Sensitivity: $\ge 99.5\%$ (Record 100/103/105: 100%)
  - Positive Predictivity: $\ge 94.7\%$ (Records 100/103/105: $\ge 99.5\%$)

---

## Critical System Invariants & Rules

1. **System Latency:** Exactly **73 clock cycles** ($17 + 54 + 2$) per sample tick when `SERIAL_SQ = 1`.
2. **Verilog Standard:** Pure Verilog-2001 across all RTL and wrappers (never use `'0` or SystemVerilog `logic`).
3. **Bit-Exactness:** RTL output `y_acc` and `gate_out` must match Golden Model v2 with **0 mismatches**.
4. **ROM Pipeline Alignment:** ROM read in `board_core.v` is synchronous (`always @(posedge clk) rom_sample <= rom[rom_addr];`), updating every clock cycle so `rom_sample` holds `rom[rom_addr]` well before `sample_tick`.
5. **No Hard-Coded Numbers in Reports:** All numbers in `generate_report.py` are loaded dynamically from JSON artifacts.

---

## How to Run Complete Verification

```bash
# Activate virtual environment
source .venv/bin/activate

# Execute complete pipeline (vectors -> sim -> quality -> activity -> synth -> noise -> report)
make all

# Verify 31/31 mutants caught
python3 scripts/mutation_check.py

# Verify bit-level UART hardware replay
verilator --binary --timing -Wno-WIDTHTRUNC -Wno-WIDTHEXPAND -Irtl -Ifpga \
  tb/tb_board_core.v fpga/board_core.v fpga/uart_tx.v rtl/*.v \
  --Mdir build_board && ./build_board/Vtb_board_core
```
