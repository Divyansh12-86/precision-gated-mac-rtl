"""
scripts/make_ecg_rom.py — Convert test vector inputs into ecg_rom.mem for board replay
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TV_DIR = os.path.join(BASE_DIR, "data", "test_vectors")

def make_rom(vector_set="std_fixed_100", max_samples=60000, out_path="ecg_rom.mem"):
    in_hex = os.path.join(TV_DIR, vector_set, "tv_inputs.hex")
    if not os.path.exists(in_hex):
        print(f"Error: {in_hex} does not exist!")
        sys.exit(1)

    with open(in_hex, "r") as f:
        lines = [line.strip() for line in f if line.strip()]

    lines = lines[:max_samples]
    with open(out_path, "w") as f:
        for line in lines:
            f.write(line + "\n")

    print(f"Exported {len(lines)} samples from {vector_set} to {out_path}")

if __name__ == "__main__":
    vset = sys.argv[1] if len(sys.argv) > 1 else "std_fixed_100"
    out = sys.argv[2] if len(sys.argv) > 2 else "ecg_rom.mem"
    make_rom(vset, out_path=out)
