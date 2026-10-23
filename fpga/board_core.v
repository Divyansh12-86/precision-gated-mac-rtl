// =============================================================================
// Module: board_core
// Description: Unified board-agnostic hardware demonstration core for
//              Precision-Gated MAC ECG filter.
//              Architecture:
//                1. ecg_rom: On-chip ROM loaded via $readmemh with MIT-BIH ECG vectors.
//                2. sample_tick_gen: 360 Hz sample pacing from 100 MHz clock.
//                3. pg_top: Precision-Gated Approximate-MAC ECG filter core.
//                4. uart_tx: 115200 8N1 serial transmitter streaming 7-byte frames:
//                   - Byte 0: Sync preamble (0xA5)
//                   - Byte 1..4: 32-bit filtered output y_acc (big-endian)
//                   - Byte 5: Flags {5'b0, mode_force_active, peak, gate}
//                   - Byte 6: XOR checksum of bytes 0..5
// =============================================================================
`timescale 1ns / 1ps

module board_core #(
    parameter CLK_HZ     = 100_000_000,
    parameter FS         = 360,
    parameter BAUD       = 115_200,
    parameter ROM_FILE   = "ecg_rom.mem",
    parameter ROM_DEPTH  = 60_000,
    parameter FAST_TICK  = 0 // If > 0, tick period = FAST_TICK cycles (for fast TB simulation)
)(
    input  wire        clk,
    input  wire        rst_n,
    input  wire [1:0]  sw_mode_force, // 00=Auto, 01=Force Full, 10=Force Approx
    input  wire        sw_pause,      // 1=Pause playback
    output wire        uart_txd,      // Serial UART output
    output wire        led_gate,      // Stretched gate active LED
    output wire        led_peak,      // Stretched QRS peak pulse LED
    output wire        led_busy,      // Filter busy LED
    output wire        led_heartbeat, // 1 Hz alive heartbeat LED
    output wire [7:0]  led_y_msb      // Filtered output MSB monitor
);

    // -------------------------------------------------------------------------
    // 1. ECG Vector ROM
    // -------------------------------------------------------------------------
    reg signed [15:0] rom [0:ROM_DEPTH-1];
    reg [$clog2(ROM_DEPTH)-1:0] rom_addr;
    reg signed [15:0] rom_sample;

    initial begin
        if (ROM_FILE != "") begin
            $readmemh(ROM_FILE, rom);
        end
    end

    // -------------------------------------------------------------------------
    // 2. Sample Pacing
    // -------------------------------------------------------------------------
    wire sample_tick;

    generate
        if (FAST_TICK > 0) begin : g_fast_tick
            reg [$clog2(FAST_TICK+1)-1:0] fast_cnt;
            reg tick_r;
            always @(posedge clk) begin
                if (!rst_n) begin
                    fast_cnt <= 0;
                    tick_r   <= 1'b0;
                end else if (!sw_pause) begin
                    if (fast_cnt < FAST_TICK - 1) begin
                        fast_cnt <= fast_cnt + 1;
                        tick_r   <= 1'b0;
                    end else begin
                        fast_cnt <= 0;
                        tick_r   <= 1'b1;
                    end
                end else begin
                    tick_r <= 1'b0;
                end
            end
            assign sample_tick = tick_r;
        end else begin : g_realrate_tick
            sample_tick_gen #(
                .CLK_HZ(CLK_HZ),
                .FS(FS)
            ) u_pacer (
                .clk(clk),
                .rst_n(rst_n),
                .enable(~sw_pause),
                .tick(sample_tick)
            );
        end
    endgenerate

    // Read ROM synchronously so rom_sample holds rom[rom_addr] well before sample_tick
    always @(posedge clk) begin
        rom_sample <= rom[rom_addr];
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            rom_addr <= 0;
        end else if (sample_tick) begin
            if (rom_addr < ROM_DEPTH - 1) begin
                rom_addr <= rom_addr + 1;
            end else begin
                rom_addr <= 0; // Loop replay
            end
        end
    end

    // -------------------------------------------------------------------------
    // 3. Precision-Gated ECG Filter Core
    // -------------------------------------------------------------------------
    wire signed [31:0] y_acc;
    wire y_valid;
    wire gate_out;
    wire peak_pulse;
    wire busy;

    pg_top #(
        .N_TAPS(51),
        .PIPE(2),
        .MULT_IMPL("LUT"),
        .COEFF_FILE("coeffs.mem"),
        .SQ_SHIFT(11)
    ) u_pg_core (
        .clk(clk),
        .rst_n(rst_n),
        .sample_valid(sample_tick),
        .x_in(rom_sample),
        .mode_force(sw_mode_force),
        .y_valid(y_valid),
        .y_acc(y_acc),
        .gate_out(gate_out),
        .peak_pulse(peak_pulse),
        .mwi_dbg(),
        .busy(busy)
    );

    // -------------------------------------------------------------------------
    // 4. Framed UART Streaming
    // -------------------------------------------------------------------------
    localparam F_IDLE   = 3'd0;
    localparam F_BYTE0  = 3'd1;
    localparam F_BYTE1  = 3'd2;
    localparam F_BYTE2  = 3'd3;
    localparam F_BYTE3  = 3'd4;
    localparam F_BYTE4  = 3'd5;
    localparam F_BYTE5  = 3'd6;
    localparam F_BYTE6  = 3'd7;

    reg [2:0] f_state;
    reg [7:0] tx_data_reg;
    reg       tx_start_reg;

    wire tx_busy;

    uart_tx #(
        .CLK_HZ(CLK_HZ),
        .BAUD(BAUD)
    ) u_uart (
        .clk(clk),
        .rst_n(rst_n),
        .tx_start(tx_start_reg),
        .tx_data(tx_data_reg),
        .tx_pin(uart_txd),
        .tx_busy(tx_busy)
    );

    // Latched frame payload
    reg signed [31:0] latched_y;
    reg [7:0]         latched_flags;
    reg [7:0]         latched_chk;

    always @(posedge clk) begin
        if (!rst_n) begin
            f_state       <= F_IDLE;
            tx_data_reg   <= 8'd0;
            tx_start_reg  <= 1'b0;
            latched_y     <= 32'sd0;
            latched_flags <= 8'd0;
            latched_chk   <= 8'd0;
        end else begin
            tx_start_reg <= 1'b0;

            case (f_state)
                F_IDLE: begin
                    if (y_valid) begin
                        latched_y     <= y_acc;
                        latched_flags <= {5'b00000, (sw_mode_force != 2'b00), peak_pulse, gate_out};
                        latched_chk   <= 8'hA5 ^ y_acc[31:24] ^ y_acc[23:16] ^ y_acc[15:8] ^ y_acc[7:0] ^
                                         {5'b00000, (sw_mode_force != 2'b00), peak_pulse, gate_out};
                        f_state       <= F_BYTE0;
                    end
                end

                F_BYTE0: begin
                    if (!tx_busy && !tx_start_reg) begin
                        tx_data_reg  <= 8'hA5; // Sync preamble
                        tx_start_reg <= 1'b1;
                        f_state      <= F_BYTE1;
                    end
                end

                F_BYTE1: begin
                    if (!tx_busy && !tx_start_reg) begin
                        tx_data_reg  <= latched_y[31:24];
                        tx_start_reg <= 1'b1;
                        f_state      <= F_BYTE2;
                    end
                end

                F_BYTE2: begin
                    if (!tx_busy && !tx_start_reg) begin
                        tx_data_reg  <= latched_y[23:16];
                        tx_start_reg <= 1'b1;
                        f_state      <= F_BYTE3;
                    end
                end

                F_BYTE3: begin
                    if (!tx_busy && !tx_start_reg) begin
                        tx_data_reg  <= latched_y[15:8];
                        tx_start_reg <= 1'b1;
                        f_state      <= F_BYTE4;
                    end
                end

                F_BYTE4: begin
                    if (!tx_busy && !tx_start_reg) begin
                        tx_data_reg  <= latched_y[7:0];
                        tx_start_reg <= 1'b1;
                        f_state      <= F_BYTE5;
                    end
                end

                F_BYTE5: begin
                    if (!tx_busy && !tx_start_reg) begin
                        tx_data_reg  <= latched_flags;
                        tx_start_reg <= 1'b1;
                        f_state      <= F_BYTE6;
                    end
                end

                F_BYTE6: begin
                    if (!tx_busy && !tx_start_reg) begin
                        tx_data_reg  <= latched_chk;
                        tx_start_reg <= 1'b1;
                        f_state      <= F_IDLE;
                    end
                end

                default: f_state <= F_IDLE;
            endcase
        end
    end

    // -------------------------------------------------------------------------
    // 5. Diagnostics & Visual Indicators
    // -------------------------------------------------------------------------
    // Stretched pulses for human visibility (~50 ms at 100 MHz)
    reg [22:0] peak_stretch_cnt;
    reg [22:0] gate_stretch_cnt;
    reg [26:0] heartbeat_cnt;

    always @(posedge clk) begin
        if (!rst_n) begin
            peak_stretch_cnt <= 23'd0;
            gate_stretch_cnt <= 23'd0;
            heartbeat_cnt    <= 27'd0;
        end else begin
            heartbeat_cnt <= heartbeat_cnt + 27'd1;

            if (peak_pulse) peak_stretch_cnt <= 23'd5_000_000;
            else if (peak_stretch_cnt > 23'd0) peak_stretch_cnt <= peak_stretch_cnt - 23'd1;

            if (gate_out) gate_stretch_cnt <= 23'd5_000_000;
            else if (gate_stretch_cnt > 23'd0) gate_stretch_cnt <= gate_stretch_cnt - 23'd1;
        end
    end

    assign led_gate      = (gate_stretch_cnt > 23'd0);
    assign led_peak      = (peak_stretch_cnt > 23'd0);
    assign led_busy      = busy;
    assign led_heartbeat = heartbeat_cnt[26]; // ~0.74 Hz blink
    assign led_y_msb      = y_acc[23:16];

endmodule
