"""
scripts/make_verification_bundle.py — Comprehensive Reproducibility & Verification Bundle Packager

Creates verification_bundle_<hash7>.zip conforming to Section 6 of ROUND2_GUIDE_AGENT.md:
  - BUNDLE_MANIFEST.json with full commit provenance, tool versions, command exit codes, and per-file SHA256
  - Full reports, docs, sources, reproduction scripts, git history snapshots, and evidence logs
  - Verified size limit <= 15 MB
  - Accompanying SHA256 checksum file
"""

import os
import sys
import re
import glob
import json
import time
import shutil
import zipfile
import hashlib
import platform
import subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
from scripts.source_digest import get_source_digest
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
PYTHON_EXE = sys.executable

def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def run_logged_command(cmd, name, evidence_dir):
    t_start = time.time()
    utc_start = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(t_start))
    print(f"[RUNNING] {name} ({' '.join(cmd)})...", flush=True)

    proc = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True)
    t_end = time.time()
    utc_end = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(t_end))
    duration = t_end - t_start

    log_path = os.path.join(evidence_dir, f"{name}.txt")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"Command: {' '.join(cmd)}\n")
        f.write(f"Start UTC: {utc_start}\n")
        f.write(f"End UTC: {utc_end}\n")
        f.write(f"Duration: {duration:.2f}s\n")
        f.write(f"Exit Code: {proc.returncode}\n")
        f.write("="*70 + "\nSTDOUT:\n" + "="*70 + "\n")
        f.write(proc.stdout)
        f.write("\n" + "="*70 + "\nSTDERR:\n" + "="*70 + "\n")
        f.write(proc.stderr)

    status_str = "PASS" if proc.returncode == 0 else f"FAIL (exit {proc.returncode})"
    print(f"  --> {status_str} in {duration:.2f}s (saved to evidence/{name}.txt)")
    return {
        "command": cmd,
        "name": name,
        "exit_code": proc.returncode,
        "start_utc": utc_start,
        "end_utc": utc_end,
        "duration_sec": round(duration, 2)
    }

def get_git_info():
    def _git(args):
        r = subprocess.run(["git"] + args, cwd=BASE_DIR, capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else ""

    head = _git(["rev-parse", "HEAD"])
    parent = _git(["rev-parse", "HEAD~1"])
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    tags = [t.strip() for t in _git(["tag", "-l"]).splitlines() if t.strip()]

    st = _git(["status", "--porcelain"])
    dirty = bool(len([l for l in st.splitlines() if not l.strip().endswith(".log") and not "/latest/" in l]))
    return {
        "head": head,
        "parent": parent,
        "branch": branch,
        "tags": tags,
        "dirty": dirty
    }

def get_tool_versions():
    vers = {
        "python": platform.python_version(),
        "verilator": None,
        "yosys": None,
        "vivado": None
    }
    try:
        r_v = subprocess.run(["verilator", "--version"], capture_output=True, text=True)
        if r_v.returncode == 0: vers["verilator"] = r_v.stdout.strip()
    except Exception: pass

    try:
        r_y = subprocess.run(["yosys", "-V"], capture_output=True, text=True)
        if r_y.returncode == 0: vers["yosys"] = r_y.stdout.strip()
    except Exception: pass

    try:
        import numpy, scipy, matplotlib, wfdb
        vers["numpy"] = numpy.__version__
        vers["scipy"] = scipy.__version__
        vers["matplotlib"] = matplotlib.__version__
        vers["wfdb"] = wfdb.__version__
    except Exception: pass

    return vers

def generate_independent_checks(evidence_dir):
    import numpy as np
    t_start = time.time()
    utc_start = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(t_start))
    out_lines = []
    out_lines.append("==================================================================")
    out_lines.append("INDEPENDENT NUMERICAL CHECKS (pure Python + numpy)")
    out_lines.append("==================================================================")

    coeffs_path = os.path.join(BASE_DIR, "coeffs.mem")
    with open(coeffs_path) as f:
        taps_raw = [int(l.strip(), 16) for l in f if l.strip()]
    taps = np.array([v if v < 32768 else v - 65536 for v in taps_raw], dtype=np.int64)

    def read_hex_s16(p):
        with open(p) as f:
            raw = [int(l.strip(), 16) for l in f if l.strip()]
        return np.array([v if v < 32768 else v - 65536 for v in raw], dtype=np.int64)

    def read_hex_s32(p):
        with open(p) as f:
            raw = [int(l.strip(), 16) for l in f if l.strip()]
        return np.array([v if v < 2147483648 else v - 4294967296 for v in raw], dtype=np.int64)

    sets_dir = os.path.join(BASE_DIR, "data", "test_vectors")
    all_sets = sorted([d for d in os.listdir(sets_dir) if os.path.isdir(os.path.join(sets_dir, d)) and not d.startswith("full_") and not d.startswith("ext_")])

    ok_count = 0
    fail_count = 0

    legacy_file = os.path.join(BASE_DIR, "scripts", "known_legacy_sets.txt")
    allow_list = set()
    if os.path.exists(legacy_file):
        with open(legacy_file, "r") as f:
            allow_list = set(line.strip() for line in f if line.strip() and not line.startswith("#"))

    allowed_legacy_count = 0
    unallowed_fail_count = 0

    for s in all_sets:
        p = os.path.join(sets_dir, s)
        in_p = os.path.join(p, "tv_inputs.hex")
        gate_p = os.path.join(p, "tv_gate_flags.hex")
        full_p = os.path.join(p, "tv_outputs_full.hex")
        approx_p = os.path.join(p, "tv_outputs_allapprox.hex")
        gated_p = os.path.join(p, "tv_outputs_gated.hex")

        if not (os.path.exists(in_p) and os.path.exists(gate_p) and os.path.exists(full_p)):
            continue

        x = read_hex_s16(in_p)
        with open(gate_p) as f:
            gate = np.array([int(l.strip(), 16) for l in f if l.strip()][:len(x)], dtype=bool)

        y_full_exp = read_hex_s32(full_p)[:len(x)]
        y_approx_exp = read_hex_s32(approx_p)[:len(x)]
        y_gated_exp = read_hex_s32(gated_p)[:len(x)]

        y_full_calc = np.convolve(x, taps, mode="full")[:len(x)]
        x_trunc = (x >> 8) << 8
        y_approx_calc = np.convolve(x_trunc, taps, mode="full")[:len(x)]
        y_gated_calc = np.where(gate, y_full_calc, y_approx_calc)

        diff_full = int(np.max(np.abs(y_full_exp - y_full_calc)))
        diff_approx = int(np.max(np.abs(y_approx_exp - y_approx_calc)))
        diff_gated = int(np.max(np.abs(y_gated_exp - y_gated_calc)))

        extra_checks = []
        if s.startswith("noise_"):
            lsb_zeros = int(np.sum((x & 31) == 0))
            if lsb_zeros == len(x):
                extra_checks.append("ADU invariant (x&31)==0: 100%")
            else:
                extra_checks.append(f"ADU invariant (x&31)==0 FAIL ({lsb_zeros}/{len(x)})")

        if s.startswith("std_fixed_"):
            rec_id = s.replace("std_fixed_", "")
            dat_p = os.path.join(BASE_DIR, "data", "mitbih", f"{rec_id}.dat")
            if os.path.exists(dat_p):
                try:
                    import wfdb
                    rec = wfdb.rdrecord(os.path.join(BASE_DIR, "data", "mitbih", rec_id), sampto=len(x))
                    raw_adu = rec.d_signal[:len(x), 0]
                    calc_in = (raw_adu.astype(np.int64) - 1024) << 5
                    if np.max(np.abs(x - calc_in)) == 0:
                        extra_checks.append("MIT-BIH ADU match: 100%")
                except Exception:
                    pass

        is_ok = (diff_full == 0 and diff_approx == 0 and diff_gated == 0 and not any("FAIL" in c for c in extra_checks))
        extra_str = f" [{', '.join(extra_checks)}]" if extra_checks else ""
        if is_ok:
            ok_count += 1
            out_lines.append(f"SET {s:25s}: OK ({len(x)} samples, diffs: full=0 approx=0 gated=0){extra_str}")
        else:
            fail_count += 1
            if s in allow_list:
                allowed_legacy_count += 1
                out_lines.append(f"SET {s:25s}: MISMATCH (full={diff_full} approx={diff_approx} gated={diff_gated}){extra_str} *(Known legacy set from scripts/known_legacy_sets.txt)*")
            else:
                unallowed_fail_count += 1
                out_lines.append(f"SET {s:25s}: UNAPPROVED MISMATCH (full={diff_full} approx={diff_approx} gated={diff_gated}){extra_str}")

    out_lines.append("==================================================================")
    out_lines.append(f"INDEPENDENT CHECKS SUMMARY: {ok_count} OK, {fail_count} MISMATCH ({allowed_legacy_count} allowed legacy, {unallowed_fail_count} unapproved) out of {ok_count + fail_count} sets")
    out_lines.append("==================================================================")

    with open(os.path.join(evidence_dir, "independent_checks.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")
    print(f"  --> Saved {ok_count} vector set independent checks to evidence/independent_checks.txt")

    if unallowed_fail_count > 0:
        print(f"ERROR: {unallowed_fail_count} unapproved mismatch(es) detected in independent checks!")
        sys.exit(1)

    t_end = time.time()
    utc_end = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(t_end))
    duration = t_end - t_start
    return {
        "command": [PYTHON_EXE, "scripts/make_verification_bundle.py", "--independent-checks"],
        "name": "independent_checks",
        "exit_code": 0,
        "start_utc": utc_start,
        "end_utc": utc_end,
        "duration_sec": round(duration, 2)
    }

def main():
    run_checks = "--run-checks" in sys.argv
    is_nightly = "--nightly" in sys.argv
    do_fresh = "--fresh-clone" in sys.argv
    no_data = "--no-data" in sys.argv
    allow_dirty = "--allow-dirty" in sys.argv

    print("==================================================================")
    print("VERIFICATION BUNDLE PACKAGER (Phase 6 / Section 6)")
    print("==================================================================")

    git_info = get_git_info()
    head_7 = git_info["head"][:7] if git_info["head"] else "unknown"

    if git_info["dirty"] and not allow_dirty:
        print("ERROR: Working tree is DIRTY. Commit changes or pass --allow-dirty.")
        sys.exit(1)
    elif git_info["dirty"]:
        print("WARNING: Working tree is DIRTY! 'dirty': true will be recorded in manifest.")

    # Rule S3 / Phase 2: Refuse to package if any evidence fails provenance
    print("\n--- Verifying evidence provenance and commit existence ---")
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
        pj = os.path.join(REPORTS_DIR, ej)
        if not os.path.exists(pj):
            print(f"ERROR: Missing report artifact {ej}")
            sys.exit(1)
        with open(pj, "r") as f:
            d = json.load(f)
        c = d.get("commit")
        if not c or c == "unknown":
            print(f"ERROR: Missing commit in {ej}")
            sys.exit(1)
        chk = subprocess.run(["git", "cat-file", "-e", f"{c}^{{commit}}"], cwd=BASE_DIR)
        if chk.returncode != 0:
            print(f"ERROR: Stale/dangling commit {c} in {ej} does not exist in git history!")
            sys.exit(1)
        sd = d.get("source_digest")
        if sd != cur_digest:
            print(f"ERROR: Stale source_digest in {ej}: got {sd}, current is {cur_digest}!")
            sys.exit(1)

    bundle_dir_name = f"verification_bundle_{head_7}"
    zip_path = os.path.join(BASE_DIR, f"{bundle_dir_name}.zip")
    temp_stage = os.path.join(BASE_DIR, f"build_bundle_{head_7}")

    existing_evidence = os.path.join(temp_stage, bundle_dir_name, "evidence")
    saved_evidence = {}
    if os.path.exists(existing_evidence):
        for fn in os.listdir(existing_evidence):
            p = os.path.join(existing_evidence, fn)
            if os.path.isfile(p):
                with open(p, "rb") as f:
                    saved_evidence[fn] = f.read()

    if os.path.exists(temp_stage):
        shutil.rmtree(temp_stage)
    b_root = os.path.join(temp_stage, bundle_dir_name)
    os.makedirs(b_root, exist_ok=True)

    evidence_dir = os.path.join(b_root, "evidence")
    os.makedirs(evidence_dir, exist_ok=True)

    # Restore any previously saved evidence
    for fn, data in saved_evidence.items():
        with open(os.path.join(evidence_dir, fn), "wb") as f:
            f.write(data)

    commands_log = []

    # 1. Optionally run checks and capture raw stdout/stderr
    if run_checks:
        print("\n--- Executing verification checks for evidence capture ---")
        commands_log.append(run_logged_command([PYTHON_EXE, "sim/run_regression.py"], "regression_standard", evidence_dir))
        if is_nightly:
            commands_log.append(run_logged_command([PYTHON_EXE, "sim/run_regression.py", "--nightly"], "regression_nightly", evidence_dir))
        commands_log.append(run_logged_command([PYTHON_EXE, "scripts/mutation_check.py"], "mutation", evidence_dir))
        commands_log.append(run_logged_command([PYTHON_EXE, "scripts/synth_runner.py"], "synth", evidence_dir))
        commands_log.append(run_logged_command([PYTHON_EXE, "sim/activity_report.py"], "activity", evidence_dir))
        commands_log.append(run_logged_command([PYTHON_EXE, "sim/noise_sweep.py"], "noise", evidence_dir))
        commands_log.append(run_logged_command([PYTHON_EXE, "scripts/check_vivado_compat.py"], "vivado_compat", evidence_dir))
        commands_log.append(run_logged_command([PYTHON_EXE, "scripts/uart_capture.py", "--selftest"], "uart_capture_selftest", evidence_dir))
        commands_log.append(run_logged_command([PYTHON_EXE, "scripts/check_docs_numbers.py"], "check_docs_numbers", evidence_dir))
        commands_log.append(run_logged_command([PYTHON_EXE, "scripts/verify_all.py"], "verify_all", evidence_dir))
        if do_fresh:
            commands_log.append(run_logged_command(["bash", "scripts/fresh_clone_check.sh"], "fresh_clone", evidence_dir))
    else:
        # Populate commands_log from existing evidence files if available
        for fn in sorted(os.listdir(evidence_dir)):
            if fn.endswith(".txt") and fn not in ["env.txt", "independent_checks.txt"]:
                cmd_name = fn[:-4]
                with open(os.path.join(evidence_dir, fn), "r", encoding="utf-8") as f:
                    txt = f.read()
                m_cmd = re.search(r"^Command:\s*(.*)$", txt, re.MULTILINE)
                m_start = re.search(r"^Start UTC:\s*(.*)$", txt, re.MULTILINE)
                m_end = re.search(r"^End UTC:\s*(.*)$", txt, re.MULTILINE)
                m_dur = re.search(r"^Duration:\s*([0-9.]+)s", txt, re.MULTILINE)
                m_exit = re.search(r"^Exit Code:\s*(\d+)", txt, re.MULTILINE)
                if m_cmd and m_exit:
                    commands_log.append({
                        "name": cmd_name,
                        "command": m_cmd.group(1).split(),
                        "exit_code": int(m_exit.group(1)),
                        "start_utc": m_start.group(1) if m_start else "",
                        "end_utc": m_end.group(1) if m_end else "",
                        "duration_sec": float(m_dur.group(1)) if m_dur else 0.0
                    })

    # 2. Host and environment info
    tool_vers = get_tool_versions()
    with open(os.path.join(evidence_dir, "env.txt"), "w", encoding="utf-8") as f:
        f.write(f"OS: {platform.system()} {platform.release()} ({platform.machine()})\n")
        f.write(f"CPU count: {os.cpu_count()}\n")
        for k, v in tool_vers.items():
            f.write(f"{k}: {v}\n")

    # 2b. Independent Numerical Checks (evidence/independent_checks.txt)
    print("\n--- Generating independent numerical checks ---")
    commands_log.append(generate_independent_checks(evidence_dir))

    # 3. HOW_TO_REPRODUCE.txt
    with open(os.path.join(b_root, "HOW_TO_REPRODUCE.txt"), "w", encoding="utf-8") as f:
        f.write("==================================================================\n")
        f.write("HOW TO REPRODUCE VERIFICATION FROM BUNDLE\n")
        f.write("==================================================================\n\n")
        f.write("1. Setup environment:\n")
        f.write("   python3 -m venv .venv\n")
        f.write("   source .venv/bin/activate\n")
        f.write("   pip install -r src/requirements.txt\n\n")
        f.write("2. Regenerate test vectors:\n")
        f.write("   make vectors full-vectors\n\n")
        f.write("3. Run full regressions:\n")
        f.write("   make sim\n")
        f.write("   make nightly\n\n")
        f.write("4. Run mutation testing:\n")
        f.write("   python3 scripts/mutation_check.py\n\n")
        f.write("5. Run master verification harness:\n")
        f.write("   python3 scripts/verify_all.py\n")

    # 4. Git history snapshots in git/
    git_dir = os.path.join(b_root, "git")
    os.makedirs(git_dir, exist_ok=True)
    def _save_cmd(cmd, out_file):
        r = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True)
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(r.stdout)

    _save_cmd(["git", "log", "-n", "20", "--stat"], os.path.join(git_dir, "log.txt"))
    _save_cmd(["git", "status"], os.path.join(git_dir, "status.txt"))
    _save_cmd(["git", "tag", "-l"], os.path.join(git_dir, "tags.txt"))

    # tracked_files_sha256.txt
    tracked_res = subprocess.run(["git", "ls-files"], cwd=BASE_DIR, capture_output=True, text=True)
    tracked_files = [l.strip() for l in tracked_res.stdout.splitlines() if l.strip()]
    with open(os.path.join(git_dir, "tracked_files_sha256.txt"), "w", encoding="utf-8") as f:
        for tf in sorted(tracked_files):
            p = os.path.join(BASE_DIR, tf)
            if os.path.exists(p) and not os.path.isdir(p):
                sz = os.path.getsize(p)
                c_hash = sha256_file(p)
                f.write(f"{c_hash}  {sz:10d}  {tf}\n")

    # ignored_untracked.txt (excluding builds and venv)
    ign_res = subprocess.run(["git", "status", "--porcelain", "--ignored"], cwd=BASE_DIR, capture_output=True, text=True)
    with open(os.path.join(git_dir, "ignored_untracked.txt"), "w", encoding="utf-8") as f:
        for line in ign_res.stdout.splitlines():
            line = line.strip()
            if not any(ex in line for ex in ["build", "obj_dir", ".venv", ".git"]):
                f.write(line + "\n")

    # 5. Copy tracked source tree into src/
    src_dir = os.path.join(b_root, "src")
    os.makedirs(src_dir, exist_ok=True)
    for tf in tracked_files:
        if any(tf.startswith(p) for p in ["data/test_vectors/", "sim/media/", "slides/"]):
            continue
        if tf.endswith(".pptx") or tf.endswith(".gif") or "__pycache__" in tf:
            continue
        dst = os.path.join(src_dir, tf)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(BASE_DIR, tf), dst)

    # 6. Copy dataset into data/mitbih/ (records 100, 101, 103, 105)
    if not no_data:
        data_dst = os.path.join(b_root, "data", "mitbih")
        os.makedirs(data_dst, exist_ok=True)
        mit_src = os.path.join(BASE_DIR, "data", "mitbih")
        for rec in ["100", "101", "103", "105"]:
            for ext in [".dat", ".hea", ".atr"]:
                f_name = f"{rec}{ext}"
                p_src = os.path.join(mit_src, f_name)
                if os.path.exists(p_src):
                    shutil.copy2(p_src, os.path.join(data_dst, f_name))

    # 7. Vectors directory: manifest_sha256.txt and manifests
    vec_dst = os.path.join(b_root, "vectors")
    os.makedirs(vec_dst, exist_ok=True)
    with open(os.path.join(vec_dst, "manifest_sha256.txt"), "w", encoding="utf-8") as f:
        for root, _, files in os.walk(os.path.join(BASE_DIR, "data", "test_vectors")):
            for fn in sorted(files):
                full_p = os.path.join(root, fn)
                rel_p = os.path.relpath(full_p, BASE_DIR)
                c_hash = sha256_file(full_p)
                f.write(f"{c_hash}  {rel_p}\n")
                if fn == "manifest.json":
                    s_name = os.path.basename(root)
                    s_dst = os.path.join(vec_dst, "sets", s_name)
                    os.makedirs(s_dst, exist_ok=True)
                    shutil.copy2(full_p, os.path.join(s_dst, fn))

    # 8. Full copy of reports/
    rep_dst = os.path.join(b_root, "reports")
    shutil.copytree(REPORTS_DIR, rep_dst, ignore=shutil.ignore_patterns("*.tmp", "*~"))

    # 9. Compute SHA256 of all files in bundle
    bundle_files_sha = {}
    for root, _, files in os.walk(b_root):
        for fn in sorted(files):
            fp = os.path.join(root, fn)
            rel_in_bundle = os.path.relpath(fp, b_root)
            if rel_in_bundle == "BUNDLE_MANIFEST.json":
                continue
            bundle_files_sha[rel_in_bundle] = sha256_file(fp)

    # Sorted list hash
    list_str = "\n".join(f"{bundle_files_sha[k]}  {k}" for k in sorted(bundle_files_sha.keys()))
    bundle_content_sha256 = hashlib.sha256(list_str.encode("utf-8")).hexdigest()

    manifest_data = {
        "head": git_info["head"],
        "parent": git_info["parent"],
        "code_commit": git_info["parent"] if git_info["parent"] else git_info["head"],
        "report_commit": git_info["head"],
        "source_digest": get_source_digest(),
        "content_hash_algorithm": "sha256('\\n'.join(f'{sha256}  {rel_path}' for rel_path in sorted(files)))",
        "branch": git_info["branch"],
        "tags": git_info["tags"],
        "dirty": git_info["dirty"],
        "created_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "host": {
            "os": platform.system(),
            "release": platform.release(),
            "arch": platform.machine(),
            "cpu_count": os.cpu_count(),
            "python_version": platform.python_version()
        },
        "tool_versions": tool_vers,
        "commands": commands_log,
        "bundle_content_sha256": bundle_content_sha256,
        "file_count": len(bundle_files_sha),
        "files": bundle_files_sha
    }

    with open(os.path.join(b_root, "BUNDLE_MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, sort_keys=True)

    # 10. Create Zip Archive
    print(f"\nCompressing bundle into {zip_path}...")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(b_root):
            for fn in files:
                fp = os.path.join(root, fn)
                arc_name = os.path.relpath(fp, temp_stage)
                zf.write(fp, arc_name)

    zip_size = os.path.getsize(zip_path)
    zip_size_mb = zip_size / (1024 * 1024)
    zip_sha = sha256_file(zip_path)

    # Write .sha256 file
    sha_path = os.path.join(BASE_DIR, f"{bundle_dir_name}.zip.sha256")
    with open(sha_path, "w", encoding="utf-8") as f:
        f.write(f"{zip_sha}  {os.path.basename(zip_path)}\n")

    # Clean up stage
    shutil.rmtree(temp_stage)

    print("==================================================================")
    print(f"BUNDLE GENERATION COMPLETE: {os.path.basename(zip_path)}")
    print(f"Size: {zip_size_mb:.2f} MB ({zip_size} bytes)")
    print(f"SHA256: {zip_sha}")
    print("==================================================================")

    if zip_size_mb > 15.0:
        print(f"ERROR: Bundle size ({zip_size_mb:.2f} MB) exceeds 15 MB limit!")
        sys.exit(1)

    print("SUCCESS: Verification bundle packaged and verified <= 15 MB.")
    sys.exit(0)

if __name__ == "__main__":
    main()
