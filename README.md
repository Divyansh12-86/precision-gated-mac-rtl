# Precision-Gated Approximate-MAC FIR Filter for Low-Power ECG Noise Removal

**Course:** BEEE302L Digital Signal Processing — VIT Vellore
**Status:** In progress (repo is private until provisional patent filing)

## What this is

A hardware-only DSP project implementing a **QRS-aware, precision-gated MAC architecture** for low-power ECG filtering on FPGA.

The core idea: the MAC unit inside the FIR filter dynamically switches between full-precision (16-bit) and approximate (truncated) arithmetic, gated in real time by a lightweight on-chip QRS/R-peak detector. Full precision during the diagnostically critical QRS window; reduced precision — and therefore reduced dynamic power — during the baseline/T-wave regions that occupy the majority of each cardiac cycle.

Full project context, design rationale, patent framing, and timeline: `docs/DSP_project_full_summary.md`.

## Repo layout

```
precision-gated-mac-ecg/
├── docs/        project context, design decisions, IDF drafts
├── slides/      review presentations
├── sim/         Python golden model (NumPy/SciPy)
├── rtl/         Verilog RTL — FIR core, MAC unit, QRS detector
├── tb/          testbenches and test vectors
├── data/        ECG data (MIT-BIH; see data/README.md for download)
└── reports/     synthesis reports, power/area characterization
```

## Quick start (simulation)

```bash
pip install wfdb numpy scipy matplotlib
python sim/golden_model.py
```

See `data/README.md` for downloading the MIT-BIH Arrhythmia Database.

## Tech stack

- **RTL:** Verilog | **Toolchain:** Vivado (Xilinx) or Quartus (Intel/Altera)
- **FPGA:** Artix-class dev board (TBD)
- **Sensor front-end:** AD8232 ECG module
- **Simulation:** Python 3, NumPy, SciPy, wfdb (PhysioNet MIT-BIH)
