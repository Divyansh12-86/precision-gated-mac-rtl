# =============================================================================
# Vivado Out-Of-Context Synthesis Script
# Target: Xilinx Artix-7 (xc7a35tcpg236-1)
# =============================================================================

set OUTPUT_DIR reports
file mkdir $OUTPUT_DIR

# Read RTL design files
read_verilog [glob rtl/*.v]

# Run synthesis in out-of-context mode
synth_design -mode out_of_context -top pg_top -part xc7a35tcpg236-1

# Define 100 MHz clock constraint (10.0 ns period)
create_clock -period 10.0 -name clk [get_ports clk]

# Generate utilization and timing reports
report_utilization -file $OUTPUT_DIR/vivado_utilization.rpt
report_timing_summary -file $OUTPUT_DIR/vivado_timing.rpt

puts "Vivado OOC synthesis completed successfully."
