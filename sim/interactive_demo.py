"""
sim/interactive_demo.py — Real-Time Live Oscilloscope & Power Visualizer

Demonstrates live real-time ECG filtering with dynamic precision gating.
Ideal for live professor demonstrations, video recordings, or slide embeds.

Features:
1. Panel 1 (Top): Raw, Unfiltered ECG from MIT-BIH dataset (showing baseline drift & sensor noise).
2. Panel 2 (Middle): Denoised Precision-Gated Output:
   - Distinct Gray Dotted Line (width 3.2): 16-bit Full Precision Reference
   - Multi-Color Active Trace: Crimson Red (#ef4444) for 16-bit QRS, Neon Cyan (#06b6d4) for 8-bit Baseline
3. Panel 3 (Bottom): Instantaneous Dynamic Power Consumption: Fixed 16-bit (100%) vs Precision-Gated (~57.5%).
4. Bottom Dashboard: 4 clean, non-overlapping cards with mode, live power reduction, PRD, and active gating specs.
"""

import os
import sys
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.collections as mcoll
import wfdb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from golden_model import design_fir_filter, to_fixed, from_fixed, truncate_bits, FS
from qrs_detector import HardwareQRSDetector

def create_interactive_demo(record_id='100', duration_sec=30, save_gif=False, gif_path=None):
    base_data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'mitbih')
    path = os.path.join(base_data_dir, record_id)
    record = wfdb.rdrecord(path)
    raw = record.p_signal[:, 0]
    
    # Normalize & quantize to Q1.15
    sig_min, sig_max = np.min(raw), np.max(raw)
    norm = (raw - sig_min) / (sig_max - sig_min) * 2.0 - 1.0
    x_fixed = to_fixed(norm)
    taps = design_fir_filter()
    
    # Detector setup
    detector = HardwareQRSDetector(fs=FS)
    detector.calibrate(x_fixed[:2*FS])
    
    total_samples = int(duration_sec * FS)
    x_fixed = x_fixed[:total_samples]
    raw_sub = raw[:total_samples]
    
    # Pre-simulate with accurate Q1.15 scaling (>> 15)
    n_samples = len(x_fixed)
    n_taps = len(taps)
    y_full = np.zeros(n_samples)
    y_gated = np.zeros(n_samples)
    gate_flags = np.zeros(n_samples, dtype=bool)
    pwr_full = np.zeros(n_samples)
    pwr_gated = np.zeros(n_samples)
    
    buf_f = np.zeros(n_taps, dtype=np.int64)
    buf_g = np.zeros(n_taps, dtype=np.int64)
    
    for i in range(n_samples):
        gf, is_pk, _ = detector.step(x_fixed[i])
        gate_flags[i] = gf
        
        buf_f[1:] = buf_f[:-1]; buf_f[0] = x_fixed[i]
        buf_g[1:] = buf_g[:-1]; buf_g[0] = x_fixed[i]
        
        # Hardware Q1.15 FIR: product is 32-bit (Q2.30), shifted right by 15
        acc_f = np.sum(buf_f * taps) >> 15
        y_full[i] = from_fixed(acc_f)
        pwr_full[i] = 100.0 # 100% baseline continuous 16-bit MAC
        
        # Gated Path: Lower 8 bits truncated to zero when gate is False
        op_g = buf_g if gf else truncate_bits(buf_g, 8)
        acc_g = np.sum(op_g * taps) >> 15
        y_gated[i] = from_fixed(acc_g)
        pwr_gated[i] = 100.0 if gf else 57.5 # ~42.5% power reduction in approx mode

    # Setup animation figure with 4 stacked rows (Raw, Filtered, Power, Dashboard)
    fig = plt.figure(figsize=(15, 9.4), facecolor='#0b0f19')
    gs = fig.add_gridspec(4, 1, height_ratios=[1.5, 2.1, 1.1, 0.8], hspace=0.38, bottom=0.06, top=0.95)
    
    ax_raw = fig.add_subplot(gs[0], facecolor='#111827')
    ax_ecg = fig.add_subplot(gs[1], facecolor='#111827', sharex=ax_raw)
    ax_pwr = fig.add_subplot(gs[2], facecolor='#111827', sharex=ax_raw)
    ax_dash = fig.add_subplot(gs[3], facecolor='#0b0f19')
    ax_dash.axis('off')
    
    win_len = 720 # 2.0 seconds visible window (720 samples @ 360 Hz)
    time_axis = np.arange(win_len) / FS
    
    # --- 1. Top Plot: Raw Unfiltered Dataset ECG ---
    line_raw, = ax_raw.plot([], [], color='#f59e0b', linewidth=1.4, alpha=0.9, label='Raw Dataset Input (Noisy Sensor Signal)')
    ax_raw.set_xlim(0, win_len / FS)
    raw_min_v, raw_max_v = np.min(raw_sub), np.max(raw_sub)
    ax_raw.set_ylim(raw_min_v - 0.2, raw_max_v + 0.2)
    ax_raw.set_ylabel("Raw Input (mV)", color='#94a3b8', fontsize=9.5, fontweight='bold')
    ax_raw.set_title("STAGE 1: RAW UNFILTERED ECG FROM MIT-BIH DATASET (WITH BASELINE DRIFT & NOISE)",
                     color='#f8fafc', fontsize=11, fontweight='bold', pad=8)
    ax_raw.tick_params(colors='#94a3b8', labelsize=8.5)
    ax_raw.grid(True, color='#1f2937', linestyle=':', alpha=0.8)
    ax_raw.legend(loc='upper right', facecolor='#1e293b', edgecolor='#334155', labelcolor='white', fontsize=8.5)
    
    # --- 2. Middle Plot: Denoised Precision-Gated ECG ---
    line_ref, = ax_ecg.plot([], [], color='#64748b', linewidth=3.2, linestyle=':', alpha=0.95,
                             label='16-bit Full Precision Reference (Exact Baseline)')
    
    lc_ecg = mcoll.LineCollection([], linewidths=1.8, zorder=3)
    ax_ecg.add_collection(lc_ecg)
    
    ax_ecg.set_ylim(-1.05, 0.85)
    ax_ecg.set_ylabel("Filtered Output", color='#94a3b8', fontsize=9.5, fontweight='bold')
    ax_ecg.set_title("STAGE 2: PRECISION-GATED MAC DENOISED OUTPUT (16-BIT QRS / 8-BIT BASELINE)",
                     color='#f8fafc', fontsize=11, fontweight='bold', pad=8)
    ax_ecg.tick_params(colors='#94a3b8', labelsize=8.5)
    ax_ecg.grid(True, color='#1f2937', linestyle=':', alpha=0.8)
    
    custom_lines = [
        plt.Line2D([0], [0], color='#64748b', lw=3.0, linestyle=':'),
        plt.Line2D([0], [0], color='#06b6d4', lw=2.0),
        plt.Line2D([0], [0], color='#ef4444', lw=2.0)
    ]
    ax_ecg.legend(custom_lines, [
        '16-bit Reference (Gray Dotted)',
        'Live Approx Mode (8-bit Baseline)',
        'Live Full Mode (16-bit QRS)'
    ], loc='upper right', facecolor='#1e293b', edgecolor='#334155', labelcolor='white', fontsize=8.5)

    # --- 3. Third Plot: Dynamic Power Dissipation ---
    line_pwr_f, = ax_pwr.plot([], [], color='#f43f5e', linewidth=1.4, linestyle='--', label='Fixed 16-bit Continuous Power (100%)')
    line_pwr_g, = ax_pwr.plot([], [], color='#10b981', linewidth=2.0, label='Precision-Gated Dynamic Power')
    ax_pwr.set_ylim(40, 115)
    ax_pwr.set_ylabel("Power (%)", color='#94a3b8', fontsize=9.5, fontweight='bold')
    ax_pwr.set_xlabel("Oscilloscope Window (seconds)", color='#94a3b8', fontsize=9.5, fontweight='bold')
    ax_pwr.tick_params(colors='#94a3b8', labelsize=8.5)
    ax_pwr.grid(True, color='#1f2937', linestyle=':', alpha=0.8)
    ax_pwr.legend(loc='upper right', facecolor='#1e293b', edgecolor='#334155', labelcolor='white', fontsize=8.0)

    # --- 4. Bottom Dashboard: 4 Distinct Non-Overlapping Cards ---
    bbox_style = dict(boxstyle='round,pad=0.45', facecolor='#1e293b', edgecolor='#334155', alpha=0.95)
    
    text_mode = ax_dash.text(0.01, 0.5, "", color='white', fontsize=10, fontweight='bold',
                             verticalalignment='center', bbox=bbox_style)
    text_pwr = ax_dash.text(0.36, 0.5, "", color='#10b981', fontsize=10, fontweight='bold',
                            verticalalignment='center', bbox=bbox_style)
    text_prd = ax_dash.text(0.66, 0.5, "", color='#facc15', fontsize=10, fontweight='bold',
                            verticalalignment='center', bbox=bbox_style)
    text_arch = ax_dash.text(0.86, 0.5, "ACTIVE GATING\n50% Mult Matrix", color='#38bdf8', fontsize=9.5, fontweight='bold',
                             verticalalignment='center', bbox=bbox_style)

    step_size = 6 # Smooth ~60 fps playback
    
    def update(frame):
        idx = frame * step_size
        if idx + win_len >= n_samples:
            idx = 0
            
        w_slice = slice(idx, idx + win_len)
        t_w = time_axis
        
        raw_w = raw_sub[w_slice]
        y_f_w = y_full[w_slice]
        y_g_w = y_gated[w_slice]
        p_f_w = pwr_full[w_slice]
        p_g_w = pwr_gated[w_slice]
        gf_w = gate_flags[w_slice]
        current_gate = gf_w[-1]
        
        # 1. Update raw signal
        line_raw.set_data(t_w, raw_w)
        
        # 2. Update 16-bit reference line
        line_ref.set_data(t_w, y_f_w)
        
        # 3. Update multi-colored filtered signal
        points = np.array([t_w, y_g_w]).T.reshape(-1, 1, 2)
        segments = np.concatenate([points[:-1], points[1:]], axis=1)
        colors = ['#ef4444' if gf_w[k] else '#06b6d4' for k in range(len(segments))]
        lc_ecg.set_segments(segments)
        lc_ecg.set_color(colors)
        
        # 4. Update power traces
        line_pwr_f.set_data(t_w, p_f_w)
        line_pwr_g.set_data(t_w, p_g_w)
        
        # 5. Realistic running window metrics
        window_pwr_sav = (1.0 - np.mean(p_g_w) / 100.0) * 100.0
        window_noise = np.sum((y_f_w - y_g_w)**2)
        window_sig = np.sum(y_f_w**2)
        window_prd = np.sqrt(window_noise / window_sig) * 100.0 if window_sig > 0 else 0.0
        
        # 6. Dashboard card updates
        if current_gate:
            mode_str = "CURRENT MODE: [FULL 16-BIT]\nQRS Spike Window Active"
            mode_col = '#ef4444'
        else:
            mode_str = "CURRENT MODE: [APPROX 8-BIT]\nLow-Power Baseline Active"
            mode_col = '#06b6d4'
            
        text_mode.set_text(mode_str)
        text_mode.set_color(mode_col)
        text_pwr.set_text(f"POWER REDUCTION\n{window_pwr_sav:.1f}% Active Savings")
        text_prd.set_text(f"CLINICAL PRD\n{window_prd:.2f}% (< 2% Very Good)")
        
        return line_raw, line_ref, lc_ecg, line_pwr_f, line_pwr_g, text_mode, text_pwr, text_prd, text_arch

    frames = (n_samples - win_len) // step_size
    ani = animation.FuncAnimation(fig, update, frames=frames, interval=25, blit=True)
    
    if save_gif:
        if gif_path is None:
            gif_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'live_filter_demo.gif')
        print(f"Rendering animated GIF demo to: {gif_path}...")
        ani.save(gif_path, writer='pillow', fps=30)
        print("GIF render complete!")
    else:
        plt.show()

if __name__ == "__main__":
    save_gif_flag = '--gif' in sys.argv
    create_interactive_demo(record_id='100', duration_sec=25, save_gif=save_gif_flag)
