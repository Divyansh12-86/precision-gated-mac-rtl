// =============================================================================
// Module: pg_fir
// Description: Precision-Gated 51-Tap FIR Filter Core with Single Time-Multiplexed MAC.
//              Operates at full precision or 8-bit approximate precision based on
//              latched gate/mode control for each sample.
//              Parameters:
//                N_TAPS: filter order + 1 (default 51)
//                PIPE: multiplier pipeline stages (default 2)
//                MULT_IMPL: "LUT" or "DSP" (default "LUT")
//                COEFF_FILE: path to coefficients hex file
// =============================================================================
`timescale 1ns / 1ps

module pg_fir #(
    parameter N_TAPS     = 51,
    parameter PIPE       = 2,
    parameter MULT_IMPL  = "LUT",
    parameter COEFF_FILE = "coeffs.mem"
)(
    input  wire                   clk,
    input  wire                   rst_n,
    input  wire                   sample_valid,
    input  wire signed [15:0]     x_in,
    input  wire                   gate_in,
    input  wire [1:0]             mode_force,
    output reg                    y_valid,
    output wire signed [31:0]     y_acc,
    output wire                   busy
);

    localparam STATE_IDLE    = 2'b00;
    localparam STATE_COMPUTE = 2'b01;
    localparam STATE_DRAIN   = 2'b10;

    reg [1:0] state;
    reg [$clog2(N_TAPS+1)-1:0] tap_cnt;
    reg [$clog2(PIPE+2)-1:0]   drain_cnt;

    reg mode_approx_q;
    reg shift_en;
    reg mult_valid_in;
    reg first_prod_done;

    // Determine effective gate: 01=force full, 10=force approx, else auto (gate_in)
    wire eff_gate = (mode_force == 2'b01) ? 1'b1 :
                    (mode_force == 2'b10) ? 1'b0 : gate_in;

    // Delay line
    wire signed [15:0] sample_tap;
    wire [$clog2(N_TAPS)-1:0] tap_idx = tap_cnt[$clog2(N_TAPS)-1:0];

    sample_delay_line #(
        .N_TAPS(N_TAPS),
        .DATA_WIDTH(16)
    ) u_delay_line (
        .clk(clk),
        .rst_n(rst_n),
        .shift_en(shift_en),
        .sample_in(x_in),
        .tap_idx(tap_idx),
        .sample_out(sample_tap)
    );

    // Coefficient ROM
    wire signed [15:0] coeff_tap;
    fir_coeff_rom #(
        .N_TAPS(N_TAPS),
        .COEFF_WIDTH(16),
        .COEFF_FILE(COEFF_FILE)
    ) u_rom (
        .clk(clk),
        .tap_idx(tap_idx),
        .coeff_out(coeff_tap)
    );

    // Multiplier
    wire signed [31:0] prod_out;
    wire               prod_valid;

    mult_split #(
        .MULT_IMPL(MULT_IMPL),
        .PIPE(PIPE)
    ) u_mult (
        .clk(clk),
        .rst_n(rst_n),
        .enable(1'b1),
        .mode_approx(mode_approx_q),
        .x_in(sample_tap),
        .h_in(coeff_tap),
        .valid_in(mult_valid_in),
        .prod_out(prod_out),
        .valid_out(prod_valid)
    );

    // MAC Accumulator
    reg mac_clr;
    pg_mac u_mac (
        .clk(clk),
        .rst_n(rst_n),
        .clr(mac_clr),
        .prod_valid(prod_valid),
        .prod_in(prod_out),
        .acc_out(y_acc)
    );

    assign busy = (state != STATE_IDLE);

    // Control FSM
    always @(posedge clk) begin
        if (!rst_n) begin
            state           <= STATE_IDLE;
            tap_cnt         <= 0;
            drain_cnt       <= 0;
            mode_approx_q   <= 1'b0;
            shift_en        <= 1'b0;
            mult_valid_in   <= 1'b0;
            mac_clr         <= 1'b0;
            y_valid         <= 1'b0;
            first_prod_done <= 1'b0;
        end else begin
            shift_en <= 1'b0;
            y_valid  <= 1'b0;
            mac_clr  <= 1'b0;

            case (state)
                STATE_IDLE: begin
                    mult_valid_in   <= 1'b0;
                    first_prod_done <= 1'b0;
                    if (sample_valid) begin
                        shift_en      <= 1'b1; // Shift in new sample x_in
                        mode_approx_q <= ~eff_gate; // Latch mode for all 51 taps
                        tap_cnt       <= 0;
                        mult_valid_in <= 1'b1;
                        state         <= STATE_COMPUTE;
                    end
                end

                STATE_COMPUTE: begin
                    // Feeding taps 0 to N_TAPS-1 into multiplier
                    if (tap_cnt == N_TAPS - 1) begin
                        mult_valid_in <= 1'b0; // All 51 taps fed
                        drain_cnt     <= 0;
                        state         <= STATE_DRAIN;
                    end else begin
                        tap_cnt <= tap_cnt + 1'b1;
                    end
                end

                STATE_DRAIN: begin
                    // Waiting for multiplier pipeline to drain
                    if (drain_cnt == PIPE) begin
                        y_valid <= 1'b1; // Completed 32-bit output ready
                        state   <= STATE_IDLE;
                    end else begin
                        drain_cnt <= drain_cnt + 1'b1;
                    end
                end

                default: state <= STATE_IDLE;
            endcase

            // Clear accumulator when the first product of the sample arrives
            if (prod_valid && !first_prod_done) begin
                mac_clr         <= 1'b1;
                first_prod_done <= 1'b1;
            end
        end
    end

endmodule
