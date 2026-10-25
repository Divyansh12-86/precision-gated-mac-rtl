# Running the Precision-Gated ECG Demo on FPGA Hardware

This guide explains how to program and verify the bit-exact ECG filter demo on Basys 3 or Nexys A7.

## 1. Prerequisites
- **Hardware:** Digilent Basys 3 (`xc7a35tcpg236-1`) or Nexys A7 (`xc7a100tcsg324-1`), micro-USB cable.
- **Software:** Xilinx Vivado (2020.2+), Python 3 with `pyserial`.

## 2. Project Setup & Bitstream Generation
1. Open Vivado, create an **RTL Project**, select target part (`xc7a35tcpg236-1` or `xc7a100tcsg324-1`).
2. **Add 12 Verilog Sources:**
   - RTL: `pg_top.v`, `pg_fir.v`, `qrs_detector.v`, `sample_delay_line.v`, `fir_coeff_rom.v`, `mult_split.v`, `pg_mac.v`, `sample_tick_gen.v`
   - FPGA: `board_core.v`, `uart_tx.v`, and the top wrapper `top_basys3.v` or `top_nexys_a7.v`
   - **WARNING:** Do NOT add `baseline_fir_exact.v` (separate comparison benchmark core).
3. **Add Memory Files as Design Sources:** `ecg_rom.mem` and `coeffs.mem` (coefficients will be zero if omitted).
4. **Add Constraints:** `fpga/boards/basys3.xdc` (for Basys 3) or `fpga/boards/nexys_a7.xdc` (for Nexys A7).
5. **Set Top Module:** Set `top_basys3` or `top_nexys_a7` as Top, then click **Generate Bitstream**.

## 3. Programming & Live Capture Verification
1. Power on board and connect via USB. Open **Hardware Manager** -> **Program Device**.
2. Internal 16-bit Power-On Reset (POR) automatically initializes detector registers; button reset (`btnC` / `CPU_RESETN`) is optional. Mode-switch changes take effect after 1–2 samples (≈ 3–6 ms) due to sample-tick latching.
3. Run the host capture script within ~2 minutes of power-up/reset (during first ROM playback pass):
   ```bash
   python3 scripts/uart_capture.py --port /dev/ttyUSB0 --baud 115200 --ref data/test_vectors/std_fixed_100
   ```
4. **Expected Output:**
   ```text
   Alignment: first captured frame = ROM sample 0, matching reference 'gated (automatic mode)'
   Samples compared         : 5000
   Filter output mismatches : 0
   Gate flag mismatches     : 0
   STATUS: PASS - the FPGA output is bit-exact with the Python/RTL golden model
   ```
