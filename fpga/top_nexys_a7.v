// =============================================================================
// Module: top_nexys_a7
// Description: Clean Verilog-2001 wrapper for Digilent Nexys A7 (xc7a50t / xc7a100t).
//              Instantiates unified board_core without extraneous internal logic.
//              Pins:
//                - CLK100MHZ: 100 MHz onboard oscillator (E3)
//                - CPU_RESETN: Active-low red pushbutton reset (C12)
//                - SW[1:0]: Mode select (00=Auto, 01=Force Full, 10=Force Approx)
//                - SW[2]: Playback pause switch
//                - UART_RXD_OUT: UART serial output from FPGA to USB-UART bridge (pin D4)
//                - LED[0]: Gate active indicator
//                - LED[1]: QRS peak pulse indicator
//                - LED[2]: Filter busy indicator
//                - LED[3]: System heartbeat (0.74 Hz)
//                - LED[15:8]: Filtered ECG MSB monitor
// =============================================================================
`timescale 1ns / 1ps

module top_nexys_a7 (
    input  wire        CLK100MHZ,
    input  wire        CPU_RESETN, // Active-low reset button
    input  wire [2:0]  SW,         // SW[1:0]=mode_force, SW[2]=pause
    output wire        UART_RXD_OUT,// FPGA TX -> FTDI RX (pin D4, Digilent name UART_RXD_OUT)
    output wire [15:0] LED         // Diagnostic LEDs
);

    wire rst_n = CPU_RESETN;
    wire led_gate;
    wire led_peak;
    wire led_busy;
    wire led_heartbeat;
    wire [7:0] led_y_msb;

    board_core #(
        .CLK_HZ(100_000_000),
        .FS(360),
        .BAUD(115_200),
        .ROM_FILE("ecg_rom.mem"),
        .ROM_DEPTH(60_000),
        .FAST_TICK(0)
    ) u_core (
        .clk(CLK100MHZ),
        .rst_n(rst_n),
        .sw_mode_force(SW[1:0]),
        .sw_pause(SW[2]),
        .uart_txd(UART_RXD_OUT),
        .led_gate(led_gate),
        .led_peak(led_peak),
        .led_busy(led_busy),
        .led_heartbeat(led_heartbeat),
        .led_y_msb(led_y_msb)
    );

    assign LED[0]    = led_gate;
    assign LED[1]    = led_peak;
    assign LED[2]    = led_busy;
    assign LED[3]    = led_heartbeat;
    assign LED[7:4]  = 4'b0000;
    assign LED[15:8] = led_y_msb;

endmodule
