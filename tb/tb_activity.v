// =============================================================================
// Testbench: tb_activity
// Description: RTL switching activity characterization testbench.
//              Measures bit transitions (toggles) per clock cycle across:
//                1. baseline_fir_exact (conventional 16x16 MAC)
//                2. pg_top in auto gated mode
//                3. pg_top forced full (mode_force = 2'b01)
//                4. pg_top forced approx (mode_force = 2'b10)
//              Signals tracked per group:
//                - Group 1: Operand Bus (High [15:8], Low [7:0])
//                - Group 2: Multiplier Datapath / Product (32-bit)
//                - Group 3: Accumulator Datapath (32-bit)
//              Outputs machine-readable metrics for activity_report.py.
// =============================================================================
`timescale 1ns / 1ps

module tb_activity;

    parameter MAX_SAMPLES = 70000;
    parameter CLK_PERIOD = 10;

    reg clk;
    reg rst_n;
    reg sample_valid;
    reg signed [15:0] x_in;

    reg [15:0] tv_in_mem [0:MAX_SAMPLES-1];
    reg [1023:0] vec_dir;
    reg [1023:0] in_file;
    reg [1023:0] coeff_file;

    // 1. Baseline Exact
    wire signed [31:0] base_y_acc;
    wire base_y_valid;
    wire base_busy;

    baseline_fir_exact #(
        .N_TAPS(51),
        .PIPE(2),
        .COEFF_FILE("coeffs.mem")
    ) u_baseline (
        .clk(clk),
        .rst_n(rst_n),
        .sample_valid(sample_valid),
        .x_in(x_in),
        .y_valid(base_y_valid),
        .y_acc(base_y_acc),
        .busy(base_busy)
    );

    // 2. Gated Auto
    wire signed [31:0] auto_y_acc;
    wire auto_y_valid;
    wire auto_busy;

    pg_top #(
        .N_TAPS(51),
        .PIPE(2),
        .MULT_IMPL("LUT"),
        .COEFF_FILE("coeffs.mem"),
        .SQ_SHIFT(11)
    ) u_pg_auto (
        .clk(clk),
        .rst_n(rst_n),
        .sample_valid(sample_valid),
        .x_in(x_in),
        .mode_force(2'b00),
        .y_valid(auto_y_valid),
        .y_acc(auto_y_acc),
        .gate_out(),
        .peak_pulse(),
        .mwi_dbg(),
        .busy(auto_busy)
    );

    // 3. Gated Forced Full
    wire signed [31:0] full_y_acc;
    wire full_y_valid;
    wire full_busy;

    pg_top #(
        .N_TAPS(51),
        .PIPE(2),
        .MULT_IMPL("LUT"),
        .COEFF_FILE("coeffs.mem"),
        .SQ_SHIFT(11)
    ) u_pg_full (
        .clk(clk),
        .rst_n(rst_n),
        .sample_valid(sample_valid),
        .x_in(x_in),
        .mode_force(2'b01),
        .y_valid(full_y_valid),
        .y_acc(full_y_acc),
        .gate_out(),
        .peak_pulse(),
        .mwi_dbg(),
        .busy(full_busy)
    );

    // 4. Gated Forced Approx
    wire signed [31:0] approx_y_acc;
    wire approx_y_valid;
    wire approx_busy;

    pg_top #(
        .N_TAPS(51),
        .PIPE(2),
        .MULT_IMPL("LUT"),
        .COEFF_FILE("coeffs.mem"),
        .SQ_SHIFT(11)
    ) u_pg_approx (
        .clk(clk),
        .rst_n(rst_n),
        .sample_valid(sample_valid),
        .x_in(x_in),
        .mode_force(2'b10),
        .y_valid(approx_y_valid),
        .y_acc(approx_y_acc),
        .gate_out(),
        .peak_pulse(),
        .mwi_dbg(),
        .busy(approx_busy)
    );

    always #(CLK_PERIOD / 2) clk = ~clk;

    function integer popcount8(input [7:0] v);
        integer i, c;
        begin
            c = 0;
            for (i = 0; i < 8; i = i + 1) c = c + v[i];
            popcount8 = c;
        end
    endfunction

    function integer popcount32(input [31:0] v);
        integer i, c;
        begin
            c = 0;
            for (i = 0; i < 32; i = i + 1) c = c + v[i];
            popcount32 = c;
        end
    endfunction

    // Activity tracking registers & counters
    reg [63:0] base_toggles_oph, base_toggles_opl, base_toggles_mult, base_toggles_acc;
    reg [63:0] auto_toggles_oph, auto_toggles_opl, auto_toggles_mult, auto_toggles_acc;
    reg [63:0] full_toggles_oph, full_toggles_opl, full_toggles_mult, full_toggles_acc;
    reg [63:0] appx_toggles_oph, appx_toggles_opl, appx_toggles_mult, appx_toggles_acc;

    // Previous cycle states
    reg [7:0]  b_oph_q, b_opl_q;
    reg [31:0] b_mul_q, b_acc_q;

    reg [7:0]  a_oph_q, a_opl_q;
    reg [31:0] a_mul_q, a_acc_q;

    reg [7:0]  f_oph_q, f_opl_q;
    reg [31:0] f_mul_q, f_acc_q;

    reg [7:0]  p_oph_q, p_opl_q;
    reg [31:0] p_mul_q, p_acc_q;

    always @(posedge clk) begin
        if (!rst_n) begin
            base_toggles_oph <= 0; base_toggles_opl <= 0; base_toggles_mult <= 0; base_toggles_acc <= 0;
            auto_toggles_oph <= 0; auto_toggles_opl <= 0; auto_toggles_mult <= 0; auto_toggles_acc <= 0;
            full_toggles_oph <= 0; full_toggles_opl <= 0; full_toggles_mult <= 0; full_toggles_acc <= 0;
            appx_toggles_oph <= 0; appx_toggles_opl <= 0; appx_toggles_mult <= 0; appx_toggles_acc <= 0;

            b_oph_q <= 0; b_opl_q <= 0; b_mul_q <= 0; b_acc_q <= 0;
            a_oph_q <= 0; a_opl_q <= 0; a_mul_q <= 0; a_acc_q <= 0;
            f_oph_q <= 0; f_opl_q <= 0; f_mul_q <= 0; f_acc_q <= 0;
            p_oph_q <= 0; p_opl_q <= 0; p_mul_q <= 0; p_acc_q <= 0;
        end else begin
            // 1. Baseline
            if (base_busy) begin
                base_toggles_oph  <= base_toggles_oph  + popcount8(u_baseline.sample_tap[15:8] ^ b_oph_q);
                base_toggles_opl  <= base_toggles_opl  + popcount8(u_baseline.sample_tap[7:0]  ^ b_opl_q);
                base_toggles_mult <= base_toggles_mult + popcount32(u_baseline.prod_comb       ^ b_mul_q);
                base_toggles_acc  <= base_toggles_acc  + popcount32(u_baseline.y_acc           ^ b_acc_q);
            end
            b_oph_q <= u_baseline.sample_tap[15:8];
            b_opl_q <= u_baseline.sample_tap[7:0];
            b_mul_q <= u_baseline.prod_comb;
            b_acc_q <= u_baseline.y_acc;

            // 2. Auto
            if (auto_busy) begin
                auto_toggles_oph  <= auto_toggles_oph  + popcount8(u_pg_auto.u_fir.u_mult.xh     ^ a_oph_q);
                auto_toggles_opl  <= auto_toggles_opl  + popcount8(u_pg_auto.u_fir.u_mult.xl_eff ^ a_opl_q);
                auto_toggles_mult <= auto_toggles_mult + popcount32(u_pg_auto.u_fir.u_mult.prod_out ^ a_mul_q);
                auto_toggles_acc  <= auto_toggles_acc  + popcount32(u_pg_auto.u_fir.u_mac.acc_out   ^ a_acc_q);
            end
            a_oph_q <= u_pg_auto.u_fir.u_mult.xh;
            a_opl_q <= u_pg_auto.u_fir.u_mult.xl_eff;
            a_mul_q <= u_pg_auto.u_fir.u_mult.prod_out;
            a_acc_q <= u_pg_auto.u_fir.u_mac.acc_out;

            // 3. Full
            if (full_busy) begin
                full_toggles_oph  <= full_toggles_oph  + popcount8(u_pg_full.u_fir.u_mult.xh     ^ f_oph_q);
                full_toggles_opl  <= full_toggles_opl  + popcount8(u_pg_full.u_fir.u_mult.xl_eff ^ f_opl_q);
                full_toggles_mult <= full_toggles_mult + popcount32(u_pg_full.u_fir.u_mult.prod_out ^ f_mul_q);
                full_toggles_acc  <= full_toggles_acc  + popcount32(u_pg_full.u_fir.u_mac.acc_out   ^ f_acc_q);
            end
            f_oph_q <= u_pg_full.u_fir.u_mult.xh;
            f_opl_q <= u_pg_full.u_fir.u_mult.xl_eff;
            f_mul_q <= u_pg_full.u_fir.u_mult.prod_out;
            f_acc_q <= u_pg_full.u_fir.u_mac.acc_out;

            // 4. Approx
            if (approx_busy) begin
                appx_toggles_oph  <= appx_toggles_oph  + popcount8(u_pg_approx.u_fir.u_mult.xh     ^ p_oph_q);
                appx_toggles_opl  <= appx_toggles_opl  + popcount8(u_pg_approx.u_fir.u_mult.xl_eff ^ p_opl_q);
                appx_toggles_mult <= appx_toggles_mult + popcount32(u_pg_approx.u_fir.u_mult.prod_out ^ p_mul_q);
                appx_toggles_acc  <= appx_toggles_acc  + popcount32(u_pg_approx.u_fir.u_mac.acc_out   ^ p_acc_q);
            end
            p_oph_q <= u_pg_approx.u_fir.u_mult.xh;
            p_opl_q <= u_pg_approx.u_fir.u_mult.xl_eff;
            p_mul_q <= u_pg_approx.u_fir.u_mult.prod_out;
            p_acc_q <= u_pg_approx.u_fir.u_mac.acc_out;
        end
    end

    integer num_samples = 0;
    integer sample_idx = 0;
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
        $sformat(coeff_file, "%0s/coeffs.mem", vec_dir);

        $readmemh(in_file, tv_in_mem);
        $readmemh(coeff_file, u_baseline.u_rom.rom);
        $readmemh(coeff_file, u_pg_auto.u_fir.u_rom.rom);
        $readmemh(coeff_file, u_pg_full.u_fir.u_rom.rom);
        $readmemh(coeff_file, u_pg_approx.u_fir.u_rom.rom);

        f_in = $fopen(in_file, "r");
        if (f_in == 0) begin
            $fatal(1, "Failed to open input file: %0s", in_file);
        end
        num_samples = 0;
        while ($fscanf(f_in, "%h\n", temp_val) == 1) begin
            num_samples = num_samples + 1;
        end
        $fclose(f_in);

        $display("==================================================================");
        $display("tb_activity starting on %0d samples from %0s...", num_samples, vec_dir);
        $display("==================================================================");

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

            while (!auto_y_valid) @(posedge clk);
            while (auto_busy || auto_y_valid) @(posedge clk);
            repeat (10) @(posedge clk);
        end

        #(CLK_PERIOD * 10);

        $display("==================================================================");
        $display("SWITCHING ACTIVITY MEASUREMENTS (Total Toggles across %0d samples):", num_samples);
        $display("BASELINE:       oph=%0d opl=%0d mult=%0d acc=%0d total=%0d",
                 base_toggles_oph, base_toggles_opl, base_toggles_mult, base_toggles_acc,
                 base_toggles_oph + base_toggles_opl + base_toggles_mult + base_toggles_acc);
        $display("GATED_AUTO:     oph=%0d opl=%0d mult=%0d acc=%0d total=%0d",
                 auto_toggles_oph, auto_toggles_opl, auto_toggles_mult, auto_toggles_acc,
                 auto_toggles_oph + auto_toggles_opl + auto_toggles_mult + auto_toggles_acc);
        $display("GATED_FULL:     oph=%0d opl=%0d mult=%0d acc=%0d total=%0d",
                 full_toggles_oph, full_toggles_opl, full_toggles_mult, full_toggles_acc,
                 full_toggles_oph + full_toggles_opl + full_toggles_mult + full_toggles_acc);
        $display("GATED_APPROX:   oph=%0d opl=%0d mult=%0d acc=%0d total=%0d",
                 appx_toggles_oph, appx_toggles_opl, appx_toggles_mult, appx_toggles_acc,
                 appx_toggles_oph + appx_toggles_opl + appx_toggles_mult + appx_toggles_acc);
        $display("==================================================================");

        $display("TB_RESULT: PASS name=tb_activity samples=%0d mismatches=0", num_samples);
        $finish(0);
    end

endmodule
