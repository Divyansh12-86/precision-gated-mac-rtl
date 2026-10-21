// =============================================================================
// Testbench: tb_top_reset
// Description: Robustness test verifying that a mid-stream reset pulse cleanly
//              restores all internal state (delay line, accumulator, detector).
//              Outputs standardized line:
//              TB_RESULT: PASS name=tb_top_reset samples=700 mismatches=0
// =============================================================================
`timescale 1ns / 1ps

module tb_top_reset;

    parameter PRE_SAMPLES = 300;
    parameter POST_SAMPLES = 700;
    parameter CLK_PERIOD = 10;

    reg clk;
    reg rst_n;
    reg sample_valid;
    reg signed [15:0] x_in;

    wire y_valid;
    wire signed [31:0] y_acc;
    wire gate_out;
    wire peak_pulse;
    wire [17:0] mwi_dbg;
    wire busy;

    reg [15:0] tv_in_pre  [0:PRE_SAMPLES-1];
    reg [15:0] tv_in_post [0:POST_SAMPLES-1];
    reg [31:0] tv_out_post_exp [0:POST_SAMPLES-1];

    pg_top #(
        .N_TAPS(51),
        .PIPE(2),
        .MULT_IMPL("LUT"),
        .COEFF_FILE("coeffs.mem"),
        .SQ_SHIFT(11)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .sample_valid(sample_valid),
        .x_in(x_in),
        .mode_force(2'b00),
        .y_valid(y_valid),
        .y_acc(y_acc),
        .gate_out(gate_out),
        .peak_pulse(peak_pulse),
        .mwi_dbg(mwi_dbg),
        .busy(busy)
    );

    always #(CLK_PERIOD / 2) clk = ~clk;

    integer out_idx = 0;
    integer mismatches = 0;
    reg check_en = 0;

    always @(posedge clk) begin
        if (rst_n && y_valid && check_en) begin
            if (out_idx < POST_SAMPLES) begin
                if (y_acc !== $signed(tv_out_post_exp[out_idx])) begin
                    mismatches = mismatches + 1;
                    if (mismatches <= 5) begin
                        $display("RESET TEST MISMATCH at post-sample %0d: actual=0x%08X, expected=0x%08X",
                                 out_idx, y_acc, tv_out_post_exp[out_idx]);
                    end
                end
                out_idx = out_idx + 1;
            end
        end
    end

    integer s;

    initial begin
        clk = 0;
        rst_n = 0;
        sample_valid = 0;
        x_in = 0;
        check_en = 0;

        $readmemh("data/test_vectors/reset_test/tv_inputs_pre.hex", tv_in_pre);
        $readmemh("data/test_vectors/reset_test/tv_inputs_post.hex", tv_in_post);
        $readmemh("data/test_vectors/reset_test/tv_outputs_post.hex", tv_out_post_exp);
        $readmemh("data/test_vectors/reset_test/coeffs.mem", dut.u_fir.u_rom.rom);

        $display("Starting tb_top_reset...");

        #(CLK_PERIOD * 4);
        @(posedge clk);
        rst_n = 1;
        #(CLK_PERIOD * 2);

        // Phase 1: feed 300 pre-reset samples to dirty all registers
        for (s = 0; s < PRE_SAMPLES; s = s + 1) begin
            @(posedge clk);
            sample_valid <= 1'b1;
            x_in <= tv_in_pre[s];
            @(posedge clk);
            sample_valid <= 1'b0;
            while (!y_valid) @(posedge clk);
            while (busy || y_valid) @(posedge clk);
            repeat (10) @(posedge clk);
        end

        $display("Completed 300 pre-reset samples. Asserting MID-STREAM RESET!");

        // Phase 2: assert mid-stream reset pulse
        @(posedge clk);
        rst_n <= 1'b0;
        repeat (10) @(posedge clk);
        rst_n <= 1'b1;
        repeat (5) @(posedge clk);

        $display("Deasserted reset. Now feeding 700 post-reset samples and verifying bit-exact restart...");
        check_en = 1;

        // Phase 3: feed 700 post-reset samples and verify
        for (s = 0; s < POST_SAMPLES; s = s + 1) begin
            @(posedge clk);
            sample_valid <= 1'b1;
            x_in <= tv_in_post[s];
            @(posedge clk);
            sample_valid <= 1'b0;
            while (!y_valid) @(posedge clk);
            while (busy || y_valid) @(posedge clk);
            repeat (10) @(posedge clk);
        end

        while (out_idx < POST_SAMPLES) @(posedge clk);
        #(CLK_PERIOD * 5);

        $display("Post-reset samples checked: %0d, mismatches: %0d", out_idx, mismatches);
        if (mismatches == 0 && out_idx == POST_SAMPLES) begin
            $display("TB_RESULT: PASS name=tb_top_reset samples=700 mismatches=0");
            $finish(0);
        end else begin
            $display("TB_RESULT: FAIL name=tb_top_reset samples=%0d mismatches=%0d", out_idx, mismatches);
            $finish(1);
        end
    end

endmodule
