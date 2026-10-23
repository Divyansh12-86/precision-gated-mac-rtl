// =============================================================================
// Module: top_basys3
// Description: Clean Verilog-2001 wrapper for Digilent Basys 3 (Artix-7 xc7a35tcpg236-1).
//              Instantiates unified board_core without extraneous internal logic.
//              Pins:
//                - clk: 100 MHz onboard oscillator (W5)
//                - btnC: Pushbutton reset (U18, active high -> active low rst_n)
//                - sw[1:0]: Mode select (00=Auto, 01=Force Full, 10=Force Approx)
//                - sw[2]: Playback pause switch
//                - RsTx: UART serial stream out to PC (A18, 115200 8N1)
//                - led[0]: Gate active indicator
//                - led[1]: QRS peak pulse indicator
//                - led[2]: Filter busy indicator
//                - led[3]: System heartbeat (0.74 Hz)
//                - led[15:8]: Filtered ECG MSB monitor
// =============================================================================
`timescale 1ns / 1ps

module top_basys3 (
    input  wire        clk,
    input  wire        btnC,   // Active-high reset button
    input  wire [2:0]  sw,     // sw[1:0]=mode_force, sw[2]=pause
    output wire        RsTx,   // UART TX output (pin A18)
    output wire [15:0] led     // Diagnostic LEDs
);

    wire rst_n = ~btnC;
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
        .clk(clk),
        .rst_n(rst_n),
        .sw_mode_force(sw[1:0]),
        .sw_pause(sw[2]),
        .uart_txd(RsTx),
        .led_gate(led_gate),
        .led_peak(led_peak),
        .led_busy(led_busy),
        .led_heartbeat(led_heartbeat),
        .led_y_msb(led_y_msb)
    );

    assign led[0]    = led_gate;
    assign led[1]    = led_peak;
    assign led[2]    = led_busy;
    assign led[3]    = led_heartbeat;
    assign led[7:4]  = 4'b0000;
    assign led[15:8] = led_y_msb;

endmodule
