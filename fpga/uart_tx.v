// =============================================================================
// Module: uart_tx
// Description: Standard 8N1 UART transmitter for FPGA ECG data streaming.
//              - Parameterized clock rate and baud rate (default 100 MHz / 115200)
//              - 1 start bit, 8 data bits LSB first, 1 stop bit
//              - Pure Verilog-2001
// =============================================================================
`timescale 1ns / 1ps

module uart_tx #(
    parameter CLK_HZ = 100_000_000,
    parameter BAUD   = 115_200
)(
    input  wire       clk,
    input  wire       rst_n,
    input  wire       tx_start,
    input  wire [7:0] tx_data,
    output reg        tx_pin,
    output wire       tx_busy
);

    localparam CLKS_PER_BIT = CLK_HZ / BAUD;

    localparam STATE_IDLE  = 2'b00;
    localparam STATE_START = 2'b01;
    localparam STATE_DATA  = 2'b10;
    localparam STATE_STOP  = 2'b11;

    reg [1:0]  state;
    reg [15:0] clk_cnt;
    reg [2:0]  bit_idx;
    reg [7:0]  tx_shift;

    assign tx_busy = (state != STATE_IDLE);

    always @(posedge clk) begin
        if (!rst_n) begin
            state    <= STATE_IDLE;
            clk_cnt  <= 16'd0;
            bit_idx  <= 3'd0;
            tx_shift <= 8'd0;
            tx_pin   <= 1'b1;
        end else begin
            case (state)
                STATE_IDLE: begin
                    tx_pin  <= 1'b1;
                    clk_cnt <= 16'd0;
                    bit_idx <= 3'd0;
                    if (tx_start) begin
                        tx_shift <= tx_data;
                        tx_pin   <= 1'b0; // Start bit
                        state    <= STATE_START;
                    end
                end

                STATE_START: begin
                    tx_pin <= 1'b0;
                    if (clk_cnt < CLKS_PER_BIT - 1) begin
                        clk_cnt <= clk_cnt + 16'd1;
                    end else begin
                        clk_cnt <= 16'd0;
                        tx_pin  <= tx_shift[0];
                        state   <= STATE_DATA;
                    end
                end

                STATE_DATA: begin
                    tx_pin <= tx_shift[bit_idx];
                    if (clk_cnt < CLKS_PER_BIT - 1) begin
                        clk_cnt <= clk_cnt + 16'd1;
                    end else begin
                        clk_cnt <= 16'd0;
                        if (bit_idx < 3'd7) begin
                            bit_idx <= bit_idx + 3'd1;
                        end else begin
                            bit_idx <= 3'd0;
                            tx_pin  <= 1'b1; // Stop bit
                            state   <= STATE_STOP;
                        end
                    end
                end

                STATE_STOP: begin
                    tx_pin <= 1'b1;
                    if (clk_cnt < CLKS_PER_BIT - 1) begin
                        clk_cnt <= clk_cnt + 16'd1;
                    end else begin
                        clk_cnt <= 16'd0;
                        state   <= STATE_IDLE;
                    end
                end

                default: state <= STATE_IDLE;
            endcase
        end
    end

endmodule
