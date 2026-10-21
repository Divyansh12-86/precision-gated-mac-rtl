// =============================================================================
// Testbench: tb_detector
// Description: Unit test for qrs_detector against golden test vectors.
//              Compares gate_out, peak_pulse, and mwi_dbg bit-exactly
//              against tv_gate_flags.hex, tv_peaks.hex, and tv_mwi.hex.
//              Outputs standardized line:
//              TB_RESULT: PASS name=tb_detector samples=<N> mismatches=0
// =============================================================================
`timescale 1ns / 1ps

module tb_detector #(
    parameter SQ_SHIFT = 11
);

    parameter MAX_SAMPLES = 70000;
    parameter CLK_PERIOD = 10; // 100 MHz

    reg clk;
    reg rst_n;
    reg sample_valid;
    reg signed [15:0] x_in;

    wire gate_out;
    wire peak_pulse;
    wire [17:0] mwi_dbg;
    wire valid_out;

    // Test storage
    reg [15:0] tv_in_mem     [0:MAX_SAMPLES-1];
    reg        tv_gate_mem   [0:MAX_SAMPLES-1];
    reg        tv_peaks_mem  [0:MAX_SAMPLES-1];
    reg [17:0] tv_mwi_mem    [0:MAX_SAMPLES-1];

    reg [1023:0] vec_dir;
    reg [1023:0] in_file;
    reg [1023:0] gate_file;
    reg [1023:0] peak_file;
    reg [1023:0] mwi_file;

    // DUT
    qrs_detector #(
        .SQ_SHIFT(SQ_SHIFT),
        .MWI_LEN(54),
        .GATE_LEN(43),
        .REFRACT_LEN(72),
        .DECAY_AFTER(288),
        .INIT_SPKI(1500),
        .INIT_NPKI(50),
        .INIT_THRESH(412)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .sample_valid(sample_valid),
        .x_in(x_in),
        .gate_out(gate_out),
        .peak_pulse(peak_pulse),
        .mwi_dbg(mwi_dbg),
        .valid_out(valid_out)
    );

    always #(CLK_PERIOD / 2) clk = ~clk;

    integer num_samples = 0;
    integer sample_idx = 0;
    integer check_idx = 0;
    integer mismatches_gate = 0;
    integer mismatches_peak = 0;
    integer mismatches_mwi  = 0;
    integer total_mismatches = 0;
    integer first_peak_idx = -1;

    // Checker process
    always @(posedge clk) begin
        if (rst_n && valid_out) begin
            if (check_idx < num_samples) begin
                reg [0:0]  exp_gate;
                reg [0:0]  exp_peak;
                reg [17:0] exp_mwi;

                exp_gate = tv_gate_mem[check_idx];
                exp_peak = tv_peaks_mem[check_idx];
                exp_mwi  = tv_mwi_mem[check_idx];

                if (gate_out !== exp_gate) begin
                    mismatches_gate = mismatches_gate + 1;
                    total_mismatches = total_mismatches + 1;
                    if (total_mismatches <= 5) begin
                        $display("MISMATCH GATE at sample %0d: actual=%b, expected=%b", check_idx, gate_out, exp_gate);
                    end
                end

                if (peak_pulse !== exp_peak) begin
                    mismatches_peak = mismatches_peak + 1;
                    total_mismatches = total_mismatches + 1;
                    if (total_mismatches <= 5) begin
                        $display("MISMATCH PEAK at sample %0d: actual=%b, expected=%b", check_idx, peak_pulse, exp_peak);
                    end
                end

                if (mwi_dbg !== exp_mwi) begin
                    mismatches_mwi = mismatches_mwi + 1;
                    total_mismatches = total_mismatches + 1;
                    if (total_mismatches <= 5) begin
                        $display("MISMATCH MWI at sample %0d: actual=0x%05X (%d), expected=0x%05X (%d)",
                                 check_idx, mwi_dbg, mwi_dbg, exp_mwi, exp_mwi);
                    end
                end

                if (peak_pulse && first_peak_idx == -1) begin
                    first_peak_idx = check_idx;
                    $display("First QRS peak confirmed at sample %0d (time %0.2f s)",
                             check_idx, (check_idx * 1.0) / 360.0);
                end

                check_idx = check_idx + 1;
            end
        end
    end

    integer f_in;
    reg [15:0] temp_val;

    initial begin
        clk = 0;
        rst_n = 0;
        sample_valid = 0;
        x_in = 0;

        if (!$value$plusargs("VEC_DIR=%s", vec_dir)) begin
            vec_dir = "data/test_vectors/smoke";
        end

        $sformat(in_file, "%0s/tv_inputs.hex", vec_dir);
        $sformat(gate_file, "%0s/tv_gate_flags.hex", vec_dir);
        $sformat(peak_file, "%0s/tv_peaks.hex", vec_dir);
        $sformat(mwi_file, "%0s/tv_mwi.hex", vec_dir);

        $display("==================================================================");
        $display("tb_detector starting on vectors: %0s", vec_dir);
        $display("==================================================================");

        $readmemh(in_file, tv_in_mem);
        $readmemh(gate_file, tv_gate_mem);
        $readmemh(peak_file, tv_peaks_mem);
        $readmemh(mwi_file, tv_mwi_mem);

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

            // Wait 1 cycle for valid_out check
            @(posedge clk);
            #(CLK_PERIOD * 1);
        end

        // Wait for final check
        while (check_idx < num_samples) begin
            @(posedge clk);
        end

        #(CLK_PERIOD * 5);

        $display("==================================================================");
        $display("tb_detector summary for %0s:", vec_dir);
        $display("  Samples tested: %0d", num_samples);
        $display("  First peak index: %0d", first_peak_idx);
        $display("  Gate mismatches: %0d", mismatches_gate);
        $display("  Peak mismatches: %0d", mismatches_peak);
        $display("  MWI mismatches:  %0d", mismatches_mwi);
        $display("  Total mismatches: %0d", total_mismatches);
        $display("==================================================================");

        if (total_mismatches == 0) begin
            $display("TB_RESULT: PASS name=tb_detector samples=%0d mismatches=0", num_samples);
            $finish(0);
        end else begin
            $display("TB_RESULT: FAIL name=tb_detector samples=%0d mismatches=%0d", num_samples, total_mismatches);
            $finish(1);
        end
    end

endmodule
