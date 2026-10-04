set tclpath [pwd]
set projpath [file normalize "$tclpath/.."]
set rootpath [file normalize "$projpath/.."]
set project_file "$projpath/ov5640_single/ov5640_single.xpr"
set report_dir "$projpath/reports"

open_project $project_file

# Add the implementation-only asynchronous clock relationship to the existing project.
set async_src "$tclpath/src/constraints/async_clock_groups.xdc"
set async_dst "$projpath/ov5640_single/ov5640_single.srcs/constrs_1/new/async_clock_groups.xdc"
file copy -force $async_src $async_dst
if {[llength [get_files -quiet $async_dst]] == 0} {
  add_files -fileset constrs_1 -norecurse $async_dst
}
set async_clock_xdc [get_files -quiet */async_clock_groups.xdc]
set_property USED_IN_SYNTHESIS false $async_clock_xdc
set_property USED_IN_IMPLEMENTATION true $async_clock_xdc

# Rebuild the edited camera IP, then rebuild the top-level design and bitstream.
set camera_run design_1_alinx_ov5640_0_0_synth_1
reset_run $camera_run
launch_runs $camera_run -jobs 5
wait_on_run $camera_run
if {![string match "*Complete*" [get_property STATUS [get_runs $camera_run]]]} {
  error "Camera IP synthesis failed"
}

reset_run synth_1
launch_runs synth_1 -jobs 5
wait_on_run synth_1
if {![string match "*Complete*" [get_property STATUS [get_runs synth_1]]]} {
  error "Top-level synthesis failed"
}

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

set bit_file "$projpath/ov5640_single/ov5640_single.runs/impl_1/design_1_wrapper.bit"
file copy -force $bit_file "$projpath/design_1_wrapper.bit"
write_hw_platform -fixed -include_bit -force -file "$rootpath/Vitis/design_1_wrapper.xsa"
save_project_as ov5640_single "$projpath/ov5640_single" -force
puts "CDC_FIX_BUILD_OK"
