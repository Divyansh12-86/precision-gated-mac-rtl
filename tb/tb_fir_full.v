// =============================================================================
// Testbench: tb_fir_full
// Description: Tests pg_fir in full-precision mode (mode_force = 2'b01).
//              Reads tv_inputs.hex, tv_outputs_full.hex, and coeffs.mem from
//              the directory specified by plusarg +VEC_DIR=<dir>.
//              Verifies cycle latency constancy and bit-exact output match.
//              Outputs standardized machine-readable line:
//              TB_RESULT: PASS name=tb_fir_full samples=<N> mismatches=0
// =============================================================================
`timescale 1ns / 1ps

module tb_fir_full #(
    parameter PIPE = 2
);

    parameter MAX_SAMPLES = 70000;
    parameter CLK_PERIOD = 10; // 100 MHz

    reg clk;
    reg rst_n;
    reg sample_valid;
    reg signed [15:0] x_in;
    reg gate_in;
    reg [1:0] mode_force;

    wire y_valid;
    wire signed [31:0] y_acc;
    wire busy;

    // Test storage
    reg [15:0] tv_in_mem [0:MAX_SAMPLES-1];
    reg [31:0] tv_out_exp_mem [0:MAX_SAMPLES-1];

    reg [1023:0] vec_dir;
    reg [1023:0] in_file;
    reg [1023:0] out_file;
    reg [1023:0] coeff_file;

    // DUT instantiation
    pg_fir #(
        .N_TAPS(51),
        .PIPE(PIPE),
        .MULT_IMPL("LUT"),
        .COEFF_FILE("coeffs.mem")
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .sample_valid(sample_valid),
        .x_in(x_in),
        .gate_in(gate_in),
        .mode_force(mode_force),
        .y_valid(y_valid),
        .y_acc(y_acc),
        .busy(busy)
    );

    always #(CLK_PERIOD / 2) clk = ~clk;

    integer num_samples = 0;
    integer sample_idx = 0;
    integer out_idx = 0;
    integer mismatches = 0;
    integer first_mismatch_idx = -1;

    integer cycles_since_valid = 0;
    integer expected_latency = -1;
    integer latency_error = 0;

    // Checker process
    always @(posedge clk) begin
        if (rst_n) begin
            if (sample_valid) begin
                cycles_since_valid <= 0;
            end else if (busy) begin
                cycles_since_valid <= cycles_since_valid + 1;
            end

            if (y_valid) begin
                // Check constant latency
                if (expected_latency == -1) begin
                    expected_latency = cycles_since_valid;
                end else if (cycles_since_valid !== expected_latency) begin
                    latency_error = latency_error + 1;
                    $display("LATENCY ERROR at out_idx %0d: was %0d, expected %0d", out_idx, cycles_since_valid, expected_latency);
                end

                // Check 32-bit output match
                if (out_idx < num_samples) begin
                    if (y_acc !== $signed(tv_out_exp_mem[out_idx])) begin
                        if (mismatches == 0) first_mismatch_idx = out_idx;
                        mismatches = mismatches + 1;
                        if (mismatches <= 5) begin
                            $display("FAIL MISMATCH at sample %0d: actual=0x%08X (%d), expected=0x%08X (%d)",
                                     out_idx, y_acc, y_acc, tv_out_exp_mem[out_idx], $signed(tv_out_exp_mem[out_idx]));
                        end
                    end
                    out_idx = out_idx + 1;
                end
            end
        end
    end

    integer f_in, r;
    reg [15:0] temp_val;

    initial begin
        clk = 0;
        rst_n = 0;
        sample_valid = 0;
        x_in = 0;
        gate_in = 1;
        mode_force = 2'b01; // Force Full Precision

        if (!$value$plusargs("VEC_DIR=%s", vec_dir)) begin
            vec_dir = "data/test_vectors/smoke";
        end

        $sformat(in_file, "%0s/tv_inputs.hex", vec_dir);
        $sformat(out_file, "%0s/tv_outputs_full.hex", vec_dir);
        $sformat(coeff_file, "%0s/coeffs.mem", vec_dir);

        $display("Loading vectors from: %0s", vec_dir);
        $readmemh(in_file, tv_in_mem);
        $readmemh(out_file, tv_out_exp_mem);
        $readmemh(coeff_file, dut.u_rom.rom);

        // Count lines in inputs
        f_in = $fopen(in_file, "r");
        if (f_in == 0) begin
            $fatal(1, "Failed to open input file: %0s", in_file);
        end
        num_samples = 0;
        while ($fscanf(f_in, "%h\n", temp_val) == 1) begin
            num_samples = num_samples + 1;
        end
        $fclose(f_in);

        $display("Loaded %0d samples. Starting simulation...", num_samples);

        #(CLK_PERIOD * 5);
        rst_n = 1;
        #(CLK_PERIOD * 2);

        for (sample_idx = 0; sample_idx < num_samples; sample_idx = sample_idx + 1) begin
            @(posedge clk);
            sample_valid <= 1'b1;
            x_in <= tv_in_mem[sample_idx];

            @(posedge clk);
            sample_valid <= 1'b0;

            // Wait until compute finishes (spacing = 80 cycles, well above 54-cycle latency)
            repeat (78) @(posedge clk);

            // Sanity check: busy must be 0 before the next sample arrives
            if (busy) begin
                $fatal(1, "Timing Violation: DUT still busy when next sample period arrives at sample %0d!", sample_idx);
            end
        end

        // Wait for final drainage
        #(CLK_PERIOD * 10);

        if (out_idx != num_samples) begin
            $display("ERROR: Processed outputs (%0d) does not match input samples (%0d)!", out_idx, num_samples);
            mismatches = mismatches + 1;
        end

        if (mismatches == 0 && latency_error == 0) begin
            $display("TB_RESULT: PASS name=tb_fir_full samples=%0d mismatches=0", out_idx);
            $finish;
        end else begin
            $display("TB_RESULT: FAIL name=tb_fir_full samples=%0d mismatches=%0d first_idx=%0d", out_idx, mismatches, first_mismatch_idx);
            $fatal(1, "tb_fir_full regression failed!");
        end
    end

endmodule
