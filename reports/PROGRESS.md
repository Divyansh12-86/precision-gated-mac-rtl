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
  - `pg_top`: **1,394 LUTs, 417 FFs** (smashed target of $\le 1500$ LUTs, $\le 800$ FFs; down from 2,691 LUTs, 2,246 FFs).
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
  - `scripts/mutation_check.py`: 29 of 29 mandatory mutants caught (0 survived).
  - `sim/noise_sweep.py`: Characterized SNRs 24, 18, 12, 6, 0 dB across records 100, 103, 105. All 15 sweeps verified bit-exact on RTL (0 mismatches).
  - `sim/run_regression.py`: Executed comprehensive regression suite (**36 PASSED, 0 FAILED** standard, **50 PASSED, 0 FAILED** nightly).

---

## Phase 7: Round-2 Verification Hardening & Hardware Robustness [COMPLETED]

- **Date:** 2026-10-24
- **Evidence-Layer & Documentation Integrity:**
  - Removed all hard-coded/frozen summary logic in `sim/run_regression.py`. Summaries always generated dynamically with HEAD hash, tool versions, test list, and 0 wall-clock timestamps in tracked files.
  - Eliminated medical and clinical overclaim terminology across documentation.
  - Added `scripts/check_docs_numbers.py` ensuring zero drift between README/AGENTS documentation and reports JSON metrics.
  - Characterized Yosys 7-series LUT synthesis variability spread (1,376–1,402 LUTs, ±1.9%).
- **Hardware Robustness Hardening:**
  - `fpga/board_core.v`: Implemented 16-bit Power-On Reset (POR) counter, 2-flop metastability synchronizers on mode and pause inputs, 1 ms glitch rejection filter, and sample-tick mode latching.
  - `tb/tb_board_core.v`: Expanded test scenarios covering `por_replay`, `async_switch`, and `debounce_glitch`.
  - Mutation harness expanded to 29 mandatory mutants (MUT01–MUT29), catching all 29 mutants (0 survived, 0 build errors).
- **Signal & Noise Sweep Methodology:**
  - Injected noise strictly in the integer ADU domain before bit shifts, preserving the hardware invariant `(x & 31) == 0` for 100% of samples.
  - Characterized clean baseline references for identical 5,000-sample pipeline windows and computed delta activity metrics.
- **Unified Verification & Release Packaging:**
  - Rewrote `scripts/verify_all.py` (v2) with live re-runs, independent NumPy convolution bit-exact checks, and negative test verification.
  - Implemented `scripts/make_verification_bundle.py` producing self-contained verification bundles $\le 15$ MB.

---

## Phase 8: Round-3 Honesty Gap Closure, Default Hardware Parameters & Provenance Integrity [COMPLETED]

- **Date:** 2026-10-26
- **Phase 1: Truthful Headline Numbers & Legacy Allow-List (S1, S2, S5, S6):**
  - Re-anchored noise degradation statements to real integer ADU sweep metrics ($\le 6\text{ dB}$: 8.3%–9.7% datapath and 3.0%–4.0% whole-core savings; $+P$ drops to 28%–38% and gate-full duty increases to 58%).
  - Demarcated legacy `noise_stress` as non-comparable (post-scaling noise violating $(x \ \& \ 31) == 0$) and added strict allow-list `scripts/known_legacy_sets.txt`.
  - Updated QRS-region PRD claims to exact dynamic values ($0.000\% - 0.730\%$, min finite ratio $3.3\times$).
  - Full Yosys synthesis spread honestly characterized: 1.9% spread on `pg_top` and 9.0% wrapper variation between `top_basys3` and `top_nexys_a7`, attributing to ABC netlist naming/ordering heuristics without asserting unverified "purely".
  - Negative Test (X-05): Temporarily emptied `scripts/known_legacy_sets.txt` $\to$ `verify_all.py` check V-27 failed on `noise_stress`; restoring the entry passed.

- **Phase 2: Provenance Integrity & Verifier Hardening (S3, S4):**
  - Created `scripts/source_digest.py` computing canonical SHA256 over 60 tracked RTL/TB/script sources.
  - Hardened check V-25 to verify that every evidence JSON commit exists in git (`git cat-file -e <hash>^{commit}`) and that its `source_digest` matches current project sources.
  - Replaced `FRESH_CLONE_RUNNING` bypass with `--skip-fresh-clone-dependent` requiring `INSIDE_FRESH_CLONE_CHECK=1` or failing (X-09).
  - Negative Test 1 (X-10a): Corrupted 1 byte in `rtl/qrs_detector.v` $\to$ verifier failed on `source_digest` mismatch.
  - Negative Test 2 (X-10b): Deleted the nightly block from log $\to$ V-10 and V-20 failed.

- **Phase 3: Shipped Board-Core Default Hardware Simulation (S7):**
  - Added scenario `realparams` to `tb/tb_board_core.v` evaluating `dut_real` under 100% shipped default hardware parameters (`POR_CYCLES=65535`, `DEBOUNCE_CYCLES=100000`, 360 Hz pacing, 115200 baud). Verified 8 initial frames against golden model, 0.4 ms glitch rejection, and 1.5 ms reset re-synchronization.
  - Added mutants MUT30 (POR cycles) and MUT31 (debounce cycles) to `scripts/mutation_check.py`.
  - Mutation harness: **31 of 31 mutants CAUGHT** (0 survived, 0 build errors).
  - Updated `docs/RUN_ON_BOARD.md` (33 lines $\le 45$) documenting 1–2 sample mode switch latency.

- **Phase 4: Two-Stage Commit Sequence, Fresh Clone & Release Packaging:**
  - Stage 1 code commit: `570f492cc6738d4ec7f5bf2b3bd69a494748edcd`.
  - Stage 2 report commit: `613847ca9d9a8af2483c17ae7641b06e26a4fc5e` (touching only `reports/`).
  - Fresh clone check (`scripts/fresh_clone_check.sh`) passed in isolated `/tmp` directory with clean working tree, standard regression (37/37 PASS), nightly regression (53/53 PASS), and harness PASS.
  - Master harness `scripts/verify_all.py`: **27 PASSED, 0 FAILED, 0 SKIPPED**.
  - Generated `reports/RESULTS.pdf` (characterization deliverable).
  - Packaged final verification bundle: `verification_bundle_613847c.zip` (8.28 MB $\le 15$ MB, SHA256: `504a2a04...`) with `dirty: false`, `code_commit` = parent of `report_commit`, reproducible `content_hash_algorithm`, and all 12 command execution logs.

---

## Phase 9: Round-4 Final Pass — Dynamic Doc Checks, Strict Reachability & Ancestor Provenance [COMPLETED]

- **Date:** 2026-10-26
- **Code/Script Commit:** `066976ab061cd397ef136fb34f67130dce110dd9`
- **Source Digest:** `c270671c4e7a9ac8debbc8e26cd829393696cfbd3cff7db05289a0aac693b7f7` (61 tracked source files)
- **Hardened Documentation Validator (`scripts/check_docs_numbers.py` - D1, D3):**
  - Removed all hardcoded mutant numbers (`expected_m = 29`).
  - Dynamically extracts `total_mutants` (31), `caught` (31), and `survived` (0) from `reports/mutation.json`.
  - Dynamically extracts standard passed suites (37) from `reports/regress_summary.json` and nightly passed suites (53) from `reports/regress_summary_nightly.json`.
  - Enforces exact numbers across `README.md`, `AGENTS.md`, and `reports/RESULTS.md`.
  - Added strict regex scans rejecting stale mutant, suites, and regression counts.
- **Negative Test of D1 (D2):**
  - Temporarily corrupted `README.md` by replacing `"31 / 31 caught (0 survived)"` with `"21 / 21 caught (0 survived)"`.
  - Executed `python3 scripts/check_docs_numbers.py` $\to$ returned exit code 1 (`[DOCS_CHECK] FAILED with 2 mismatch(es)`: missing expected metric and wrong mutant count detected).
  - Restored `README.md` and re-executed `python3 scripts/check_docs_numbers.py` $\to$ returned exit code 0 (`[DOCS_CHECK] ALL DOCUMENTATION NUMBERS VALIDATED AND MATCH JSON (0 mismatches)`).
- **Strict Reachability & Ancestor Provenance (D4):**
  - Updated `scripts/verify_all.py` (V-25) and `scripts/make_verification_bundle.py` to replace `git cat-file -e` with `git merge-base --is-ancestor <commit> HEAD`.
  - Updated `scripts/source_digest.py` `get_git_commit()` to automatically return the parent code commit ancestor when HEAD is a report/docs-only commit.
  - Verified that all evidence artifacts in `reports/*.json` reference reachable ancestor commits and bit-exact source digests.
- **Evidence Verification (D5, D6, D7):**
  - `sim/run_regression.py` $\to$ **37 PASSED, 0 FAILED** (bit-exact on RTL).
  - `sim/run_regression.py --nightly` $\to$ **53 PASSED, 0 FAILED** (all 650,000-sample nightly runs passed with 0 mismatches).
  - `scripts/mutation_check.py` $\to$ **31 of 31 mutants CAUGHT** (0 survived, 0 build errors).
  - `scripts/verify_all.py` $\to$ **27 PASSED, 0 FAILED, 0 SKIPPED**.
- **Automated Summary & Benchmark Deliverables:**
  - `scripts/generate_benchmarks_and_summary.py`: generates `reports/BENCHMARKS.json` and `reports/REVIEW_SUMMARY.md` (`REVIEW_STATUS: READY`).

---

## Phase 10: Round-5 Self-Verifying Provenance & Integrity [COMPLETED]

- **Date:** 2026-10-26
- **Code Commit:** `a9b0fcd486f97a2f26a8af2fc65b3c9eada76119`
- **Canonical Source Digest:** `a6de0c9454d1dbe00fcc457bf1ea9c8ec14bdb3c1f1d93090d567a39e9422230` (61 tracked source files)
- **Provenance & Integrity Hardening (Z1, Z2, Z3, Z4, Z5):**
  - **Eliminated Internal Bundle Checksum:** Removed `bundle_sha256` from `reports/BENCHMARKS.json` and `reports/REVIEW_SUMMARY.md`. The archive SHA-256 is strictly emitted to an external sidecar `.sha256` file outside the zip (`verification_bundle_<hash>.zip.sha256`).
  - **Relabelled Legacy Noise Stress:** Formally labelled `noise_stress` as `legacy_noise_stress_not_comparable` in `reports/BENCHMARKS.json`.
  - **Fresh Clone Header Extraction:** Updated `scripts/fresh_clone_check.sh` to log both `HEAD commit: <hash>` and `SOURCE_DIGEST: <digest>`.
  - **Self-Verification Mode (`--verify`):** Implemented `--verify` in `scripts/make_verification_bundle.py` performing full member re-hashing against `manifest.json`, recomputing `bundle_content_sha256`, verifying ancestor reachability (`git merge-base --is-ancestor`), checking `dirty == False`, checking `code_commit` is parent of `report_commit`, and asserting absence of bundle hash inside internal files.
  - **Dynamic Review Integrity:** Updated `verify_all.py` (V-19, V-28) to cross-check exit codes against `evidence/*.txt`, verify ancestor reachability of fresh clone HEAD commit, verify `SOURCE_DIGEST` match, and assert `REVIEW_STATUS: READY` only when all checks pass.
- **Negative Testing of Verification Harness (Z7):**
  - **Negative Test (a) - Corrupted Zip Member Detection:**
    - Flipped one byte in `reports/BENCHMARKS.json` inside a copy of the bundle zip.
    - Executed `python3 scripts/make_verification_bundle.py --verify test_corrupt.zip`.
    - **Observed Result:** Exit code 1, failed with:
      `BUNDLE VERIFY: FAIL`
      `SHA256 mismatch in 2 file(s): ['reports/BENCHMARKS.json', 'reports/REVIEW_SUMMARY.md']`
      `bundle_content_sha256 mismatch: computed ... manifest has ...`
    - Removed test corrupted copy; restored clean state.
  - **Negative Test (b) - Premature REVIEW_STATUS: READY Conflict Detection:**
    - Forced one row in `reports/REVIEW_SUMMARY.md` to indicate a failure (`| check_v04 | ... | **FAIL** | ... |`) while keeping `REVIEW_STATUS: READY`.
    - Executed `python3 scripts/verify_all.py`.
    - **Observed Result:** Exit code 1, check V-28 failed with:
      `[V-28] FAIL: Conflict: REVIEW_STATUS is READY but failing evidence/table row detected! Row: check_v04 | ... | **FAIL**`
    - Restored `reports/REVIEW_SUMMARY.md`; re-executed `verify_all.py` $\to$ passed check V-28.
  - **Negative Test (c) - Non-Ancestor Fresh Clone Commit Rejection:**
    - Modified `reports/fresh_clone.log` to claim a non-ancestral fictitious commit: `HEAD commit: deadbeef0123456789abcdef0123456789abcdef`.
    - Executed `python3 scripts/verify_all.py`.
    - **Observed Result:** Exit code 1, check V-19 failed with:
      `[V-19] FAIL: Fresh clone commit 'deadbeef0123456789abcdef0123456789abcdef' is not an ancestor of HEAD`
    - Restored `reports/fresh_clone.log`; check restored.
- **Full Verification Suite on Code Commit `a9b0fcd` (Z6, Z8):**
  - `git diff --stat a1a8f6d HEAD -- rtl fpga tb sim/*.py coeffs.mem ecg_rom.mem data/test_vectors`: **0 lines changed (strictly empty)**.
  - Standard regression: **37 PASSED, 0 FAILED**.
  - Nightly regression: **53 PASSED, 0 FAILED**.
  - Mutation testing: **31 of 31 caught (0 survived, 0 build errors)**.

---

## Phase 11: Round-6 Complete Evidence, Live Viewer v2, and Offline Verification [COMPLETED]

- **Date:** 2026-10-29
- **Code Commit:** `a282469bf955d71ff8b7ffb8b8801353824af50c`
- **Report Commit:** `9142d086d4d3d5dc278ee3c5887418c2ccb8cb81`
- **Canonical Source Digest:** `5e2a89f7e5426b5a41419fcbc8385bce4cebddc13ccb29d3b0cefda40712a0da`
- **Viewer-v2 Addendum & Visual Demonstrator:**
  - Integrated `scripts/ecg_live_viewer.py` byte-identical (`sha256: 38689b90bf02017317d9313c8b8d854bceac112150b2886ebf59f50c2868ea94`).
  - Implemented 12/12 passing selftest suite (`scripts/ecg_live_viewer.py --selftest`).
  - Added headless snapshot generation (`scripts/run_viewer_snapshots.py`) yielding 4 publication-grade figures in `reports/figs/` (`viewer_rtl_dump.png`, `viewer_sim_auto.png`, `viewer_sim_full.png`, `viewer_sim_approx.png`, all 1496x902 px, > 200 kB).
  - Bit-exact hardware replay verified against real RTL UART dump `reports/board_uart_dump.bin` (4,949 frames, 0 mismatches).
- **Synthetic Noisy Demo Dataset (`demo_noisy_100`):**
  - Generated 60,000-sample dataset `data/test_vectors/demo_noisy_100` and `ecg_rom_demo_noisy.mem` (`make demo-rom`).
  - Conforms strictly to ADC structure with 11-bit alignment: `(x & 31) == 0` for 100% of samples (60,000/60,000).
  - Detector performance: Sensitivity = 100.00% (target $\ge 99\%$), Positive Predictivity = 98.58% (target $\ge 90\%$).
- **Filter Frequency Response Characterization:**
  - Implemented `scripts/filter_response.py` computing 8192-point FFT on `coeffs.mem`.
  - Frequency response: Kaiser $\beta = 14$, 51 taps, DC gain 1.029, -3 dB at 16.57 Hz, -6 dB at 20.04 Hz, -22.56 dB at 30 Hz.
  - Honestly documented filter as low-pass smoothing; logged OPEN DECISION FOR THE USER in `reports/DECISIONS.md`.
- **Complete Evidence Package & Dynamic Review Summary:**
  - Master harness (`scripts/verify_all.py`): **30 PASSED, 0 FAILED, 0 SKIPPED** out of 30 criteria.
  - Standard regression: **39 PASSED, 0 FAILED** (bit-exact on RTL).
  - Nightly regression: **55 PASSED, 0 FAILED** (all 650,000-sample nightly runs passed with 0 mismatches).
  - Mutation testing: **31 of 31 caught (0 survived, 0 build errors)**.
  - Full evidence suite (14 files in `evidence/`): `regression_standard.txt`, `regression_nightly.txt`, `mutation.txt`, `synth.txt`, `activity.txt`, `noise.txt`, `vivado_compat.txt`, `verify_all.txt`, `uart_selftest.txt`, `fresh_clone.txt`, `independent_checks.txt`, `viewer_selftest.txt`, `viewer_snapshot.txt`, `filter_response.txt`.
- **Negative Testing of Verification Harness (A-04):**
  - **Negative Test (a) - Corrupted Zip Member Detection:**
    - Flipped one byte in `reports/BENCHMARKS.json` inside a copy of the bundle zip.
    - Executed `python3 scripts/make_verification_bundle.py --verify test_corrupt.zip`.
    - **Observed Result:** Exit code 1, failed with `BUNDLE VERIFY: FAIL`, naming `SHA256 mismatch in 2 file(s): ['reports/BENCHMARKS.json', 'reports/REVIEW_SUMMARY.md']`.
  - **Negative Test (b) - Corrupted Parent Hash in git/parents.txt:**
    - Modified parent hash in `git/parents.txt` inside a bundle copy to a non-matching commit hash.
    - Executed `python3 scripts/make_verification_bundle.py --verify test_corrupt_parents.zip`.
    - **Observed Result:** Exit code 1, failed with `code_commit ... is not the parent of report_commit ... in git/parents.txt`.
  - **Negative Test (c) - Corrupted Count in REVIEW_SUMMARY.md:**
    - Modified a test pass count in `reports/REVIEW_SUMMARY.md` inside a bundle copy.
    - Executed `python3 scripts/make_verification_bundle.py --verify test_corrupt_summary.zip`.
    - **Observed Result:** Exit code 1, failed with `SHA256 mismatch in 1 file(s): ['reports/REVIEW_SUMMARY.md']` and content hash mismatch.
  - **Negative Test (d) - Corrupted Viewer Implementation in scripts/ecg_live_viewer.py:**
    - Corrupted `feed()` implementation in `scripts/ecg_live_viewer.py` to return an empty frame list.
    - Executed `python3 scripts/ecg_live_viewer.py --selftest` and `python3 scripts/verify_all.py`.
    - **Observed Result:** `ecg_live_viewer.py --selftest` exited with code 1, and `verify_all.py` failed check V-30 with `[V-30] FAIL: Viewer selftest failed with code 1`.


