// =============================================================================
// Module: top_nexys_a7
// Description: FPGA Board Top-Level for Digilent Nexys A7 (Artix-7 xc7a100tcsg324-1).
// =============================================================================
`timescale 1ns / 1ps

module top_nexys_a7 (
    input  wire        clk,
    input  wire        resetn,      // Active-low CPU reset
    input  wire [1:0]  sw,          // Switches: mode_force
    output wire [15:0] led          // LEDs
);

    wire rst_n = resetn;
    wire sample_tick;
    reg signed [15:0] test_sample;

    sample_tick_gen #(
        .CLK_HZ(100_000_000),
        .FS(360)
    ) u_tick (
        .clk(clk),
        .rst_n(rst_n),
        .enable(1'b1),
        .tick(sample_tick)
    );

    always @(posedge clk) begin
        if (!rst_n) begin
            test_sample <= 16'sd0;
        end else if (sample_tick) begin
            test_sample <= test_sample + 16'sd17;
        end
    end

    wire y_valid;
    wire signed [31:0] y_acc;
    wire gate_out;
    wire peak_pulse;
    wire [17:0] mwi_dbg;
    wire busy;

    pg_top #(
        .N_TAPS(51),
        .PIPE(2),
        .MULT_IMPL("LUT"),
        .COEFF_FILE("coeffs.mem"),
        .SQ_SHIFT(11)
    ) u_pg_top (
        .clk(clk),
        .rst_n(rst_n),
        .sample_valid(sample_tick),
        .x_in(test_sample),
        .mode_force(sw[1:0]),
        .y_valid(y_valid),
        .y_acc(y_acc),
        .gate_out(gate_out),
        .peak_pulse(peak_pulse),
        .mwi_dbg(mwi_dbg),
        .busy(busy)
    );

    reg [22:0] peak_stretch_cnt;
    reg [22:0] gate_stretch_cnt;

    always @(posedge clk) begin
        if (!rst_n) begin
            peak_stretch_cnt <= '0;
            gate_stretch_cnt <= '0;
        end else begin
            if (peak_pulse) peak_stretch_cnt <= 23'd5_000_000;
            else if (peak_stretch_cnt > 0) peak_stretch_cnt <= peak_stretch_cnt - 1'b1;

            if (gate_out) gate_stretch_cnt <= 23'd5_000_000;
            else if (gate_stretch_cnt > 0) gate_stretch_cnt <= gate_stretch_cnt - 1'b1;
        end
    end

    assign led[0]    = (gate_stretch_cnt > 0);
    assign led[1]    = (peak_stretch_cnt > 0);
    assign led[2]    = busy;
    assign led[3]    = y_valid;
    assign led[7:4]  = 4'b0000;
    assign led[15:8] = y_acc[23:16];

endmodule
