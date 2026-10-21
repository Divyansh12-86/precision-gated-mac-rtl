// =============================================================================
// Header: pg_params.vh
// Description: Global hardware parameters for precision-gated MAC ECG processor.
// =============================================================================
`ifndef PG_PARAMS_VH
`define PG_PARAMS_VH

// System timing
`define CLK_FREQ_HZ         100_000_000
`define SAMPLING_FREQ_HZ    360

// FIR filter parameters
`define FIR_ORDER           50
`define FIR_NUM_TAPS        51
`define FIR_DATA_WIDTH      16
`define FIR_COEFF_WIDTH     16
`define FIR_ACC_WIDTH       32
`define FIR_PIPE_STAGES     2

// Approximate mode parameters
`define APPROX_TRUNC_BITS   8   // Truncate low 8 bits of operand (keep 8 MSBs)

// QRS detector parameters
`define DET_SQ_SHIFT_FIXED  11  // Right shift after squaring (fixed-scale policy)
`define DET_SQ_SHIFT_MINMAX 15  // Right shift after squaring (minmax policy)
`define DET_MWI_LEN         54  // 150 ms @ 360 Hz
`define DET_GATE_LEN        43  // 120 ms @ 360 Hz
`define DET_REFRACT_LEN     72  // 200 ms @ 360 Hz
`define DET_DECAY_AFTER     288 // 800 ms @ 360 Hz

// Detector initial reset thresholds
`define DET_INIT_SPKI       1500
`define DET_INIT_NPKI       50
`define DET_INIT_THRESH     412

`endif // PG_PARAMS_VH
