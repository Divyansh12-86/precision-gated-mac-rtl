// =============================================================================
// Module: qrs_detector
// Description: Synthesizable integer Pan-Tompkins QRS detector conforming
//              to HardwareQRSDetectorV2 (sim/qrs_detector_v2.py).
//              - Division-free: MWI output uses right shift (>> 6).
//              - Deterministic start-up without calibration pass.
//              - Evaluates per-sample: produces gate_out, peak_pulse, mwi_dbg
//                with valid_out 1 cycle after sample_valid.
//              - Squarer implemented using a single 17x17 multiplier with 17-bit saturation.
//              - All threshold updates use bit shifts and adds.
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
    parameter INIT_THRESH  = 412
)(
    input  wire                   clk,
    input  wire                   rst_n,
    input  wire                   sample_valid,
    input  wire signed [15:0]     x_in,
    output reg                    gate_out,
    output reg                    peak_pulse,
    output reg         [17:0]     mwi_dbg,
    output reg                    valid_out
);

    // 16-bit input delay registers
    reg signed [15:0] x_d1;
    reg signed [15:0] x_d2;

    // MWI circular buffer & accumulator
    reg [16:0] mwi_buf [0:MWI_LEN-1];
    reg [$clog2(MWI_LEN)-1:0] ptr;
    reg [23:0] mwi_acc;

    // Counters & timing
    reg [6:0]  refractory_cnt;
    reg [15:0] time_since_peak;
    reg [6:0]  gate_cnt;

    // Adaptive thresholds
    reg [23:0] spki;
    reg [23:0] npki;
    reg [23:0] threshold;

    // Peak history registers
    reg [17:0] prev_mwi;
    reg [17:0] prev_mwi_2;

    // -------------------------------------------------------------------------
    // Combinational Step Logic
    // -------------------------------------------------------------------------

    // 1. Derivative: d = x - x_d2
    wire signed [16:0] x_ext  = {x_in[15], x_in};
    wire signed [16:0] x_d2_ext = {x_d2[15], x_d2};
    wire signed [16:0] d = x_ext - x_d2_ext;

    // 2. Squaring and shift with 17-bit saturation
    wire signed [33:0] prod_signed = d * d;
    wire [33:0] prod = prod_signed[33:0];
    wire [33:0] s_shifted = prod >> SQ_SHIFT;
    wire [16:0] s = (s_shifted > 34'd131071) ? 17'd131071 : s_shifted[16:0];

    // 3. MWI circular buffer update
    wire [16:0] old_s = mwi_buf[ptr];
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

    // QRS EMA update
    wire [23:0] spki_cand_a = spki - (spki >> 3) + (pk >> 3);
    wire signed [24:0] spki_diff_a = $signed({1'b0, spki_cand_a}) - $signed({1'b0, npki});
    wire signed [24:0] spki_diff_a_shift = spki_diff_a >>> 2;
    wire signed [24:0] thresh_cand_a_s = $signed({1'b0, npki}) + spki_diff_a_shift;
    wire [23:0] thresh_cand_a = thresh_cand_a_s[23:0];

    // Noise EMA update
    wire [23:0] npki_cand_b = npki - (npki >> 4) + (pk >> 4);
    wire signed [24:0] spki_diff_b = $signed({1'b0, spki}) - $signed({1'b0, npki_cand_b});
    wire signed [24:0] spki_diff_b_shift = spki_diff_b >>> 2;
    wire signed [24:0] thresh_cand_b_s = $signed({1'b0, npki_cand_b}) + spki_diff_b_shift;
    wire [23:0] thresh_cand_b = thresh_cand_b_s[23:0];

    // Threshold state multiplexers
    wire [23:0] next_spki = is_qrs_cand   ? spki_cand_a   : spki;
    wire [23:0] next_npki = is_noise_cand ? npki_cand_b   : npki;
    wire [23:0] next_threshold = is_qrs_cand   ? thresh_cand_a :
                                 is_noise_cand ? thresh_cand_b : thresh_curr;

    wire [6:0]  next_refractory_cnt  = is_qrs_cand ? REFRACT_LEN[6:0] : refract_dec;
    wire [15:0] next_time_since_peak = is_qrs_cand ? 16'd0 : time_inc;

    // 6. Gate flag evaluation
    wire [6:0] gate_cnt_init = is_qrs_cand ? GATE_LEN[6:0] : gate_cnt;
    wire next_gate_flag = (gate_cnt_init > 7'd0) ? 1'b1 : 1'b0;
    wire [6:0] next_gate_cnt = (gate_cnt_init > 7'd0) ? (gate_cnt_init - 7'd1) : 7'd0;

    // -------------------------------------------------------------------------
    // Sequential State Registers
    // -------------------------------------------------------------------------
    integer idx;

    always @(posedge clk) begin
        if (!rst_n) begin
            x_d1            <= 16'sd0;
            x_d2            <= 16'sd0;
            ptr             <= '0;
            mwi_acc         <= 24'd0;
            refractory_cnt  <= 7'd0;
            time_since_peak <= 16'd0;
            gate_cnt        <= 7'd0;
            spki            <= INIT_SPKI[23:0];
            npki            <= INIT_NPKI[23:0];
            threshold       <= INIT_THRESH[23:0];
            prev_mwi        <= 18'd0;
            prev_mwi_2      <= 18'd0;

            for (idx = 0; idx < MWI_LEN; idx = idx + 1) begin
                mwi_buf[idx] <= 17'd0;
            end

            gate_out        <= 1'b0;
            peak_pulse      <= 1'b0;
            mwi_dbg         <= 18'd0;
            valid_out       <= 1'b0;
        end else if (sample_valid) begin
            // 1. Shift input delay registers
            x_d1 <= x_in;
            x_d2 <= x_d1;

            // 2 & 3. MWI update
            mwi_buf[ptr] <= s;
            ptr <= (ptr == MWI_LEN - 1) ? '0 : ptr + 1'b1;
            mwi_acc <= next_mwi_acc;

            // 4 & 5. Thresholds and timing
            refractory_cnt  <= next_refractory_cnt;
            time_since_peak <= next_time_since_peak;
            spki            <= next_spki;
            npki            <= next_npki;
            threshold       <= next_threshold;

            prev_mwi_2      <= prev_mwi;
            prev_mwi        <= next_mwi_out;

            // 6. Gate count
            gate_cnt        <= next_gate_cnt;

            // Output registers (ready at cycle 1)
            gate_out        <= next_gate_flag;
            peak_pulse      <= is_qrs_cand;
            mwi_dbg         <= next_mwi_out;
            valid_out       <= 1'b1;
        end else begin
            valid_out       <= 1'b0;
            peak_pulse      <= 1'b0;
        end
    end

endmodule
