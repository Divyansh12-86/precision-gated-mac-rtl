// =============================================================================
// Module: fir_coeff_rom
// Description: Synchronous/combinational coefficient ROM for 51-tap FIR filter.
//              Loaded from hexadecimal coefficients file (COEFF_FILE) at compile time.
// =============================================================================
`timescale 1ns / 1ps

module fir_coeff_rom #(
    parameter N_TAPS = 51,
    parameter COEFF_WIDTH = 16,
    parameter COEFF_FILE = "coeffs.mem"
)(
    input  wire                   clk,
    input  wire [$clog2(N_TAPS)-1:0]   tap_idx,
    output wire signed [COEFF_WIDTH-1:0] coeff_out
);

    reg signed [COEFF_WIDTH-1:0] rom [0:N_TAPS-1];

    initial begin
        if (COEFF_FILE != "") begin
            $readmemh(COEFF_FILE, rom);
        end
    end

    assign coeff_out = (tap_idx < N_TAPS) ? rom[tap_idx] : {COEFF_WIDTH{1'b0}};

endmodule
