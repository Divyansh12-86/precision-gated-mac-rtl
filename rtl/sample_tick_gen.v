// =============================================================================
// Module: sample_tick_gen
// Description: Fractional accumulator rate generator for periodic sample ticks.
//              Generates a single-cycle tick at frequency FS from system clock CLK_HZ.
//              Zero cumulative long-term frequency error.
// =============================================================================
`timescale 1ns / 1ps

module sample_tick_gen #(
    parameter CLK_HZ = 100_000_000,
    parameter FS     = 360
)(
    input  wire clk,
    input  wire rst_n,
    input  wire enable,
    output reg  tick
);

    reg [31:0] acc;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            acc  <= 32'd0;
            tick <= 1'b0;
        end else if (enable) begin
            if (acc + FS >= CLK_HZ) begin
                acc  <= acc + FS - CLK_HZ;
                tick <= 1'b1;
            end else begin
                acc  <= acc + FS;
                tick <= 1'b0;
            end
        end else begin
            tick <= 1'b0;
        end
    end

endmodule
