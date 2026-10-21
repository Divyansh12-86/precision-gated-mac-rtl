// =============================================================================
// Module: pg_mac
// Description: Synchronous 32-bit signed accumulator for time-multiplexed FIR.
//              Synchronous clear (clr) resets accumulator to 0 before tap 0.
//              Accumulates product when prod_valid is asserted.
// =============================================================================
`timescale 1ns / 1ps

module pg_mac (
    input  wire                   clk,
    input  wire                   rst_n,
    input  wire                   clr,
    input  wire                   prod_valid,
    input  wire signed [31:0]     prod_in,
    output reg  signed [31:0]     acc_out
);

    always @(posedge clk) begin
        if (!rst_n) begin
            acc_out <= 32'sd0;
        end else if (clr) begin
            acc_out <= prod_valid ? prod_in : 32'sd0;
        end else if (prod_valid) begin
            acc_out <= acc_out + prod_in;
        end
    end

endmodule
