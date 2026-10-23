// =============================================================================
// Module: mult_split
// Description: Precision-scalable approximable multiplier with operand isolation
//              and clock-enable gating.
//              Splits 16-bit operand x into:
//                xh = x[15:8] (signed 8-bit)
//                xl = x[7:0]  (unsigned 8-bit)
//              Identity: x * h = ((xh * h) << 8) + (xl * h).
//              In Approximate Mode (mode_approx = 1):
//                xl is forced to 0 (operand isolation).
//                The low-part multiplier register is clock-enable gated (holds value).
//                Stage 2 adder masks held low product with 0.
//                Product equals ((x >> 8) << 8) * h bit-exactly.
//              Parameters:
//                MULT_IMPL: "LUT" (uses (* use_dsp = "no" *)) or "DSP"
//                PIPE: pipeline latency (1, 2, or 3 cycles, default 2)
// =============================================================================
`timescale 1ns / 1ps

module mult_split #(
    parameter MULT_IMPL = "LUT",
    parameter PIPE = 2
)(
    input  wire                   clk,
    input  wire                   rst_n,
    input  wire                   enable,
    input  wire                   mode_approx, // 1 = 8-bit approx, 0 = 16-bit full
    input  wire signed [15:0]     x_in,
    input  wire signed [15:0]     h_in,
    input  wire                   valid_in,
    output reg  signed [31:0]     prod_out,
    output reg                    valid_out
);

    // High byte signed, low byte unsigned
    wire signed [7:0]  xh = x_in[15:8];
    wire        [7:0]  xl_raw = x_in[7:0];

    // Operand isolation: clamp low byte to 0 in approximate mode
    wire [7:0] xl_eff = mode_approx ? 8'h00 : xl_raw;
    wire signed [8:0] xl_signed = {1'b0, xl_eff}; // zero-extended 9-bit signed

    // Full products with literal (* use_dsp *) attributes inside generate branches
    wire signed [23:0] prod_high_comb;
    wire signed [24:0] prod_low_comb;

    generate
        if (MULT_IMPL == "DSP") begin : g_mult_dsp
            (* use_dsp = "yes" *) wire signed [23:0] ph = xh * h_in;
            (* use_dsp = "yes" *) wire signed [24:0] pl = xl_signed * h_in;
            assign prod_high_comb = ph;
            assign prod_low_comb  = pl;
        end else begin : g_mult_lut
            (* use_dsp = "no" *)  wire signed [23:0] ph = xh * h_in;
            (* use_dsp = "no" *)  wire signed [24:0] pl = xl_signed * h_in;
            assign prod_high_comb = ph;
            assign prod_low_comb  = pl;
        end
    endgenerate

    // Combined 32-bit product (combinational for PIPE=1)
    wire signed [31:0] prod_comb = ({{8{prod_high_comb[23]}}, prod_high_comb} <<< 8) +
                                   (mode_approx ? 32'sd0 : {{7{prod_low_comb[24]}}, prod_low_comb});

    // Pipelining per PIPE parameter
    generate
        if (PIPE == 1) begin : g_pipe1
            always @(posedge clk) begin
                if (!rst_n) begin
                    prod_out  <= 32'sd0;
                    valid_out <= 1'b0;
                end else if (enable) begin
                    prod_out  <= prod_comb;
                    valid_out <= valid_in;
                end else begin
                    valid_out <= 1'b0;
                end
            end
        end else if (PIPE == 2) begin : g_pipe2
            // Stage 1: registers for partial products
            reg signed [23:0] p_high_r1;
            reg signed [24:0] p_low_r1;
            reg               approx_r1;
            reg               val_r1;

            always @(posedge clk) begin
                if (!rst_n) begin
                    p_high_r1 <= 24'sd0;
                    p_low_r1  <= 25'sd0;
                    approx_r1 <= 1'b0;
                    val_r1    <= 1'b0;
                end else if (enable) begin
                    p_high_r1 <= prod_high_comb;
                    // Clock-enable gating: low multiplier register only updates in full mode (holds in approx)
                    if (!mode_approx) begin
                        p_low_r1  <= prod_low_comb;
                    end
                    approx_r1 <= mode_approx;
                    val_r1    <= valid_in;
                end else begin
                    val_r1    <= 1'b0;
                end
            end

            // Stage 2: addition and final product register
            always @(posedge clk) begin
                if (!rst_n) begin
                    prod_out  <= 32'sd0;
                    valid_out <= 1'b0;
                end else if (enable) begin
                    prod_out  <= ({{8{p_high_r1[23]}}, p_high_r1} <<< 8) +
                                 (approx_r1 ? 32'sd0 : {{7{p_low_r1[24]}}, p_low_r1});
                    valid_out <= val_r1;
                end else begin
                    valid_out <= 1'b0;
                end
            end
        end else begin : g_pipe3
            // Stage 1: input operand registers
            reg signed [7:0]  xh_r1;
            reg signed [8:0]  xl_r1;
            reg signed [15:0] h_r1;
            reg               approx_r1;
            reg               val_r1;

            always @(posedge clk) begin
                if (!rst_n) begin
                    xh_r1     <= 8'sd0;
                    xl_r1     <= 9'sd0;
                    h_r1      <= 16'sd0;
                    approx_r1 <= 1'b0;
                    val_r1    <= 1'b0;
                end else if (enable) begin
                    xh_r1     <= xh;
                    if (!mode_approx) begin
                        xl_r1 <= xl_signed;
                    end
                    h_r1      <= h_in;
                    approx_r1 <= mode_approx;
                    val_r1    <= valid_in;
                end else begin
                    val_r1    <= 1'b0;
                end
            end

            // Stage 2: multiplier product registers
            reg signed [23:0] p_high_r2;
            reg signed [24:0] p_low_r2;
            reg               approx_r2;
            reg               val_r2;

            always @(posedge clk) begin
                if (!rst_n) begin
                    p_high_r2 <= 24'sd0;
                    p_low_r2  <= 25'sd0;
                    approx_r2 <= 1'b0;
                    val_r2    <= 1'b0;
                end else if (enable) begin
                    p_high_r2 <= xh_r1 * h_r1;
                    if (!approx_r1) begin
                        p_low_r2  <= xl_r1 * h_r1;
                    end
                    approx_r2 <= approx_r1;
                    val_r2    <= val_r1;
                end else begin
                    val_r2    <= 1'b0;
                end
            end

            // Stage 3: addition and final product register
            always @(posedge clk) begin
                if (!rst_n) begin
                    prod_out  <= 32'sd0;
                    valid_out <= 1'b0;
                end else if (enable) begin
                    prod_out  <= ({{8{p_high_r2[23]}}, p_high_r2} <<< 8) +
                                 (approx_r2 ? 32'sd0 : {{7{p_low_r2[24]}}, p_low_r2});
                    valid_out <= val_r2;
                end else begin
                    valid_out <= 1'b0;
                end
            end
        end
    endgenerate

endmodule
