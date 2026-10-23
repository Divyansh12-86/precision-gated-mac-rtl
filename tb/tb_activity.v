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

    // Whole-core tracking registers & counters
    reg [63:0] base_toggles_dline, base_toggles_ctrl;
    reg [63:0] auto_toggles_dline, auto_toggles_ctrl, auto_toggles_det;

    // Previous cycle states - Datapath
    reg [7:0]  b_oph_q, b_opl_q;
    reg [31:0] b_mul_q, b_acc_q;

    reg [7:0]  a_oph_q, a_opl_q;
    reg [31:0] a_mul_q, a_acc_q;

    reg [7:0]  f_oph_q, f_opl_q;
    reg [31:0] f_mul_q, f_acc_q;

    reg [7:0]  p_oph_q, p_opl_q;
    reg [31:0] p_mul_q, p_acc_q;

    // Previous cycle states - Whole Core (Baseline)
    reg [5:0]  b_tidx_q;
    reg [15:0] b_stap_q;
    reg        b_shft_q;
    reg [1:0]  b_st_q;
    reg [5:0]  b_tcnt_q;
    reg [1:0]  b_dcnt_q;

    // Previous cycle states - Whole Core (Auto Gated)
    reg [5:0]  a_tidx_q;
    reg [15:0] a_stap_q;
    reg        a_shft_q;
    reg [1:0]  a_st_q;
    reg [5:0]  a_tcnt_q;
    reg [1:0]  a_dcnt_q;

    reg [15:0] a_xd1_q, a_xd2_q;
    reg [5:0]  a_ptr_q;
    reg [23:0] a_mwi_acc_q;
    reg [23:0] a_spki_q, a_npki_q, a_thresh_q;
    reg [33:0] a_sqacc_q;
    reg [16:0] a_sqcand_q;
    reg [6:0]  a_refcnt_q;
    reg [15:0] a_tsync_q;
    reg [6:0]  a_gtcnt_q;
    reg        a_gout_q;

    always @(posedge clk) begin
        if (!rst_n) begin
            base_toggles_oph <= 0; base_toggles_opl <= 0; base_toggles_mult <= 0; base_toggles_acc <= 0;
            auto_toggles_oph <= 0; auto_toggles_opl <= 0; auto_toggles_mult <= 0; auto_toggles_acc <= 0;
            full_toggles_oph <= 0; full_toggles_opl <= 0; full_toggles_mult <= 0; full_toggles_acc <= 0;
            appx_toggles_oph <= 0; appx_toggles_opl <= 0; appx_toggles_mult <= 0; appx_toggles_acc <= 0;

            base_toggles_dline <= 0; base_toggles_ctrl <= 0;
            auto_toggles_dline <= 0; auto_toggles_ctrl <= 0; auto_toggles_det <= 0;

            b_oph_q <= 0; b_opl_q <= 0; b_mul_q <= 0; b_acc_q <= 0;
            a_oph_q <= 0; a_opl_q <= 0; a_mul_q <= 0; a_acc_q <= 0;
            f_oph_q <= 0; f_opl_q <= 0; f_mul_q <= 0; f_acc_q <= 0;
            p_oph_q <= 0; p_opl_q <= 0; p_mul_q <= 0; p_acc_q <= 0;

            b_tidx_q <= 0; b_stap_q <= 0; b_shft_q <= 0;
            b_st_q <= 0; b_tcnt_q <= 0; b_dcnt_q <= 0;

            a_tidx_q <= 0; a_stap_q <= 0; a_shft_q <= 0;
            a_st_q <= 0; a_tcnt_q <= 0; a_dcnt_q <= 0;

            a_xd1_q <= 0; a_xd2_q <= 0; a_ptr_q <= 0; a_mwi_acc_q <= 0;
            a_spki_q <= 0; a_npki_q <= 0; a_thresh_q <= 0;
            a_sqacc_q <= 0; a_sqcand_q <= 0; a_refcnt_q <= 0; a_tsync_q <= 0;
            a_gtcnt_q <= 0; a_gout_q <= 0;
        end else begin
            // 1. Baseline Datapath
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

            // Baseline Whole Core (Dline & Ctrl)
            base_toggles_dline <= base_toggles_dline +
                                  popcount8({2'b0, u_baseline.tap_idx ^ b_tidx_q}) +
                                  popcount32({16'b0, u_baseline.sample_tap ^ b_stap_q}) +
                                  (u_baseline.shift_en ^ b_shft_q);
            base_toggles_ctrl  <= base_toggles_ctrl +
                                  popcount8({6'b0, u_baseline.state ^ b_st_q}) +
                                  popcount8({2'b0, u_baseline.tap_cnt ^ b_tcnt_q}) +
                                  popcount8({6'b0, u_baseline.drain_cnt ^ b_dcnt_q});
            b_tidx_q <= u_baseline.tap_idx;
            b_stap_q <= u_baseline.sample_tap;
            b_shft_q <= u_baseline.shift_en;
            b_st_q   <= u_baseline.state;
            b_tcnt_q <= u_baseline.tap_cnt;
            b_dcnt_q <= u_baseline.drain_cnt;

            // 2. Auto Datapath
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

            // Auto Whole Core (Dline, Ctrl, Det)
            auto_toggles_dline <= auto_toggles_dline +
                                  popcount8({2'b0, u_pg_auto.u_fir.tap_idx ^ a_tidx_q}) +
                                  popcount32({16'b0, u_pg_auto.u_fir.sample_tap ^ a_stap_q}) +
                                  (u_pg_auto.u_fir.shift_en ^ a_shft_q);
            auto_toggles_ctrl  <= auto_toggles_ctrl +
                                  popcount8({6'b0, u_pg_auto.u_fir.state ^ a_st_q}) +
                                  popcount8({2'b0, u_pg_auto.u_fir.tap_cnt ^ a_tcnt_q}) +
                                  popcount8({6'b0, u_pg_auto.u_fir.drain_cnt ^ a_dcnt_q});
            auto_toggles_det   <= auto_toggles_det +
                                  popcount32({16'b0, u_pg_auto.u_detector.x_d1 ^ a_xd1_q}) +
                                  popcount32({16'b0, u_pg_auto.u_detector.x_d2 ^ a_xd2_q}) +
                                  popcount8({2'b0, u_pg_auto.u_detector.ptr ^ a_ptr_q}) +
                                  popcount32({8'b0, u_pg_auto.u_detector.mwi_acc ^ a_mwi_acc_q}) +
                                  popcount32({8'b0, u_pg_auto.u_detector.spki ^ a_spki_q}) +
                                  popcount32({8'b0, u_pg_auto.u_detector.npki ^ a_npki_q}) +
                                  popcount32({8'b0, u_pg_auto.u_detector.threshold ^ a_thresh_q}) +
                                  popcount32(u_pg_auto.u_detector.sq_accum[31:0] ^ a_sqacc_q[31:0]) +
                                  popcount8({6'b0, u_pg_auto.u_detector.sq_accum[33:32] ^ a_sqacc_q[33:32]}) +
                                  popcount32({15'b0, u_pg_auto.u_detector.sq_cand ^ a_sqcand_q}) +
                                  popcount8({1'b0, u_pg_auto.u_detector.refractory_cnt ^ a_refcnt_q}) +
                                  popcount32({16'b0, u_pg_auto.u_detector.time_since_peak ^ a_tsync_q}) +
                                  popcount8({1'b0, u_pg_auto.u_detector.gate_cnt ^ a_gtcnt_q}) +
                                  (u_pg_auto.u_detector.gate_out ^ a_gout_q);

            a_tidx_q <= u_pg_auto.u_fir.tap_idx;
            a_stap_q <= u_pg_auto.u_fir.sample_tap;
            a_shft_q <= u_pg_auto.u_fir.shift_en;
            a_st_q   <= u_pg_auto.u_fir.state;
            a_tcnt_q <= u_pg_auto.u_fir.tap_cnt;
            a_dcnt_q <= u_pg_auto.u_fir.drain_cnt;

            a_xd1_q     <= u_pg_auto.u_detector.x_d1;
            a_xd2_q     <= u_pg_auto.u_detector.x_d2;
            a_ptr_q     <= u_pg_auto.u_detector.ptr;
            a_mwi_acc_q <= u_pg_auto.u_detector.mwi_acc;
            a_spki_q    <= u_pg_auto.u_detector.spki;
            a_npki_q    <= u_pg_auto.u_detector.npki;
            a_thresh_q  <= u_pg_auto.u_detector.threshold;
            a_sqacc_q   <= u_pg_auto.u_detector.sq_accum;
            a_sqcand_q  <= u_pg_auto.u_detector.sq_cand;
            a_refcnt_q  <= u_pg_auto.u_detector.refractory_cnt;
            a_tsync_q   <= u_pg_auto.u_detector.time_since_peak;
            a_gtcnt_q   <= u_pg_auto.u_detector.gate_cnt;
            a_gout_q    <= u_pg_auto.u_detector.gate_out;

            // 3. Full Datapath
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

            // 4. Approx Datapath
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
        $display("------------------------------------------------------------------");
        $display("WHOLE-CORE ACTIVITY (Datapath + DelayLine + Control + Detector):");
        $display("CORE_BASELINE:  dp=%0d dline=%0d ctrl=%0d det=0 core_total=%0d",
                 (base_toggles_oph + base_toggles_opl + base_toggles_mult + base_toggles_acc),
                 base_toggles_dline, base_toggles_ctrl,
                 (base_toggles_oph + base_toggles_opl + base_toggles_mult + base_toggles_acc) + base_toggles_dline + base_toggles_ctrl);
        $display("CORE_GATED_AUTO: dp=%0d dline=%0d ctrl=%0d det=%0d core_total=%0d",
                 (auto_toggles_oph + auto_toggles_opl + auto_toggles_mult + auto_toggles_acc),
                 auto_toggles_dline, auto_toggles_ctrl, auto_toggles_det,
                 (auto_toggles_oph + auto_toggles_opl + auto_toggles_mult + auto_toggles_acc) + auto_toggles_dline + auto_toggles_ctrl + auto_toggles_det);
        $display("==================================================================");

        $display("TB_RESULT: PASS name=tb_activity samples=%0d mismatches=0", num_samples);
        $finish(0);
    end

endmodule
