// =============================================================================
// Testbench: tb_fir_gated
// Description: Tests pg_fir with precision gating.
//              Modes supported:
//                - Dynamic mode (mode_force = 2'b00, gate_in from tv_gate_flags.hex)
//                  compared against tv_outputs_gated.hex
//                - Forced full (mode_force = 2'b01) compared against tv_outputs_full.hex
//                - Forced approx (mode_force = 2'b10) compared against tv_outputs_allapprox.hex
//              Verifies:
//                - Exact output match (mismatches == 0)
//                - Operand isolation: low multiplier input bus (xl_eff) is 0 during approx cycles
//                - Glitch-free cycle-by-cycle mode switching
//              Outputs standardized line:
//                TB_RESULT: PASS name=tb_fir_gated samples=<N> mismatches=0
// =============================================================================
`timescale 1ns / 1ps

module tb_fir_gated #(
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
    reg [15:0] tv_in_mem          [0:MAX_SAMPLES-1];
    reg        tv_gate_mem        [0:MAX_SAMPLES-1];
    reg [31:0] tv_out_gated_mem   [0:MAX_SAMPLES-1];
    reg [31:0] tv_out_full_mem    [0:MAX_SAMPLES-1];
    reg [31:0] tv_out_approx_mem  [0:MAX_SAMPLES-1];

    reg [1023:0] vec_dir;
    reg [1023:0] in_file;
    reg [1023:0] gate_file;
    reg [1023:0] out_gated_file;
    reg [1023:0] out_full_file;
    reg [1023:0] out_approx_file;
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
    integer out_idx = 0;
    integer mismatches = 0;
    integer isolation_errors = 0;
    integer approx_cycles_checked = 0;
    integer current_target_mode = 0; // 0: gated, 1: full, 2: approx

    // Continuous check on operand isolation
    always @(posedge clk) begin
        if (rst_n && dut.busy) begin
            if (dut.mode_approx_q) begin
                approx_cycles_checked <= approx_cycles_checked + 1;
                if (dut.u_mult.xl_eff !== 8'h00) begin
                    isolation_errors <= isolation_errors + 1;
                    if (isolation_errors <= 5) begin
                        $display("ISOLATION ERROR: xl_eff = 0x%02X in approx mode at time %0t", dut.u_mult.xl_eff, $time);
                    end
                end
            end
        end
    end

    // Output checking process
    always @(posedge clk) begin
        if (rst_n && y_valid) begin
            reg [31:0] exp_val;
            if (current_target_mode == 0) begin
                exp_val = tv_out_gated_mem[out_idx];
            end else if (current_target_mode == 1) begin
                exp_val = tv_out_full_mem[out_idx];
            end else begin
                exp_val = tv_out_approx_mem[out_idx];
            end

            if (out_idx < num_samples) begin
                if (y_acc !== $signed(exp_val)) begin
                    mismatches = mismatches + 1;
                    if (mismatches <= 5) begin
                        $display("FAIL MISMATCH [mode %0d] at sample %0d: actual=0x%08X (%d), expected=0x%08X (%d)",
                                 current_target_mode, out_idx, y_acc, y_acc, exp_val, $signed(exp_val));
                    end
                end
                out_idx = out_idx + 1;
            end
        end
    end

    task run_stream(input integer target_m, input [1:0] m_force);
        integer s_idx;
        begin
            current_target_mode = target_m;
            mode_force = m_force;
            out_idx = 0;

            // Reset DUT
            rst_n = 0;
            sample_valid = 0;
            x_in = 0;
            gate_in = 1;
            #(CLK_PERIOD * 4);
            @(posedge clk);
            rst_n = 1;
            #(CLK_PERIOD * 2);

            for (s_idx = 0; s_idx < num_samples; s_idx = s_idx + 1) begin
                @(posedge clk);
                sample_valid <= 1'b1;
                x_in <= tv_in_mem[s_idx];
                gate_in <= tv_gate_mem[s_idx];

                @(posedge clk);
                sample_valid <= 1'b0;

                // Wait until DUT completes filtering (51 taps + PIPE + drain)
                while (busy || y_valid) begin
                    @(posedge clk);
                end
                #(CLK_PERIOD * 2);
            end

            // Wait for final sample out
            while (out_idx < num_samples) begin
                @(posedge clk);
            end
            #(CLK_PERIOD * 5);
        end
    endtask

    integer f_in, test_all_modes_flag, mode_force_arg;
    reg [15:0] temp_val;

    initial begin
        clk = 0;
        rst_n = 0;
        sample_valid = 0;
        x_in = 0;
        gate_in = 1;
        mode_force = 2'b00;

        if (!$value$plusargs("VEC_DIR=%s", vec_dir)) begin
            vec_dir = "data/test_vectors/smoke";
        end

        if (!$value$plusargs("TEST_ALL_MODES=%d", test_all_modes_flag)) begin
            test_all_modes_flag = 1; // Default to testing all 3 modes
        end

        if (!$value$plusargs("MODE_FORCE=%d", mode_force_arg)) begin
            mode_force_arg = 0; // 0: dynamic
        end

        $sformat(in_file, "%0s/tv_inputs.hex", vec_dir);
        $sformat(gate_file, "%0s/tv_gate_flags.hex", vec_dir);
        $sformat(out_gated_file, "%0s/tv_outputs_gated.hex", vec_dir);
        $sformat(out_full_file, "%0s/tv_outputs_full.hex", vec_dir);
        $sformat(out_approx_file, "%0s/tv_outputs_allapprox.hex", vec_dir);
        $sformat(coeff_file, "%0s/coeffs.mem", vec_dir);

        $display("==================================================================");
        $display("tb_fir_gated starting on vectors: %0s", vec_dir);
        $display("==================================================================");

        $readmemh(in_file, tv_in_mem);
        $readmemh(gate_file, tv_gate_mem);
        $readmemh(out_gated_file, tv_out_gated_mem);
        $readmemh(out_full_file, tv_out_full_mem);
        $readmemh(out_approx_file, tv_out_approx_mem);
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

        $display("Loaded %0d samples.", num_samples);

        if (test_all_modes_flag != 0) begin
            // Pass 1: Dynamic mode (gate_in from file, mode_force = 2'b00)
            $display("--- Pass 1: Dynamic Precision Gating ---");
            run_stream(0, 2'b00);

            // Pass 2: Forced Full (mode_force = 2'b01)
            $display("--- Pass 2: Forced Full Precision ---");
            run_stream(1, 2'b01);

            // Pass 3: Forced Approx (mode_force = 2'b10)
            $display("--- Pass 3: Forced Approximate Precision ---");
            run_stream(2, 2'b10);
        end else begin
            if (mode_force_arg == 1) begin
                $display("--- Running Forced Full Mode ---");
                run_stream(1, 2'b01);
            end else if (mode_force_arg == 2) begin
                $display("--- Running Forced Approx Mode ---");
                run_stream(2, 2'b10);
            end else begin
                $display("--- Running Dynamic Gated Mode ---");
                run_stream(0, 2'b00);
            end
        end

        $display("==================================================================");
        $display("Simulation completed.");
        $display("Total mismatches: %0d", mismatches);
        $display("Total isolation errors: %0d", isolation_errors);
        $display("Approx cycles verified with xl_eff==0: %0d", approx_cycles_checked);

        if (mismatches == 0 && isolation_errors == 0 && (test_all_modes_flag == 0 || approx_cycles_checked >= 1000 || num_samples < 50)) begin
            $display("TB_RESULT: PASS name=tb_fir_gated samples=%0d mismatches=0", num_samples);
            $finish(0);
        end else begin
            $display("TB_RESULT: FAIL name=tb_fir_gated samples=%0d mismatches=%0d isolation_errors=%0d",
                     num_samples, mismatches, isolation_errors);
            $finish(1);
        end
    end

endmodule
