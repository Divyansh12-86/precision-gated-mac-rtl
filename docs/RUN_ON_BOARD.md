# Running the Precision-Gated ECG Demo on FPGA Hardware

This guide explains how to program and verify the bit-exact ECG filter demo on Basys 3 or Nexys A7.

## 1. Setup & Bitstream Generation
1. Connect Digilent Basys 3 or Nexys A7 via micro-USB. Run `make demo-rom` for noisy ECG playback (`ecg_rom_demo_noisy.mem`) or use clean `ecg_rom.mem`.
2. Open Vivado, create an RTL project with part `xc7a35tcpg236-1` (Basys 3) or `xc7a100tcsg324-1` (Nexys A7).
3. Add 12 Verilog sources (`rtl/*.v` except `baseline_fir_exact.v`, plus `fpga/*.v`), `coeffs.mem`, and `ecg_rom.mem` (or `ecg_rom_demo_noisy.mem`).
4. Add constraints (`fpga/boards/basys3.xdc` or `nexys_a7.xdc`), set `top_basys3` or `top_nexys_a7` as Top, and click **Generate Bitstream**.

## 2. Programming & Verification
1. Power board, open Vivado Hardware Manager, and program device. Internal POR auto-initializes all detector states.
2. Verify bit-exact output via UART capture within first ROM playback pass:
   ```bash
   python3 scripts/uart_capture.py --port /dev/ttyUSB0 --baud 115200 --ref data/test_vectors/std_fixed_100
   ```
   Confirms `STATUS: PASS` (0 filter and 0 gate mismatches).

## 3. Demo Computer Without Vivado (Live Viewer)
1. For standalone demonstrations, program board flash memory via SPI/QSPI (set jumper JP1 = QSPI for persistent boot).
2. Connect board via USB and run the interactive live viewer:
   ```bash
   python3 scripts/ecg_live_viewer.py --port /dev/ttyUSB0 --rom ecg_rom.mem
   ```
   Use `--simulate` for offline rehearsal; interactive keys: `p` (pause), `d` (display), `s` (step), `f` (freeze), `q` (quit).
3. The unfiltered panel displays the viewer's local ROM copy (proven by 100% bit-exact stream matching). Output lags input by exactly **25 samples** = **69.4 ms** (filter group delay); host USB and display buffering add ~20–200 ms to both traces.
