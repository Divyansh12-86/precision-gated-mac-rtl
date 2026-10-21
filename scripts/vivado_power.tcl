# =============================================================================
# Vivado Power Analysis Script
# Analyzes dynamic power using SAIF activity file or switching rate constraints
# =============================================================================

set OUTPUT_DIR reports
file mkdir $OUTPUT_DIR

# Check if synthesized design is open, otherwise synthesize
if {[get_designs -quiet] eq ""} {
    source scripts/synth_vivado_ooc.tcl
}

# Apply default activity rates or read SAIF if generated
# Gated mode duty cycle: 85% approximate (low bus inactive), 15% full
set_switching_activity -type signal -toggle_rate 20.0 -static_probability 0.5 [all_inputs]

# Generate detailed power report
report_power -file $OUTPUT_DIR/vivado_power.rpt

puts "Vivado power analysis completed successfully."
