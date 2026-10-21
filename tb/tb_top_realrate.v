// =============================================================================
// Testbench: tb_top_realrate
// Description: Real-rate (360 Hz) system testbench for pg_top with sample_tick_gen.
//              - Uses sample_tick_gen to pace samples at 100 MHz clock -> 360 Hz.
//              - Runs 1000 samples (~2.78 seconds of real-time ECG).
//              - Verifies that busy never collides with sample_tick.
//              - Verifies bit-exact output match with tv_outputs_gated.hex.
//              - Outputs standardized line:
//                TB_RESULT: PASS name=tb_top_realrate samples=1000 mismatches=0
// =============================================================================
`timescale 1ns / 1ps

module tb_top_realrate;

    parameter CLK_HZ = 100_000_000;
    parameter FS     = 360;
    parameter CLK_PERIOD = 10; // 10 ns = 100 MHz
    parameter TEST_SAMPLES = 1000;

    reg clk;
    reg rst_n;
    wire sample_tick;
    wire signed [15:0] x_in;

    wire y_valid;
    wire signed [31:0] y_acc;
    wire gate_out;
    wire peak_pulse;
    wire [17:0] mwi_dbg;
    wire busy;

    // Test storage
    reg [15:0] tv_in_mem        [0:TEST_SAMPLES-1];
    reg        tv_gate_mem      [0:TEST_SAMPLES-1];
    reg [31:0] tv_out_gated_mem [0:TEST_SAMPLES-1];

    reg [1023:0] vec_dir;
    reg [1023:0] in_file;
    reg [1023:0] gate_file;
    reg [1023:0] out_file;
    reg [1023:0] coeff_file;

    // Tick Generator
    sample_tick_gen #(
        .CLK_HZ(CLK_HZ),
        .FS(FS)
    ) u_tick (
        .clk(clk),
        .rst_n(rst_n),
        .enable(1'b1),
        .tick(sample_tick)
    );

    // DUT
    pg_top #(
        .N_TAPS(51),
        .PIPE(2),
        .MULT_IMPL("LUT"),
        .COEFF_FILE("coeffs.mem"),
        .SQ_SHIFT(11)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .sample_valid(sample_tick),
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

    integer sample_idx = 0;
    integer out_idx = 0;
    integer mismatches = 0;
    integer overflow_collisions = 0;

    // Drive x_in combinational from current sample_idx so it is set when sample_tick fires
    assign x_in = (sample_idx < TEST_SAMPLES) ? tv_in_mem[sample_idx] : 16'sd0;

    // Advance sample_idx on tick
    always @(posedge clk) begin
        if (!rst_n) begin
            sample_idx <= 0;
        end else if (sample_tick) begin
            if (sample_idx < TEST_SAMPLES) begin
                sample_idx <= sample_idx + 1;
            end
        end
    end

    // Collision check: if sample_tick arrives while DUT is busy with a previous sample
    always @(posedge clk) begin
        if (rst_n && sample_tick && busy) begin
            overflow_collisions <= overflow_collisions + 1;
            $display("ERROR: Sample tick collided with busy DUT at sample %0d!", sample_idx);
        end
    end

    // Output check
    always @(posedge clk) begin
        if (rst_n && y_valid) begin
            if (out_idx < TEST_SAMPLES) begin
                if (y_acc !== $signed(tv_out_gated_mem[out_idx])) begin
                    mismatches = mismatches + 1;
                    if (mismatches <= 5) begin
                        $display("MISMATCH at sample %0d: actual=0x%08X, expected=0x%08X",
                                 out_idx, y_acc, tv_out_gated_mem[out_idx]);
                    end
                end
                out_idx = out_idx + 1;
            end
        end
    end

    // Watchdog
    initial begin
        #(CLK_PERIOD * 350000000); // 3.5s limit
        $display("FATAL: Watchdog timeout in tb_top_realrate!");
        $finish(1);
    end

    initial begin
        clk = 0;
        rst_n = 0;

        if (!$value$plusargs("VEC_DIR=%s", vec_dir)) begin
            vec_dir = "data/test_vectors/smoke";
        end

        $sformat(in_file, "%0s/tv_inputs.hex", vec_dir);
        $sformat(gate_file, "%0s/tv_gate_flags.hex", vec_dir);
        $sformat(out_file, "%0s/tv_outputs_gated.hex", vec_dir);
        $sformat(coeff_file, "%0s/coeffs.mem", vec_dir);

        $readmemh(in_file, tv_in_mem);
        $readmemh(gate_file, tv_gate_mem);
        $readmemh(out_file, tv_out_gated_mem);
        $readmemh(coeff_file, dut.u_fir.u_rom.rom);

        $display("==================================================================");
        $display("tb_top_realrate starting on %0d samples at 360 Hz (100 MHz clock)...", TEST_SAMPLES);
        $display("==================================================================");

        #(CLK_PERIOD * 5);
        @(posedge clk);
        rst_n = 1;

        // Run until all samples processed
        while (out_idx < TEST_SAMPLES) begin
            @(posedge clk);
        end

        #(CLK_PERIOD * 10);

        $display("==================================================================");
        $display("tb_top_realrate summary:");
        $display("  Samples processed: %0d", out_idx);
        $display("  Overflow collisions: %0d", overflow_collisions);
        $display("  Mismatches: %0d", mismatches);
        $display("==================================================================");

        if (mismatches == 0 && overflow_collisions == 0) begin
            $display("TB_RESULT: PASS name=tb_top_realrate samples=%0d mismatches=0", TEST_SAMPLES);
            $finish(0);
        end else begin
            $display("TB_RESULT: FAIL name=tb_top_realrate samples=%0d mismatches=%0d collisions=%0d",
                     TEST_SAMPLES, mismatches, overflow_collisions);
            $finish(1);
        end
    end

endmodule
