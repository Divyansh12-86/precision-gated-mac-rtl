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
    reg [31:0] tv_out_gated_mem [0:60000-1];
    reg        tv_gate_mem      [0:60000-1];

    // DUT
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

    initial begin
        dump_file = $fopen("reports/board_uart_dump.bin", "wb");
        // Load reference vectors
        $readmemh("data/test_vectors/std_fixed_100/tv_outputs_gated.hex", tv_out_gated_mem);
        $readmemh("data/test_vectors/std_fixed_100/tv_gate_flags.hex", tv_gate_mem);

        clk           = 0;
        rst_n         = 0;
        sw_mode_force = 2'b00; // Auto precision gating
        sw_pause      = 0;

        $display("==================================================================");
        $display("STARTING tb_board_core (Bit-Level UART ECG Replay Verification)");
        $display("==================================================================");

        #100;
        @(posedge clk);
        rst_n = 1;
        #100;

        while (frames_received < TEST_SAMPLES) begin
            uart_rx_byte(f_byte0);
            uart_rx_byte(f_byte1);
            uart_rx_byte(f_byte2);
            uart_rx_byte(f_byte3);
            uart_rx_byte(f_byte4);
            uart_rx_byte(f_byte5);
            uart_rx_byte(f_byte6);

            if (dump_file != 0) begin
                $fwrite(dump_file, "%c%c%c%c%c%c%c", f_byte0, f_byte1, f_byte2, f_byte3, f_byte4, f_byte5, f_byte6);
            end

            // Verify preamble
            if (f_byte0 !== 8'hA5) begin
                preamble_errors = preamble_errors + 1;
                $display("FAIL: Bad preamble 0x%02X at frame %0d", f_byte0, frames_received);
            end

            // Verify XOR Checksum
            calc_chk = f_byte0 ^ f_byte1 ^ f_byte2 ^ f_byte3 ^ f_byte4 ^ f_byte5;
            if (calc_chk !== f_byte6) begin
                checksum_errors = checksum_errors + 1;
                $display("FAIL: Checksum mismatch at frame %0d: got 0x%02X, expected 0x%02X",
                         frames_received, f_byte6, calc_chk);
            end

            // Reconstruct payload
            rx_y    = {f_byte1, f_byte2, f_byte3, f_byte4};
            rx_gate = f_byte5[0];

            // Compare bit-exact against golden model vectors
            if (rx_y !== $signed(tv_out_gated_mem[frames_received])) begin
                mismatches_y = mismatches_y + 1;
                if (mismatches_y <= 5) begin
                    $display("FAIL Y_ACC MISMATCH at sample %0d: rx=0x%08X (%d), exp=0x%08X (%d)",
                             frames_received, rx_y, rx_y,
                             tv_out_gated_mem[frames_received], $signed(tv_out_gated_mem[frames_received]));
                end
            end

            if (rx_gate !== tv_gate_mem[frames_received]) begin
                mismatches_gate = mismatches_gate + 1;
                if (mismatches_gate <= 5) begin
                    $display("FAIL GATE MISMATCH at sample %0d: rx=%b, exp=%b",
                             frames_received, rx_gate, tv_gate_mem[frames_received]);
                end
            end

            frames_received = frames_received + 1;

            if (frames_received % 1000 == 0) begin
                $display("  Verified %0d / %0d frames over UART stream...", frames_received, TEST_SAMPLES);
            end
        end

        $display("==================================================================");
        $display("tb_board_core Summary:");
        $display("  Frames decoded:    %0d", frames_received);
        $display("  Preamble errors:   %0d", preamble_errors);
        $display("  Checksum errors:   %0d", checksum_errors);
        $display("  Y_ACC mismatches:  %0d", mismatches_y);
        $display("  Gate mismatches:   %0d", mismatches_gate);
        $display("==================================================================");

        if (dump_file != 0) begin
            $fclose(dump_file);
        end

        if (preamble_errors == 0 && checksum_errors == 0 && mismatches_y == 0 && mismatches_gate == 0) begin
            $display("TB_RESULT: PASS name=tb_board_core samples=%0d mismatches=0", frames_received);
            $finish(0);
        end else begin
            $display("TB_RESULT: FAIL name=tb_board_core samples=%0d mismatches=%0d",
                     frames_received, (mismatches_y + mismatches_gate + checksum_errors + preamble_errors));
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
