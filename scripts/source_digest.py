#!/usr/bin/env python3
"""
scripts/source_digest.py — Computes canonical source digest over tracked project sources

Conforms to Phase 2 of ROUND3_GUIDE_AGENT.md:
  sha256 over the sorted (rel_path, sha256) list of:
  rtl/ fpga/ sim/*.py tb/ scripts/*.py Makefile coeffs.mem ecg_rom.mem
  (excluding reports/, data/, vectors, .venv, build*/, obj_dir/, __pycache__)
"""

import os
import sys
import glob
import hashlib
import subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def get_source_file_list():
    files = []
    # 1. rtl/
    for root, _, fnames in os.walk(os.path.join(BASE_DIR, "rtl")):
        for fn in fnames:
            if fn.endswith((".v", ".vh", ".mem")):
                files.append(os.path.relpath(os.path.join(root, fn), BASE_DIR))

    # 2. fpga/
    for root, _, fnames in os.walk(os.path.join(BASE_DIR, "fpga")):
        for fn in fnames:
            if fn.endswith((".v", ".vh", ".xdc")):
                files.append(os.path.relpath(os.path.join(root, fn), BASE_DIR))

    # 3. tb/
    for root, _, fnames in os.walk(os.path.join(BASE_DIR, "tb")):
        for fn in fnames:
            if fn.endswith((".v", ".vh", ".cpp")):
                files.append(os.path.relpath(os.path.join(root, fn), BASE_DIR))

    # 4. sim/*.py
    for fn in glob.glob(os.path.join(BASE_DIR, "sim", "*.py")):
        files.append(os.path.relpath(fn, BASE_DIR))

    # 5. scripts/*.py and scripts/*.tcl and scripts/*.sh
    for fn in glob.glob(os.path.join(BASE_DIR, "scripts", "*.py")):
        files.append(os.path.relpath(fn, BASE_DIR))
    for fn in glob.glob(os.path.join(BASE_DIR, "scripts", "*.tcl")):
        files.append(os.path.relpath(fn, BASE_DIR))
    for fn in glob.glob(os.path.join(BASE_DIR, "scripts", "*.sh")):
        files.append(os.path.relpath(fn, BASE_DIR))
    for fn in glob.glob(os.path.join(BASE_DIR, "scripts", "*.txt")):
        files.append(os.path.relpath(fn, BASE_DIR))

    # 6. Specific root files
    for fn in ["Makefile", "coeffs.mem", "ecg_rom.mem"]:
        p = os.path.join(BASE_DIR, fn)
        if os.path.exists(p):
            files.append(fn)

    return sorted(list(set(files)))

def get_source_digest():
    file_list = get_source_file_list()
    items = []
    for rel_p in file_list:
        full_p = os.path.join(BASE_DIR, rel_p)
        if os.path.exists(full_p) and os.path.isfile(full_p):
            h = sha256_file(full_p)
            items.append(f"{rel_p}:{h}")
    content = "\n".join(items)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def get_git_commit(verify_exists=True):
    commit = "unknown"
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=BASE_DIR, capture_output=True, text=True)
        if r.returncode == 0:
            commit = r.stdout.strip()
            # If HEAD is a report/docs-only commit, return the parent code commit
            diff_r = subprocess.run(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit], cwd=BASE_DIR, capture_output=True, text=True)
            changed_files = diff_r.stdout.splitlines()
            if changed_files and all(any(f.startswith(p) for p in ["reports/", "docs/"]) or f in ["README.md", "AGENTS.md"] for f in changed_files):
                r_parent = subprocess.run(["git", "rev-parse", "HEAD~1"], cwd=BASE_DIR, capture_output=True, text=True)
                if r_parent.returncode == 0:
                    commit = r_parent.stdout.strip()
            if verify_exists:
                chk = subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=BASE_DIR)
                if chk.returncode != 0:
                    print(f"WARNING: commit {commit} is not an ancestor of HEAD!")
    except Exception:
        pass
    return commit

def is_git_dirty(ignore_reports=True):
    try:
        st = subprocess.run(["git", "status", "--porcelain"], cwd=BASE_DIR, capture_output=True, text=True)
        lines = st.stdout.splitlines()
        if ignore_reports:
            lines = [l for l in lines if not any(x in l for x in ["reports/", "docs/", "README.md", "AGENTS.md"])]
        return len(lines) > 0
    except Exception:
        return False

def main():
    digest = get_source_digest()
    commit = get_git_commit()
    dirty = is_git_dirty()
    print(f"Source Digest: {digest}")
    print(f"Git Commit:    {commit} (dirty={dirty})")
    print(f"Source Files:  {len(get_source_file_list())} tracked items")

if __name__ == "__main__":
    main()
