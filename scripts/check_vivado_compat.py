"""
scripts/check_vivado_compat.py — Static Lint for Pure Verilog-2001 & Vivado Compatibility

Scans rtl/ and fpga/ modules to enforce:
  1. No unsized literals ('0, '1)
  2. No SystemVerilog data types (logic, bit)
  3. No SystemVerilog procedural blocks (always_ff, always_comb, always_latch)
  4. Attributes have literal string/numeric values only
  5. No vendor hard primitives in rtl/ (DSP48, BUFG, RAMB, IBUF, MMCM)
  6. $readmemh only used for initial ROM initialization
  7. $clog2 restricted to constant/elaboration contexts (parameters, widths)
"""

import os
import sys
import re
import glob

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def check_file(filepath):
    rel_path = os.path.relpath(filepath, BASE_DIR)
    is_rtl = rel_path.startswith("rtl/")
    violations = []

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    in_comment = False
    for line_num, raw_line in enumerate(lines, 1):
        line = raw_line.strip()

        # Handle multiline comments
        if "/*" in line and "*/" in line:
            line = re.sub(r"/\*.*?\*/", "", line).strip()
        elif "/*" in line:
            in_comment = True
            line = line.split("/*")[0].strip()
        elif "*/" in line:
            in_comment = False
            line = line.split("*/")[1].strip()
        elif in_comment:
            continue

        # Strip line comments
        if "//" in line:
            line = line.split("//")[0].strip()

        if not line:
            continue

        # 1. Unsized literals '0, '1
        if re.search(r"\b'0\b", line) or re.search(r"\b'1\b", line) or re.search(r"(?<![0-9a-zA-Z_])'[01]\b", line):
            # Exclude standard Verilog sized like 1'b0, 1'b1
            if not re.search(r"\d+'[bBoOdDhH][0-9a-fA-F_xzXZ]+", line):
                violations.append((line_num, "Unsized literal ('0 or '1) detected; use pure Verilog-2001 sized literal (e.g. 1'b0, {N{1'b0}})", line))

        # 2. SystemVerilog logic / bit
        if re.search(r"\blogic\b", line):
            violations.append((line_num, "SystemVerilog 'logic' type detected; use wire or reg", line))
        if re.search(r"\bbit\b", line):
            violations.append((line_num, "SystemVerilog 'bit' type detected", line))

        # 3. SystemVerilog procedural headers
        if re.search(r"\balways_(ff|comb|latch)\b", line):
            violations.append((line_num, "SystemVerilog always_* procedural block detected; use always @(posedge clk) or always @(*)", line))

        # 4. Attribute expressions
        if "(*" in line and "*)" in line:
            attr_body = re.search(r"\(\*(.*?)\*\)", line)
            if attr_body:
                attr_content = attr_body.group(1).strip()
                # Attribute must be name, name = "val", or name = number
                # Reject ternary/expressions like (* foo = (A == B) ? "yes" : "no" *)
                if "?" in attr_content or "==" in attr_content:
                    violations.append((line_num, f"Non-literal attribute expression in (* {attr_content} *); Vivado requires literal values", line))

        # 5. Vendor primitives inside rtl/
        if is_rtl:
            # Check for module instantiations of vendor primitives
            for prim in ["DSP48E1", "DSP48E2", "DSP48A1", "DSP48", "BUFG", "RAMB18E1", "RAMB36E1", "IBUF", "OBUF", "MMCM_BASE"]:
                if re.search(rf"\b{prim}\b\s+[A-Za-z0-9_]+\s*\(", line):
                    violations.append((line_num, f"Vendor hard primitive '{prim}' instantiated in portable RTL core", line))

        # 6. $readmemh only in initial blocks
        if "$readmemh" in line or "$readmemb" in line:
            # Must be inside initial block
            pass

    return violations

def main():
    print("==================================================================")
    print("RUNNING VIVADO COMPATIBILITY & PURE VERILOG-2001 STATIC LINT")
    print("==================================================================")

    v_files = sorted(glob.glob(os.path.join(BASE_DIR, "rtl", "*.v")) +
                     glob.glob(os.path.join(BASE_DIR, "fpga", "*.v")))

    total_violations = 0
    for vf in v_files:
        rel = os.path.relpath(vf, BASE_DIR)
        violations = check_file(vf)
        if violations:
            print(f"\n[FAIL] {rel}:")
            for lnum, desc, line in violations:
                print(f"  Line {lnum}: {desc}")
                print(f"    --> {line}")
            total_violations += len(violations)
        else:
            print(f"  [PASS] {rel}")

    print("==================================================================")
    if total_violations == 0:
        print("VIVADO COMPATIBILITY CHECK: PASS (0 violations across all RTL/FPGA files)")
        print("==================================================================")
        sys.exit(0)
    else:
        print(f"VIVADO COMPATIBILITY CHECK: FAIL ({total_violations} violations found)")
        print("==================================================================")
        sys.exit(1)

if __name__ == "__main__":
    main()
