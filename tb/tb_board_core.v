// =============================================================================
// Testbench: tb_board_core
// Description: Bit-level UART simulation testbench for board_core.
//              - Instantiates shared hardware demonstration core.
//              - Bit-level asynchronous UART receiver samples uart_txd line.
//              - Reassembles 7-byte frames:
//                [0xA5, y_acc[31:24], y_acc[23:16], y_acc[15:8], y_acc[7:0], flags, XOR_checksum]
//              - Verifies sync preamble (0xA5) and XOR checksum.
//              - Compares decoded y_acc and gate flag bit-exactly against golden vectors
//                over 5,000 real MIT-BIH ECG samples.
//              - Standardized output:
//                TB_RESULT: PASS name=tb_board_core samples=<N> mismatches=0
// =============================================================================
`timescale 1ns / 1ps

module tb_board_core;

    parameter CLK_HZ    = 10_000_000;
    parameter BAUD      = 1_000_000;   // 10 cycles/bit for fast simulation
    parameter CLK_PER_BIT = CLK_HZ / BAUD; // 10
    parameter REAL_CLK_PER_BIT = 868; // 100 MHz / 115200 baud
    parameter FAST_TICK = 800;         // 800 cycles/sample (700 cycles for 7-byte UART frame)
    parameter TEST_SAMPLES = 5000;

    reg clk;
    reg rst_n;
    reg [1:0] sw_mode_force;
    reg sw_pause;

    wire uart_txd;
    wire led_gate;
    wire led_peak;
    wire led_busy;
    wire led_heartbeat;
    wire [7:0] led_y_msb;

    // Test storage (sized to hold complete vector set)
    reg [31:0] tv_out_gated_mem     [0:60000-1];
    reg [31:0] tv_out_full_mem      [0:60000-1];
    reg [31:0] tv_out_allapprox_mem [0:60000-1];
    reg        tv_gate_mem          [0:60000-1];

    // DUT (fast simulation configuration for replay/switch/glitch test scenarios)
    board_core #(
        .CLK_HZ(CLK_HZ),
        .FS(360),
        .BAUD(BAUD),
        .ROM_FILE("ecg_rom.mem"),
        .ROM_DEPTH(60_000),
        .FAST_TICK(FAST_TICK)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .sw_mode_force(sw_mode_force),
        .sw_pause(sw_pause),
        .uart_txd(uart_txd),
        .led_gate(led_gate),
        .led_peak(led_peak),
        .led_busy(led_busy),
        .led_heartbeat(led_heartbeat),
        .led_y_msb(led_y_msb)
    );

    // DUT with 100% shipped default parameters (POR 65535, DEBOUNCE 100000, 360Hz, 115200 baud)
    // No parameter overrides except ROM file and depth
    reg        rst_n_real;
    reg [1:0]  sw_mode_force_real;
    reg        sw_pause_real;
    wire       uart_txd_real;
    wire       led_gate_real;
    wire       led_peak_real;
    wire       led_busy_real;
    wire       led_heartbeat_real;
    wire [7:0] led_y_msb_real;

    board_core #(
        .ROM_FILE("data/rom_64.mem"),
        .ROM_DEPTH(64)
    ) dut_real (
        .clk(clk),
        .rst_n(rst_n_real),
        .sw_mode_force(sw_mode_force_real),
        .sw_pause(sw_pause_real),
        .uart_txd(uart_txd_real),
        .led_gate(led_gate_real),
        .led_peak(led_peak_real),
        .led_busy(led_busy_real),
        .led_heartbeat(led_heartbeat_real),
        .led_y_msb(led_y_msb_real)
    );

    always #5 clk = ~clk; // 100 MHz simulation clock (10 ns period)

    integer mismatches_y    = 0;
    integer mismatches_gate = 0;
    integer checksum_errors = 0;
    integer preamble_errors = 0;
    integer frames_received = 0;

    // Bit-level UART receiver task
    task uart_rx_byte;
        output [7:0] data;
        integer i;
        begin
            // 1. Wait for falling edge of start bit
            @(negedge uart_txd);

            // 2. Wait 1.5 bit periods to sample center of bit 0
            repeat (CLK_PER_BIT + (CLK_PER_BIT / 2)) @(posedge clk);

            // 3. Sample 8 data bits
            for (i = 0; i < 8; i = i + 1) begin
                data[i] = uart_txd;
                repeat (CLK_PER_BIT) @(posedge clk);
            end

            // 4. Sample stop bit (must be 1)
            if (uart_txd !== 1'b1) begin
                $display("ERROR: Framing error! Stop bit not 1 at frame %0d", frames_received);
            end
        end
    endtask

    // Frame receiver process
    reg [7:0] f_byte0;
    reg [7:0] f_byte1;
    reg [7:0] f_byte2;
    reg [7:0] f_byte3;
    reg [7:0] f_byte4;
    reg [7:0] f_byte5;
    reg [7:0] f_byte6;
    reg [7:0] calc_chk;
    reg signed [31:0] rx_y;
    reg rx_gate;
    integer dump_file;

    task rx_frame;
        output [31:0] y_out;
        output [7:0]  flags_out;
        begin
            uart_rx_byte(f_byte0);
            uart_rx_byte(f_byte1);
            uart_rx_byte(f_byte2);
            uart_rx_byte(f_byte3);
            uart_rx_byte(f_byte4);
            uart_rx_byte(f_byte5);
            uart_rx_byte(f_byte6);

            if (f_byte0 !== 8'hA5) begin
                preamble_errors = preamble_errors + 1;
                $display("FAIL: Bad preamble 0x%02X at frame %0d", f_byte0, frames_received);
            end

            calc_chk = f_byte0 ^ f_byte1 ^ f_byte2 ^ f_byte3 ^ f_byte4 ^ f_byte5;
            if (calc_chk !== f_byte6) begin
                checksum_errors = checksum_errors + 1;
                $display("FAIL: Checksum mismatch at frame %0d: got 0x%02X, expected 0x%02X",
                         frames_received, f_byte6, calc_chk);
            end

            y_out     = {f_byte1, f_byte2, f_byte3, f_byte4};
            flags_out = f_byte5;
        end
    endtask

    // Bit-level receiver for 115,200 baud default demonstration core
    task uart_rx_byte_real;
        output [7:0] data;
        integer i;
        begin
            @(negedge uart_txd_real);
            repeat (REAL_CLK_PER_BIT + (REAL_CLK_PER_BIT / 2)) @(posedge clk);
            for (i = 0; i < 8; i = i + 1) begin
                data[i] = uart_txd_real;
                repeat (REAL_CLK_PER_BIT) @(posedge clk);
            end
            if (uart_txd_real !== 1'b1) begin
                $display("ERROR: Real baud framing error! Stop bit not 1 at frame %0d", frames_received);
            end
        end
    endtask

    task rx_frame_real;
        output [31:0] y_out;
        output [7:0]  flags_out;
        reg [7:0] rb0, rb1, rb2, rb3, rb4, rb5, rb6, rchk;
        begin
            uart_rx_byte_real(rb0);
            uart_rx_byte_real(rb1);
            uart_rx_byte_real(rb2);
            uart_rx_byte_real(rb3);
            uart_rx_byte_real(rb4);
            uart_rx_byte_real(rb5);
            uart_rx_byte_real(rb6);

            if (rb0 !== 8'hA5) begin
                preamble_errors = preamble_errors + 1;
                $display("FAIL: Bad real preamble 0x%02X at frame %0d", rb0, frames_received);
            end

            rchk = rb0 ^ rb1 ^ rb2 ^ rb3 ^ rb4 ^ rb5;
            if (rchk !== rb6) begin
                checksum_errors = checksum_errors + 1;
                $display("FAIL: Real checksum mismatch at frame %0d: got 0x%02X, expected 0x%02X",
                         frames_received, rb6, rchk);
            end

            y_out     = {rb1, rb2, rb3, rb4};
            flags_out = rb5;
        end
    endtask

    reg [255:0] scenario;
    integer k;
    reg [31:0] frame_y;
    reg [7:0]  frame_flags;

    initial begin
        scenario = "por_replay";
        $value$plusargs("SCENARIO=%s", scenario);

        // Load reference vectors
        $readmemh("data/test_vectors/std_fixed_100/tv_outputs_gated.hex", tv_out_gated_mem);
        $readmemh("data/test_vectors/std_fixed_100/tv_outputs_full.hex", tv_out_full_mem);
        $readmemh("data/test_vectors/std_fixed_100/tv_outputs_allapprox.hex", tv_out_allapprox_mem);
        $readmemh("data/test_vectors/std_fixed_100/tv_gate_flags.hex", tv_gate_mem);

        clk           = 0;
        rst_n         = 1; // Pure power-on reset: NO reset pulse at time 0
        sw_mode_force = 2'b00; // Auto precision gating
        sw_pause      = 0;
        rst_n_real    = 1;
        sw_mode_force_real = 2'b00;
        sw_pause_real = 0;

        $display("==================================================================");
        $display("STARTING tb_board_core (SCENARIO: %0s)", scenario);
        $display("==================================================================");

        if (scenario == "por_replay") begin
            dump_file = $fopen("reports/board_uart_dump.bin", "wb");

            while (frames_received < TEST_SAMPLES) begin
                rx_frame(frame_y, frame_flags);

                if (dump_file != 0) begin
                    $fwrite(dump_file, "%c%c%c%c%c%c%c", f_byte0, f_byte1, f_byte2, f_byte3, f_byte4, f_byte5, f_byte6);
                end

                if ($signed(frame_y) !== $signed(tv_out_gated_mem[frames_received])) begin
                    mismatches_y = mismatches_y + 1;
                    if (mismatches_y <= 5) begin
                        $display("FAIL Y_ACC MISMATCH at sample %0d: rx=0x%08X, exp=0x%08X",
                                 frames_received, frame_y, tv_out_gated_mem[frames_received]);
                    end
                end

                if (frame_flags[0] !== tv_gate_mem[frames_received]) begin
                    mismatches_gate = mismatches_gate + 1;
                    if (mismatches_gate <= 5) begin
                        $display("FAIL GATE MISMATCH at sample %0d: rx=%b, exp=%b",
                                 frames_received, frame_flags[0], tv_gate_mem[frames_received]);
                    end
                end

                frames_received = frames_received + 1;
                if (frames_received % 1000 == 0) begin
                    $display("  Verified %0d / %0d frames over UART stream...", frames_received, TEST_SAMPLES);
                end
            end

            if (dump_file != 0) $fclose(dump_file);

        end else if (scenario == "async_switch") begin
            // Scenario 2: Switch toggles asynchronous to clock at random times
            // Sample 0..49: Auto
            for (k = 0; k < 50; k = k + 1) begin
                rx_frame(frame_y, frame_flags);
                if ($signed(frame_y) !== $signed(tv_out_gated_mem[k])) mismatches_y = mismatches_y + 1;
                frames_received = frames_received + 1;
            end

            // Wait for sample 50 computation to start, then toggle switch mid-flight
            @(posedge dut.sample_tick); // sample 50 tick
            repeat (20) @(posedge clk);  // mid-flight at tap 20
            #1;
            sw_mode_force = 2'b01;      // switch to Force Full mid-sample
            repeat (5) @(posedge clk);
            if (dut.mode_force_latched !== 2'b00) begin
                $display("ERROR: Mode latch failed! mode_force_latched changed mid-sample while sample_tick is low!");
                mismatches_gate = mismatches_gate + 1;
            end

            // Sample 50 must complete with Auto mode (protected by mode latch)
            rx_frame(frame_y, frame_flags);
            if ($signed(frame_y) !== $signed(tv_out_gated_mem[50])) begin
                $display("ERROR: Mode latch failed! Sample 50 corrupted by mid-flight switch toggle.");
                mismatches_y = mismatches_y + 1;
            end
            frames_received = frames_received + 1;

            // Sample 51..99: Force Full
            for (k = 51; k < 100; k = k + 1) begin
                rx_frame(frame_y, frame_flags);
                if (k > 52) begin // allow 1 sample pipeline latency
                    if ($signed(frame_y) !== $signed(tv_out_full_mem[k])) mismatches_y = mismatches_y + 1;
                    if (frame_flags[2] !== 1'b1) mismatches_gate = mismatches_gate + 1; // force bit
                end
                frames_received = frames_received + 1;
            end

            // Asynchronously switch to Force Approx
            #456;
            sw_mode_force = 2'b10;

            // Sample 100..149: Force Approx
            for (k = 100; k < 150; k = k + 1) begin
                rx_frame(frame_y, frame_flags);
                if (k > 101) begin
                    if ($signed(frame_y) !== $signed(tv_out_allapprox_mem[k])) mismatches_y = mismatches_y + 1;
                    if (frame_flags[2] !== 1'b1) mismatches_gate = mismatches_gate + 1;
                end
                frames_received = frames_received + 1;
            end

            // Test pause synchronizer: toggle sw_pause and verify 2-cycle synchronizer pipeline
            sw_pause = 1;
            @(posedge clk);
            if (dut.sw_pause_sync2 !== 1'b0) begin
                $display("ERROR: sw_pause synchronizer bypassed (active after 1 cycle)!");
                mismatches_gate = mismatches_gate + 1;
            end
            @(posedge clk);
            if (dut.sw_pause_sync2 !== 1'b1) begin
                $display("ERROR: sw_pause synchronizer failed to propagate after 2 cycles!");
                mismatches_gate = mismatches_gate + 1;
            end
            sw_pause = 0;
            repeat (10) @(posedge clk);

            rx_frame(frame_y, frame_flags);
            if ($signed(frame_y) !== $signed(tv_out_allapprox_mem[150])) begin
                $display("ERROR: After pause: Expected sample 150, got 0x%08X", frame_y);
                mismatches_y = mismatches_y + 1;
            end
            frames_received = frames_received + 1;

            $display("  Async switch and pause synchronizer verified across 151 frames with 0 hazards.");

        end else if (scenario == "debounce_glitch") begin
            // Scenario 3: 100 ns glitch ignored; >= 5 ms press resets cleanly
            for (k = 0; k < 30; k = k + 1) begin
                rx_frame(frame_y, frame_flags);
                frames_received = frames_received + 1;
            end

            // Inject 100 ns glitch on rst_n (10 cycles < 32 cycles debounce)
            $display("  Injecting 100 ns glitch on rst_n line...");
            rst_n = 0;
            #100;
            rst_n = 1;

            // Verify core continues without reset (sample 30 onwards)
            rx_frame(frame_y, frame_flags);
            frames_received = frames_received + 1;
            if ($signed(frame_y) !== $signed(tv_out_gated_mem[30])) begin
                $display("ERROR: Core reset on glitch! Expected sample 30, got 0x%08X", frame_y);
                mismatches_y = mismatches_y + 1;
            end else begin
                $display("  Glitch successfully filtered by debounce logic.");
            end

            // Assert long press (500 cycles > 32 cycles debounce)
            $display("  Asserting verified button press (500 cycles)...");
            rst_n = 0;
            repeat (500) @(posedge clk);
            rst_n = 1;

            // Verify core restarts cleanly from sample 0
            rx_frame(frame_y, frame_flags);
            frames_received = frames_received + 1;
            if ($signed(frame_y) !== $signed(tv_out_gated_mem[0])) begin
                $display("ERROR: Core failed to restart at sample 0 after reset! Got 0x%08X, expected 0x%08X",
                         frame_y, tv_out_gated_mem[0]);
                mismatches_y = mismatches_y + 1;
            end else begin
                $display("  Core cleanly restarted at sample 0 after verified reset press.");
            end
        end else if (scenario == "realparams") begin
            // Scenario 4: Shipped defaults (POR=65535, DEBOUNCE=100000, 360Hz, 115200 baud)
            // No reset pulse at time 0 (power-on reset only)
            rst_n_real = 1;
            sw_mode_force_real = 2'b00;
            sw_pause_real = 0;

            // MUT30 check: Check por_done == 0 before 65,535 cycles (e.g. at cycle 10,000)
            repeat (10000) @(posedge clk);
            if (dut_real.por_done !== 1'b0) begin
                $display("FAIL: dut_real.por_done asserted prematurely at cycle 10,000! (Expected POR_CYCLES=65535)");
                mismatches_y = mismatches_y + 1;
            end

            // Capture first 8 frames
            for (k = 0; k < 8; k = k + 1) begin
                rx_frame_real(frame_y, frame_flags);
                if ($signed(frame_y) !== $signed(tv_out_gated_mem[k])) begin
                    $display("FAIL: realparams frame %0d mismatch: rx=0x%08X, exp=0x%08X",
                             k, frame_y, tv_out_gated_mem[k]);
                    mismatches_y = mismatches_y + 1;
                end
                frames_received = frames_received + 1;
            end

            // Glitch test: 0.4 ms glitch on rst_n_real (40,000 cycles < 100,000 debounce) -> must NOT reset
            // Core should continue to frame 8
            rst_n_real = 0;
            repeat (40000) @(posedge clk);
            rst_n_real = 1;

            // MUT31 check: If debounce was mutated to 10,000 cycles, 40,000 cycles would cause a reset!
            // When not reset, next frame is frame 8
            rx_frame_real(frame_y, frame_flags);
            if ($signed(frame_y) !== $signed(tv_out_gated_mem[8])) begin
                $display("FAIL: realparams glitch caused reset or corrupted frame 8! rx=0x%08X, exp=0x%08X",
                         frame_y, tv_out_gated_mem[8]);
                mismatches_y = mismatches_y + 1;
            end
            frames_received = frames_received + 1;

            // Verified reset test: 1.5 ms reset on rst_n_real (150,000 cycles >= 100,000 debounce) -> resets to sample 0
            rst_n_real = 0;
            repeat (150000) @(posedge clk);
            rst_n_real = 1;

            // Wait for next frame after reset - must be sample 0
            rx_frame_real(frame_y, frame_flags);
            if ($signed(frame_y) !== $signed(tv_out_gated_mem[0])) begin
                $display("FAIL: realparams after 1.5 ms reset expected frame 0, got rx=0x%08X, exp=0x%08X",
                         frame_y, tv_out_gated_mem[0]);
                mismatches_y = mismatches_y + 1;
            end
            frames_received = frames_received + 1;
        end

        $display("==================================================================");
        $display("tb_board_core Summary (%0s):", scenario);
        $display("  Frames decoded:    %0d", frames_received);
        $display("  Preamble errors:   %0d", preamble_errors);
        $display("  Checksum errors:   %0d", checksum_errors);
        $display("  Y_ACC mismatches:  %0d", mismatches_y);
        $display("  Gate mismatches:   %0d", mismatches_gate);
        $display("==================================================================");

        if (preamble_errors == 0 && checksum_errors == 0 && mismatches_y == 0 && mismatches_gate == 0) begin
            $display("TB_RESULT: PASS name=tb_board_core_%0s samples=%0d mismatches=0", scenario, frames_received);
            $finish(0);
        end else begin
            $display("TB_RESULT: FAIL name=tb_board_core_%0s samples=%0d mismatches=%0d",
                     scenario, frames_received, (mismatches_y + mismatches_gate + checksum_errors + preamble_errors));
            $finish(1);
        end
    end

    // Simulation watchdog (prevents runaway)
    initial begin
        #500_000_000;
        $display("FATAL: Testbench watchdog timeout in tb_board_core!");
        $finish(1);
    end

endmodule
