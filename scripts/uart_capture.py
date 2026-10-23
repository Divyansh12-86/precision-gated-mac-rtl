#!/usr/bin/env python3
"""
uart_capture_aligned.py - live capture + verification for the Precision-Gated MAC board demo.

Why this exists
---------------
The board streams 7-byte frames continuously and loops its ECG ROM, so a PC program can start
listening at ANY byte of ANY sample.  This tool therefore
  1. locks onto the frame boundary (0xA5 preamble + valid XOR checksum on 3 consecutive frames),
  2. finds which ROM sample the first captured frame corresponds to (alignment against the golden vectors),
  3. verifies every following frame bit-for-bit,
  4. reports gate duty and detected heart rate (so you have numbers to show in the demo).

Frame format (board_core.v):  A5 | y[31:24] | y[23:16] | y[15:8] | y[7:0] | flags | chk
    flags bit0 = gate (1 = full precision), bit1 = peak pulse, bit2 = a manual mode switch is active
    chk   = XOR of the first six bytes

IMPORTANT: bit-exact comparison with the golden vectors is only valid during the FIRST pass of the
ROM after a reset (about 166 s after you press reset), because the ROM loops without clearing the filter.
Press the reset button, then start this program within ~2 minutes.

Usage examples
--------------
  python uart_capture_aligned.py --port COM5                       (Windows)
  python uart_capture_aligned.py --port /dev/ttyUSB1               (Linux)
  python uart_capture_aligned.py --port COM5 --samples 6000 --dump run1.bin
  python uart_capture_aligned.py --file run1.bin                   (re-analyse a saved dump)
  python uart_capture_aligned.py --selftest                        (no board needed)
  python uart_capture_aligned.py --list-ports
"""
import argparse
import os
import random
import struct
import sys
import time

FS = 360
FRAME = 7
HERE = os.path.dirname(os.path.abspath(__file__))
# works whether the script sits in <repo>/scripts or next to the repo root
CANDIDATE_REF_ROOTS = [
    os.path.join(HERE, "..", "data", "test_vectors"),
    os.path.join(HERE, "data", "test_vectors"),
    os.path.join(os.getcwd(), "data", "test_vectors"),
]


def find_ref_dir(name):
    if os.path.isdir(name):
        return name
    for root in CANDIDATE_REF_ROOTS:
        p = os.path.join(root, name)
        if os.path.isdir(p):
            return p
    return None


def read_hex_file(path, bits):
    vals = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                v = int(line, 16)
                if bits == 32 and v >= 1 << 31:
                    v -= 1 << 32
                vals.append(v)
    return vals


def load_reference(ref_dir):
    refs = {}
    gate = read_hex_file(os.path.join(ref_dir, "tv_gate_flags.hex"), 1)
    for key, fname in (("gated (automatic mode)", "tv_outputs_gated.hex"),
                       ("force full precision", "tv_outputs_full.hex"),
                       ("force approximate", "tv_outputs_allapprox.hex")):
        p = os.path.join(ref_dir, fname)
        if os.path.exists(p):
            refs[key] = read_hex_file(p, 32)
    return refs, gate


def checksum_ok(buf, i):
    c = 0
    for k in range(6):
        c ^= buf[i + k]
    return c == buf[i + 6]


def lock_frames(buf):
    """Return index of first byte of a frame such that 3 consecutive frames are valid."""
    n = len(buf)
    for i in range(0, n - 3 * FRAME + 1):
        if buf[i] != 0xA5:
            continue
        if all(buf[i + j * FRAME] == 0xA5 and checksum_ok(buf, i + j * FRAME) for j in range(3)):
            return i
    return None


def decode(buf, start):
    ys, flags, bad = [], [], 0
    i = start
    while i + FRAME <= len(buf):
        if buf[i] != 0xA5 or not checksum_ok(buf, i):
            bad += 1
            # try to resynchronise byte by byte
            i += 1
            continue
        ys.append(struct.unpack(">i", bytes(buf[i + 1:i + 5]))[0])
        flags.append(buf[i + 5])
        i += FRAME
    return ys, flags, bad


def build_index(ref, k=4):
    idx = {}
    for s in range(len(ref) - k + 1):
        idx.setdefault(tuple(ref[s:s + k]), []).append(s)
    return idx


def align(ys, refs, probe=24):
    """Find (mode_name, start_index) so that ys[0:probe] == ref[start:start+probe]."""
    best = None
    for name, ref in refs.items():
        idx = build_index(ref)
        key = tuple(ys[:4])
        for s in idx.get(key, []):
            m = 0
            while m < probe and s + m < len(ref) and m < len(ys) and ys[m] == ref[s + m]:
                m += 1
            if m >= probe and (best is None or s < best[1]):
                best = (name, s)
                break
    return best


def analyse(buf, ref_dir):
    refs, ref_gate = load_reference(ref_dir)
    print("Loaded reference vectors from %s (%d samples)" % (ref_dir, len(ref_gate)))
    print("Captured %d bytes" % len(buf))
    start = lock_frames(buf)
    if start is None:
        print("RESULT: NO FRAME LOCK. No valid 7-byte frames found.")
        print("  -> check baud (115200), COM port, that the board is programmed, and press the reset button.")
        return 2
    ys, flags, bad = decode(buf, start)
    print("Frame lock at byte %d (dropped %d leading byte(s)); %d frames decoded; %d bad/skipped" %
          (start, start, len(ys), bad))
    if len(ys) < 50:
        print("RESULT: TOO FEW FRAMES (%d). Capture longer (--samples 3000 or more)." % len(ys))
        return 2

    gate_stream = [f & 1 for f in flags]
    secs = len(ys) / float(FS)
    duty = 100.0 * sum(gate_stream) / len(gate_stream)
    rises = sum(1 for a, b in zip(gate_stream, gate_stream[1:]) if a == 0 and b == 1)
    bpm = rises * 60.0 / secs if secs > 0 else 0.0
    print("\nLIVE NUMBERS FROM THE BOARD")
    print("  Captured time            : %.1f s (%d samples)" % (secs, len(ys)))
    print("  Full-precision duty      : %.1f %%   (approximate mode: %.1f %%)" % (duty, 100 - duty))
    print("  QRS gates detected       : %d  ->  about %.0f beats/min" % (rises, bpm))
    forced = any(f & 4 for f in flags)
    print("  Manual mode switch used  : %s" % ("yes" if forced else "no"))

    hit = align(ys, refs)
    if hit is None:
        print("\nRESULT: ALIGNMENT FAILED. The captured filtered output does not match any golden vector.")
        print("  Common causes: (1) more than ~166 s passed since reset - press reset and capture again;")
        print("                 (2) a different ecg_rom.mem was used than the --ref set;")
        print("                 (3) the design was changed. Save the capture with --dump and inspect it.")
        return 1
    mode, s0 = hit
    ref = refs[mode]
    print("\nAlignment: first captured frame = ROM sample %d, matching reference '%s'" % (s0, mode))
    n = min(len(ys), len(ref) - s0)
    mism = sum(1 for i in range(n) if ys[i] != ref[s0 + i])
    gate_mism = 0
    if mode.startswith("gated"):
        gate_mism = sum(1 for i in range(n) if gate_stream[i] != ref_gate[s0 + i])
    print("\nVERIFICATION against golden model")
    print("  Samples compared         : %d" % n)
    print("  Filter output mismatches : %d" % mism)
    if mode.startswith("gated"):
        print("  Gate flag mismatches     : %d" % gate_mism)
    ok = (mism == 0 and gate_mism == 0 and bad == 0)
    if ok:
        print("\nSTATUS: PASS - the FPGA output is bit-exact with the Python/RTL golden model")
        return 0
    print("\nSTATUS: FAIL - see counts above (bad frames: %d)" % bad)
    return 1


# ----------------------------------------------------------------------------------------------
def make_stream(ref_y, ref_gate, start, count, flip_forced=False, corrupt=0, junk=0, seed=1):
    """Synthesise what the board would send, starting at ROM sample `start`."""
    rnd = random.Random(seed)
    data = bytearray(rnd.randrange(256) for _ in range(junk))   # started listening mid-stream
    prev_g = 0
    for i in range(start, start + count):
        y = ref_y[i] & 0xFFFFFFFF
        g = ref_gate[i]
        peak = 1 if (g == 1 and prev_g == 0) else 0
        prev_g = g
        flags = g | (peak << 1) | ((1 if flip_forced else 0) << 2)
        b = [0xA5, (y >> 24) & 255, (y >> 16) & 255, (y >> 8) & 255, y & 255, flags]
        c = 0
        for v in b:
            c ^= v
        data.extend(b + [c])
    for _ in range(corrupt):
        data[rnd.randrange(len(data))] ^= 0x10
    return data


def selftest(ref_dir):
    refs, gate = load_reference(ref_dir)
    ref = refs["gated (automatic mode)"]
    tests = [
        ("start at sample 0, aligned", dict(start=0, count=2500, junk=0), 0),
        ("start mid-frame, sample 1234", dict(start=1234, count=2500, junk=3), 0),
        ("start at sample 30000, 100 junk bytes", dict(start=30000, count=2500, junk=100), 0),
        ("corrupted stream must FAIL", dict(start=500, count=2500, junk=5, corrupt=4), 1),
    ]
    allok = True
    for name, kw, want in tests:
        print("=" * 70)
        print("SELF-TEST: %s" % name)
        buf = make_stream(ref, gate, **kw)
        rc = analyse(bytes(buf), ref_dir)
        good = (rc == want)
        allok &= good
        print(">>> expected exit code %d, got %d  ->  %s" % (want, rc, "OK" if good else "WRONG"))
    print("=" * 70)
    print("SELF-TEST SUMMARY: %s" % ("ALL OK" if allok else "PROBLEM"))
    return 0 if allok else 1


def capture_serial(port, baud, nbytes, dump):
    try:
        import serial
    except ImportError:
        print("pyserial is not installed.  Run:  python -m pip install pyserial")
        sys.exit(3)
    print("Opening %s at %d baud ..." % (port, baud))
    ser = serial.Serial(port, baud, timeout=1.0)
    ser.reset_input_buffer()
    buf = bytearray()
    t0 = time.time()
    last = 0
    while len(buf) < nbytes:
        chunk = ser.read(min(4096, nbytes - len(buf)))
        buf.extend(chunk)
        if time.time() - last > 1.0:
            last = time.time()
            print("  received %6d / %d bytes" % (len(buf), nbytes), end="\r")
        if not chunk and time.time() - t0 > 10 and len(buf) == 0:
            print("\nNo data received in 10 s. Is the board programmed? Is this the right COM port?")
            ser.close()
            sys.exit(4)
    ser.close()
    print("\nCapture finished in %.1f s" % (time.time() - t0))
    if dump:
        with open(dump, "wb") as f:
            f.write(buf)
        print("Raw capture saved to %s" % dump)
    return bytes(buf)


def main():
    ap = argparse.ArgumentParser(description="Capture and verify the FPGA ECG stream")
    ap.add_argument("--port")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--samples", type=int, default=3000, help="frames to capture (360 per second)")
    ap.add_argument("--ref", default="std_fixed_100", help="reference vector set name or directory")
    ap.add_argument("--file", help="analyse a saved raw dump instead of using a serial port")
    ap.add_argument("--dump", help="save the raw capture to this file")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--list-ports", action="store_true")
    a = ap.parse_args()

    if a.list_ports:
        try:
            from serial.tools import list_ports
            for p in list_ports.comports():
                print("%s  -  %s" % (p.device, p.description))
        except ImportError:
            print("pyserial is not installed.  Run:  python -m pip install pyserial")
        return 0

    ref_dir = find_ref_dir(a.ref)
    if ref_dir is None:
        print("Reference vector set '%s' not found. Run this from the repo folder or pass --ref <folder>." % a.ref)
        return 3
    if a.selftest:
        return selftest(ref_dir)
    if a.file:
        with open(a.file, "rb") as f:
            return analyse(f.read(), ref_dir)
    if a.port:
        buf = capture_serial(a.port, a.baud, (a.samples + 20) * FRAME, a.dump)
        return analyse(buf, ref_dir)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
