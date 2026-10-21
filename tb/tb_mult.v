// =============================================================================
// Testbench: tb_mult
// Description: Exhaustive and randomized testbench for mult_split.
//              Tests full precision vs SystemVerilog $signed(x) * $signed(h).
//              Tests approximate precision vs ((x >>> 8) <<< 8) * h.
//              Verifies operation across PIPE = 1, 2, and 3.
//              Outputs standardized machine-readable line:
//              TB_RESULT: PASS name=tb_mult samples=<N> mismatches=0
// =============================================================================
`timescale 1ns / 1ps

module tb_mult;

    reg clk;
    reg rst_n;
    reg enable;
    reg mode_approx;
    reg signed [15:0] x_in;
    reg signed [15:0] h_in;
    reg valid_in;

    wire signed [31:0] prod_p1, prod_p2, prod_p3;
    wire val_p1, val_p2, val_p3;

    // Instantiate for PIPE = 1, 2, 3
    mult_split #(.MULT_IMPL("LUT"), .PIPE(1)) dut_p1 (
        .clk(clk), .rst_n(rst_n), .enable(enable), .mode_approx(mode_approx),
        .x_in(x_in), .h_in(h_in), .valid_in(valid_in),
        .prod_out(prod_p1), .valid_out(val_p1)
    );

    mult_split #(.MULT_IMPL("LUT"), .PIPE(2)) dut_p2 (
        .clk(clk), .rst_n(rst_n), .enable(enable), .mode_approx(mode_approx),
        .x_in(x_in), .h_in(h_in), .valid_in(valid_in),
        .prod_out(prod_p2), .valid_out(val_p2)
    );

    mult_split #(.MULT_IMPL("LUT"), .PIPE(3)) dut_p3 (
        .clk(clk), .rst_n(rst_n), .enable(enable), .mode_approx(mode_approx),
        .x_in(x_in), .h_in(h_in), .valid_in(valid_in),
        .prod_out(prod_p3), .valid_out(val_p3)
    );

    // Clock generator (100 MHz -> 10 ns period)
    always #5 clk = ~clk;

    // Shift registers to delay expected golden outputs by PIPE cycles
    reg signed [31:0] exp_pipe [1:4];
    reg [3:0] val_pipe;

    integer mismatches = 0;
    integer total_samples = 0;
    integer first_mismatch_idx = -1;

    // Golden model computation function
    function signed [31:0] calc_expected(input signed [15:0] x, input signed [15:0] h, input approx);
        reg signed [15:0] x_eff;
        begin
            x_eff = approx ? ((x >>> 8) <<< 8) : x;
            calc_expected = x_eff * h;
        end
    endfunction

    // Checker process
    always @(posedge clk) begin
        if (rst_n) begin
            exp_pipe[1] <= calc_expected(x_in, h_in, mode_approx);
            exp_pipe[2] <= exp_pipe[1];
            exp_pipe[3] <= exp_pipe[2];
            exp_pipe[4] <= exp_pipe[3];

            val_pipe <= {val_pipe[2:0], valid_in};

            // Check PIPE 1
            if (val_p1) begin
                if (prod_p1 !== exp_pipe[1]) begin
                    if (mismatches == 0) first_mismatch_idx = total_samples;
                    mismatches = mismatches + 1;
                    $display("FAIL P1 at %0t: x=%d h=%d approx=%b -> act=%d exp=%d", $time, x_in, h_in, mode_approx, prod_p1, exp_pipe[1]);
                end
            end

            // Check PIPE 2
            if (val_p2) begin
                if (prod_p2 !== exp_pipe[2]) begin
                    if (mismatches == 0) first_mismatch_idx = total_samples;
                    mismatches = mismatches + 1;
                    $display("FAIL P2 at %0t: act=%d exp=%d", $time, prod_p2, exp_pipe[2]);
                end
                total_samples = total_samples + 1;
            end

            // Check PIPE 3
            if (val_p3) begin
                if (prod_p3 !== exp_pipe[3]) begin
                    if (mismatches == 0) first_mismatch_idx = total_samples;
                    mismatches = mismatches + 1;
                    $display("FAIL P3 at %0t: act=%d exp=%d", $time, prod_p3, exp_pipe[3]);
                end
            end
        end
    end

    integer x_val, h_idx;
    reg signed [15:0] extreme_h [0:4];

    initial begin
        clk = 0;
        rst_n = 0;
        enable = 1;
        mode_approx = 0;
        x_in = 0;
        h_in = 0;
        valid_in = 0;
        val_pipe = 0;

        extreme_h[0] = -32768;
        extreme_h[1] = -1;
        extreme_h[2] = 0;
        extreme_h[3] = 1;
        extreme_h[4] = 32767;

        #20 rst_n = 1;

        $display("Starting tb_mult exhaustive and randomized testing...");

        // 1. Test all 65,536 x values against 5 extreme h values in Full Mode
        for (h_idx = 0; h_idx < 5; h_idx = h_idx + 1) begin
            for (x_val = -32768; x_val <= 32767; x_val = x_val + 1) begin
                @(posedge clk);
                x_in <= x_val[15:0];
                h_in <= extreme_h[h_idx];
                mode_approx <= 0;
                valid_in <= 1;
            end
        end

        // 2. Test all 65,536 x values against 5 extreme h values in Approx Mode
        for (h_idx = 0; h_idx < 5; h_idx = h_idx + 1) begin
            for (x_val = -32768; x_val <= 32767; x_val = x_val + 1) begin
                @(posedge clk);
                x_in <= x_val[15:0];
                h_in <= extreme_h[h_idx];
                mode_approx <= 1;
                valid_in <= 1;
            end
        end

        // 3. 50,000 random pairs with randomized mode
        for (x_val = 0; x_val < 50000; x_val = x_val + 1) begin
            @(posedge clk);
            x_in <= $random;
            h_in <= $random;
            mode_approx <= $random & 1'b1;
            valid_in <= 1;
        end

        @(posedge clk);
        valid_in <= 0;
        #100;

        if (mismatches == 0) begin
            $display("TB_RESULT: PASS name=tb_mult samples=%0d mismatches=0", total_samples);
            $finish;
        end else begin
            $display("TB_RESULT: FAIL name=tb_mult samples=%0d mismatches=%0d first_idx=%0d", total_samples, mismatches, first_mismatch_idx);
            $fatal(1, "tb_mult failed with mismatches!");
        end
    end

endmodule
