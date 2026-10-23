// =============================================================================
// Module: sample_delay_line
// Description: Circular buffer / Distributed-RAM based sample delay line for FIR filter.
//              Replaces 51-word register array and 51:1 multiplexer with
//              inferred 64x16 distributed RAM (LUTRAM).
//              - Synchronous write on shift_en.
//              - Asynchronous read indexed by (wr_ptr - 1 - tap_idx) & 63.
//              - Fast instantaneous reset using valid_cnt (x[<0] = 0).
// =============================================================================
`timescale 1ns / 1ps

module sample_delay_line #(
    parameter N_TAPS = 51,
    parameter DATA_WIDTH = 16
)(
    input  wire                   clk,
    input  wire                   rst_n,
    input  wire                   shift_en,
    input  wire signed [DATA_WIDTH-1:0] sample_in,
    input  wire [$clog2(N_TAPS)-1:0]   tap_idx,
    output wire signed [DATA_WIDTH-1:0] sample_out
);

    // Distributed RAM storage (64 words depth natively matches 6-input LUTRAM)
    (* ram_style = "distributed" *)
    reg signed [DATA_WIDTH-1:0] ram [0:63];

    reg [5:0] wr_ptr;
    reg [5:0] valid_cnt;

    // Synchronous write & pointer tracking
    always @(posedge clk) begin
        if (!rst_n) begin
            wr_ptr    <= 6'd0;
            valid_cnt <= 6'd0;
        end else if (shift_en) begin
            ram[wr_ptr] <= sample_in;
            wr_ptr      <= wr_ptr + 6'd1;
            if (valid_cnt < N_TAPS[5:0]) begin
                valid_cnt <= valid_cnt + 6'd1;
            end
        end
    end

    // Asynchronous read access: tap 0 = wr_ptr - 1, tap j = wr_ptr - 1 - j
    wire [5:0] rd_addr = wr_ptr - 6'd1 - {1'b0, tap_idx};
    wire is_valid = ({1'b0, tap_idx} < valid_cnt) && (tap_idx < N_TAPS);

    assign sample_out = is_valid ? ram[rd_addr] : {DATA_WIDTH{1'b0}};

endmodule
