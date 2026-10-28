# Round-6 Verification & Review Summary

**Code Commit:** `a282469bf955d71ff8b7ffb8b8801353824af50c`  
**Report Commit:** `d8e16976f8953a2c7918df544e011da2f1fb794b`  
**Source Digest:** `5e2a89f7e5426b5a41419fcbc8385bce4cebddc13ccb29d3b0cefda40712a0da`  
**Bundle Name:** `verification_bundle_d8e1697.zip`  

## Verification Matrix (Criteria D1 – D8)

| Check ID | Command | Result | Evidence File | Commit |
|---|---|:---:|---|---|
| **D1** | `python3 scripts/check_docs_numbers.py` | **PASS** | `evidence/check_docs_numbers.txt` | `a282469` |
| **D2** | Negative test of D1 (temporary corruption check) | **PASS** | `reports/PROGRESS.md` | `a282469` |
| **D3** | Stale string absence check across README.md, AGENTS.md, reports/*.md | **PASS** | `README.md`, `AGENTS.md`, `reports/RESULTS.md` | `a282469` |
| **D4** | Provenance & reachability check (`git merge-base --is-ancestor`) | **PASS** | `reports/*.json`, `evidence/*.txt` | `a282469` |
| **D5** | `python3 sim/run_regression.py` (39 passed) & `--nightly` (55 passed) | **PASS** | `evidence/regression_standard.txt`, `evidence/regression_nightly.txt` | `a282469` |
| **D6** | `python3 scripts/mutation_check.py` (31 caught, 0 survived) | **PASS** | `evidence/mutation.txt` | `a282469` |
| **D7** | `python3 scripts/verify_all.py` (30/30 PASSED, 0 SKIPPED) | **PASS** | `evidence/verify_all.txt`, `evidence/fresh_clone.txt` | `a282469` |
| **D8** | `python3 scripts/make_verification_bundle.py --run-checks --nightly --fresh-clone` | **PASS** | `evidence/fresh_clone.txt`, `verification_bundle_d8e1697.zip` | `d8e1697` |

---

## Disclosures & Limitations

1. **Silicon Hardware Programming:** NOT RUN (requires physical FPGA board connection).
2. **Extended MIT-BIH Records (`ext_*`):** NOT RUN (offline environment; standard 4 records 100, 101, 103, 105 fully characterized).
3. **Vivado Timing & Vectorless Power:** NOT RUN (proprietary Vivado not in toolchain; out-of-context synthesis scripts provided in `scripts/synth_vivado_ooc.tcl`).
4. **PhysioNet NSTDB Muscle Artifact (`demo_ma_100`):** NOT RUN (no network / offline self-contained bundle policy).

---

REVIEW_STATUS: READY
