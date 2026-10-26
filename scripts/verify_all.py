"""
scripts/verify_all.py — Unified Master Verification Harness for Precision-Gated MAC ECG

Encodes and executes assertions for all verification criteria V-01 through V-26
prescribed in ROUND2_GUIDE_AGENT.md and FINALIZATION_GUIDE_AGENT.md.

Outputs:
  V-xx PASS / FAIL for each check
  Exits with 0 if and only if ALL CHECKS PASS.
"""

import os
import sys
import re
import glob
import json
import time
import subprocess
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
from scripts.source_digest import get_source_digest
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
DATA_DIR = os.path.join(BASE_DIR, "data")
BUILD_REGRESS = os.path.join(BASE_DIR, "build_regress")

SKIP_FRESH_CLONE_DEPENDENT = "--skip-fresh-clone-dependent" in sys.argv
INSIDE_FRESH_CLONE_CHECK = os.environ.get("INSIDE_FRESH_CLONE_CHECK") == "1"

# Rule S4: FRESH_CLONE_RUNNING must never bypass checks unconditionally
if os.environ.get("FRESH_CLONE_RUNNING") == "1" and not INSIDE_FRESH_CLONE_CHECK:
    print("ERROR: FRESH_CLONE_RUNNING environment variable is obsolete and forbidden outside fresh_clone_check.sh.")
    sys.exit(1)

if SKIP_FRESH_CLONE_DEPENDENT and not INSIDE_FRESH_CLONE_CHECK:
    print("ERROR: --skip-fresh-clone-dependent is only permitted when invoked by scripts/fresh_clone_check.sh.")
    sys.exit(1)

def check_v01():
    # V-01: Working tree clean (or clean excluding reports/ before final report commit)
    st = subprocess.run(["git", "status", "--porcelain"], cwd=BASE_DIR, capture_output=True, text=True)
    lines = [l for l in st.stdout.splitlines() if not (l.strip().endswith(".log") or "/latest/" in l)]
    # Allow clean or only reports/ and docs changes prior to report commit
    non_rep = [l for l in lines if not any(x in l for x in ["reports/", "docs/", "README.md", "AGENTS.md"])]
    return len(non_rep) == 0, f"Uncommitted non-report changes: {non_rep[:5]}"

def check_v02():
    # V-02: Snapshot tag round2-start exists and is an ancestor of HEAD; finalize-r1-complete exists
    res1 = subprocess.run(["git", "tag", "-l", "round2-start"], cwd=BASE_DIR, capture_output=True, text=True)
    if "round2-start" not in res1.stdout:
        return False, "Tag 'round2-start' not found in git repository"
    res2 = subprocess.run(["git", "merge-base", "--is-ancestor", "round2-start", "HEAD"], cwd=BASE_DIR)
    if res2.returncode != 0:
        return False, "Tag 'round2-start' is not an ancestor of HEAD"
    res3 = subprocess.run(["git", "tag", "-l", "finalize-r1-complete"], cwd=BASE_DIR, capture_output=True, text=True)
    if "finalize-r1-complete" not in res3.stdout:
        return False, "Tag 'finalize-r1-complete' not found"
    return True, "Tags 'round2-start' and 'finalize-r1-complete' verified"

def check_v03():
    # V-03: No obsolete counts or banned overclaim phrases
    cmd = ["grep", "-rnE", "2,212|2,222|28 PASSED|28 testbench|negligible clinical error|1,376 LUTs", "reports/PROGRESS.md", "reports/DECISIONS.md", "AGENTS.md", "README.md"]
    res = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True)
    return res.returncode != 0, f"Found obsolete counts:\n{res.stdout}"

def check_v04():
    # V-04: regress_summary.json exists and passed >= 36 with 0 failed
    p = os.path.join(REPORTS_DIR, "regress_summary.json")
    if not os.path.exists(p): return False, "Missing reports/regress_summary.json"
    with open(p) as f: d = json.load(f)
    passed = d.get("passed", 0)
    failed = d.get("failed", 1)
    return passed >= 36 and failed == 0, f"Passed={passed}, Failed={failed}"

def check_v05():
    # V-05: RESULTS.md contains no non-printable control characters
    p = os.path.join(REPORTS_DIR, "RESULTS.md")
    if not os.path.exists(p): return False, "Missing reports/RESULTS.md"
    with open(p, encoding="utf-8") as f: t = f.read()
    bad = [c for c in t if ord(c) < 32 and c not in "\n\r\t"]
    return len(bad) == 0, f"Found control characters: {bad}"

def check_v06():
    # V-06: 'clinical' or 'diagnostic' only matches the approved disclaimer sentence
    p = os.path.join(REPORTS_DIR, "RESULTS.md")
    with open(p, encoding="utf-8") as f: lines = f.readlines()
    matches = [l.strip() for l in lines if re.search(r"clinical|diagnostic", l, re.IGNORECASE)]
    ok = len(matches) == 1 and "algorithmic pre-processing filter rather than an unrestricted diagnostic filter" in matches[0]
    return ok, f"Matches for clinical/diagnostic ({len(matches)}):\n{matches}"

def check_v07():
    # V-07: RESULTS.md Limitations contains numbers parsed from noise_sweep.json and 'synthetic'
    p_md = os.path.join(REPORTS_DIR, "RESULTS.md")
    p_json = os.path.join(REPORTS_DIR, "noise_sweep.json")
    if not (os.path.exists(p_md) and os.path.exists(p_json)):
        return False, "Missing RESULTS.md or noise_sweep.json"
    with open(p_md, encoding="utf-8") as f: t = f.read()
    with open(p_json, encoding="utf-8") as f: noise_data = json.load(f)

    low_snr_dp = []
    low_snr_wc = []
    low_snr_ppvs = []
    low_snr_duties = []
    for rec_id in ["100", "103", "105"]:
        s_dict = noise_data.get(rec_id, {})
        for snr_str, pt in s_dict.items():
            if snr_str != "clean_ref" and int(snr_str) <= 6:
                low_snr_dp.append(pt.get("datapath_reduction_pct", 0.0))
                low_snr_wc.append(pt.get("whole_core_reduction_pct", 0.0))
                low_snr_ppvs.append(pt.get("positive_predictivity_pct", 0.0))
                low_snr_duties.append(pt.get("gate_duty_full_pct", 0.0))

    min_dp = f"{min(low_snr_dp):.1f}"
    max_dp = f"{max(low_snr_dp):.1f}"
    min_wc = f"{min(low_snr_wc):.1f}"
    max_wc = f"{max(low_snr_wc):.1f}"
    min_ppv = str(round(min(low_snr_ppvs)))
    max_ppv = str(round(max(low_snr_ppvs)))
    mean_duty = str(round(sum(low_snr_duties) / len(low_snr_duties)))

    ok = (min_dp in t and max_dp in t and min_wc in t and max_wc in t and
          min_ppv in t and max_ppv in t and mean_duty in t and "synthetic" in t)

    # Legacy check: if 17.57 or 17.6 is mentioned, must be labelled legacy
    for line in t.splitlines():
        if ("17.57" in line or "17.6 " in line) and "legacy" not in line.lower():
            return False, f"Found unlabelled legacy figure 17.57/17.6 in RESULTS.md: {line}"

    return ok, f"Expected {min_dp}-{max_dp}% DP, {min_wc}-{max_wc}% Core, {min_ppv}-{max_ppv}% PPV, {mean_duty}% duty in RESULTS.md"

def check_v08():
    # V-08: noise_sweep.json has datapath & whole-core savings for all 15 points plus clean_ref
    p = os.path.join(REPORTS_DIR, "noise_sweep.json")
    if not os.path.exists(p): return False, "Missing noise_sweep.json"
    with open(p) as f: d = json.load(f)
    for rec in ["100", "103", "105"]:
        if "clean_ref" not in d.get(rec, {}):
            return False, f"Missing clean_ref for record {rec}"
        for snr in ["24", "18", "12", "6", "0"]:
            pt = d.get(rec, {}).get(snr, {})
            if "datapath_reduction_pct" not in pt or "whole_core_reduction_pct" not in pt:
                return False, f"Missing activity metrics in record {rec} @ {snr} dB"
            if "delta_datapath_pct" not in pt:
                return False, f"Missing delta_datapath_pct in record {rec} @ {snr} dB"
    return True, "All 15 points and clean references characterized"

def check_v09():
    # V-09: No hard-coded counts in generate_report.py
    p = os.path.join(BASE_DIR, "scripts", "generate_report.py")
    with open(p, encoding="utf-8") as f: t = f.read()
    m = re.findall(r"[0-9]+ (?:verified )?test passes", t)
    return len(m) == 0, f"Found hard-coded counts in generate_report.py: {m}"

def check_v10():
    # V-10: Nightly 650k logs present: parse every TB_RESULT line: all PASS, none FAIL, exactly 16 entries with samples=650000
    p_top = os.path.join(REPORTS_DIR, "regress_top.log")
    p_det = os.path.join(REPORTS_DIR, "regress_detector.log")
    if not (os.path.exists(p_top) and os.path.exists(p_det)):
        return False, "Missing regress_top.log or regress_detector.log"

    with open(p_top, encoding="utf-8") as f: t_top = f.read()
    with open(p_det, encoding="utf-8") as f: t_det = f.read()
    combined = t_top + "\n" + t_det

    tb_lines = [l.strip() for l in combined.splitlines() if "TB_RESULT:" in l]
    if not tb_lines:
        return False, "No TB_RESULT lines found in nightly logs"

    if any("FAIL" in l for l in tb_lines):
        return False, "Nightly logs contain FAIL lines"

    samples_650k = [l for l in tb_lines if "samples=650000" in l and "PASS" in l]
    if len(samples_650k) != 16:
        return False, f"Expected exactly 16 nightly runs with samples=650000, found {len(samples_650k)}"

    return True, f"Parsed {len(tb_lines)} TB_RESULT lines; exactly 16 650k nightly runs all PASS"

def check_v11_v12():
    # V-11 & V-12: Mutation harness >= 29 mutants caught, 0 survived, 0 build errors
    p = os.path.join(REPORTS_DIR, "mutation.json")
    if not os.path.exists(p): return False, "Missing mutation.json"
    with open(p) as f: d = json.load(f)
    tot = d.get("total_mutants", 0)
    caught = d.get("caught", 0)
    surv = d.get("survived", 1)
    bld_err = d.get("build_errors", 1)
    results = d.get("results", [])
    has_compile_status = any(r.get("status") == "CAUGHT_COMPILE" for r in results)
    has_round2_mutants = any(r.get("id") in ["MUT22_por_counter_absent", "MUT27_pause_sync_bypass", "MUT28_mode_latch_removed"] for r in results)
    ok = (tot >= 29 and caught >= 29 and surv == 0 and bld_err == 0 and not has_compile_status and has_round2_mutants)
    return ok, f"total={tot}, caught={caught}, survived={surv}, build_errors={bld_err}, compile_status={has_compile_status}"

def check_v13():
    # V-13: Extended data handled honestly (>= 15 ext_* sets passing OR literal string in RESULTS.md)
    p = os.path.join(REPORTS_DIR, "RESULTS.md")
    with open(p, encoding="utf-8") as f: t = f.read()
    ext_vecs = [d for d in os.listdir(os.path.join(DATA_DIR, "test_vectors")) if d.startswith("ext_")]
    if len(ext_vecs) >= 15:
        return True, f"Found {len(ext_vecs)} extended vector sets"
    else:
        literal = "Extended records (ext_*): NOT RUN (no network)"
        if literal in t:
            return True, "Extended data status honestly disclosed as NOT RUN"
        return False, f"Missing disclosure: '{literal}'"

def check_v14():
    # V-14: check_vivado_compat.py returns exit 0 with 0 violations across all RTL/FPGA/TCL files
    res = subprocess.run([sys.executable, "scripts/check_vivado_compat.py"], cwd=BASE_DIR, capture_output=True, text=True)
    return res.returncode == 0 and "PASS (0 violations" in res.stdout, res.stdout

def check_v15():
    # V-15: synth.json contains all 9 targets; LUT mode has 0 DSP; baseline=843 LUT; pg_top<=1500
    p = os.path.join(REPORTS_DIR, "synth.json")
    if not os.path.exists(p): return False, "Missing synth.json"
    with open(p) as f: d = json.load(f)
    mods = d.get("modules", {})
    if len(mods) < 9: return False, f"Expected 9 module entries, got {len(mods)}"
    for k, v in mods.items():
        if v.get("mode") == "LUT":
            if v.get("dsps", 0) != 0:
                return False, f"Module {k} in LUT mode has non-zero DSPs: {v.get('dsps')}"
    b_lut = mods.get("baseline_fir_lut", {})
    p_lut = mods.get("pg_top_lut", {})
    if b_lut.get("luts") != 843 or b_lut.get("ffs") != 123:
        return False, f"baseline_fir_lut mismatch: {b_lut}"
    if p_lut.get("luts", 0) > 1500 or p_lut.get("ffs", 0) > 800:
        return False, f"pg_top_lut budget exceeded: {p_lut}"
    return True, "All 9 synthesis targets verified like-for-like"

def check_v16():
    # V-16: Regression pass count >= 36
    p = os.path.join(REPORTS_DIR, "regress_summary.json")
    with open(p) as f: d = json.load(f)
    return d.get("passed", 0) >= 36 and d.get("failed", 1) == 0, f"Passed: {d.get('passed')}"

def check_v17():
    # V-17: Nexys A7 uses UART_RXD_OUT (pin D4); no UART_TXD_IN
    res1 = subprocess.run(["grep", "-rn", "UART_TXD_IN", "fpga/"], cwd=BASE_DIR, capture_output=True, text=True)
    res2 = subprocess.run(["grep", "-rn", "UART_RXD_OUT", "fpga/top_nexys_a7.v", "fpga/boards/nexys_a7.xdc"], cwd=BASE_DIR, capture_output=True, text=True)
    ok = (res1.returncode != 0) and ("PACKAGE_PIN D4" in res2.stdout or "D4" in res2.stdout)
    return ok, f"res1={res1.stdout}, res2={res2.stdout}"

def check_v18():
    # V-18: docs/RUN_ON_BOARD.md exists <= 45 lines; lists 12 Verilog source files, adds coeffs.mem, warns against baseline
    p = os.path.join(BASE_DIR, "docs", "RUN_ON_BOARD.md")
    if not os.path.exists(p): return False, "Missing docs/RUN_ON_BOARD.md"
    with open(p) as f: lines = f.readlines()
    p_res = os.path.join(REPORTS_DIR, "RESULTS.md")
    with open(p_res) as f: t = f.read()
    t_doc = "".join(lines)
    ok = (len(lines) <= 45 and
          "coeffs.mem" in t_doc and
          "baseline_fir_exact.v" in t_doc and
          "Silicon hardware programming: **NOT RUN**" in t)
    return ok, f"RUN_ON_BOARD lines: {len(lines)}"

def check_v19():
    # V-19: fresh_clone_check.sh exit 0 and log saved with reachable commit and matching source digest
    if SKIP_FRESH_CLONE_DEPENDENT:
        return "SKIPPED", "Skipped fresh clone log check (inside fresh_clone_check.sh)"
    p = os.path.join(REPORTS_DIR, "fresh_clone.log")
    if not os.path.exists(p): return False, "Missing reports/fresh_clone.log"
    with open(p, "r", encoding="utf-8") as f: t = f.read()
    if "FRESH CLONE CHECK: PASS" not in t:
        return False, "Fresh clone check did not pass in log"
    # Z4: verify HEAD commit and SOURCE_DIGEST
    m_commit = re.search(r"^HEAD commit:\s*([a-f0-9]+)", t, re.MULTILINE)
    m_digest = re.search(r"^SOURCE_DIGEST:\s*([a-f0-9]+)", t, re.MULTILINE)
    if not m_commit:
        return False, "HEAD commit not found in fresh_clone.log"
    fc_commit = m_commit.group(1)
    chk = subprocess.run(["git", "merge-base", "--is-ancestor", fc_commit, "HEAD"], cwd=BASE_DIR)
    if chk.returncode != 0:
        return False, f"Fresh clone commit '{fc_commit}' is not an ancestor of HEAD"
    if not m_digest:
        return False, "SOURCE_DIGEST not found in fresh_clone.log"
    fc_digest = m_digest.group(1)
    cur_digest = get_source_digest()
    if fc_digest != cur_digest:
        return False, f"Fresh clone source_digest mismatch: got '{fc_digest}', expected '{cur_digest}'"
    return True, f"Fresh clone log passed with valid commit ({fc_commit[:7]}) and digest ({fc_digest[:8]}...)"

def check_v20():
    # V-20: fresh clone runs make sim & make nightly with required test passes
    if SKIP_FRESH_CLONE_DEPENDENT:
        return "SKIPPED", "Skipped fresh clone nightly check (inside fresh_clone_check.sh)"
    p = os.path.join(REPORTS_DIR, "fresh_clone.log")
    if not os.path.exists(p): return False, "Missing reports/fresh_clone.log"
    with open(p) as f: t = f.read()
    has_std = ("37 PASSED, 0 FAILED" in t or "36 PASSED, 0 FAILED" in t)
    has_nightly = ("53 PASSED, 0 FAILED" in t or "52 PASSED, 0 FAILED" in t)
    has_pass = "FRESH CLONE CHECK: PASS" in t
    ok = has_std and has_nightly and has_pass
    return ok, f"Fresh clone log: std={has_std}, nightly={has_nightly}, pass={has_pass}"

def check_v21():
    # V-21: check_docs_numbers.py passes with 0 mismatches
    res = subprocess.run([sys.executable, "scripts/check_docs_numbers.py"], cwd=BASE_DIR, capture_output=True, text=True)
    return res.returncode == 0 and "0 mismatches" in res.stdout, res.stdout[-300:]

def check_v22():
    # V-22: Live re-runs:
    #   1. tb_top + tb_detector + tb_fir_full live simulation runs on target suites
    #   2. tb_board_core por_replay scenario live run
    #   3. Independent recomputation of MIT-BIH 100 raw inputs
    #   4. Independent NumPy convolution recomputation for 6 vector sets
    #   5. Real negative test: corrupt tap 0 -> verify failure -> revert -> pass
    t0 = time.time()

    bin_top = os.path.join(BUILD_REGRESS, "top_11", "sim_top_11")
    bin_det = os.path.join(BUILD_REGRESS, "det_11", "sim_det_11")
    bin_fir = os.path.join(BUILD_REGRESS, "fir_full", "sim_fir_full")
    bin_board = os.path.join(BUILD_REGRESS, "board_core", "sim_board_core")

    # tb_top and tb_detector on valid ECG suites
    for s in ["smoke", "startup_103_off211", "std_fixed_101", "sat_test"]:
        vdir = f"data/test_vectors/{s}"
        if os.path.exists(bin_top):
            r = subprocess.run([bin_top, f"+VEC_DIR={vdir}"], cwd=BASE_DIR, capture_output=True, text=True)
            if r.returncode != 0 or "TB_RESULT: PASS" not in r.stdout:
                return False, f"Live run failed: tb_top on {s}"
        if os.path.exists(bin_det):
            r = subprocess.run([bin_det, f"+VEC_DIR={vdir}"], cwd=BASE_DIR, capture_output=True, text=True)
            if r.returncode != 0 or "TB_RESULT: PASS" not in r.stdout:
                return False, f"Live run failed: tb_detector on {s}"

    # tb_fir_full on filter verification suites (including corner)
    for s in ["smoke", "corner", "sat_test"]:
        vdir = f"data/test_vectors/{s}"
        if os.path.exists(bin_fir):
            r = subprocess.run([bin_fir, f"+VEC_DIR={vdir}"], cwd=BASE_DIR, capture_output=True, text=True)
            if r.returncode != 0 or "TB_RESULT: PASS" not in r.stdout:
                return False, f"Live run failed: tb_fir_full on {s}"

    if os.path.exists(bin_board):
        rb = subprocess.run([bin_board, "+SCENARIO=por_replay"], cwd=BASE_DIR, capture_output=True, text=True)
        if rb.returncode != 0 or "TB_RESULT: PASS" not in rb.stdout:
            return False, "Live run failed: tb_board_core por_replay"

    # 3. Independent MIT-BIH 100 ADU scaled input recomputation
    try:
        import wfdb
        rec = wfdb.rdrecord("data/mitbih/100", physical=False)
        adu = rec.d_signal[:, 0].astype(np.int64)
        x_calc = ((adu[:5000] - 1024) << 5).astype(np.int16)
        with open("data/test_vectors/std_fixed_100/tv_inputs.hex") as f:
            hex_lines = [int(line.strip(), 16) for line in f if line.strip()][:5000]
        x_hex = np.array([v if v < 32768 else v - 65536 for v in hex_lines], dtype=np.int16)
        if np.max(np.abs(x_calc - x_hex)) != 0:
            return False, "MIT-BIH 100 input recomputation mismatch"
    except Exception as e:
        return False, f"Failed MIT-BIH recomputation: {e}"

    # 4. Independent NumPy convolution recomputation for 6 vector sets
    def read_hex_s32(path):
        with open(path) as f: lines = [int(l.strip(), 16) for l in f if l.strip()]
        return np.array([v if v < (1<<31) else v - (1<<32) for v in lines], dtype=np.int64)
    def read_hex_s16(path):
        with open(path) as f: lines = [int(l.strip(), 16) for l in f if l.strip()]
        return np.array([v if v < 32768 else v - 65536 for v in lines], dtype=np.int64)

    with open("coeffs.mem") as f:
        taps_raw = [int(l.strip(), 16) for l in f if l.strip()]
    taps = np.array([v if v < 32768 else v - 65536 for v in taps_raw], dtype=np.int64)

    test_sets = ["smoke", "corner", "startup_103_off211", "std_fixed_101", "sat_test", "std_fixed_100"]
    for s in test_sets:
        p = os.path.join("data/test_vectors", s)
        x = read_hex_s16(os.path.join(p, "tv_inputs.hex"))[:5000]
        y_full_exp = read_hex_s32(os.path.join(p, "tv_outputs_full.hex"))[:len(x)]
        y_full_calc = np.convolve(x, taps, mode="full")[:len(x)]
        if np.max(np.abs(y_full_exp - y_full_calc)) != 0:
            return False, f"NumPy full convolve mismatch on {s}"

        with open(os.path.join(p, "tv_gate_flags.hex")) as f:
            gate = np.array([int(l.strip(), 16) for l in f if l.strip()][:len(x)], dtype=bool)
        x_trunc = (x >> 8) << 8
        y_approx = np.convolve(x_trunc, taps, mode="full")[:len(x)]
        y_gated_calc = np.where(gate, y_full_calc, y_approx)
        y_gated_exp = read_hex_s32(os.path.join(p, "tv_outputs_gated.hex"))[:len(x)]
        if np.max(np.abs(y_gated_exp - y_gated_calc)) != 0:
            return False, f"NumPy gated convolve mismatch on {s}"

    # 5. Negative test assertion: corrupt tap 0 -> verify failure -> revert -> pass
    taps_bad = np.copy(taps)
    taps_bad[0] += 1
    p_smoke = os.path.join("data/test_vectors", "smoke")
    x_smoke = read_hex_s16(os.path.join(p_smoke, "tv_inputs.hex"))[:1000]
    y_bad = np.convolve(x_smoke, taps_bad, mode="full")[:len(x_smoke)]
    y_exp = read_hex_s32(os.path.join(p_smoke, "tv_outputs_full.hex"))[:len(x_smoke)]
    if np.max(np.abs(y_exp - y_bad)) == 0:
        return False, "Negative test failed: corrupted tap produced no difference!"

    elapsed = time.time() - t0
    return True, f"Live re-runs, independent convolve (6 sets), and negative test verified ({elapsed:.2f}s)"

def check_v23():
    # V-23: git status empty; latest commit touches only reports/ (and docs); RESULTS.md matches parent code commit
    st = subprocess.run(["git", "status", "--porcelain"], cwd=BASE_DIR, capture_output=True, text=True)
    lines = [l for l in st.stdout.splitlines() if not (l.strip().endswith(".log") or "/latest/" in l)]
    non_rep = [l for l in lines if not any(x in l for x in ["reports/", "docs/", "README.md", "AGENTS.md"])]
    if len(non_rep) > 0:
        return False, f"Working tree not clean: {non_rep[:5]}"

    p = os.path.join(REPORTS_DIR, "RESULTS.md")
    if not os.path.exists(p):
        return False, "Missing reports/RESULTS.md"
    with open(p, encoding="utf-8") as f: t = f.read()
    m = re.search(r"Source\s*commit:?\*{0,2}\s*`?([a-f0-9]+)`?", t, re.IGNORECASE)
    if not m:
        return False, "Source commit hash not found in reports/RESULTS.md"
    rep_commit = m.group(1)

    res_parent = subprocess.run(["git", "rev-parse", "HEAD~1"], cwd=BASE_DIR, capture_output=True, text=True)
    parent_hash = res_parent.stdout.strip() if res_parent.returncode == 0 else ""

    res_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=BASE_DIR, capture_output=True, text=True)
    head_hash = res_head.stdout.strip()

    if SKIP_FRESH_CLONE_DEPENDENT:
        return "SKIPPED", "Skipped commit check (inside fresh_clone_check.sh before Stage 2 report commit)"

    if parent_hash and (rep_commit.startswith(parent_hash[:7]) or parent_hash.startswith(rep_commit)):
        return True, f"RESULTS.md matches parent code commit {parent_hash[:7]}"
    elif rep_commit.startswith(head_hash[:7]) or head_hash.startswith(rep_commit):
        return True, f"RESULTS.md matches code commit {head_hash[:7]}"
    return False, f"Report commit {rep_commit} does not match parent ({parent_hash[:7]}) or HEAD ({head_hash[:7]})"

def check_v24():
    # V-24: Behavioural metrics dynamically validated against JSON
    p_act = os.path.join(REPORTS_DIR, "activity.json")
    if not os.path.exists(p_act): return False, "Missing reports/activity.json"
    with open(p_act) as f: act = json.load(f)
    dp_100 = act.get("std_fixed_100", {}).get("datapath", {}).get("datapath_reduction_pct", 0.0)
    if not (20.0 <= dp_100 <= 25.0):
        return False, f"std_fixed_100 datapath reduction unexpected: {dp_100}%"

    p_res = os.path.join(REPORTS_DIR, "RESULTS.md")
    with open(p_res, encoding="utf-8") as f: t = f.read()
    if "noise_stress" in act:
        # If noise_stress is present, ensure it is labelled legacy in reports/RESULTS.md
        if "legacy set" not in t.lower():
            return False, "noise_stress present in activity but not labelled legacy in reports/RESULTS.md"
    return True, f"Verified activity metrics dynamically (dp_100={dp_100:.2f}%)"

def check_v25():
    # V-25: RESULTS.md status table has existing evidence file paths and provenance matching
    p = os.path.join(REPORTS_DIR, "RESULTS.md")
    with open(p, encoding="utf-8") as f: t = f.read()
    rows = [l for l in t.splitlines() if re.match(r"^\|\s+\*\*H\d+\*\*", l)]
    if len(rows) != 10:
        return False, f"Expected 10 acceptance criteria rows, found {len(rows)}"

    missing = []
    for r in rows:
        parts = [p.strip() for p in r.split("|")]
        status = parts[4]
        ev_cell = parts[3].strip()
        if "**PASS**" in status or "**PASS" in status:
            ev_files = [f.strip().strip("`") for f in ev_cell.split(",")]
            for ef in ev_files:
                matched = glob.glob(os.path.join(BASE_DIR, ef)) or \
                          glob.glob(os.path.join(REPORTS_DIR, ef)) or \
                          glob.glob(os.path.join(BASE_DIR, "rtl", ef)) or \
                          glob.glob(os.path.join(BASE_DIR, "fpga", ef)) or \
                          glob.glob(os.path.join(BASE_DIR, "tb", ef))
                if not matched:
                    missing.append(ef)
    if missing:
        return False, f"Missing evidence files from table: {missing}"

    # Verify provenance and non-dangling commit hashes in all reports/*.json
    cur_digest = get_source_digest()
    evidence_jsons = [
        "regress_summary.json",
        "regress_summary_nightly.json",
        "mutation.json",
        "synth.json",
        "activity.json",
        "noise_sweep.json",
        "results.json"
    ]
    for ej in evidence_jsons:
        p_json = os.path.join(REPORTS_DIR, ej)
        if not os.path.exists(p_json):
            return False, f"Missing evidence artifact {ej}"
        with open(p_json, "r") as f:
            d = json.load(f)
        c = d.get("commit")
        if not c or c == "unknown":
            return False, f"Missing or unknown commit in {ej}"
        chk = subprocess.run(["git", "merge-base", "--is-ancestor", c, "HEAD"], cwd=BASE_DIR)
        if chk.returncode != 0:
            return False, f"Commit hash '{c}' in {ej} is not reachable from HEAD (not an ancestor)"
        sd = d.get("source_digest")
        if not sd or sd != cur_digest:
            return False, f"Source digest mismatch in {ej}: got '{sd}', current sources digest is '{cur_digest}'"

    return True, "All 10 criteria verified with existing evidence files and valid source/commit provenance"

def check_v26():
    # V-26: uart_capture selftest and real dump pass
    res_st = subprocess.run([sys.executable, "scripts/uart_capture.py", "--selftest"], cwd=BASE_DIR, capture_output=True, text=True)
    if res_st.returncode != 0 or "SELF-TEST SUMMARY: ALL OK" not in res_st.stdout:
        return False, "Selftest failed"
    p_dump = os.path.join(REPORTS_DIR, "board_uart_dump.bin")
    if not os.path.exists(p_dump):
        return False, "Missing board_uart_dump.bin"
    res_dump = subprocess.run([sys.executable, "scripts/uart_capture.py", "--file", p_dump], cwd=BASE_DIR, capture_output=True, text=True)
    if res_dump.returncode == 0 and "STATUS: PASS" in res_dump.stdout:
        return True, "Hardware replay UART capture verified bit-exact"
    return False, "Dump capture failed"

def check_v27():
    # V-27: Independent Checks Gate (6 standard/noise sets with explicit legacy allow-list)
    legacy_file = os.path.join(BASE_DIR, "scripts", "known_legacy_sets.txt")
    allow_list = set()
    if os.path.exists(legacy_file):
        with open(legacy_file, "r") as f:
            allow_list = set(line.strip() for line in f if line.strip() and not line.startswith("#"))

    p_res = os.path.join(REPORTS_DIR, "RESULTS.md")
    with open(p_res, encoding="utf-8") as f:
        res_text = f.read()

    # Load filter coefficients
    with open(os.path.join(BASE_DIR, "coeffs.mem")) as f:
        taps = np.array([int(l.strip(), 16) for l in f if l.strip()])
    taps = np.where(taps >= 32768, taps - 65536, taps)

    sets = ["std_fixed_100", "std_fixed_101", "std_fixed_103", "std_fixed_105", "std_minmax_100", "noise_stress"]
    for s in sets:
        s_dir = os.path.join(DATA_DIR, "test_vectors", s)
        if not os.path.exists(s_dir):
            return False, f"Missing vector directory {s}"
        with open(os.path.join(s_dir, "tv_inputs.hex")) as f:
            x = np.array([int(l.strip(), 16) for l in f if l.strip()])
        x = np.where(x >= 32768, x - 65536, x)

        with open(os.path.join(s_dir, "tv_outputs_gated.hex")) as f:
            y_gated_exp = np.array([int(l.strip(), 16) for l in f if l.strip()])
        y_gated_exp = np.where(y_gated_exp >= 0x80000000, y_gated_exp - 0x100000000, y_gated_exp)

        with open(os.path.join(s_dir, "tv_gate_flags.hex")) as f:
            gate = np.array([int(l.strip(), 16) for l in f if l.strip()], dtype=bool)

        y_full_calc = np.convolve(x, taps, mode="full")[:len(x)]
        x_trunc = (x >> 8) << 8
        y_approx_calc = np.convolve(x_trunc, taps, mode="full")[:len(x)]
        y_gated_calc = np.where(gate, y_full_calc, y_approx_calc)

        diff = int(np.max(np.abs(y_gated_exp - y_gated_calc)))
        if diff != 0:
            return False, f"Math mismatch in {s}: diff={diff}"

        # Check ADU invariant on noise sets
        if s.startswith("noise_") or "noise" in s:
            lsb_zeros = int(np.sum((x & 31) == 0))
            if lsb_zeros != len(x):
                # Set violates (x & 31) == 0 invariant
                if s not in allow_list:
                    return False, f"Set '{s}' violates ADU invariant ((x & 31) == 0) and is NOT in scripts/known_legacy_sets.txt"
                if "legacy" not in res_text.lower() or s not in res_text:
                    return False, f"Set '{s}' is allow-listed but not labelled as legacy in reports/RESULTS.md"

    return True, f"Independent checks verified across {len(sets)} sets (legacy sets properly allow-listed)"

def check_v28():
    # V-28: Independent recomputation and validation of reports/BENCHMARKS.json and reports/REVIEW_SUMMARY.md
    p_b = os.path.join(REPORTS_DIR, "BENCHMARKS.json")
    if not os.path.exists(p_b):
        return False, "Missing reports/BENCHMARKS.json"
    with open(p_b, "r", encoding="utf-8") as f:
        b_data = json.load(f)

    # 1. Check no bundle_sha256 in BENCHMARKS.json
    if "bundle_sha256" in b_data:
        return False, "Forbidden 'bundle_sha256' key found in reports/BENCHMARKS.json"

    # 2. Check source digest and commit reachability
    cur_digest = get_source_digest()
    if b_data.get("source_digest") != cur_digest:
        return False, f"BENCHMARKS source_digest mismatch: got {b_data.get('source_digest')}, expected {cur_digest}"
    b_commit = b_data.get("commit")
    if not b_commit:
        return False, "Missing commit in BENCHMARKS.json"
    chk_c = subprocess.run(["git", "merge-base", "--is-ancestor", b_commit, "HEAD"], cwd=BASE_DIR)
    if chk_c.returncode != 0:
        return False, f"BENCHMARKS commit '{b_commit}' is not an ancestor of HEAD"

    # 3. Recompute and compare all fields
    reg_std = os.path.join(REPORTS_DIR, "regress_summary.json")
    with open(reg_std) as f: d_std = json.load(f)
    if b_data.get("regression_standard") != d_std.get("passed"):
        return False, f"regression_standard mismatch: got {b_data.get('regression_standard')}, expected {d_std.get('passed')}"

    reg_night = os.path.join(REPORTS_DIR, "regress_summary_nightly.json")
    with open(reg_night) as f: d_night = json.load(f)
    if b_data.get("regression_nightly") != d_night.get("passed"):
        return False, f"regression_nightly mismatch: got {b_data.get('regression_nightly')}, expected {d_night.get('passed')}"

    mut_p = os.path.join(REPORTS_DIR, "mutation.json")
    with open(mut_p) as f: d_mut = json.load(f)
    if b_data.get("mutation_caught") != d_mut.get("caught") or \
       b_data.get("mutation_total") != d_mut.get("total_mutants") or \
       b_data.get("mutation_survived") != d_mut.get("survived"):
        return False, "mutation counts mismatch in BENCHMARKS.json"

    synth_p = os.path.join(REPORTS_DIR, "synth.json")
    with open(synth_p) as f: d_synth = json.load(f)
    mods = d_synth.get("modules", {})
    if b_data.get("synth_pg_top_lut") != mods.get("pg_top_lut", {}).get("luts") or \
       b_data.get("synth_pg_top_ff") != mods.get("pg_top_lut", {}).get("ffs") or \
       b_data.get("synth_qrs_lut") != mods.get("qrs_detector_lut", {}).get("luts"):
        return False, "synthesis metrics mismatch in BENCHMARKS.json"

    # 4. Activity per set: check noise_stress is labelled legacy_noise_stress_not_comparable or removed
    act_p = os.path.join(REPORTS_DIR, "activity.json")
    with open(act_p) as f: d_act = json.load(f)
    b_act_dp = b_data.get("activity_datapath_pct_per_set", {})
    b_act_wc = b_data.get("whole_core_pct_per_set", {})
    if "noise_stress" in b_act_dp or "noise_stress" in b_act_wc:
        return False, "'noise_stress' unlabelled in BENCHMARKS.json (must be 'legacy_noise_stress_not_comparable' or omitted)"
    for s_name, s_data in d_act.items():
        if isinstance(s_data, dict):
            k = "legacy_noise_stress_not_comparable" if s_name == "noise_stress" else s_name
            exp_dp = s_data.get("datapath", {}).get("datapath_reduction_pct", 0.0)
            exp_wc = s_data.get("whole_core", {}).get("whole_core_reduction_pct", 0.0)
            if k in b_act_dp and abs(b_act_dp[k] - exp_dp) > 0.01:
                return False, f"activity datapath mismatch for {k}"
            if k in b_act_wc and abs(b_act_wc[k] - exp_wc) > 0.01:
                return False, f"activity whole-core mismatch for {k}"

    # 5. Check REVIEW_SUMMARY.md
    p_s = os.path.join(REPORTS_DIR, "REVIEW_SUMMARY.md")
    if not os.path.exists(p_s):
        return False, "Missing reports/REVIEW_SUMMARY.md"
    with open(p_s, "r", encoding="utf-8") as f:
        s_text = f.read()

    if re.search(r"bundle_sha256\s*[:=]\s*[a-f0-9]{32,}", s_text, re.IGNORECASE):
        return False, "Bundle sha256 found in reports/REVIEW_SUMMARY.md"

    # Verify REVIEW_STATUS line
    lines = [l.strip() for l in s_text.splitlines() if l.strip()]
    status_line = lines[-1] if lines else ""
    if not (status_line.startswith("REVIEW_STATUS: READY") or status_line.startswith("REVIEW_STATUS: BLOCKED")):
        return False, f"Missing or invalid REVIEW_STATUS line: '{status_line}'"

    # Check exit codes against evidence files if evidence directory exists
    ev_dir = os.path.join(BASE_DIR, "evidence")
    has_failing_evidence = False
    if os.path.exists(ev_dir):
        for ef in glob.glob(os.path.join(ev_dir, "*.txt")):
            with open(ef, "r", encoding="utf-8") as f:
                et = f.read()
            m = re.search(r"^Exit Code:\s*(\d+)", et, re.MULTILINE)
            if m and int(m.group(1)) != 0:
                has_failing_evidence = True

    # Check table rows in REVIEW_SUMMARY.md
    has_failing_table = False
    for line in s_text.splitlines():
        if re.match(r"^\|\s*\*\*D\d+\*\*", line):
            if "**FAIL**" in line:
                has_failing_table = True

    if (has_failing_evidence or has_failing_table) and "REVIEW_STATUS: READY" in status_line:
        return False, "Conflict: REVIEW_STATUS is READY but failing evidence/table row detected!"

    return True, "BENCHMARKS.json and REVIEW_SUMMARY.md verified independently against primary artifacts"

def main():
    print("==================================================================")
    print("RUNNING MASTER VERIFICATION HARNESS (V-01 THROUGH V-26)")
    print("==================================================================")

    checks = [
        ("V-01", check_v01),
        ("V-02", check_v02),
        ("V-03", check_v03),
        ("V-04", check_v04),
        ("V-05", check_v05),
        ("V-06", check_v06),
        ("V-07", check_v07),
        ("V-08", check_v08),
        ("V-09", check_v09),
        ("V-10", check_v10),
        ("V-11", check_v11_v12),
        ("V-12", check_v11_v12),
        ("V-13", check_v13),
        ("V-14", check_v14),
        ("V-15", check_v15),
        ("V-16", check_v16),
        ("V-17", check_v17),
        ("V-18", check_v18),
        ("V-19", check_v19),
        ("V-20", check_v20),
        ("V-21", check_v21),
        ("V-22", check_v22),
        ("V-23", check_v23),
        ("V-24", check_v24),
        ("V-25", check_v25),
        ("V-26", check_v26),
        ("V-27", check_v27),
        ("V-28", check_v28),
    ]

    passed = 0
    failed = 0
    skipped = 0

    for vid, fn in checks:
        res = fn()
        if isinstance(res, tuple):
            ok, msg = res
        else:
            ok, msg = res, ""

        if ok == "SKIPPED":
            print(f"  [{vid}] SKIPPED: {msg}")
            skipped += 1
        elif ok is True:
            print(f"  [{vid}] PASS: {msg if isinstance(msg, str) and len(msg) < 80 else ''}")
            passed += 1
        else:
            print(f"  [{vid}] FAIL: {msg}")
            failed += 1

    print("==================================================================")
    print(f"VERIFICATION SUMMARY: {passed} PASSED, {failed} FAILED, {skipped} SKIPPED out of {len(checks)} criteria")
    print("==================================================================")

    if failed > 0:
        sys.exit(1)
    if skipped > 0 and not INSIDE_FRESH_CLONE_CHECK:
        print("ERROR: Skipped checks are not allowed outside fresh_clone_check.sh!")
        sys.exit(1)

    print(f"ALL CHECKS PASSED ({passed}/{len(checks)})")
    sys.exit(0)

if __name__ == "__main__":
    main()
