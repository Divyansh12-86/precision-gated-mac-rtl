#!/usr/bin/env python3
"""
ecg_live_viewer.py (v2) - live visual demo for the Precision-Gated MAC FPGA design (no Vivado needed).

Run it on ANY PC/laptop that has Python 3 + `pip install pyserial matplotlib numpy`.
It reads the 7-byte frames the board sends over its USB-UART and shows, in one window:
  TOP    : percentage of time the multiplier is ACTIVE at full precision (vs low-power 8-bit) + LED dots
  PANEL 1: the UNFILTERED INPUT the FPGA is processing (the stored MIT-BIH recording)
  PANEL 2: the FILTERED OUTPUT received live from the board (green = full-precision windows)
  PANEL 3: error of the board output versus a full-precision calculation
It checks every frame bit-for-bit against a software model of the same design and shows how many
multiplier-operand bit toggles the precision gating avoids.

About the input panel: the board stores the ECG in its own ROM and does NOT send it back. The viewer
holds an identical copy (ecg_rom.mem) and plots the samples at the position the board is currently at.
That this is really the board's input is PROVEN by the bit-exact match of the filtered output.

Frame (board_core.v):  A5 | y[31:24] | y[23:16] | y[15:8] | y[7:0] | flags | chk(XOR of first 6 bytes)
flags: bit0 = gate (1 = full precision), bit1 = peak pulse, bit2 = a manual mode switch is active.

Files needed next to the repo root (or give --rom / --coeffs):  ecg_rom.mem  coeffs.mem

Examples
  python ecg_live_viewer.py --port COM5                 live board (Windows)
  python ecg_live_viewer.py --port /dev/ttyUSB1         live board (Linux)
  python ecg_live_viewer.py --simulate                  rehearse WITHOUT the board (simulated stream)
  python ecg_live_viewer.py --file run1.bin             replay a saved raw capture
  python ecg_live_viewer.py --simulate --snapshot s.png --duration 12      headless screenshot
  python ecg_live_viewer.py --selftest                  built-in tests (no display, no board)
Keys in the window: p = pause, s = screenshot, d = toggle input alignment (arrival / delay-compensated), f = full screen, q = quit.

What is measured and what is modelled (be honest on stage):
  * waveform, gate, frame checksum, bit-exact check: MEASURED from the board's real output.
  * operand toggle saving: computed by a software model from the stored ECG and the board's real gate
    decisions. It is NOT a power measurement of the board.
"""
import argparse
import os
import struct
import sys
import time
from collections import deque

import numpy as np

FS = 360
FRAME = 7
N_TAPS = 51
MV_PER_LSB = 1.0 / (200.0 * 32.0)       # MIT-BIH 200 ADU/mV, samples scaled <<5
HERE = os.path.dirname(os.path.abspath(__file__))

PC8 = np.array([bin(i).count("1") for i in range(256)], dtype=np.int64)


# ----------------------------------------------------------------------------- reference model
def find_file(name, explicit=None):
    if explicit:
        return explicit if os.path.exists(explicit) else None
    for base in (os.getcwd(), HERE, os.path.join(HERE, ".."), os.path.join(HERE, "..", "..")):
        p = os.path.join(base, name)
        if os.path.exists(p):
            return p
    return None


def read_mem16(path):
    v = np.array([int(l, 16) for l in open(path).read().split()], dtype=np.int64)
    return np.where(v >= 32768, v - 65536, v)


class Model:
    """Software twin of the FPGA filter, evaluated on the looping ECG ROM (no state needed)."""

    def __init__(self, rom, taps):
        self.x = rom.astype(np.int64)
        self.h = taps.astype(np.int64)
        self.N = len(self.x)
        t = np.concatenate([self.x, self.x])
        ta = np.concatenate([(self.x >> 8) << 8] * 2)
        self.y_full = np.convolve(t, self.h)[self.N:2 * self.N]
        self.y_apx = np.convolve(ta, self.h)[self.N:2 * self.N]
        self.u16 = (self.x & 0xFFFF)

    def operand_low_bytes(self, k):
        """Low byte of the multiplier operand for the 51 cycles of output sample k."""
        idx = (k - np.arange(N_TAPS)) % self.N
        return self.u16[idx] & 0xFF


def toggles(seq, prev):
    s = np.concatenate([[prev], seq[:-1]])
    return int(PC8[seq ^ s].sum()), int(seq[-1])


# ----------------------------------------------------------------------------- byte stream -> frames
class FrameParser:
    def __init__(self):
        self.buf = bytearray()
        self.locked = False
        self.bad = 0
        self.dropped = 0

    @staticmethod
    def ok(b, i):
        c = 0
        for k in range(6):
            c ^= b[i + k]
        return b[i] == 0xA5 and c == b[i + 6]

    def feed(self, data):
        self.buf.extend(data)
        out = []
        b = self.buf
        i = 0
        while True:
            if not self.locked:
                # need 3 consecutive valid frames to lock
                found = False
                while i + 3 * FRAME <= len(b):
                    if b[i] == 0xA5 and self.ok(b, i) and self.ok(b, i + FRAME) and self.ok(b, i + 2 * FRAME):
                        self.locked = True
                        found = True
                        self.dropped += i
                        break
                    i += 1
                if not found:
                    break
            if i + FRAME > len(b):
                break
            if self.ok(b, i):
                y = struct.unpack(">i", bytes(b[i + 1:i + 5]))[0]
                out.append((y, b[i + 5]))
                i += FRAME
            else:
                self.bad += 1
                self.locked = False      # resynchronise
                i += 1
        del self.buf[:i]
        return out


# ----------------------------------------------------------------------------- sources
class SerialSource:
    def __init__(self, port, baud):
        try:
            import serial
        except ImportError:
            sys.exit("pyserial missing: python -m pip install pyserial")
        self.ser = serial.Serial(port, baud, timeout=0)
        self.ser.reset_input_buffer()

    def read(self):
        n = self.ser.in_waiting
        return self.ser.read(n) if n else b""


class FileSource:
    def __init__(self, path, realtime=True):
        self.data = open(path, "rb").read()
        self.pos = 0
        self.t0 = time.time()
        self.realtime = realtime

    def read(self):
        if self.realtime:
            want = int((time.time() - self.t0) * FS * FRAME)
        else:
            want = len(self.data)
        chunk = self.data[self.pos:want]
        self.pos = max(self.pos, min(want, len(self.data)))
        return chunk


class SimSource:
    """Generates exactly the stream the board would send (mode: auto/full/approx)."""

    def __init__(self, model, gate, start=0, mode="auto", realtime=True, junk=3):
        self.m, self.g, self.k, self.mode = model, gate, start, mode
        self.t0 = time.time()
        self.sent = 0
        self.realtime = realtime
        self.junk = junk
        self.prev_g = 0
        self.first = True

    def read(self):
        target = int((time.time() - self.t0) * FS) if self.realtime else 360 * 3600
        n = target - self.sent
        if not self.realtime:
            n = min(n, 360 * 40)
        out = bytearray()
        if self.first:
            out.extend(b"\x13\x37\xA5"[: self.junk])   # start listening in the middle of a frame
            self.first = False
        for _ in range(max(0, n)):
            i = self.k % self.m.N
            g = int(self.g[i])
            if self.mode == "full":
                y = self.m.y_full[i]
            elif self.mode == "approx":
                y = self.m.y_apx[i]
            else:
                y = self.m.y_full[i] if g else self.m.y_apx[i]
            peak = 1 if (g and not self.prev_g) else 0
            self.prev_g = g
            flags = g | (peak << 1) | ((1 if self.mode != "auto" else 0) << 2)
            b = [0xA5] + list(struct.pack(">i", int(np.int32(y)))) + [flags]
            c = 0
            for v in b:
                c ^= v
            out.extend(bytes(b + [c]))
            self.k += 1
            self.sent += 1
        return bytes(out)


def fallback_gate(model, thr_frac=0.25):
    """Rehearsal-only gate when the golden gate file is not available (simple envelope detector)."""
    env = np.abs(model.y_full).astype(float)
    thr = thr_frac * env.max()
    g = np.zeros(model.N, dtype=np.int8)
    i = 0
    while i < model.N:
        if env[i] > thr:
            g[i:i + 43] = 1
            i += 72
        else:
            i += 1
    return g


# ----------------------------------------------------------------------------- viewer state
GROUP_DELAY = (N_TAPS - 1) // 2      # 25 samples = 69.4 ms: inherent delay of the linear-phase FIR


class State:
    def __init__(self, model, win_s=6.0):
        self.m = model
        self.W = int(win_s * FS)
        self.ys = deque(maxlen=self.W)
        self.gs = deque(maxlen=self.W)
        self.errs = deque(maxlen=self.W)
        self.ks = deque(maxlen=self.W)         # ROM index of every displayed frame
        self.pending = []
        self.k = None
        self.total = 0
        self.match = 0
        self.mismatch = 0
        self.recent = deque(maxlen=60)
        self.gate_hist = deque(maxlen=FS * 30)
        self.full_hist = deque(maxlen=FS * 30)
        self.peak_hist = deque(maxlen=54)       # last 150 ms
        self.base_tog = 0
        self.act_tog = 0
        self.prev_b = 0
        self.prev_a = 0
        self.mode_votes = deque(maxlen=90)
        self.aligned_at = None
        self.realigns = 0
        self.bad = 0
        self.last_frame_wall = 0.0
        self.last_full = 0

    def try_align(self, frames):
        F = min(24, len(frames))
        if F < 16:
            return None
        Y = np.array([f[0] for f in frames[:F]], dtype=np.int64)
        G = np.array([f[1] & 1 for f in frames[:F]], dtype=bool)
        N = self.m.N
        ks = (np.arange(N)[:, None] + np.arange(F)[None, :]) % N
        yf = self.m.y_full[ks]
        ya = self.m.y_apx[ks]
        cand = ((yf == Y).all(1)) | ((ya == Y).all(1)) | ((np.where(G[None, :], yf, ya) == Y).all(1))
        hits = np.flatnonzero(cand)
        return int(hits[0]) if len(hits) else None

    def push(self, frames):
        if frames:
            self.last_frame_wall = time.time()
        while frames:
            if self.k is None:
                self.pending.extend(frames)
                frames = []
                k0 = None
                for s in (0, 60):   # s = 60: board just reset, its first 51 outputs used a zero history
                    if len(self.pending) >= s + 24:
                        kk = self.try_align(self.pending[s:s + 24])
                        if kk is not None:
                            k0 = (kk - s) % self.m.N
                            break
                if k0 is None:
                    if len(self.pending) > 400:
                        self.pending = self.pending[-100:]
                    return
                self.k = k0
                frames, self.pending = self.pending, []
                self.aligned_at = self.total
            for i, (y, fl) in enumerate(frames):
                self.one(y, fl)
                if len(self.recent) == self.recent.maxlen and sum(self.recent) < 0.5 * len(self.recent):
                    # the stream no longer matches the model (board reset, other ROM, ...): align again
                    self.k = None
                    self.realigns += 1
                    self.recent.clear()
                    frames = frames[i + 1:]
                    break
            else:
                return

    def one(self, y, fl):
        m = self.m
        k = self.k % m.N
        gate = fl & 1
        forced = (fl >> 2) & 1
        yf, ya = m.y_full[k], m.y_apx[k]
        ym = yf if gate else ya
        warm = k < N_TAPS
        if forced:
            if y == yf and y != ya:
                mode = "F"
            elif y == ya and y != yf:
                mode = "A"
            else:
                mode = self.mode_votes[-1] if self.mode_votes else "F"
            self.mode_votes.append(mode)
            ok = (y == (yf if mode == "F" else ya))
            full_used = (mode == "F")
        else:
            self.mode_votes.append("G")
            ok = (y == ym)
            full_used = bool(gate)
        if not warm:
            self.recent.append(1 if ok else 0)
            self.total += 1
            self.match += 1 if ok else 0
            self.mismatch += 0 if ok else 1
        low = m.operand_low_bytes(k)
        tb, self.prev_b = toggles(low, self.prev_b)
        ta, self.prev_a = toggles(low if full_used else np.zeros_like(low), self.prev_a)
        self.base_tog += tb
        self.act_tog += ta
        self.ys.append(y)
        self.gs.append(1 if full_used else 0)
        self.errs.append(y - yf)
        self.ks.append(k)
        self.gate_hist.append(gate)
        self.full_hist.append(1 if full_used else 0)
        self.peak_hist.append(1 if (fl >> 1) & 1 else 0)
        self.last_full = 1 if full_used else 0
        self.k += 1

    def mode_label(self):
        if not self.mode_votes:
            return "locking ..."
        last = list(self.mode_votes)[-60:]
        g, f, a = last.count("G"), last.count("F"), last.count("A")
        if g >= f and g >= a:
            return "AUTOMATIC  (gated precision)"
        return "FORCED FULL precision" if f >= a else "FORCED APPROXIMATE (8-bit)"

    def mode_kind(self):
        t = self.mode_label()
        return "auto" if t.startswith("AUTO") else ("full" if "FULL" in t else ("approx" if "APPROX" in t else "lock"))

    def bpm(self):
        h = np.array(self.gate_hist, dtype=int)
        if len(h) < FS * 6:
            return None
        rises = int(((h[1:] == 1) & (h[:-1] == 0)).sum())
        return rises * 60.0 / (len(h) / FS)

    def duty(self):
        """share of the last 30 s in which the multiplier really ran at 16-bit precision"""
        return 100.0 * float(np.mean(self.full_hist)) if self.full_hist else 0.0

    def toggle_saving(self):
        return 100.0 * (1.0 - self.act_tog / self.base_tog) if self.base_tog else 0.0

    def input_trace(self):
        """unfiltered input (mV) for the displayed frames, indexed by ROM position"""
        if not self.ks:
            return np.zeros(0)
        idx = np.array(self.ks, dtype=np.int64) % self.m.N
        return self.m.x[idx] * MV_PER_LSB


# ----------------------------------------------------------------------------- drawing
def build_figure(plt, compensated):
    from matplotlib.patches import Rectangle, Circle
    fig = plt.figure(figsize=(13.6, 8.2), facecolor="white")
    gs = fig.add_gridspec(4, 2, height_ratios=[1.1, 2.6, 2.6, 1.25], width_ratios=[4.6, 1.5],
                          left=0.06, right=0.985, top=0.955, bottom=0.07, hspace=0.34, wspace=0.05)
    axh = fig.add_subplot(gs[0, :])
    axh.set_xlim(0, 1)
    axh.set_ylim(0, 1)
    axh.axis("off")
    axa = fig.add_subplot(gs[1, 0])
    axb = fig.add_subplot(gs[2, 0], sharex=axa)
    axc = fig.add_subplot(gs[3, 0], sharex=axa)
    axt = fig.add_subplot(gs[1:, 1])
    axt.axis("off")
    for ax in (axa, axb, axc):
        ax.grid(alpha=0.25)
    axa.set_ylabel("mV", fontsize=10)
    axb.set_ylabel("mV equivalent", fontsize=10)
    axc.set_ylabel("error (uV)", fontsize=10)
    axc.set_xlabel("time (s), 0 = now", fontsize=10)
    axa.set_title("1  UNFILTERED INPUT  -  the recording stored in the FPGA, exactly what goes into the filter", fontsize=11,
                  loc="left", fontweight="bold", color="#555555")
    axb.set_title("2  FILTERED OUTPUT  -  live from the FPGA over USB  (green = full 16-bit precision)", fontsize=11,
                  loc="left", fontweight="bold", color="#1f4e9c")
    axc.set_title("3  error of the FPGA output vs a full-precision calculation", fontsize=9.5, loc="left", color="#b3261e")
    # header: bar + LED dots
    axh.add_patch(Rectangle((0.0, 0.08), 1.0, 0.84, facecolor="#f3f6fb", edgecolor="#c9d3e3", lw=1))
    art = {"bar_bg": Rectangle((0.02, 0.12), 0.50, 0.17, facecolor="#dfe6f0", edgecolor="#9aa7bb"),
           "bar": Rectangle((0.02, 0.12), 0.0, 0.17, facecolor="#2ca02c", edgecolor="none"),
           "leds": [], "ledtx": []}
    axh.add_patch(art["bar_bg"])
    axh.add_patch(art["bar"])
    art["h_big"] = axh.text(0.02, 0.93, "", fontsize=16.5, fontweight="bold", color="#14325c", va="top", transform=axh.transAxes)
    art["h_sub"] = axh.text(0.02, 0.60, "", fontsize=9.4, color="#444444", va="top", transform=axh.transAxes)
    names = ["GATE", "PEAK", "MODE", "LINK"]
    for i, nm in enumerate(names):
        cx = 0.62 + i * 0.100
        c = axh.scatter([cx], [0.66], s=620, facecolor="#bbbbbb", edgecolor="#444444", linewidths=1.5, zorder=3, transform=axh.transAxes)
        art["leds"].append(c)
        axh.text(cx, 0.27, nm, fontsize=8.6, ha="center", fontweight="bold", color="#333333", transform=axh.transAxes)
        art["ledtx"].append(axh.text(cx, 0.10, "", fontsize=7.4, ha="center", color="#666666", transform=axh.transAxes))
    (lraw,) = axa.plot([], [], color="#555555", lw=1.1)
    (lout,) = axb.plot([], [], color="#1f4e9c", lw=1.3)
    (lerr,) = axc.plot([], [], color="#b3261e", lw=1.0)
    art.update({"lraw": lraw, "lout": lout, "lerr": lerr, "shade": [], "texts": [], "axes": (axa, axb, axc, axt, axh)})
    art["note_a"] = axa.text(0.995, 0.04, "", fontsize=8.2, color="#444444", ha="right", va="bottom", transform=axa.transAxes,
                             bbox=dict(facecolor="white", alpha=0.85, edgecolor="none", pad=1.5))
    art["comp"] = {"v": compensated}
    return fig, art


def draw(state, fig, art, args, src_name):
    axa, axb, axc, axt, axh = art["axes"]
    comp = art["comp"]["v"]
    n = len(state.ys)
    duty = state.duty()
    # ---- header
    art["bar"].set_width(0.46 * duty / 100.0)
    art["h_big"].set_text("SYSTEM ACTIVE (full 16-bit precision):  %.1f %%" % duty)
    art["h_sub"].set_text("low-power 8-bit precision: %.1f %%   -   the multiplier only works hard around heartbeats" % (100 - duty))
    link_ok = (time.time() - state.last_frame_wall) < 1.0 if state.last_frame_wall else False
    kind = state.mode_kind()
    cols = {
        0: ("#2ca02c" if state.last_full else "#bbbbbb", "full now" if state.last_full else "8-bit now"),
        1: ("#f5a623" if any(state.peak_hist) else "#bbbbbb", "heartbeat" if any(state.peak_hist) else "-"),
        2: ({"auto": "#1f77b4", "full": "#d62728", "approx": "#ff7f0e", "lock": "#bbbbbb"}[kind],
            {"auto": "automatic", "full": "forced full", "approx": "forced 8-bit", "lock": "locking"}[kind]),
        3: ("#2ca02c" if link_ok else "#d62728", "data flowing" if link_ok else "no data"),
    }
    for i, c in enumerate(art["leds"]):
        c.set_facecolor(cols[i][0])
        art["ledtx"][i].set_text(cols[i][1])
    # ---- traces
    if n >= 2:
        y = np.array(state.ys, dtype=float) * MV_PER_LSB / 32768.0
        g = np.array(state.gs, dtype=bool)
        e = np.array(state.errs, dtype=float) * MV_PER_LSB / 32768.0 * 1000.0
        raw = state.input_trace()
        t = (np.arange(n) - (n - 1)) / FS
        shift = GROUP_DELAY / FS if comp else 0.0
        art["lraw"].set_data(t + shift, raw)
        art["lout"].set_data(t, y)
        art["lerr"].set_data(t, e)
        for c in art["shade"]:
            c.remove()
        art["shade"].clear()
        for ax in (axa, axb, axc):
            art["shade"].append(ax.fill_between(t, 0, 1, where=g, transform=ax.get_xaxis_transform(),
                                                color="#2ca02c", alpha=0.14, linewidth=0))
        lo, hi = float(raw.min()), float(raw.max())
        pad = max(0.08, (hi - lo) * 0.12)
        axa.set_ylim(lo - pad, hi + pad)
        span = max(0.05, float(np.max(np.abs(y))) * 1.25)
        axb.set_ylim(-span, span)
        es = max(5.0, float(np.max(np.abs(e))) * 1.2)
        axc.set_ylim(-es, es)
        axa.set_xlim(-state.W / FS, 0)
    art["note_a"].set_text("shown %s" % ("DELAY-COMPENSATED (+%d samples = %.0f ms): input beat lines up with output beat   [d to switch]" % (GROUP_DELAY, 1000.0 * GROUP_DELAY / FS)
                                         if comp else "as it ENTERS the filter: output beat appears %d samples = %.0f ms later (filter delay)   [d to switch]" % (GROUP_DELAY, 1000.0 * GROUP_DELAY / FS)))
    # ---- text panel
    bpm = state.bpm()
    status = "BIT-EXACT" if state.total and state.mismatch == 0 else ("CHECKING ..." if not state.total else "MISMATCH")
    colr = "#1b7f4b" if status == "BIT-EXACT" else ("#555555" if status == "CHECKING ..." else "#b3261e")
    lines = [("SOURCE", src_name, "k"),
             ("MODE (from the data)", state.mode_label(), "#1f4e9c"),
             ("FPGA output vs software model", "%s  %d/%d" % (status, state.match, state.total), colr),
             ("heart rate (detector gates)", ("%.0f beats/min" % bpm) if bpm else "measuring ...", "k"),
             ("operand-bus toggles (model)", "%.1f %% fewer" % state.toggle_saving(), "#b86e00"),
             ("  exact -> gated", "{:,} -> {:,}".format(state.base_tog, state.act_tog), "#555555"),
             ("bad bytes / re-syncs", "%d / %d" % (state.bad, state.realigns), "#555555")]
    for tx in art["texts"]:
        tx.remove()
    art["texts"].clear()
    ypos = 0.985
    for lab, val, col in lines:
        art["texts"].append(axt.text(0.0, ypos, lab, fontsize=8.4, color="#555555", transform=axt.transAxes, va="top"))
        art["texts"].append(axt.text(0.0, ypos - 0.036, val, fontsize=10.2, fontweight="bold", color=col, transform=axt.transAxes, va="top", wrap=True))
        ypos -= 0.098
    art["texts"].append(axt.text(0.0, 0.0,
                                 "Input panel = stored recording (identical copy\nin the viewer, proven by the bit-exact check).\n"
                                 "Toggle figure = software model, NOT a power\nmeasurement. RTL simulation (record 100):\n"
                                 "datapath -%.1f %%, whole core -%.1f %%." % (args.sim_dp, args.sim_wc),
                                 fontsize=7.6, color="#666666", transform=axt.transAxes, va="bottom"))


# ----------------------------------------------------------------------------- self test
def selftest(model, gate):
    ok_all = True

    def check(name, cond, extra=""):
        nonlocal ok_all
        ok_all &= bool(cond)
        print("  [%s] %s %s" % ("PASS" if cond else "FAIL", name, extra))

    print("VIEWER SELFTEST")
    for mode in ("auto", "full", "approx"):
        src = SimSource(model, gate, 5000, mode, realtime=False, junk=3)
        data = src.read()[: 3000 * FRAME + 3]
        p = FrameParser()
        st = State(model)
        st.push(p.feed(data))
        check("simulated %s stream bit-exact" % mode, st.total > 2500 and st.mismatch == 0,
              "(%d frames, %d mismatches)" % (st.total, st.mismatch))
        check("mode %s inferred" % mode, st.mode_kind() == mode, "(%s)" % st.mode_label())
        if mode == "auto":
            sv = st.toggle_saving()
            check("operand toggle saving plausible (70-95 %%)", 70.0 < sv < 95.0, "(%.1f %%)" % sv)
            ks = np.array(st.ks)
            check("input panel index = consecutive ROM positions", bool(np.all((ks[1:] - ks[:-1]) % model.N == 1)))
            check("input panel shows the ROM samples", np.allclose(st.input_trace(), model.x[ks] * MV_PER_LSB))
            check("input trace length equals output length", len(st.input_trace()) == len(st.ys))
            check("group delay = 25 samples (69.4 ms)", GROUP_DELAY == 25 and abs(1000 * GROUP_DELAY / FS - 69.44) < 0.01)
    # corrupted byte -> resync, still mostly exact
    src = SimSource(model, gate, 12000, "auto", realtime=False, junk=0)
    data = bytearray(src.read()[: 2000 * FRAME])
    data[7 * 700 + 3] ^= 0xFF
    p = FrameParser()
    st = State(model)
    st.push(p.feed(bytes(data)))
    check("survives one corrupted byte (resync)", st.total > 1800 and p.bad >= 1, "(frames %d, bad %d)" % (st.total, p.bad))
    # board reset in the middle: stream jumps back to sample 0
    a = SimSource(model, gate, 20000, "auto", realtime=False, junk=0).read()[: 1500 * FRAME]
    b = SimSource(model, gate, 0, "auto", realtime=False, junk=0).read()[: 1500 * FRAME]
    p = FrameParser()
    st = State(model)
    st.push(p.feed(a + b))
    check("re-aligns after a board reset", st.realigns >= 1 and st.mismatch < 60, "(realigns %d, mismatches %d)" % (st.realigns, st.mismatch))
    print("VIEWER SELFTEST: %s" % ("PASS" if ok_all else "FAIL"))
    return 0 if ok_all else 1


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Live viewer for the FPGA ECG demo")
    ap.add_argument("--port")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--file")
    ap.add_argument("--simulate", action="store_true")
    ap.add_argument("--sim-mode", choices=["auto", "full", "approx"], default="auto")
    ap.add_argument("--sim-start", type=int, default=0, help="ROM sample index where the simulated stream starts")
    ap.add_argument("--rom", help="ecg_rom.mem (or any tv_inputs.hex) used to build the board's bitstream")
    ap.add_argument("--coeffs")
    ap.add_argument("--gate-file", help="tv_gate_flags.hex for --simulate (optional)")
    ap.add_argument("--window", type=float, default=6.0, help="seconds shown")
    ap.add_argument("--align", choices=["arrival", "compensated"], default="arrival",
                    help="arrival = input shown when it enters the filter; compensated = shifted by the 25-sample filter delay")
    ap.add_argument("--snapshot", help="write a PNG and exit (headless)")
    ap.add_argument("--duration", type=float, default=12.0, help="seconds of data for --snapshot")
    ap.add_argument("--sim-dp", type=float, default=21.75, help="RTL-simulation datapath reduction to print (%%)")
    ap.add_argument("--sim-wc", type=float, default=14.29, help="RTL-simulation whole-core reduction to print (%%)")
    ap.add_argument("--interval", type=int, default=120, help="screen refresh interval in ms (smaller = smoother, more CPU)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--list-ports", action="store_true")
    a = ap.parse_args()

    if a.list_ports:
        try:
            from serial.tools import list_ports
            for p in list_ports.comports():
                print("%s - %s" % (p.device, p.description))
        except ImportError:
            print("pyserial missing: python -m pip install pyserial")
        return 0

    rom_p, co_p = find_file("ecg_rom.mem", a.rom), find_file("coeffs.mem", a.coeffs)
    if not rom_p or not co_p:
        sys.exit("Cannot find ecg_rom.mem / coeffs.mem. Run from the repo folder or pass --rom/--coeffs.")
    model = Model(read_mem16(rom_p), read_mem16(co_p))

    gp = find_file(os.path.join("data", "test_vectors", "std_fixed_100", "tv_gate_flags.hex"), a.gate_file)
    if gp:
        gate = np.resize(np.array([int(l, 16) for l in open(gp).read().split()], dtype=np.int8), model.N)
    else:
        gate = fallback_gate(model)
    if a.selftest:
        return selftest(model, gate)

    headless = bool(a.snapshot)
    import matplotlib
    if headless:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    realtime = not headless
    if a.simulate:
        src = SimSource(model, gate, a.sim_start, a.sim_mode, realtime)
        src_name = "SIMULATED stream (%s)" % a.sim_mode
    elif a.file:
        src = FileSource(a.file, realtime)
        src_name = "file " + os.path.basename(a.file)[:26]
    elif a.port:
        src = SerialSource(a.port, a.baud)
        src_name = "LIVE board on " + a.port
    else:
        ap.print_help()
        return 0

    parser = FrameParser()
    state = State(model, a.window)
    fig, art = build_figure(plt, a.align == "compensated")
    paused = {"v": False}

    def step():
        data = src.read()
        if data:
            frames = parser.feed(data)
            state.bad = parser.bad
            state.push(frames)

    if headless:
        t_end = a.duration * FS
        guard = 0
        while state.total + len(state.pending) < t_end + 30 and guard < 200:
            before = state.total
            step()
            guard += 1
            if isinstance(src, FileSource) and src.pos >= len(src.data) and state.total == before:
                break
            if isinstance(src, SimSource) and state.total > t_end:
                break
        state.bad = parser.bad
        state.last_frame_wall = time.time()
        draw(state, fig, art, a, src_name)
        fig.savefig(a.snapshot, dpi=110)
        print("saved", a.snapshot, "frames", state.total, "match", state.match, "mismatch", state.mismatch,
              "mode", state.mode_label(), "toggle saving %.2f%%" % state.toggle_saving(), "active %.1f%%" % state.duty())
        return 0

    from matplotlib.animation import FuncAnimation

    def on_key(ev):
        if ev.key == "p":
            paused["v"] = not paused["v"]
        elif ev.key == "d":
            art["comp"]["v"] = not art["comp"]["v"]
        elif ev.key == "s":
            fn = time.strftime("viewer_%H%M%S.png")
            fig.savefig(fn, dpi=130)
            print("saved", fn)
        elif ev.key == "q":
            plt.close(fig)

    fig.canvas.mpl_connect("key_press_event", on_key)

    def tick(_):
        if not paused["v"]:
            step()
            state.bad = parser.bad
        draw(state, fig, art, a, src_name + ("   [PAUSED]" if paused["v"] else ""))
        return []

    anim = FuncAnimation(fig, tick, interval=max(30, a.interval), blit=False, cache_frame_data=False)
    plt.show()
    return 0


if __name__ == "__main__":
    sys.exit(main())
