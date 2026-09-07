# Project Context Summary — DSP Hardware Project (BEEE302L)

**How to use this file:** This is a complete, standalone context dump. Paste this entire file as the first message to any AI assistant (Claude or otherwise) to give it full understanding of this project — no other conversation history is needed. It is also sufficient on its own to draft a presentation, a report, a resume bullet, or an IDF (Invention Disclosure Form) for this project.

---

## 1. Project Title

**For patent filing / IDF (kept broad, protects claim scope):**
> **"QRS-Synchronized Adaptive Precision Arithmetic Unit for Low-Power Biomedical Signal Filtering"**

**For course project / report / GitHub (more descriptive):**
> **"Precision-Gated Approximate-MAC FIR Filter for Low-Power ECG Noise Removal"**

**Middle-ground / general-use title:**
> **"QRS-Aware Precision-Gated MAC Architecture for Low-Power ECG Filtering"**

Rationale: patent/IDF titles conventionally stay broad and application-agnostic ("biomedical signal filtering" rather than "ECG specifically") so the claim isn't narrowed by the title. Course/resume/GitHub titles can be more descriptive since they're read by humans skimming for keywords, not examiners scoping claims.

---

## 2. Who this is for

Divyansh — 3rd-year Electronics and Electrical Engineering student, VIT Vellore. Software Engineer on Team Ardra (university drone development team; computer vision/OpenCV/YOLO, A*/RRT path planning, C++20). Strong competitive-programming background. Career priority: **VLSI**, while also actively applying for SWE/data-science internships. Building a portfolio deliberately straddling both VLSI/core-electronics and software engineering paths.

---

## 3. What this project is (plain-language summary)

A **solo, hardware-only project** for the course **BEEE302L Digital Signal Processing** (VIT Vellore, 3 credits, L-T-P-C: 3-0-0-3).

**The idea:** An ECG (heart signal) has a diagnostically critical portion — the QRS complex (the sharp spike corresponding to ventricular contraction) — and less critical portions (baseline, T-wave). Conventional digital noise-removal filters run their internal arithmetic (the multiply-accumulate, or MAC, operations) at a fixed precision all the time, which wastes power. This project designs a filter whose **MAC unit dynamically switches between full precision and reduced/approximate precision, gated in real time by a lightweight on-chip QRS/R-peak detector** — full precision during the diagnostically important QRS window, reduced precision during the less-critical baseline/T-wave regions — saving power with a controlled, quantified, and clinically justifiable accuracy tradeoff.

**Why it's real, not just theoretical:** this targets a genuine engineering problem — wearable and implantable ECG monitors (Holter monitors, health patches) are severely battery-constrained, so any technique that saves power without meaningfully degrading diagnostic quality has real product relevance.

**Deliverable:** a working, end-to-end hardware system — real ECG electrodes → live signal acquisition → FPGA-based precision-gated filtering → quantified, characterized output (power savings vs. accuracy cost) — not just a simulation.

---

## 4. Why this specific project — full reasoning chain

### 4.1 Constraints and goals stated by the person (unchanged throughout)
- Solo project, must be **hardware**, not just RTL simulation — professor wants TRL 3/4-ready hardware.
- Wants genuine novelty — ideally **patent-worthy**. This was later clarified to mean something very specific and literal: **VIT's IPR & Technology Transfer Cell must approve the project through its formal Invention Disclosure Form (IDF) process** (see Section 7). The professor's grading is tied to this approval — a rejection can lower the grade. This is the single most important constraint governing the whole project now.
- Wants strong resume/GitHub differentiation — explicitly does NOT want a project "for the sake of it." Wants something demonstrably useful, not a checkbox exercise.
- VLSI is top career priority, though open to any solid EE/electronics outcome.
- Wants to learn fixed-point arithmetic / custom number representations (Q-format, CORDIC, RNS, approximate computing) hands-on through the project itself — new to this area.
- Timeline: **2–4 months, moderate depth acceptable.**
- Wants the project useful for cold-emailing companies/professors and for interview conversations, not just a resume line.
- Explicit resume-improvement work (rewording, framing) is meant to happen **after grading is complete** — right now, satisfying the professor/IPR Cell is the first priority.

### 4.2 How the topic was narrowed (important: shows genuine diligence, not arbitrary choice)
1. **Domain-level fit:** DSP + VLSI overlap naturally in **accelerator/MAC-datapath design** (syllabus Module 5: DSP processor architectures — MAC, pipelining, fixed/floating point), not just algorithm simulation. Person confirmed interest in general-purpose hardware/accelerators over a specific application domain initially.
2. **Novelty-angle choice:** considered approximate computing (power/area tradeoffs), RNS arithmetic, and reconfigurable datapaths. **Chose approximate computing** — richer/more accessible learning material for a beginner, naturally teaches fixed-point arithmetic, active real research/industry area.
3. **Application-domain choice:** considered **audio FIR filtering** and rejected it — extremely oversaturated on student GitHub, no differentiation value. Chose **biomedical (ECG) signal denoising** — less saturated, and gives the power-efficiency story a genuine real-world justification (wearables are actually power-constrained), unlike a contrived audio use case.
4. **Prior-art checks (via web search) — caused two real pivots:**
   - **Rejected idea 1:** "Coefficient-magnitude-aware approximate MAC that dynamically switches precision based on filter coefficient values." Already prior-arted: an actual patent, **US7277479** ("Reconfigurable FIR filter," precision-independent critical path), plus substantial published work on approximate distributed-arithmetic FIR filters (Booth/Wallace-tree approximation) and dynamically reconfigurable-precision filters on real silicon.
   - **Rejected as a standalone claim:** general "QRS-gated filter behavior switching." Already prior-arted: **US5259387A** ("ECG muscle artifact filter system," 1993) — detects the R-wave and switches the filter's **cutoff frequency** based on QRS timing (low cutoff outside QRS for max smoothing, higher cutoff during QRS to preserve signal shape). This patent is old enough to have likely expired, making it safe, citable prior art rather than a blocker.
   - **Current, standing claim:** gating **MAC arithmetic precision** (a power/computational-effort lever) based on QRS timing — mechanistically different from US5259387A (which gates a *filter/DSP parameter*, not *arithmetic hardware precision*) and different from the coefficient/data-based approximate computing literature (which doesn't use physiological/diagnostic timing as the gating signal). As of the last check, this specific combination has not been found in prior art — but only a web search has been done, not full patent-database diligence (see Section 7).
5. **Claim-scoping decision:** to keep the patent claim clean and defensible, the QRS/R-peak detection algorithm itself should be treated as an **existing, known technique being used**, not claimed as novel. All inventive weight rests on the **precision-gated MAC mechanism** alone. Avoid stacking multiple uncertain novelty claims (QRS detection method + precision gating) — a single, sharp, well-differentiated claim is easier for a review committee to evaluate and approve.

### 4.3 Saturation / resume-value discussion (person raised doubts, addressed directly)
- Concern raised: is biomedical/ECG too saturated a field to be resume-valuable for VLSI, after all the effort?
- Position taken: **generic** wearable/health-tracker projects (step counters, basic ECG display) are saturated; this project is a different tier — a custom low-power arithmetic architecture, verified on real hardware, with an actual patent-filing attempt — which is not commonly duplicated.
- VLSI recruiters evaluate the **skills demonstrated** (RTL design, verification, arithmetic/architecture-level design decisions, low-power design thinking, synthesis/characterization, real hardware bring-up), not the application domain. The domain explains *why* the project exists; it doesn't define what it proves technically.
- Biomedical/low-power health-tech VLSI is also a real, legitimate industry niche (wearable SoCs, medical device chips, low-power sensor front-ends at companies like TI's medical group, Qualcomm, various fabless startups) — so the domain can even be a plus for a subset of roles, not just neutral.
- The actual risk identified is **framing/wording**, not the domain itself: resume/GitHub copy should lead with the architectural contribution ("precision-scalable MAC architecture... demonstrated on real-time ECG filtering"), not lead with "biomedical engineering project," so recruiters skimming for VLSI/RTL keywords don't miscategorize it. This wording work is explicitly deferred to **after grading is complete**, per the person's stated priority.

---

## 5. Course syllabus context (BEEE302L Digital Signal Processing, VIT Vellore, 45 lecture hours)

Relevant modules this project draws on:
- **Module 2** — DFT/DTFT, Radix-2 FFT, filter realization structures (direct I/II, cascade, parallel, lattice)
- **Module 4** — FIR filter design (windowing: rectangular, Hamming, Hanning, Bartlett, Blackman, Kaiser) — relevant if FIR is the chosen filter type
- **Module 5** — DSP processor architectures: finite word length effects, MAC, pipelining, addressing modes, fixed vs. floating point — the core VLSI/architecture tie-in for this project
- **Module 7** — Adaptive filters (Wiener, LMS) — relevant if adaptive filtering is chosen instead of FIR

---

## 6. Technical architecture

### 6.0 System block diagram (text form, for portability into any AI/document)

```
 [Electrodes on body]
        |
        v
 [AD8232 ECG front-end]  --(analog ECG signal)-->  [Buffer / level-shift stage]
                                                              |
                                                              v
                                                    [ADC: XADC or ADS1115]
                                                              |
                                                              v
                                          +-------------------+-------------------+
                                          |                                       |
                                          v                                       v
                              [QRS / R-peak detector]                [Noise-removal filter core]
                              (always-on, low-complexity,             (FIR or adaptive/Wiener)
                               NOT the novel element)                 with a PRECISION-GATED MAC
                                          |                                       ^
                                          |------(precision mode control)---------|
                                          |          (full vs. approximate)
                                          v
                              [Filtered, denoised ECG output]
                                          |
                                          v
                        [Characterization: SNR, power/area reports,
                         exact-vs-approximate comparison]
```

**Reading the diagram:** the QRS detector and the filter core run in parallel on the same digitized ECG stream. The detector's only job is to tell the filter's MAC unit which precision mode to use, moment to moment. The filter does the actual noise removal; the MAC's precision mode is the one thing being dynamically controlled, and that control signal is the entire inventive contribution of this project (Section 6.3).

### 6.1 Core inventive mechanism
A lightweight, always-on QRS/R-peak detector runs continuously on the incoming ECG stream. Its output gates the precision mode of the noise-removal filter's MAC datapath:
- **Full precision** during the QRS complex window (diagnostically critical — accuracy matters most here)
- **Reduced/approximate precision** during baseline/T-wave regions (more error-tolerant, saves power)

**Why this actually saves power (the mechanism, not just the claim):** in digital hardware, a multiply-accumulate (MAC) operation's power draw scales with how many bits are actively switching on every clock cycle and how much logic the signal has to propagate through (the critical path). A "full precision" MAC — say, 16-bit operands — has to switch and propagate through significantly more transistors per operation than a "reduced precision" MAC operating on, for example, the top 8 bits only (with the lower bits truncated or held constant). Fewer active bits per operation means less dynamic power dissipation (dynamic power in CMOS logic is roughly proportional to switching activity × capacitance × voltage² × frequency — reducing the number of bits that switch directly reduces the switching-activity term). So the "approximate mode" isn't a vague notion of "less accurate, therefore less power" — it's a concrete hardware fact: fewer bits computed per cycle literally means fewer transistors switching, which is where the power saving comes from. The tradeoff is that fewer bits also means less numerical accuracy, hence the SNR cost that has to be measured and reported. This is also precisely why the QRS-timing gate matters: it lets the design spend the "expensive" full-precision computation only during the ~100–120ms diagnostically critical QRS window per heartbeat, and the "cheap" approximate computation for the rest of each ~0.6–1s cardiac cycle — meaning the power-saving mode is active for the large majority of the time, not a marginal fraction.

### 6.2 Signal acquisition path (real, not purely simulated — deliberate choice for genuine TRL3/4, not just idealized data)
- **Sensor front-end:** AD8232 ECG module (electrodes → analog ECG signal; ~₹300–600 in India; standard hobbyist/prototype part; does its own onboard bandpass filtering and instrumentation amplification — the project's contribution starts downstream of this, at digital filtering)
- **De-risking step (recommended first):** validate acquisition via a simple MCU (Arduino/ESP32) capturing the person's own real ECG over serial, before integrating into the FPGA — separates the sensor/acquisition risk from the RTL/architecture risk
- **Digitization into FPGA — two options considered:**
  1. Board's built-in XADC (on Xilinx Artix-7 boards like Basys3/Nexys) with a buffer/level-shift stage to match AD8232's output range — more "pure hardware," more analog bring-up effort
  2. External ADC module (e.g., ADS1115) over SPI/I2C — more beginner-friendly, better documented, one extra BOM item
- **Safety practice (explicitly noted):** run any electrode-connected acquisition hardware off battery/USB-isolated power, not directly off a mains-grounded laptop — standard AD8232 hobbyist practice, low risk at these voltages but worth doing correctly since testing will be on a real body.

### 6.3 Processing core (the actual design/patent content)
- **QRS/R-peak detector:** algorithm not yet finalized. Must be hardware-friendly and low-complexity itself (must not itself consume so much power/area that it defeats the purpose of the precision-gating scheme). Treated as an existing/known technique for claim purposes, not the novel element.
- **QRS window definition — not yet finalized, flagged explicitly as an open decision:** typical physiological QRS complex duration is roughly 80–120ms, within a cardiac cycle of roughly 0.6–1s at resting heart rate — these are general physiological reference figures, not project-specific decisions yet. The project still needs to define exactly how the detector's output is converted into a precision-switch signal (e.g., a fixed-width window centered on the detected R-peak, versus a more adaptive window derived from detected QRS onset/offset). This directly affects both the SNR-vs-power tradeoff and the complexity of the detector, so it should be decided alongside the QRS algorithm choice itself (see Section 11, item 4).
- **Noise-removal filter core:** type not yet finalized — candidates are:
  - **FIR (windowed design)** — ties to syllabus Module 4
  - **Adaptive/Wiener filter** — ties to syllabus Module 7
- **MAC unit:** the actual novel element — supports (at least) two precision modes, switched in real time by the QRS detector's output.

### 6.4 Validation / verification flow
1. **Python golden model first** (NumPy/SciPy) — simulate the entire precision-gating idea numerically (approximate MAC modeled via bit-truncation or similar) against the **MIT-BIH Arrhythmia Database** (via PhysioNet), before writing any RTL. Cheap to iterate on; catches conceptual flaws early.
2. **Verilog implementation** of the exact-precision filter core + testbench, bit-matched against the Python golden model using real ECG test vectors.
3. **Add approximate-MAC mode + QRS-gating logic** in RTL. Synthesize; pull area/power reports comparing exact vs. approximate/gated modes.
4. **Real hardware bring-up:** MCU + AD8232 acquisition validation first, then FPGA integration of the full real-time pipeline.
5. **End-to-end live demo:** real electrodes → live filtering → output, with real quantified numbers (e.g., "X% power reduction, Y dB SNR cost") measured on real captured data, not just simulation.

### 6.5 Board / BOM
- **FPGA board:** not finalized — either Xilinx or Intel/Altera, Artix-class or equivalent (e.g., Basys3/Nexys on the Xilinx side). Deliberately deferred since board choice mostly matters for I/O and constraints work, which happens late in the process. Likely sourced through the college.
- Deferring this decision was a deliberate choice, not an oversight.

---

## 7. Tech stack

- **Hardware:** FPGA dev board (TBD: Xilinx or Intel/Altera, Artix-class), AD8232 ECG front-end module, MCU (Arduino/ESP32) for initial acquisition validation, possibly an external ADC module (e.g., ADS1115)
- **RTL:** Verilog
- **Software / modeling:** Python (NumPy/SciPy) for the golden model; MIT-BIH Arrhythmia Database (PhysioNet) as reference dataset, supplemented by the person's own real captured ECG data
- **Toolchain:** Vivado (if Xilinx) or Quartus (if Intel/Altera) — not yet decided, tied to board choice
- **Verification:** RTL testbenches bit-matched against the Python golden model

---

## 8. Patent / IPR process (VIT-specific — this is now the critical path, not an afterthought)

### 8.1 What was learned about VIT's actual process
VIT has a formal **IPR & Technology Transfer Cell**, with a documented process:
- Inventor fills out an **Invention Disclosure Form (IDF)** — two parts, Part 1 and Part 2 (formats differ for patents vs. design registrations)
- Submitted via **VTOP** (VIT's portal) → Research → "IPR and Technology Transfer Cell" → "Manage IDF"
- Reviewed by an **IPAC (IP Advisory Committee)** — the inventor presents the idea and answers committee questions
- If approved, VIT routes the application through an approved patent attorney from their panel; financial support for filing typically comes from the institute
- VIT publishes its own **"Guide to Technology Readiness Levels (TRL)"** — this is almost certainly where the professor's TRL3/4 requirement originates, meaning it's VIT's own institutional rubric, not a personal preference of the professor's

### 8.2 Why this matters for sequencing
The professor's grading is tied to actual IPAC approval — a rejection can lower the grade. This means the IDF/IPAC review is the **real critical-path gate**, not a formality to handle after the hardware is built. The plan explicitly moved IDF submission earlier: it should happen in parallel with early Python-golden-model work (Phase 1), not after a working FPGA prototype exists — so that if the committee has concerns, there's still time to adjust before deep build investment is sunk.

### 8.3 Risk-mitigation steps identified (some not yet acted on)
1. **Draft and submit IDF Part 1 early** — using the precision-gated-MAC framing and the prior-art differentiation already established (vs. US7277479 and US5259387A).
2. **Get calibration from the professor**: has any past student/project from this course actually received IPAC approval, and what did that project look like? This establishes the real bar rather than a guessed one.
3. **Keep the claim narrow and singular** (precision-gated MAC mechanism only — see Section 4.2/4.3) to make committee evaluation cleaner.
4. **Public-disclosure caution:** publishing the repo, posting about the specific technical idea publicly, or presenting it too early/broadly could jeopardize patentability in some jurisdictions (India has a narrow grace-period provision for inventor's own prior disclosure, but it's not something to rely on casually). Practical implication: **keep the GitHub repo private / avoid publicizing the specific technical mechanism until after at least a provisional filing**, then make it public afterward. This is a sequencing decision, not a lost opportunity — resume value is simply delayed until post-filing.
5. **Time-box a decision point** with the professor — agree on a date by which IPAC's verdict is needed, so there's still runway to pivot the framing (or fall back to a rigorous non-patent TRL3/4 project on its own merits) if the answer is a rejection.

### 8.4 Important distinction to keep in mind
"Patent-worthy" (IPAC approval) and "job-worthy" (resume/interview value) are **separable outcomes**, not one pass/fail bar. Even if IPAC review stalls or rejects the patent angle, the TRL3/4 hardware project itself — done well, with real hardware and real quantified characterization — still stands on its own for both grading (as a rigorous project, separate from patent outcome, if the professor's rubric allows partial credit for the process) and for resume value. This should not be treated as an all-or-nothing bet.

---

## 9. Timeline (~4 months from the point of finalizing scope, phased with demoable checkpoints at every stage — deliberate, since hardware bring-up is the most likely place for schedule slip)

1. **Weeks 1–2:** Full prior-art diligence (proper patent-database search, not just web search) + **draft and submit IDF Part 1 to VIT's IPR Cell** (moved earlier in priority given Section 8). Finalize filter type (FIR vs. adaptive/Wiener) and QRS detection algorithm. Build the Python golden model.
2. **Weeks 3–5:** Verilog exact-precision filter core + testbench, bit-matched against the Python model.
3. **Weeks 5–7:** Add approximate-MAC mode + QRS-gating logic. Synthesize; get area/power reports.
4. **Weeks 7–9:** Hardware bring-up — MCU + AD8232 acquisition validation first, then FPGA integration.
5. **Weeks 9–11:** End-to-end live demo (real electrodes → live filtering → output/plot). Characterize real power/accuracy tradeoffs on real captured data.
6. **Weeks 11–16:** Buffer for hardware debugging (expected to overrun), documentation, GitHub polish (kept private until after filing — see 8.3), report/write-up, interview narrative prep.

---

## 10. Resume / job-hunting framing (explicitly deferred to after grading, but worth having on record)

- Lead with the **architectural contribution**, not the application domain. Example resume-bullet direction discussed: *"Designed a precision-scalable MAC architecture (Verilog, FPGA, low-power arithmetic) for error-tolerant, always-on signal processing, demonstrated on real-time ECG filtering"* — not *"Built a biomedical ECG filtering system."*
- What will determine real job-worthiness, in order of importance:
  1. It actually runs end-to-end on real hardware, with a demo (video or live).
  2. Real quantified numbers exist (e.g., % power reduction, dB SNR cost) — not just "it works."
  3. The GitHub repo (once made public, post-filing) is documented like an engineer wrote it — block diagrams, waveforms, synthesis reports, a README explaining the *why*, not just the *what*.
  4. Fluency explaining the design tradeoffs in live conversation — this is what interviews actually test.
- A solo undergrad publishing this as a paper at a student/undergrad IEEE conference or workshop was also floated as a realistically achievable, still resume-strong outcome to pursue **in parallel with**, not instead of, the patent route.
- Value for cold-emailing: a specific, quantified pitch ("I designed a precision-gated MAC architecture for ECG filtering — X% power reduction at Y dB SNR cost, verified on [board]") gives a recipient something concrete to react to, far more effective than a generic "interested in VLSI" message.

---

## 11. Open decisions / next steps (where things currently stand)

1. **Highest priority:** draft IDF Part 1 for VIT's IPR Cell, using the precision-gated-MAC framing, scoped narrowly (Section 4.2/8.3), and get it moving — this is the actual critical-path item everything else depends on.
2. Get professor's read on past student IPAC approval precedent in this course, to calibrate expectations.
3. Finalize filter type: FIR (windowed) vs. adaptive/Wiener.
4. Finalize QRS/R-peak detection algorithm (must be hardware-cheap).
5. Real, full patent-database diligence (Google Patents/Espacenet/USPTO full-text) — only a general web search has been done so far.
6. Board/BOM finalization (Xilinx vs. Intel/Altera, ADC approach) — deliberately still deferred.

---

## 12. Related, separate project (context only — not part of this DSP project)

A separate course project exists for **BEEE305L Measurements and Instrumentation**: an automated MOSFET/BJT I-V curve tracer with DAQ (sweep circuit, current sensing, MCU-based ADC/DAC, Python control/plotting, calibration/error-analysis writeup). Mentioned here only in case it comes up in conversation — not detailed further, as it's a distinct project with its own scope.

---
*End of summary. If continuing this work with a new AI assistant, the single most useful next message is: "Help me draft IDF Part 1 for VIT's IPR Cell for this project" (see Section 8 and Section 11, item 1).*
