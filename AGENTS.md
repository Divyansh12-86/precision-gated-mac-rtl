# AGENTS.md — Precision-Gated MAC ECG Project (precision-gated-mac-ecg/)

> **Purpose:** Compact, high-signal context for future OpenCode sessions. Only facts an agent would likely miss without help.

---

## Project Identity

| Field | Value |
|-------|-------|
| **Project** | Precision-Gated Approximate-MAC FIR Filter for Low-Power ECG Noise Removal |
| **Course** | BEEE302L Digital Signal Processing, VIT Vellore (3 credits, L-T-P-C: 3-0-0-3) |
| **Student** | Divyansh — 3rd-year EEE, VIT Vellore; VLSI career priority |
| **Status** | In progress; repo private until provisional patent filing |
| **Critical Constraint** | Professor grading tied to VIT IPR Cell **IDF approval** (Invention Disclosure Form) |

---

## Why This Project Exists

1. **Hardware requirement:** Professor demands TRL 3/4 hardware (not just RTL simulation).
2. **Patent-worthy novelty:** Must pass VIT IPAC (IP Advisory Committee) review; rejection can lower grade.
3. **VLSI portfolio differentiation:** Custom low-power arithmetic architecture + real hardware + quantified numbers = interview-ready.
4. **Learning fixed-point / approximate computing hands-on** (new domain for the student).

---

## What It Is

A **solo, hardware-only DSP project** implementing a **QRS-aware precision-gated MAC architecture** for ECG noise removal on FPGA.

**Core innovation:** The MAC unit inside the FIR filter dynamically switches between:
- **Full precision (16-bit Q1.15)** during the QRS complex (~120 ms window, diagnostically critical)
- **Approximate precision (8-bit truncated)** during baseline/T-wave regions (~85% of cardiac cycle)

This exploits the fact that **dynamic power ∝ switching activity (α)** — fewer active bits = fewer transistors switching = measurable power savings.

---

## What It Is Supposed To Do

1. **Remove noise** from raw ECG (5–15 Hz bandpass FIR, Kaiser window β=14, order 50).
2. **Preserve QRS morphology** (R-peak amplitude, width, shape) with clinically acceptable fidelity (PRD < 2%, SNR > 33 dB).
3. **Reduce dynamic power** by ~29–38% via precision gating, substantiated by:
   - Circuit-level multiplier complexity: 16×16 → 8×16 active partial products (50% multiplier reduction)
   - Bit-level switching activity model across operand bus, partial products, accumulator
   - Duty cycle integration (85% time in low-power mode)
4. **Run end-to-end on FPGA** with live ECG from AD8232 front-end.

---

## How It Works (Architecture)

```
[Electrodes] → [AD8232 analog front-end] → [ADC: XADC or ADS1115] → [FPGA]
                                                            │
                               ┌────────────────────────────┴────────────────────────────┐
                               ▼                                                           ▼
                    [QRS/R-peak detector]                                         [Noise-removal FIR filter]
                    (always-on, low-complexity)                                    (PRECISION-GATED MAC)
                    NOT the novel element                                                    │
                               │                                      │
                               └──────────► Gate: full (1) / approx (0) ◄───────────────┘
```

- QRS detector runs in parallel on digitized stream; outputs per-sample gate flag.
- Gate flag controls MAC precision mode in real time.
- All inventive weight rests on the **precision-gated MAC mechanism** (QRS detection is treated as known technique per patent claim scoping).

---

## Key Technical Specifications

| Parameter | Value |
|-----------|-------|
| Sampling rate (FS) | 360 Hz (MIT-BIH standard) |
| Fixed-point format | Q1.15 (1 sign, 15 fractional bits) |
| Full precision | 16 bits |
| Approximate precision | 8 bits (LSB truncation) |
| FIR type | Bandpass 5–15 Hz, Kaiser window β=14, order 50 |
| QRS window | 120 ms (±60 ms around R-peak) = 43 samples @ 360 Hz |
| Target SNR | > 33 dB (achieved ~33.59 dB in simulation) |
| Approx mode duty cycle | ~85% |
| Estimated switching reduction | ~29% (simulation) |

---

## Development Plan (4-Month Timeline)

| Phase | Weeks | Deliverable |
|-------|-------|-------------|
| **1. Python Golden Model** | 1–2 | `sim/golden_model.py` — FIR + QRS gating + fixed-point + metrics; IDF Part 1 submitted |
| **2. Verilog Exact FIR + TB** | 3–5 | Bit-matched RTL core + testbench using exported test vectors |
| **3. Approximate MAC + Gating** | 5–7 | RTL with dynamic precision; synthesis area/power reports |
| **4. Hardware Bring-up** | 7–9 | MCU + AD8232 validation → FPGA integration |
| **5. Live Demo** | 9–11 | Real electrodes → live filtering → quantified output |
| **6. Buffer / Docs** | 11–16 | Debug, report, GitHub polish (post-filing), interview prep |

---

## Deliverables (Expected Final Outputs)

1. **Working FPGA prototype** — real-time filtering of live ECG
2. **Quantified characterization** — % power reduction, dB SNR cost, PRD, peak error
3. **Python golden model** — `sim/golden_model.py` (bit-exact reference)
4. **Verilog RTL** — `rtl/` (FIR core, MAC unit, QRS detector, gating logic)
5. **Test vectors** — `data/test_vectors/` (hex files for RTL verification)
6. **Synthesis reports** — `reports/` (area, timing, power for full vs. gated modes)
7. **Presentation slides** — `slides/dsp_review1_ppt.pptx` (review-ready)
8. **IDF documents** — `docs/` (for VIT IPR Cell submission)

---

## Current State (What Is Done)

| Component | Status | Location |
|-----------|--------|----------|
| Python golden model | **Complete** | `sim/golden_model.py` |
| FIR design (Kaiser, Q1.15) | **Complete** | `sim/golden_model.py:38-49` |
| Fixed-point arithmetic | **Complete** | `sim/golden_model.py:20-33` |
| Precision-gated MAC simulation | **Complete** | `sim/golden_model.py:67-127` |
| Metrics (SNR, duty cycle, switching proxy) | **Complete** | `sim/golden_model.py:190-204` |
| Test vector export | **Complete** | `sim/golden_model.py:132-154` |
| Multi-record test vectors (100, 101, 103, 105) | **Generated** | `data/test_vectors/` |
| Results plot | **Generated** | `sim/results_plot.png` |
| MIT-BIH data download script | **Documented** | `data/README.md` |
| Project context summary | **Complete** | `docs/DSP_project_full_summary.md` |
| Review 1 slides | **Complete** | `slides/dsp_review1_ppt.pptx` |

---

## What Is NOT Done (Critical Gaps)

| Gap | Why It Matters | Planned Location |
|-----|----------------|------------------|
| **Autonomous QRS detector** | Current `detect_qrs()` returns `None`; uses MIT-BIH `.atr` annotations. Must work on raw/self-captured data. | `sim/qrs_detector.py` (new) + RTL in `rtl/` |
| **Multiplier-level power model** | Current proxy only tracks accumulator output bit-flips. Need operand bus + partial product switching for "unquestionable proof." | `sim/golden_model.py` enhancement |
| **Clinical metrics (PRD, peak error)** | Professor expects clinical validation, not just SNR. | `sim/golden_model.py` enhancement |
| **Multi-record benchmark** | Only Record 100 run so far. Need 100, 101, 103, 105 for statistical consistency. | `sim/golden_model.py` loop |
| **Verilog RTL** | Entire `rtl/` is empty (`.gitkeep` only). | `rtl/` |
| **Testbenches** | Entire `tb/` is empty. | `tb/` |
| **FPGA synthesis/characterization** | No Vivado/Quartus project exists yet. | `reports/` |
| **Hardware bring-up** | No MCU/FPGA code; AD8232 not yet acquired. | External |
| **Interactive demo visualizer** | Needed for professor presentation. | `sim/interactive_demo.py` (new) |
| **IDF Part 1 draft** | Critical path for grading. | `docs/` |

---

## How To Run / Verify (Commands)

```bash
# 1. Setup (inside project root)
cd /mnt/D64C86FE4C86D91F/projects/precision-gated-mac-ecg
source .venv/bin/activate  # or create venv: python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt  # if exists, else: pip install wfdb numpy scipy matplotlib

# 2. Download MIT-BIH data (one-time)
python -c "
import wfdb, os
os.makedirs('data/mitbih', exist_ok=True)
for r in ['100','101','103','105']:
    wfdb.dl_database('mitdb', dl_dir='data/mitbih', records=[r])
    print(f'Downloaded {r}')
"

# 3. Run golden model (produces metrics + plot + test vectors)
python sim/golden_model.py
# Expected output: SNR ~33.59 dB, Approx Duty ~85.31%, Switching Reduction ~29.10%

# 4. View results
open sim/results_plot.png
cat data/test_vectors/tv_inputs.hex | head -5
```

---

## Repo Structure & Ownership

```
precision-gated-mac-ecg/
├── docs/              # Project context, IDF drafts, design decisions (SOURCE OF TRUTH)
├── slides/            # Review presentations (dsp_review1_ppt.pptx)
├── sim/               # Python golden model, future interactive demo
│   ├── golden_model.py          ← MAIN ENTRYPOINT for simulation
│   ├── results_plot.png         ← Generated visualization
│   └── (planned) qrs_detector.py, interactive_demo.py
├── rtl/               # Verilog RTL (EMPTY — next major milestone)
├── tb/                # Verilog testbenches (EMPTY)
├── data/
│   ├── mitbih/        # MIT-BIH records (gitignored, download via wfdb)
│   └── test_vectors/  # Exported hex files for RTL verification (COMMITTED)
├── reports/           # Synthesis reports, power/area (EMPTY)
├── .venv/             # Python virtual environment (gitignored)
└── README.md          # Quick start
```

---

## Critical Conventions & Gotchas

1. **Repo is PRIVATE** — do not push to public GitHub until after provisional patent filing (per IPR strategy).
2. **MIT-BIH data is NOT committed** — `data/mitbih/` is gitignored; must re-download via `wfdb` on new machine.
3. **Test vectors ARE committed** — `data/test_vectors/` contains small hex files for RTL verification.
4. **Q1.15 fixed-point** — all arithmetic uses 1 sign + 15 fractional bits; truncation = shift-right-then-left.
5. **QRS gating uses annotations currently** — `golden_model.py:176-181` builds gate flags from `ann.sample`; this is a simulation crutch.
6. **No lint/typecheck configured** — pure Python/Verilog project; no CI yet.
7. **Toolchain undecided** — Vivado (Xilinx) or Quartus (Intel); board TBD (Basys3/Nexys likely).

---

## Open Decisions (From `docs/DSP_project_full_summary.md` §11)

1. **IDF Part 1 draft** — highest priority; critical path for grading.
2. **Professor calibration** — ask about past IPAC approval precedents.
3. **Filter type** — FIR (windowed) vs. Adaptive/Wiener (syllabus Module 4 vs 7).
4. **QRS algorithm** — must be hardware-cheap; Pan-Tompkins derivative+threshold variant.
5. **Full patent-database diligence** — Google Patents/Espacenet/USPTO (only web search done so far).
6. **FPGA board & ADC** — Xilinx vs Intel; XADC vs ADS1115.

---

## Next Immediate Actions (Priority Order)

1. **Draft IDF Part 1** — use `docs/DSP_project_full_summary.md` framing (narrow claim: precision-gated MAC only).
2. **Implement autonomous QRS detector** — causal Pan-Tompkins in Python (`sim/qrs_detector.py`), then port to RTL.
3. **Upgrade power model** — bit-level switching across multiplier datapath; add PRD/peak-error metrics.
4. **Run multi-record benchmark** — Records 100, 101, 103, 105; generate comparison table for slides.
5. **Build interactive demo** — `matplotlib.animation` oscilloscope with live power gauge.
6. **Start Verilog RTL** — exact FIR core first, then approximate MAC + gating logic.
7. **Update slides** — embed multi-panel proof figure + animated GIF + Pareto curve.

---

## References

- **Primary context:** `docs/DSP_project_full_summary.md` (225 lines — complete standalone spec)
- **Simulation entrypoint:** `sim/golden_model.py`
- **Data download:** `data/README.md`
- **Slides:** `slides/dsp_review1_ppt.pptx` (6 slides: title, problem, approach, validation plan, syllabus, timeline)
- **Patent framing:** IDF titles in `docs/DSP_project_full_summary.md` §1
- **Prior art:** US7277479 (reconfigurable FIR), US5259387A (QRS-gated filter cutoff — expired)