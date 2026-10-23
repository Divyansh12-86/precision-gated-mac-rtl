// =============================================================================
// Module: pg_top
// Description: Precision-Gated Approximate-MAC FIR Filter System Top-Level.
//              Integrates:
//                1. qrs_detector: Integer Pan-Tompkins QRS detector
//                2. pg_fir: 51-tap precision-gated FIR filter core
//              Sequence per sample:
//                - Sample arrives with sample_valid
//                - qrs_detector updates in 1 cycle, asserting valid_out and gate_out
//                - pg_fir is triggered with latched sample and gate_in
//                - pg_fir completes 51-tap compute in 54 cycles
//                - y_valid asserted with 32-bit accumulated output y_acc
// =============================================================================
`timescale 1ns / 1ps

module pg_top #(
    parameter N_TAPS      = 51,
    parameter PIPE        = 2,
    parameter MULT_IMPL   = "LUT",
    parameter COEFF_FILE  = "coeffs.mem",
    parameter SQ_SHIFT    = 11
)(
    input  wire                   clk,
    input  wire                   rst_n,
    input  wire                   sample_valid,
    input  wire signed [15:0]     x_in,
    input  wire [1:0]             mode_force,
    output wire                   y_valid,
    output wire signed [31:0]     y_acc,
    output reg                    gate_out,
    output wire                   peak_pulse,
    output wire [17:0]            mwi_dbg,
    output wire                   busy
);

    // Latched input sample
    reg signed [15:0] x_in_latched;
    reg               fir_sample_valid;
    reg               det_pending;

    // Detector wires
    wire        det_gate;
    wire        det_peak;
    wire [17:0] det_mwi;
    wire        det_valid;

    // Instantiate QRS Detector (inherits parameter defaults from qrs_detector)
    qrs_detector #(
        .SQ_SHIFT(SQ_SHIFT)
    ) u_detector (
        .clk(clk),
        .rst_n(rst_n),
        .sample_valid(sample_valid),
        .x_in(x_in),
        .gate_out(det_gate),
        .peak_pulse(det_peak),
        .mwi_dbg(det_mwi),
        .valid_out(det_valid)
    );

    // FIR wires
    wire fir_busy;
    wire fir_y_valid;
    wire signed [31:0] fir_y_acc;

    // Instantiate Precision-Gated FIR Core
    pg_fir #(
        .N_TAPS(N_TAPS),
        .PIPE(PIPE),
        .MULT_IMPL(MULT_IMPL),
        .COEFF_FILE(COEFF_FILE)
    ) u_fir (
        .clk(clk),
        .rst_n(rst_n),
        .sample_valid(fir_sample_valid),
        .x_in(x_in_latched),
        .gate_in(det_gate),
        .mode_force(mode_force),
        .y_valid(fir_y_valid),
        .y_acc(fir_y_acc),
        .busy(fir_busy)
    );

    assign y_valid    = fir_y_valid;
    assign y_acc      = fir_y_acc;
    assign peak_pulse = det_peak;
    assign mwi_dbg    = det_mwi;
    assign busy       = fir_busy || det_pending || fir_sample_valid;

    // Integration control
    always @(posedge clk) begin
        if (!rst_n) begin
            x_in_latched     <= 16'sd0;
            fir_sample_valid <= 1'b0;
            det_pending      <= 1'b0;
            gate_out         <= 1'b0;
        end else begin
            fir_sample_valid <= 1'b0;

            if (sample_valid) begin
                x_in_latched <= x_in;
                det_pending  <= 1'b1;
            end

            if (det_valid) begin
                gate_out         <= det_gate;
                fir_sample_valid <= 1'b1;
                det_pending      <= 1'b0;
            end
        end
    end

endmodule
