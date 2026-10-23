# Running the Precision-Gated ECG Demo on FPGA Hardware

This guide explains how to program and verify the design on a physical Digilent FPGA board (Basys 3 or Nexys A7).

## 1. Prerequisites
- **Hardware:** Digilent Basys 3 (`xc7a35tcpg236-1`) or Nexys A7 (`xc7a100tcsg324-1` / `xc7a50tcsg324-1`), micro-USB cable.
- **Software:** Xilinx Vivado (2020.2 or newer), Python 3 with `pyserial`.

## 2. Project Setup & Bitstream Generation
1. Open Vivado and select **Create Project** -> **RTL Project**.
2. Select target FPGA part: Basys 3 (`xc7a35tcpg236-1`) or Nexys A7 (`xc7a100tcsg324-1`).
3. **Add Design Sources:** Add all files in `rtl/*.v`, `fpga/*.v`, and `ecg_rom.mem` (as Design Source).
4. **Add Constraints:** Add `fpga/boards/basys3.xdc` (for Basys 3) or `fpga/boards/nexys_a7.xdc` (for Nexys A7).
5. **Set Top Module:** Right-click `top_basys3` or `top_nexys_a7` -> **Set as Top**.
6. **Generate Bitstream:** Click **Generate Bitstream** (runs Synthesis & Implementation).

## 3. Programming & Live Capture Verification
1. Connect board to PC via USB and power on. Open **Hardware Manager** -> **Auto Connect** -> **Program Device**.
2. Identify the USB-UART serial port (`COMx` on Windows, `/dev/ttyUSBx` on Linux).
3. Press the hardware reset button (`btnC` on Basys 3, red `CPU_RESETN` on Nexys A7).
4. Run the aligned host verification script (within 2 minutes of reset):
   ```bash
   python3 scripts/uart_capture.py --port /dev/ttyUSB0 --baud 115200 --ref data/test_vectors/std_fixed_100
   ```
5. **Expected Output:**
   ```
   LIVE NUMBERS FROM THE BOARD
     Captured time            : 13.9 s (5000 samples)
     Full-precision duty      : 15.2 %   (approximate mode: 84.8 %)
     QRS gates detected       : 18  ->  about 78 beats/min
   STATUS: PASS - the FPGA output is bit-exact with the Python/RTL golden model
   ```
