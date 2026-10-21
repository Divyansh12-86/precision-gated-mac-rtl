// =============================================================================
// Testbench: tb_top
// Description: End-to-end system testbench for pg_top.
//              - Feeds only tv_inputs.hex (no external gate file).
//              - Autonomous QRS detector drives precision gating of FIR core.
//              - Compares y_acc against tv_outputs_gated.hex bit-exactly.
//              - Compares gate_out against tv_gate_flags.hex bit-exactly.
//              - Supports fixed spacing or randomized inter-sample gaps (65..300 cycles).
//              - Verifies constant cycle latency.
//              - Outputs standardized line:
//                TB_RESULT: PASS name=tb_top samples=<N> mismatches=0
// =============================================================================
`timescale 1ns / 1ps

module tb_top #(
    parameter PIPE = 2,
    parameter SQ_SHIFT = 11
);

    parameter MAX_SAMPLES = 70000;
    parameter CLK_PERIOD = 10; // 100 MHz

    reg clk;
    reg rst_n;
    reg sample_valid;
    reg signed [15:0] x_in;
    reg [1:0] mode_force;

    wire y_valid;
    wire signed [31:0] y_acc;
    wire gate_out;
    wire peak_pulse;
    wire [17:0] mwi_dbg;
    wire busy;

    // Test storage
    reg [15:0] tv_in_mem        [0:MAX_SAMPLES-1];
    reg        tv_gate_mem      [0:MAX_SAMPLES-1];
    reg [31:0] tv_out_gated_mem [0:MAX_SAMPLES-1];

    reg [1023:0] vec_dir;
    reg [1023:0] in_file;
    reg [1023:0] gate_file;
    reg [1023:0] out_file;
    reg [1023:0] coeff_file;

    // DUT instantiation
    pg_top #(
        .N_TAPS(51),
        .PIPE(PIPE),
        .MULT_IMPL("LUT"),
        .COEFF_FILE("coeffs.mem"),
        .SQ_SHIFT(SQ_SHIFT)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .sample_valid(sample_valid),
        .x_in(x_in),
        .mode_force(mode_force),
        .y_valid(y_valid),
        .y_acc(y_acc),
        .gate_out(gate_out),
        .peak_pulse(peak_pulse),
        .mwi_dbg(mwi_dbg),
        .busy(busy)
    );

    always #(CLK_PERIOD / 2) clk = ~clk;

    integer num_samples = 0;
    integer sample_idx = 0;
    integer out_idx = 0;
    integer mismatches_y = 0;
    integer mismatches_gate = 0;
    integer total_mismatches = 0;

    integer cycles_since_valid = 0;
    integer expected_latency = -1;
    integer latency_errors = 0;

    // Latency & output checker
    always @(posedge clk) begin
        if (rst_n) begin
            if (sample_valid) begin
                cycles_since_valid <= 0;
            end else if (busy) begin
                cycles_since_valid <= cycles_since_valid + 1;
            end

            if (y_valid) begin
                if (expected_latency == -1) begin
                    expected_latency = cycles_since_valid;
                    $display("Measured constant pipeline latency: %0d cycles", expected_latency);
                end else if (cycles_since_valid !== expected_latency) begin
                    latency_errors = latency_errors + 1;
                    $display("LATENCY ERROR at out_idx %0d: was %0d, expected %0d",
                             out_idx, cycles_since_valid, expected_latency);
                end

                if (out_idx < num_samples) begin
                    if (y_acc !== $signed(tv_out_gated_mem[out_idx])) begin
                        mismatches_y = mismatches_y + 1;
                        total_mismatches = total_mismatches + 1;
                        if (total_mismatches <= 5) begin
                            $display("FAIL Y_ACC MISMATCH at sample %0d: actual=0x%08X (%d), expected=0x%08X (%d)",
                                     out_idx, y_acc, y_acc, tv_out_gated_mem[out_idx], $signed(tv_out_gated_mem[out_idx]));
                        end
                    end

                    if (dut.gate_out !== tv_gate_mem[out_idx]) begin
                        mismatches_gate = mismatches_gate + 1;
                        total_mismatches = total_mismatches + 1;
                        if (total_mismatches <= 5) begin
                            $display("FAIL GATE MISMATCH at sample %0d: actual=%b, expected=%b",
                                     out_idx, dut.gate_out, tv_gate_mem[out_idx]);
                        end
                    end

                    out_idx = out_idx + 1;
                end
            end
        end
    end

    integer f_in, randomize_gap_flag;
    integer gap_cycles;
    reg [15:0] temp_val;

    // Watchdog timer (prevents runaway if simulation ever hangs)
    initial begin
        #(CLK_PERIOD * 50000000); // 500 ms limit
        $display("FATAL: Testbench watchdog timeout reached!");
        $finish(1);
    end

    initial begin
        clk = 0;
        rst_n = 0;
        sample_valid = 0;
        x_in = 0;
        mode_force = 2'b00; // Auto precision gating

        if (!$value$plusargs("VEC_DIR=%s", vec_dir)) begin
            vec_dir = "data/test_vectors/smoke";
        end

        if (!$value$plusargs("RAND_GAP=%d", randomize_gap_flag)) begin
            randomize_gap_flag = 0;
        end

        $sformat(in_file, "%0s/tv_inputs.hex", vec_dir);
        $sformat(gate_file, "%0s/tv_gate_flags.hex", vec_dir);
        $sformat(out_file, "%0s/tv_outputs_gated.hex", vec_dir);
        $sformat(coeff_file, "%0s/coeffs.mem", vec_dir);

        $display("==================================================================");
        $display("tb_top starting on vectors: %0s (RAND_GAP=%0d)", vec_dir, randomize_gap_flag);
        $display("==================================================================");

        $readmemh(in_file, tv_in_mem);
        $readmemh(gate_file, tv_gate_mem);
        $readmemh(out_file, tv_out_gated_mem);
        $readmemh(coeff_file, dut.u_fir.u_rom.rom);

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

        #(CLK_PERIOD * 4);
        @(posedge clk);
        rst_n = 1;
        #(CLK_PERIOD * 2);

        for (sample_idx = 0; sample_idx < num_samples; sample_idx = sample_idx + 1) begin
            @(posedge clk);
            sample_valid <= 1'b1;
            x_in <= tv_in_mem[sample_idx];

            @(posedge clk);
            sample_valid <= 1'b0;

            // Wait until this sample produces its y_valid
            while (!y_valid) begin
                @(posedge clk);
            end

            // Wait for y_valid to clear and DUT to return to idle
            while (busy || y_valid) begin
                @(posedge clk);
            end

            // Extra gap between samples
            if (randomize_gap_flag != 0) begin
                gap_cycles = 10 + ($urandom % 150);
            end else begin
                gap_cycles = 20;
            end
            repeat (gap_cycles) @(posedge clk);
        end

        // Wait for final sample
        while (out_idx < num_samples) begin
            @(posedge clk);
        end

        #(CLK_PERIOD * 5);

        $display("==================================================================");
        $display("tb_top summary for %0s:", vec_dir);
        $display("  Samples tested:    %0d", num_samples);
        $display("  Pipeline latency:  %0d cycles", expected_latency);
        $display("  Latency errors:    %0d", latency_errors);
        $display("  Y_ACC mismatches:  %0d", mismatches_y);
        $display("  Gate mismatches:   %0d", mismatches_gate);
        $display("  Total mismatches:  %0d", total_mismatches);
        $display("==================================================================");

        if (total_mismatches == 0 && latency_errors == 0) begin
            $display("TB_RESULT: PASS name=tb_top samples=%0d mismatches=0", num_samples);
            $finish(0);
        end else begin
            $display("TB_RESULT: FAIL name=tb_top samples=%0d mismatches=%0d latency_errors=%0d",
                     num_samples, total_mismatches, latency_errors);
            $finish(1);
        end
    end

endmodule
