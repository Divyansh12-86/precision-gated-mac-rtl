# =============================================================================
# Vivado Out-Of-Context Synthesis & Characterization Script
# Targets:
#   1. Basys 3:      xc7a35tcpg236-1
#   2. Nexys A7-50T: xc7a50tcsg324-1
#   3. Nexys A7-100T: xc7a100tcsg324-1
# Usage:
#   vivado -mode batch -source scripts/synth_vivado_ooc.tcl [-tclargs <part>]
# =============================================================================

set OUTPUT_DIR reports
file mkdir $OUTPUT_DIR

if {$argc > 0} {
    set PARTS [list [lindex $argv 0]]
} else {
    set PARTS [list "xc7a35tcpg236-1" "xc7a50tcsg324-1" "xc7a100tcsg324-1"]
}
set TOPS  [list "baseline_fir_exact" "pg_top"]

# Read RTL design files
read_verilog [glob rtl/*.v]

foreach part $PARTS {
    foreach top $TOPS {
        puts "\n=================================================================="
        puts "Synthesizing $top on $part (100 MHz target)..."
        puts "=================================================================="

        synth_design -mode out_of_context -top $top -part $part
        create_clock -period 10.0 -name clk [get_ports clk]

        report_utilization -file "$OUTPUT_DIR/vivado_${part}_util_${top}.rpt"
        report_timing_summary -file "$OUTPUT_DIR/vivado_${part}_timing_${top}.rpt"
        report_power -file "$OUTPUT_DIR/vivado_${part}_power_${top}.rpt"
    }
}

puts "\nVivado OOC multi-part synthesis characterization completed successfully."
