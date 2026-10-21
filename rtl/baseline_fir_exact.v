// =============================================================================
// Module: baseline_fir_exact
// Description: Conventional non-gated 51-tap FIR filter baseline.
//              Used for area, timing, and switching activity comparison against pg_top.
//              - Uses full 16x16 signed multiplier on every cycle.
//              - Same 51-cycle time-multiplexed compute architecture.
//              - Bit-matched output with pg_fir in full-precision mode.
// =============================================================================
`timescale 1ns / 1ps

module baseline_fir_exact #(
    parameter N_TAPS     = 51,
    parameter PIPE       = 2,
    parameter COEFF_FILE = "coeffs.mem"
)(
    input  wire                   clk,
    input  wire                   rst_n,
    input  wire                   sample_valid,
    input  wire signed [15:0]     x_in,
    output reg                    y_valid,
    output reg  signed [31:0]     y_acc,
    output wire                   busy
);

    localparam STATE_IDLE    = 2'b00;
    localparam STATE_COMPUTE = 2'b01;
    localparam STATE_DRAIN   = 2'b10;

    reg [1:0] state;
    reg [$clog2(N_TAPS+1)-1:0] tap_cnt;
    reg [$clog2(PIPE+2)-1:0]   drain_cnt;

    reg shift_en;
    reg mult_valid_in;

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

    // Standard 16x16 signed multiplier with PIPE stages
    reg signed [31:0] prod_pipe [0:PIPE-1];
    reg [PIPE-1:0]    val_pipe;
    wire signed [31:0] prod_comb = sample_tap * coeff_tap;

    integer p;
    always @(posedge clk) begin
        if (!rst_n) begin
            for (p = 0; p < PIPE; p = p + 1) begin
                prod_pipe[p] <= 32'sd0;
            end
            val_pipe <= '0;
        end else begin
            prod_pipe[0] <= prod_comb;
            val_pipe[0]  <= mult_valid_in;
            for (p = 1; p < PIPE; p = p + 1) begin
                prod_pipe[p] <= prod_pipe[p-1];
                val_pipe[p]  <= val_pipe[p-1];
            end
        end
    end

    wire signed [31:0] mult_out   = prod_pipe[PIPE-1];
    wire               mult_valid = val_pipe[PIPE-1];

    // Accumulator
    reg mac_clr;
    always @(posedge clk) begin
        if (!rst_n) begin
            y_acc <= 32'sd0;
        end else if (mac_clr) begin
            y_acc <= mult_valid ? mult_out : 32'sd0;
        end else if (mult_valid) begin
            y_acc <= y_acc + mult_out;
        end
    end

    assign busy = (state != STATE_IDLE);

    // FSM Control
    always @(posedge clk) begin
        if (!rst_n) begin
            state         <= STATE_IDLE;
            tap_cnt       <= '0;
            drain_cnt     <= '0;
            shift_en      <= 1'b0;
            mult_valid_in <= 1'b0;
            mac_clr       <= 1'b0;
            y_valid       <= 1'b0;
        end else begin
            shift_en <= 1'b0;
            y_valid  <= 1'b0;
            mac_clr  <= 1'b0;

            case (state)
                STATE_IDLE: begin
                    mult_valid_in <= 1'b0;
                    if (sample_valid) begin
                        shift_en      <= 1'b1;
                        tap_cnt       <= '0;
                        mult_valid_in <= 1'b1;
                        mac_clr       <= 1'b1;
                        state         <= STATE_COMPUTE;
                    end
                end

                STATE_COMPUTE: begin
                    if (tap_cnt == N_TAPS - 1) begin
                        mult_valid_in <= 1'b0;
                        drain_cnt     <= '0;
                        state         <= STATE_DRAIN;
                    end else begin
                        tap_cnt <= tap_cnt + 1'b1;
                    end
                end

                STATE_DRAIN: begin
                    if (drain_cnt == PIPE) begin
                        y_valid <= 1'b1;
                        state   <= STATE_IDLE;
                    end else begin
                        drain_cnt <= drain_cnt + 1'b1;
                    end
                end

                default: state <= STATE_IDLE;
            endcase
        end
    end

endmodule
