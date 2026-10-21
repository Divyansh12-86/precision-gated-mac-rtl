// =============================================================================
// Module: sample_delay_line
// Description: Synchronous 51-sample delay line (shift register) for FIR filter.
//              Synchronous active-low reset clears all samples to 0 (x[<0] = 0).
//              Shift occurs on shift_en.
//              Random read access by tap index j (0 = newest x[n], 50 = oldest x[n-50]).
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

    reg signed [DATA_WIDTH-1:0] buffer [0:N_TAPS-1];
    integer i;

    always @(posedge clk) begin
        if (!rst_n) begin
            for (i = 0; i < N_TAPS; i = i + 1) begin
                buffer[i] <= {DATA_WIDTH{1'b0}};
            end
        end else if (shift_en) begin
            for (i = N_TAPS-1; i > 0; i = i - 1) begin
                buffer[i] <= buffer[i-1];
            end
            buffer[0] <= sample_in;
        end
    end

    assign sample_out = (tap_idx < N_TAPS) ? buffer[tap_idx] : {DATA_WIDTH{1'b0}};

endmodule
