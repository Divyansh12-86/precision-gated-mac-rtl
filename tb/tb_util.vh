// =============================================================================
// Header: tb_util.vh
// Description: Reusable testbench macros and utilities.
// =============================================================================
`ifndef TB_UTIL_VH
`define TB_UTIL_VH

`define TB_PASS(name, samples) \
    $display("TB_RESULT: PASS name=%0s samples=%0d mismatches=0", name, samples)

`define TB_FAIL(name, samples, mismatches) \
    $display("TB_RESULT: FAIL name=%0s samples=%0d mismatches=%0d", name, samples, mismatches)

`define ASSERT_EQUAL_HEX(actual, expected, idx, desc) \
    if ((actual) !== (expected)) begin \
        $display("MISMATCH at %0s[%0d]: actual=0x%08X, expected=0x%08X", desc, idx, actual, expected); \
    end

`endif // TB_UTIL_VH
