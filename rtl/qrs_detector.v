// =============================================================================
// Module: qrs_detector
// Description: Synthesizable integer Pan-Tompkins QRS detector (v2).
//              Conforms strictly to Section 2.2 and Section 4.5.
//              - Pure integer arithmetic, division-free (MWI >> 6).
//              - 17-bit saturation on squared derivative.
//              - Zero external calibration, deterministic reset start-up.
//              - Circular buffer inferred as 64x17 distributed RAM (LUTRAM).
//              - Standard Verilog-2001 (no SystemVerilog literals).
//              - Serial 17-cycle squarer eliminating wide combinational multiplier.
// =============================================================================
`timescale 1ns / 1ps

module qrs_detector #(
    parameter SQ_SHIFT     = 11,
    parameter MWI_LEN      = 54,
    parameter GATE_LEN     = 43,
    parameter REFRACT_LEN  = 72,
    parameter DECAY_AFTER  = 288,
    parameter INIT_SPKI    = 1500,
    parameter INIT_NPKI    = 50,
    parameter INIT_THRESH  = 412,
    parameter SERIAL_SQ    = 1
)(
    input  wire                   clk,
    input  wire                   rst_n,
    input  wire                   sample_valid,
    input  wire signed [15:0]     x_in,
    output reg                    gate_out,
    output reg                    peak_pulse,
    output reg  [17:0]            mwi_dbg,
    output reg                    valid_out
);

    // Delay registers for derivative computation
    reg signed [15:0] x_d1;
    reg signed [15:0] x_d2;

    // Distributed RAM for MWI circular buffer
    (* ram_style = "distributed" *)
    reg [16:0] mwi_ram [0:63];
    reg [5:0]  ptr;
    reg [5:0]  valid_mwi_cnt;
    reg [23:0] mwi_acc;

    // Moving-window peak search registers
    reg [17:0] prev_mwi;
    reg [17:0] prev_mwi_2;

    // Adaptive thresholds and timing registers
    reg [6:0]  refractory_cnt;
    reg [15:0] time_since_peak;
    reg [6:0]  gate_cnt;

    reg [23:0] spki;
    reg [23:0] npki;
    reg [23:0] threshold;

    // Serial squarer registers
    reg [33:0] sq_accum;
    reg [16:0] sq_cand;
    reg [4:0]  sq_step;
    reg        sq_busy;

    // -------------------------------------------------------------------------
    // Combinational Signal Processing Datapath
    // -------------------------------------------------------------------------

    // 1. Derivative: d = x - x_d2
    wire signed [16:0] x_ext    = {x_in[15], x_in};
    wire signed [16:0] x_d2_ext = {x_d2[15], x_d2};
    wire signed [16:0] d        = x_ext - x_d2_ext;
    wire [16:0] d_abs = (d < 17'sd0) ? (-d) : d;

    // 2. Squaring and shift with 17-bit saturation
    wire signed [33:0] comb_prod_signed = d * d;
    wire [33:0] comb_prod = comb_prod_signed[33:0];

    // Iterative shift-add step for serial squarer
    wire [33:0] sq_term = sq_cand[sq_step] ? ({17'd0, sq_cand} << sq_step) : 34'd0;
    wire [33:0] next_sq_accum = sq_accum + sq_term;

    wire [33:0] final_prod = SERIAL_SQ ? next_sq_accum : comb_prod;
    wire [33:0] s_shifted = final_prod >> SQ_SHIFT;
    wire [16:0] s = (s_shifted > 34'd131071) ? 17'd131071 : s_shifted[16:0];

    // 3. MWI circular buffer update using distributed RAM
    wire is_mwi_valid = (valid_mwi_cnt >= MWI_LEN[5:0]);
    wire [16:0] old_s = is_mwi_valid ? mwi_ram[ptr] : 17'd0;
    wire [24:0] mwi_sum = {1'b0, mwi_acc} + {8'b0, s};
    wire [24:0] mwi_diff = mwi_sum - {8'b0, old_s};
    wire [23:0] next_mwi_acc = mwi_diff[23:0];
    wire [17:0] next_mwi_out = next_mwi_acc[23:6];

    // 4. Refractory & Decay updates
    wire [6:0]  refract_dec = (refractory_cnt > 7'd0) ? (refractory_cnt - 7'd1) : 7'd0;
    wire [15:0] time_inc    = time_since_peak + 16'd1;

    wire signed [24:0] decayed_s = $signed({1'b0, threshold}) - $signed({9'b0, threshold[23:8]}) - 25'sd1;
    wire [23:0] decayed = (decayed_s < 0) ? 24'd0 : decayed_s[23:0];
    wire [23:0] floor_val = {npki[22:0], 1'b0};
    wire [23:0] decayed_max = (decayed > floor_val) ? decayed : floor_val;
    wire [23:0] thresh_curr = (time_inc > DECAY_AFTER) ? decayed_max : threshold;

    // 5. Peak confirmation & Threshold Adaptation
    wire is_local_max = (prev_mwi > prev_mwi_2) && (prev_mwi >= next_mwi_out);
    wire [23:0] pk = {6'b0, prev_mwi};

    wire is_qrs_cand   = is_local_max && (refract_dec == 7'd0) && (pk > thresh_curr);
    wire is_noise_cand = is_local_max && (refract_dec == 7'd0) && (pk < thresh_curr);

    // Threshold adaptation: compute chosen SPKI and NPKI first, then adapt
    wire [23:0] spki_cand_a = spki - (spki >> 3) + (pk >> 3);
    wire [23:0] npki_cand_b = npki - (npki >> 4) + (pk >> 4);

    wire [23:0] next_spki = is_qrs_cand   ? spki_cand_a : spki;
    wire [23:0] next_npki = is_noise_cand ? npki_cand_b : npki;

    wire signed [24:0] spki_npki_diff = $signed({1'b0, next_spki}) - $signed({1'b0, next_npki});
    wire signed [24:0] thresh_adapted_s = $signed({1'b0, next_npki}) + (spki_npki_diff >>> 2);
    wire [23:0] thresh_adapted = thresh_adapted_s[23:0];

    wire [23:0] next_threshold = (is_qrs_cand || is_noise_cand) ? thresh_adapted : thresh_curr;

    wire [6:0]  next_refractory_cnt  = is_qrs_cand ? REFRACT_LEN[6:0] : refract_dec;
    wire [15:0] next_time_since_peak = is_qrs_cand ? 16'd0 : time_inc;

    // 6. Gate flag evaluation
    wire [6:0] gate_cnt_init = is_qrs_cand ? GATE_LEN[6:0] : gate_cnt;
    wire next_gate_flag = (gate_cnt_init > 7'd0) ? 1'b1 : 1'b0;
    wire [6:0] next_gate_cnt = (gate_cnt_init > 7'd0) ? (gate_cnt_init - 7'd1) : 7'd0;

    // -------------------------------------------------------------------------
    // Sequential State Registers
    // -------------------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n) begin
            x_d1            <= 16'sd0;
            x_d2            <= 16'sd0;
            ptr             <= 6'd0;
            valid_mwi_cnt   <= 6'd0;
            mwi_acc         <= 24'd0;
            refractory_cnt  <= 7'd0;
            time_since_peak <= 16'd0;
            gate_cnt        <= 7'd0;
            spki            <= INIT_SPKI[23:0];
            npki            <= INIT_NPKI[23:0];
            threshold       <= INIT_THRESH[23:0];
            prev_mwi        <= 18'd0;
            prev_mwi_2      <= 18'd0;

            sq_accum        <= 34'd0;
            sq_cand         <= 17'd0;
            sq_step         <= 5'd0;
            sq_busy         <= 1'b0;

            gate_out        <= 1'b0;
            peak_pulse      <= 1'b0;
            mwi_dbg         <= 18'd0;
            valid_out       <= 1'b0;
        end else if (sample_valid && !sq_busy) begin
            // 1. Shift input delay registers
            x_d1 <= x_in;
            x_d2 <= x_d1;

            if (SERIAL_SQ) begin
                sq_accum  <= 34'd0;
                sq_cand   <= d_abs;
                sq_step   <= 5'd0;
                sq_busy   <= 1'b1;
                valid_out <= 1'b0;
                peak_pulse<= 1'b0;
            end else begin
                // Parallel single-cycle mode
                mwi_ram[ptr] <= s;
                ptr <= (ptr == MWI_LEN[5:0] - 6'd1) ? 6'd0 : (ptr + 6'd1);
                if (valid_mwi_cnt < MWI_LEN[5:0]) begin
                    valid_mwi_cnt <= valid_mwi_cnt + 6'd1;
                end
                mwi_acc <= next_mwi_acc;

                refractory_cnt  <= next_refractory_cnt;
                time_since_peak <= next_time_since_peak;
                spki            <= next_spki;
                npki            <= next_npki;
                threshold       <= next_threshold;

                prev_mwi_2      <= prev_mwi;
                prev_mwi        <= next_mwi_out;
                gate_cnt        <= next_gate_cnt;

                gate_out        <= next_gate_flag;
                peak_pulse      <= is_qrs_cand;
                mwi_dbg         <= next_mwi_out;
                valid_out       <= 1'b1;
            end
        end else if (sq_busy) begin
            if (sq_step == 5'd16) begin
                // Serial square calculation complete: update MWI and detector state
                sq_busy <= 1'b0;

                mwi_ram[ptr] <= s;
                ptr <= (ptr == MWI_LEN[5:0] - 6'd1) ? 6'd0 : (ptr + 6'd1);
                if (valid_mwi_cnt < MWI_LEN[5:0]) begin
                    valid_mwi_cnt <= valid_mwi_cnt + 6'd1;
                end
                mwi_acc <= next_mwi_acc;

                refractory_cnt  <= next_refractory_cnt;
                time_since_peak <= next_time_since_peak;
                spki            <= next_spki;
                npki            <= next_npki;
                threshold       <= next_threshold;

                prev_mwi_2      <= prev_mwi;
                prev_mwi        <= next_mwi_out;
                gate_cnt        <= next_gate_cnt;

                gate_out        <= next_gate_flag;
                peak_pulse      <= is_qrs_cand;
                mwi_dbg         <= next_mwi_out;
                valid_out       <= 1'b1;
            end else begin
                sq_accum <= next_sq_accum;
                sq_step  <= sq_step + 5'd1;
                valid_out <= 1'b0;
                peak_pulse<= 1'b0;
            end
        end else begin
            valid_out       <= 1'b0;
            peak_pulse      <= 1'b0;
        end
    end

endmodule
