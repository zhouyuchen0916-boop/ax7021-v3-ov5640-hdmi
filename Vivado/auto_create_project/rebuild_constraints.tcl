# Keep the raw script path.  Vivado 2023.1 on this Windows host incorrectly
# removes the Documents component when `file normalize` is applied to it.
set script_dir [file dirname [info script]]
set vivado_dir "$script_dir/.."
set project_dir "$vivado_dir/ov5640_single"
set project_file "$project_dir/ov5640_single.xpr"
set report_dir "$vivado_dir/reports"
set bit_file "$project_dir/ov5640_single.runs/impl_1/design_1_wrapper.bit"
set output_bit "$vivado_dir/design_1_wrapper.bit"
set output_xsa "$vivado_dir/../Vitis/design_1_wrapper.xsa"

open_project $project_file

# Refresh the implementation-only targeted CDC exception in the generated project.
set cdc_src "$script_dir/src/constraints/async_clock_groups.xdc"
set cdc_dst "$project_dir/ov5640_single.srcs/constrs_1/new/async_clock_groups.xdc"
file copy -force $cdc_src $cdc_dst
if {[llength [get_files -quiet $cdc_dst]] == 0} {
  add_files -fileset constrs_1 -norecurse $cdc_dst
}
set cdc_xdc [get_files -quiet */async_clock_groups.xdc]
set_property USED_IN_SYNTHESIS false $cdc_xdc
set_property USED_IN_IMPLEMENTATION true $cdc_xdc

update_compile_order -fileset sources_1
reset_run impl_1
launch_runs impl_1 -to_step write_bitstream -jobs 5
wait_on_run impl_1

set impl_status [get_property STATUS [get_runs impl_1]]
puts "IMPL_STATUS=$impl_status"
if {![string match "*Complete*" $impl_status]} {
  error "Implementation failed: $impl_status"
}

open_run impl_1
file mkdir $report_dir
report_timing_summary -delay_type min_max -report_unconstrained -check_timing_verbose \
  -max_paths 10 -input_pins -file "$report_dir/timing_summary.rpt"
report_utilization -hierarchical -file "$report_dir/utilization_hierarchical.rpt"
report_drc -file "$report_dir/drc.rpt"
report_methodology -file "$report_dir/methodology.rpt"
report_cdc -details -file "$report_dir/cdc.rpt"

if {![file exists $bit_file]} {
  error "Bitstream not found: $bit_file"
}
file copy -force $bit_file $output_bit
write_hw_platform -fixed -include_bit -force -file $output_xsa

puts "REBUILD_OK"
puts "BIT_FILE=$output_bit"
puts "XSA_FILE=$output_xsa"
